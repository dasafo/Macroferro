# 🏭 Macroferro - Sistema Mayorista B2B

**Plataforma completa de gestión mayorista para ferreterías con inteligencia artificial integrada.**

---

## 📖 Descripción del Proyecto

**Macroferro** es un sistema mayorista B2B diseñado para ferreterías que permite:
- **Consulta inteligente de productos** vía bot de Telegram con IA
- **Búsqueda semántica avanzada** utilizando embeddings vectoriales
- **Gestión completa de inventario** con múltiples almacenes
- **Sistema de carrito de compras** integrado con el bot de Telegram
- **Procesamiento de pedidos** automatizado con checkout completo
- **Análisis de datos** y reportes detallados

## 🛠️ Stack Tecnológico

-   **Contenerización:** Docker & Docker Compose
-   **Base de Datos:** PostgreSQL + PgAdmin
-   **Búsqueda Vectorial:** Qdrant (embeddings)
-   **Caché:** Redis (sesiones, carritos)
-   **API Backend:** FastAPI (Python)
-   **Interacción:** Bot de Telegram con IA
-   **Inteligencia Artificial:** OpenAI API
-   **Tunnel HTTPS:** Cloudflare Tunnel (para webhooks de Telegram)

## 🎯 Características Principales

-   **🤖 Bot de Telegram Inteligente:** Interfaz conversacional para búsqueda y pedidos
-   **🛒 Carrito de Compras Completo:** Gestión de productos, cantidades y checkout
-   **👥 Gestión de Clientes:** Reconocimiento de clientes recurrentes y registro automático
-   **🔍 Búsqueda Semántica:** Encuentra productos usando lenguaje natural
-   **📦 Gestión de Inventario:** Control de stock en tiempo real
-   **🚀 API REST Completa:** Documentación automática con FastAPI
-   **🔐 Seguridad Robusta:** Autenticación y autorización integradas
-   **🌐 Webhook HTTPS:** Integración segura con Telegram mediante Cloudflare
-   **🧩 Arquitectura Modular y Escalable:** Lógica de negocio encapsulada en `Handlers` especializados, facilitando el mantenimiento y la extensión.
-   **Webhooks de Telegram gestionados** de forma segura con `python-telegram-bot`
-   **Validación de datos de entrada** con Pydantic para robustez

## Estado Actual del Proyecto: **FASE 3 COMPLETADA** 🚀

### ✅ **FASE 0: Cimientos del Entorno y Base de Datos** - **COMPLETADA**
1.  **Entorno Contenerizado Funcional:** Todos los servicios base están operativos
2.  **Base de Datos Inicializada:** Esquema completo creado e inicializado
3.  **Carga de Datos Exitosa:** Todos los datos CSV cargados correctamente
4.  **Relaciones de Datos Verificadas:** Integridad referencial funcionando

### ✅ **FASE 1: API Backend (FastAPI) – Lógica de Productos y Categorías** - **COMPLETADA**

#### Arquitectura Backend Implementada

**Estructura del Proyecto (Post-Refactorización):**
```
backend/
├── app/
│   ├── main.py                 # Punto de entrada de FastAPI
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── api_router.py
│   │       └── endpoints/
│   │           ├── products.py, categories.py, cart.py, telegram.py
│   ├── core/
│   │   ├── config.py, database.py
│   ├── crud/
│   │   ├── product_crud.py, category_crud.py, cart_crud.py, ...
│   ├── db/
│   │   ├── base.py, database.py, models/
│   ├── schemas/
│   │   ├── product.py, category.py, cart.py, order.py, ...
│   └── services/
│       ├── bot_components/
│       │   ├── ai_analyzer.py      # Encapsula lógica de OpenAI
│       │   ├── product_handler.py  # Lógica de búsqueda de productos
│       │   ├── cart_handler.py     # Lógica de gestión del carrito
│       │   └── checkout_handler.py # Lógica del flujo de compra
│       ├── product_service.py
│       ├── email_service.py
│       └── telegram_service.py   # Orquestador principal del bot
├── Dockerfile
└── requirements.txt
```

#### Funcionalidades Implementadas

**🔧 API de Productos (`/api/v1/products/`):**
- ✅ `GET /products/` - Listar productos con filtros avanzados
  - Filtros: categoría, marca, rango de precios, búsqueda por nombre
  - Paginación configurable
  - Eager loading de relaciones (categorías, imágenes)
