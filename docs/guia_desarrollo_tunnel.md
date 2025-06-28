# 📖 Guía de Desarrollo: Gestión del Túnel y Reinicio del Bot

Este documento explica cómo gestionar el túnel HTTPS necesario para el desarrollo del bot de Telegram y cuál es el flujo de trabajo recomendado para iniciar, detener y depurar el sistema.

---

## 🚀 Visión General

Para que Telegram pueda enviar actualizaciones a nuestro bot (webhooks), nuestro servidor local (`localhost:8000`) debe ser accesible desde Internet a través de una URL HTTPS. Los scripts en la carpeta `scripts/` automatizan este proceso usando un túnel (probablemente Cloudflare Tunnel o ngrok).

El script principal es `auto_start_tunnel.sh`, que puede monitorizar el estado del backend y levantar el túnel automáticamente cuando sea necesario.

---

## ⚡ Flujo de Trabajo Recomendado (Automático)

Este es el método preferido, ya que es "configurar y olvidar".

### 1. Iniciar el Auto-Monitor (una sola vez)

La primera vez que configures el entorno, o después de reiniciar tu máquina, ejecuta este comando para iniciar el monitor del túnel en segundo plano:

```bash
nohup ./scripts/auto_start_tunnel.sh monitor > tunnel.log 2>&1 &
```

- `nohup`: Asegura que el script siga corriendo aunque cierres la terminal.
- `> tunnel.log 2>&1`: Redirige toda la salida y los errores al fichero `tunnel.log`.
- `&`: Ejecuta el comando en segundo plano.

### 2. Gestionar el Backend

Una vez que el monitor está activo, tu flujo de trabajo diario se simplifica a los comandos estándar de Docker:

```bash
# Para iniciar o reiniciar el backend
docker compose up -d

# Para detener el backend
docker compose down
```

El script de monitoreo se encargará automáticamente de iniciar y detener el túnel cada vez que el backend se inicie o se detenga. ✨

---

## 🛠️ Opciones Manuales y Debugging

Si prefieres un control más granular o necesitas depurar algún problema, puedes usar los comandos directamente.

### Comandos del `auto_start_tunnel.sh`

- **Monitorear en primer plano:**
  ```bash
  ./scripts/auto_start_tunnel.sh monitor
  ```
  *Muestra los logs en tiempo real en tu terminal. Útil para ver qué está pasando.*

- **Iniciar el túnel manualmente:**
  ```bash
  ./scripts/auto_start_tunnel.sh start
  ```

- **Detener el túnel manualmente:**
  ```bash
  ./scripts/auto_start_tunnel.sh stop
  ```

### Pasos para Verificación Manual

Si el bot no responde, sigue estos pasos para encontrar el problema:

1.  **Verificar el log del monitor:**
    ```bash
    tail -f tunnel.log
    ```
    *Busca mensajes de error o confirmaciones de que el túnel está activo.*

2.  **Verificar que el backend responde localmente:**
    ```bash
    curl -s http://localhost:8000/api/v1/telegram/health
    ```
    *Deberías recibir una respuesta como `{"status": "ok"}`.*

3.  **Verificar que el túnel funciona y llega al backend:**
    ```bash
    # Reemplaza la URL con la tuya
    curl -s https://bot.dasafodata.com/api/v1/telegram/health 
    ```
    *Si esto falla, el problema está en la configuración del túnel o el DNS.*

4.  **Ver los logs del backend:**
    ```bash
    docker compose logs -f backend
    ```
    *Aquí verás si el bot recibe los mensajes de Telegram y si hay algún error en el código de Python.*

### Opción de Emergencia

Si el script automático falla por alguna razón, puedes recurrir al script manual más simple:

```bash
./scripts/start_tunnel.sh
```
*Este script probablemente contenga una lógica más directa para iniciar el túnel sin el monitoreo automático.*

---

## 🏛️ Arquitectura Asíncrona: Reglas de Oro

Después de una refactorización profunda, todo el backend opera de forma asíncrona. Esto introduce nuevas reglas que son **críticas** para evitar errores sutiles y fugas de recursos.

### **Regla #1: Las Tareas en Segundo Plano Gestionan su Propia Sesión de Base de Datos**

Este es el principio más importante.

- **El Problema:** Cuando un endpoint de FastAPI (como `/webhook`) recibe una petición, obtiene una sesión de base de datos (`db`) a través de `Depends(get_db)`. Si este endpoint delega el trabajo a una tarea en segundo plano (`background_tasks.add_task`) y termina, la sesión `db` original se cierra inmediatamente. Si se pasa esa sesión cerrada a la tarea de fondo, cualquier intento de usarla resultará en errores (`MissingGreenlet`, `SAWarning`, etc.).

- **La Solución:** **NUNCA** pases un objeto `db` de un endpoint a una tarea en segundo plano. La tarea debe ser independiente y gestionar su propio ciclo de vida de la sesión.

**Ejemplo de código CORRECTO:**

```python
# En endpoints/telegram.py

# El endpoint NO depende de get_db, porque delega el trabajo
@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    # ...
    # NO se pasa 'db' a la tarea
    background_tasks.add_task(process_update, update_data)
    # ...

# La tarea de fondo crea y cierra su propia sesión
async def process_update(update_data: dict):
    # ...
    async with AsyncSessionLocal() as db:  # <- ¡AQUÍ ESTÁ LA MAGIA!
        # Ahora puedes usar 'db' de forma segura
        await bot_service.process_message(db, update_data)
    # La sesión se cierra automáticamente al salir del bloque 'with'
```

### **Regla #2: Cuidado con la Carga Perezosa (Lazy Loading) en Tareas de Fondo**

- **El Problema:** Incluso si pasas un objeto de SQLAlchemy (como un `Order` o `Client`) que fue cargado en una sesión válida a una tarea de fondo, puedes tener problemas. Si el objeto tiene relaciones que se cargan de forma perezosa (p. ej., `order.items`), la tarea de fondo intentará acceder a ellas, pero la sesión original ya estará cerrada.

- **La Solución:** Asegúrate de que todos los datos necesarios estén completamente cargados **antes** de pasar un objeto a una tarea de fondo.

**Ejemplo de código CORRECTO:**

```python
# Cargar un pedido y sus items explícitamente antes de usarlo en un background task

# MAL ❌
order = await get_order(db, order_id) # Carga perezosa de order.items
background_tasks.add_task(send_email, order.to_dict()) # Fallará

# BIEN ✅
from sqlalchemy.orm import joinedload
#...
result = await db.execute(
    select(Order)
    .filter(Order.order_id == order.order_id)
    .options(
        joinedload(Order.items).joinedload(OrderItem.product) # Carga toda la cadena
    )
)
order_fully_loaded = result.unique().scalars().one()

# Ahora es seguro pasarlo
background_tasks.add_task(send_email, order_fully_loaded.to_dict())
``` 