- ✅ `GET /products/{sku}` - Obtener producto por SKU
- ✅ `POST /products/search` - **Búsqueda semántica con IA**
- ✅ `POST /products/` - Crear nuevo producto
- ✅ `PUT /products/{sku}` - Actualizar producto existente
- ✅ `DELETE /products/{sku}` - Eliminar producto

**📁 API de Categorías (`/api/v1/categories/`):**
- ✅ `GET /categories/` - Listar todas las categorías
- ✅ `GET /categories/main` - Obtener solo categorías principales
- ✅ `GET /categories/{category_id}/subcategories` - Obtener subcategorías
- ✅ `GET /categories/{category_id}` - Obtener categoría específica
- ✅ `POST /categories/` - Crear nueva categoría
- ✅ `PUT /categories/{category_id}` - Actualizar categoría
- ✅ `DELETE /categories/{category_id}` - Eliminar categoría

**🛒 API de Carrito (`/api/v1/cart/`):**
- ✅ `GET /cart/{chat_id}` - Obtener contenido del carrito
- ✅ `POST /cart/{chat_id}/items` - Agregar producto al carrito
- ✅ `DELETE /cart/{chat_id}/items/{product_sku}` - Eliminar producto del carrito
- ✅ `DELETE /cart/{chat_id}` - Vaciar carrito completo

**🤖 API de Telegram (`/api/v1/telegram/`):**
- ✅ `POST /telegram/webhook` - Webhook para recibir mensajes de Telegram
- ✅ **Orquestación de Lógica:** Delega tareas a Handlers especializados.

### ✅ **FASE 1.5: Indexación Semántica con IA** - **COMPLETADA**

Se ha desarrollado un sistema robusto para la indexación de productos en la base de datos vectorial Qdrant.

**Funcionalidades Clave:**
- ✅ **Script de Indexación (`scripts/index_qdrant_data.py`):**
  - **Conexión multi-servicio:** PostgreSQL, Redis, Qdrant y OpenAI
  - **Enriquecimiento con LLM:** Genera descripciones de marketing optimizadas usando `gpt-4o-mini-2024-07-18`
  - **Caché Inteligente:** Utiliza Redis para cachear las descripciones generadas
  - **Generación de Embeddings:** Convierte información en vectores semánticos con `text-embedding-3-small`
  - **Indexación en Qdrant:** Almacena productos como puntos vectoriales en `macroferro_products`
  - **Gestión de Estado:** Solo procesa productos nuevos o modificados
- ✅ **Comando `Makefile` (`make update-catalog`):** Ejecuta todo el proceso de indexación
- ✅ **Script de Prueba (`scripts/test_semantic_search.py`):** Valida la calidad de los resultados
- ✅ **Colección Indexada:** **200 productos** completamente vectorizados y listos para búsqueda

### ✅ **FASE 2: Bot de Telegram con IA y Carrito de Compras Integrado** - **COMPLETADA** 🎉

Se ha finalizado la integración completa del bot de Telegram, permitiendo una interacción fluida desde la búsqueda de productos hasta la finalización de la compra.

**Funcionalidades Clave:**
- ✅ **Conversación Inteligente:** El bot comprende lenguaje natural para buscar productos, gestionar el carrito y finalizar compras.
- ✅ **Gestión Completa del Carrito:** Los usuarios pueden agregar, ver, eliminar y vaciar su carrito con comandos o lenguaje natural.
- ✅ **Proceso de Checkout Asistido:** El bot guía al usuario para recolectar los datos necesarios para el envío.
- ✅ **Integración con API Backend:** El bot consume los endpoints de FastAPI para obtener datos de productos y gestionar el carrito en Redis.
- ✅ **Seguridad en Webhooks:** La comunicación con Telegram está asegurada mediante un token secreto.

### ✅ **FASE 2.5: Gestión de Clientes y Flujo de Compra Mejorado** - **COMPLETADA** 🚀

Hemos añadido una capa de inteligencia en el proceso de compra para mejorar la experiencia de clientes nuevos y recurrentes.

**Mejoras Implementadas:**
- ✅ **Reconocimiento de Clientes Recurrentes:**
  - Al finalizar la compra, el bot pregunta al usuario si ya es cliente.
  - Si el usuario confirma, se le pide el email para buscar sus datos.
  - Si se encuentran, se autocompletan los datos de envío, agilizando el proceso.
- ✅ **Registro Automático de Nuevos Clientes:**
  - Si un usuario realiza una compra por primera vez, sus datos se guardan automáticamente en la base de datos de clientes.
  - El sistema genera un `client_id` secuencial y consistente (`CUSTXXXX`).
- ✅ **Flujo de Conversación Flexible:**
  - El bot ahora puede manejar interrupciones. Si un usuario hace una pregunta no relacionada durante el proceso de pago, el bot responderá y luego permitirá continuar con la compra.
- ✅ **Modelo y CRUD de Clientes:**
  - Se ha implementado el modelo `Client` y las funciones CRUD para interactuar con la base de datos.

### ✅ **FASE 3: Refactorización a Arquitectura de Componentes** - **COMPLETADA** 🧩

Se ha completado una refactorización profunda para migrar de un `service layer` monolítico a una arquitectura basada en componentes especializados (`Handlers`), mejorando drásticamente la mantenibilidad, escalabilidad y claridad del código.

**Mejoras Implementadas:**
- ✅ **Creación del Directorio `bot_components/`:** Un nuevo espacio para alojar la lógica modular del bot.
- ✅ **`AIAnalyzer`:** Componente dedicado exclusivamente a interactuar con la API de OpenAI, analizar la intención del usuario y extraer entidades.
- ✅ **`ProductHandler`:** Gestiona todas las interacciones relacionadas con la búsqueda y visualización de productos.
- ✅ **`CartHandler`:** Encapsula toda la lógica del carrito de compras, desde añadir productos hasta visualizarlos.
- ✅ **`CheckoutHandler`:** Orquesta el flujo de varios pasos para finalizar la compra, incluyendo la recolección de datos del cliente.
- ✅ **`TelegramBotService` como Orquestador:** El servicio principal ahora actúa como un director de orquesta, delegando tareas a los `handlers` correspondientes, resultando en un código más limpio y enfocado.

---

## Estado de Desarrollo por Módulos

### ✅ **Módulos Completados**
- [x] **Configuración de entorno** (Docker, Docker Compose)
- [x] **Base de datos** (PostgreSQL, modelos, relaciones)
- [x] **API de productos** (CRUD completo con validaciones)
- [x] **API de categorías** (CRUD completo con jerarquías)
- [x] **API de carrito** (CRUD completo con persistencia en Redis)
- [x] **API de órdenes** (creación y gestión de pedidos)
- [x] **API de clientes** (CRUD básico y lógica de negocio integrada)
- [x] **Búsqueda semántica** (Qdrant + OpenAI embeddings)
- [x] **Bot de Telegram** (interfaz conversacional completamente integrada)
- [x] **Sistema de carrito** (agregar, modificar, eliminar, checkout)
- [x] **Arquitectura modular** (Handlers especializados para IA, productos, carrito y checkout)
- [x] **Procesamiento de órdenes** (creación automática desde carrito)
- [x] **Webhook HTTPS** (Cloudflare Tunnel configurado)
- [x] **Capa de servicios** (lógica de negocio)
- [x] **Documentación de código** (comentarios exhaustivos)
- [x] **Manejo de errores** (respuestas HTTP consistentes)
- [x] **Validación de datos** (Pydantic schemas)

### 🚧 **Módulos en Preparación**
- [ ] **API de imágenes** (gestión de archivos)
- [ ] **API de inventario** (stock y almacenes)
- [ ] **Gestión de Clientes Avanzada** (historial, perfiles B2B)
- [ ] **API de facturación** (seguimiento de órdenes y pagos)
- [ ] **Sistema de autenticación** (JWT, roles)
- [ ] **Dashboard administrativo** (gestión web)
- [ ] **Notificaciones push** (actualizaciones de estado de órdenes)
- [ ] **Bot de Telegram avanzado** (comandos adicionales como historial de pedidos)

---

## 🚀 **Configuración inicial**

### **1. Clona el repositorio**
```bash
git clone https://github.com/tu-usuario/macroferro
cd macroferro
```

### **2. Configuración del entorno**
```bash
cp .env.example .env
```

Edita el archivo `.env` con tus credenciales:
```bash
# OpenAI (REQUERIDO para búsqueda semántica)
OPENAI_API_KEY=tu_api_key_de_openai

# Telegram Bot (REQUERIDO para el bot)
TELEGRAM_BOT_TOKEN=tu_token_de_bot_telegram
TELEGRAM_WEBHOOK_URL=https://bot.tudominio.com/api/v1/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=tu-secreto-webhook

# Base de datos (ya configuradas)
POSTGRES_DB=macroferro
POSTGRES_USER=macroferro_user
POSTGRES_PASSWORD=macroferro_pass

# Redis (para carrito)
REDIS_HOST=redis
REDIS_PORT=6379
```

### **3. Configuración del Webhook de Telegram**

**Opción A: Cloudflare Tunnel (Recomendada)**

1. **Configura Cloudflare Tunnel:**
   ```bash
   # En tu panel de Cloudflare:
   # 1. Crear un tunnel
   # 2. Configurar el subdomain: bot.tudominio.com -> localhost:8000
   # 3. El certificado SSL se configura automáticamente
   ```

2. **Actualiza el .env:**
   ```bash
   TELEGRAM_WEBHOOK_URL=https://bot.tudominio.com/api/v1/telegram/webhook
   TELEGRAM_WEBHOOK_SECRET=mi-token-secreto-123
   ```

**Opción B: ngrok (Para desarrollo)**
```bash
# Instalar ngrok y ejecutar
ngrok http 8000
# Copiar la URL HTTPS generada al .env
```

### **4. Indexación de productos (REQUERIDO)**
```bash
# Indexar todos los productos en Qdrant
make update-catalog

# Verificar que la indexación funcionó
make search-test
```

### **5. Inicio de servicios**
```bash
make up
```

### **6. Verificación del bot**
```bash
# Ver logs del webhook
docker compose logs backend

# Probar enviando un mensaje al bot
# El bot debería responder automáticamente
```

### **7. Acceso a servicios**
- **API Backend:** http://localhost:8000
- **Documentación API:** http://localhost:8000/docs
- **PgAdmin:** http://localhost:5050
- **Qdrant Dashboard:** http://localhost:6333/dashboard

---

## 🛒 **Guía de Uso del Carrito**

### **Comandos del Bot de Telegram**

**Búsqueda de productos:**
```
- "Busco tornillos"
- "¿Tienes taladros?"
- "Necesito herramientas para electricista"
```

**Gestión del carrito:**
```
/agregar SKU00001 2          # Agregar 2 unidades del producto SKU00001
/ver_carrito                 # Ver contenido actual del carrito
/eliminar SKU00001           # Eliminar producto específico
/vaciar_carrito             # Vaciar completamente el carrito
/finalizar_compra           # Procesar el checkout
```

**Comandos de ayuda:**
```
/start                      # Mensaje de bienvenida
/help                       # Lista de comandos disponibles
```

### **API REST del Carrito**

```bash
# Ver carrito
GET /api/v1/cart/{chat_id}

# Agregar producto
POST /api/v1/cart/{chat_id}/items
{
  "product_sku": "SKU00001",
  "quantity": 2
}

# Eliminar producto
DELETE /api/v1/cart/{chat_id}/items/{product_sku}

# Finalizar compra
POST /api/v1/cart/{chat_id}/checkout
{
  "chat_id": "123456789",
  "customer_name": "Juan Pérez",
  "customer_email": "juan@example.com",
  "shipping_address": "Calle Falsa 123",
  "items": []
}
```

---

## 🎯 **Próximos Pasos**

### **Fase 3: Gestión Avanzada de Pedidos (En Planificación)**
1. **Seguimiento de órdenes** (estados y notificaciones)
2. **Historial de pedidos** (consulta vía bot y API)
3. **Gestión de inventario** (control de stock en tiempo real)
4. **Notificaciones automáticas** (confirmaciones y actualizaciones)

### **Fase 4: Gestión Empresarial**
1. **Sistema de autenticación** (JWT, roles de usuario)
2. **API de inventario** (gestión de stock y almacenes)
3. **API de clientes** (gestión B2B completa)
4. **API de facturación** (órdenes, pagos y reportes)
5. **Dashboard administrativo** (interfaz web de gestión)

---

## Arquitectura Técnica

### Diagrama de Servicios Actualizado
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   PostgreSQL    │    │     Redis       │
│   Backend       │◄──►│   Database      │    │   Cache/Cart    │
│   (Port 8000)   │    │   (Port 5432)   │    │   (Port 6379)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                      ▲
         │                       │                      │
         ▼                       ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Telegram Bot   │    │     Qdrant      │    │    OpenAI      │
│   (Webhook)     │    │   (Port 6333)   │    │    (IA)        │
│   + Carrito     │    │   Vector DB     │    │  Embeddings    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                                              
         │                                              
         ▼                                              
┌─────────────────┐    ┌─────────────────┐              
│ Cloudflare      │    │     PgAdmin     │              
│ Tunnel (HTTPS)  │    │   (Port 5050)   │              
└─────────────────┘    └─────────────────┘              
```

### Stack de Desarrollo
- **Lenguaje:** Python 3.9
- **Framework:** FastAPI 0.104+
- **ORM:** SQLAlchemy 2.0
- **Validación:** Pydantic v2
- **Base de Datos:** PostgreSQL 16
- **Vector DB:** Qdrant 1.7+
- **Caché:** Redis 7.0+
- **IA:** OpenAI API (GPT-4o-mini, text-embedding-3-small)
- **Bot:** python-telegram-bot 21.0+
- **Contenerización:** Docker + Docker Compose
- **Documentación:** OpenAPI 3.0 (Swagger)

---

## 📊 Datos del Sistema

### Dataset Actual
- **200 productos** indexados con embeddings vectoriales
- **33 categorías** con estructura jerárquica
- **7 imágenes únicas** con 200 asociaciones producto-imagen
- **13 clientes B2B** con información de contacto (incluyendo recurrentes)
- **3 almacenes** con ubicaciones
- **600+ registros de stock** distribuidos
- **51 facturas** con 31 items de prueba
- **Colección Qdrant:** `macroferro_products` con 200 puntos vectoriales
- **Sistema de órdenes:** Tablas `orders` y `order_items` operativas

### Rendimiento
- **Búsqueda semántica:** < 200ms promedio
- **Respuesta del bot:** < 2 segundos promedio
- **Operaciones de carrito:** < 100ms promedio
- **Precisión de búsqueda:** 85%+ con threshold 0.6
- **Disponibilidad del webhook:** 99.9% (Cloudflare)
- **Persistencia de carrito:** 100% en Redis

---

## Contribución y Desarrollo

### Estructura de Código
El proyecto sigue principios de **Clean Architecture** y **SOLID**:

- **Separación de responsabilidades** por capas
- **Inyección de dependencias** con FastAPI
- **Validación robusta** con Pydantic
- **Documentación exhaustiva** en el código
- **Manejo de errores** consistente
- **Testing** preparado (estructura lista)

### Convenciones
- **Nombres:** snake_case para Python, camelCase para JS futuro
- **Comentarios:** Docstrings completos en español
- **Commits:** Conventional Commits
- **Branching:** GitFlow para releases

---

## Solución de Problemas

### Problemas Comunes

**🤖 El bot no responde:**
```bash
# Verificar logs
docker compose logs backend

# Verificar webhook
curl -X GET "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

**🛒 El carrito no funciona:**
```bash
# Verificar Redis
docker compose logs redis

# Probar conexión Redis
docker compose exec redis redis-cli ping
```

**🔍 Búsqueda no encuentra productos:**
```bash
# Verificar indexación
make search-test

# Re-indexar si es necesario
make update-catalog
```

**🌐 Webhook no funciona:**
```bash
# Verificar configuración HTTPS
curl -I https://bot.tudominio.com

# Verificar configuración en .env
grep TELEGRAM_WEBHOOK_URL .env
```

**📦 Órdenes no se crean:**
```bash
# Verificar logs de checkout
docker compose logs backend | grep checkout

# Verificar base de datos
docker compose exec postgres psql -U macroferro_user -d macroferro -c "SELECT * FROM orders LIMIT 5;"
```

---

## Contacto y Soporte

Para preguntas técnicas o contribuciones, revisar la documentación en `/docs` o consultar los comentarios exhaustivos en el código fuente.

**Estado del proyecto:** 🟢 **Activo - Fase 2 Completada con Carrito Integrado**

## 👤 Author and Contact

**David Salas**
- Website: [dasafodata.com](https://dasafodata.com)
- GitHub: [@dasafo](https://github.com/dasafo)
- LinkedIn: [David Salas](https://www.linkedin.com/in/dasafodata/)

<p align="center">
  <sub>Created with ❤️ by David Salas - dasafodata</sub>
</p>