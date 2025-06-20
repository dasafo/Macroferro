## Proyecto Macroferro: Plan de Desarrollo Detallado

**Visión General:** Crear un sistema mayorista B2B para "Macroferro" que permita a los clientes (ferreterías) consultar productos, realizar pedidos a través de un bot de Telegram, y que permita al dueño gestionar el inventario y productos. El sistema utilizará una arquitectura moderna de microservicios contenerizada.

**Pila Tecnológica Principal:**

*   **Contenerización:** Docker, Docker Compose
*   **Base de Datos Relacional:** PostgreSQL
*   **Gestión de BD:** PgAdmin
*   **Base de Datos Vectorial:** Qdrant (para búsqueda semántica)
*   **Caché en Memoria:** Redis (para carritos de compra, sesiones)
*   **Backend API:** FastAPI (Python)
*   **Interacción con Usuario:** Bot de Telegram
*   **IA (Embeddings & Consultas):** OpenAI API
*   **Exposición Local:** ngrok (para desarrollo del webhook de Telegram)

---

### Fase 0: Cimientos – Configuración del Entorno y Base de Datos

**Objetivo:** Establecer la infraestructura base con Docker y cargar los datos iniciales en PostgreSQL.

1.  **Diseño Final del Esquema de PostgreSQL:**
    *   `categories` (category\_id PK, name, parent\_id FK)
    *   `clients` (client\_id PK, name, email UNIQUE, phone, address)
    *   `products` (sku PK, category\_id FK, name, description, price NUMERIC(10,2), brand, spec\_json JSONB)
    *   `warehouses` (warehouse\_id PK, name, address)
    *   `stock` (stock\_id SERIAL PK, sku FK, warehouse\_id FK, quantity INT, UNIQUE(sku, warehouse\_id))
    *   `images` (image\_id SERIAL PK, url TEXT UNIQUE, alt\_text)
    *   `product_images` (sku FK REFERENCES products(sku) ON DELETE CASCADE, image\_id FK REFERENCES images(image_id) ON DELETE CASCADE, PRIMARY KEY (sku, image\_id))
    *   `invoices` (invoice\_id PK, client\_id FK, total NUMERIC(10,2), pdf\_url TEXT, created\_at TIMESTAMPTZ DEFAULT NOW())
    *   `invoice_items` (item\_id SERIAL PK, invoice\_id FK REFERENCES invoices(invoice_id) ON DELETE CASCADE, sku FK, quantity INT, price\_at\_purchase NUMERIC(10,2))

2.  **Script de Inicialización (`init_db_scripts/init.sql`):**
    *   Crear todas las tablas con `CREATE TABLE`, definiendo tipos, restricciones (PK, FK, UNIQUE, NOT NULL), y `ON DELETE CASCADE` para relaciones importantes.
    *   **Carga de CSVs:**
        *   Crear un subdirectorio `init_db_scripts/csv_data/`.
        *   **Pre-procesamiento de `images.csv` (Recomendado):** Antes de la carga, modifica `images.csv` para que en lugar de `product_id` tenga el `sku` correspondiente de `products.csv`. Puedes hacerlo con un script Python/Pandas. El nuevo `images_processed.csv` tendría `sku, url, alt_text`.
        *   En `init.sql`:
            ```sql
            -- Ejemplo de carga para products
            \COPY products FROM '/docker-entrypoint-initdb.d/csv_data/products.csv' WITH CSV HEADER DELIMITER ',';

            -- Carga de imágenes pre-procesadas
            -- 1. Cargar URLs únicas en la tabla images
            CREATE TEMP TABLE temp_images (sku VARCHAR(50), url TEXT, alt_text VARCHAR(255));
            \COPY temp_images FROM '/docker-entrypoint-initdb.d/csv_data/images_processed.csv' WITH CSV HEADER DELIMITER ',';
            INSERT INTO images (url, alt_text) SELECT DISTINCT url, alt_text FROM temp_images ON CONFLICT (url) DO NOTHING;
            -- 2. Poblar product_images
            INSERT INTO product_images (sku, image_id)
            SELECT ti.sku, i.image_id
            FROM temp_images ti
            JOIN images i ON ti.url = i.url;
            DROP TABLE temp_images;

            -- Repetir \COPY para las demás tablas...
            ```
    *   Asegurar que el orden de carga respete las dependencias de FK.

3.  **Configuración de `docker-compose.yml`:**
    ```yaml
    version: '3.8'
    services:
      postgres:
        image: postgres:15
        container_name: macroferro_postgres
        restart: unless-stopped
        environment:
          POSTGRES_USER: ${POSTGRES_USER:-user}
          POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
          POSTGRES_DB: ${POSTGRES_DB:-macroferro_db}
        volumes:
          - postgres_data:/var/lib/postgresql/data
          - ./init_db_scripts:/docker-entrypoint-initdb.d
        ports:
          - "5432:5432"

      pgadmin:
        image: dpage/pgadmin4
        container_name: macroferro_pgadmin
        restart: unless-stopped
        environment:
          PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL:-admin@example.com}
          PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD:-admin}
        ports:
          - "5050:80"
        depends_on:
          - postgres

      redis:
        image: redis:7-alpine
        container_name: macroferro_redis
        restart: unless-stopped
        ports:
          - "6379:6379"

      qdrant:
        image: qdrant/qdrant:latest
        container_name: macroferro_qdrant
        restart: unless-stopped
        ports:
          - "6333:6333" # gRPC
          - "6334:6334" # REST
        volumes:
          - qdrant_storage:/qdrant/storage

      backend:
        build: ./backend
        container_name: macroferro_backend
        restart: unless-stopped
        ports:
          - "8000:8000"
        volumes:
          - ./backend:/app
        depends_on:
          - postgres
          - redis
          - qdrant
        environment:
          DATABASE_URL: postgresql://${POSTGRES_USER:-user}:${POSTGRES_PASSWORD:-password}@postgres:5432/${POSTGRES_DB:-macroferro_db}
          REDIS_HOST: redis
          REDIS_PORT: 6379
          QDRANT_HOST: qdrant
          QDRANT_PORT_GRPC: 6333
          QDRANT_PORT_REST: 6334
          OPENAI_API_KEY: ${OPENAI_API_KEY} # Debe estar en un .env o ser exportada
        command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

    volumes:
      postgres_data:
      qdrant_storage:
    ```
    *   Crear un archivo `.env` en la raíz del proyecto para las variables (POSTGRES\_USER, OPENAI\_API\_KEY, etc.).

4.  **Acciones:**
    *   Estructurar directorios, preparar `init.sql` y CSVs (con `images_processed.csv`).
    *   Crear `.env` con `OPENAI_API_KEY` y credenciales de BD.
    *   Ejecutar `docker-compose up -d --build`.
    *   Verificar en PgAdmin que las tablas existen y los datos se cargaron.

---

### Fase 1: API Backend (FastAPI) – Lógica de Productos y Categorías

**Objetivo:** Desarrollar los endpoints básicos para consultar productos y categorías.

1.  **Estructura del Backend (`./backend/app/`):**
    *   `main.py`: App FastAPI, routers.
    *   `core/config.py`: Configuración de la aplicación y variables de entorno.
    *   `db/database.py`: SQLAlchemy engine, `SessionLocal`, `get_db` dependency.
    *   `db/models.py`: Modelos SQLAlchemy para todas las tablas.
    *   `schemas/`: Esquemas Pydantic para validación de datos.
    *   `crud/`: Funciones de acceso directo a datos.
    *   `services/`: Lógica de negocio.
    *   `api/v1/endpoints/`: Endpoints de la API REST.

2.  **Acciones:**
    *   Implementar la estructura y los endpoints.
    *   Añadir dependencias (`fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `pydantic`, `python-dotenv`) a `backend/requirements.txt`.
    *   Probar endpoints con Swagger UI (`http://localhost:8000/docs`).

---

### Fase 2: Inteligencia – Búsqueda Semántica con Qdrant

**Objetivo:** Implementar la búsqueda de productos basada en embeddings de OpenAI.

1.  **Indexación de Productos en Qdrant:**
    *   Script de indexación que procesa productos desde PostgreSQL.
    *   Generación de embeddings usando OpenAI API.
    *   Almacenamiento en Qdrant para búsqueda semántica.

2.  **Endpoint de Búsqueda Semántica:**
    *   `POST /products/search` para búsquedas en lenguaje natural.
    *   Integración con OpenAI para entender consultas de usuario.

3.  **Acciones:**
    *   Desarrollar y ejecutar el script de indexación.
    *   Implementar el endpoint de búsqueda.
    *   Probar la búsqueda.

---

### Fase 3: Bot de Telegram – Interfaz Conversacional Directa

**Objetivo:** Crear un bot de Telegram que interactúe directamente con la API FastAPI usando IA.

#### 🤖 **Implementación del Bot de Telegram**

1.  **Configuración del Bot:**
    *   Crear bot con @BotFather en Telegram.
    *   Configurar webhook para recibir mensajes.
    *   Integrar con ngrok para desarrollo local.

2.  **Servicio de Telegram en FastAPI:**
    *   `POST /api/v1/telegram/webhook`: Recibir mensajes de Telegram.
    *   `GET /api/v1/telegram/health`: Verificar estado del bot.
    *   Procesamiento inteligente de mensajes usando OpenAI.

3.  **Funcionalidades del Bot:**
    *   **Búsqueda de productos:** "Busco tubos de PVC de 110mm"
    *   **Información detallada:** Mostrar especificaciones, precios, stock.
    *   **Recomendaciones:** Sugerir productos relacionados.
    *   **Gestión de carritos:** Agregar/quitar productos.
    *   **Consulta de órdenes:** Estado de pedidos anteriores.

#### 🔄 **Flujo de Conversación**

1.  **Usuario envía mensaje → Telegram → Webhook → FastAPI**
2.  **FastAPI procesa con OpenAI → Busca en BD/Qdrant**
3.  **Genera respuesta contextual → Envía a Telegram → Usuario**

#### 🛠 **Configuración Técnica**

1.  **Variables de Entorno (.env):**
    ```
    TELEGRAM_BOT_TOKEN=tu-bot-token
    TELEGRAM_WEBHOOK_URL=https://tu-ngrok-url.app/api/v1/telegram/webhook
    TELEGRAM_WEBHOOK_SECRET=tu-secreto-webhook
    ```

2.  **Desarrollo Local con ngrok:**
    ```bash
    # Terminal 1: Iniciar servicios
    docker compose up -d
    
    # Terminal 2: Exponer webhook
    ngrok http 8000
    
    # Configurar webhook
    curl -X POST "http://localhost:8000/api/v1/telegram/set-webhook"
    ```

---

### Fase 4: Gestión de Pedidos y Carritos

**Objetivo:** Implementar funcionalidad completa de e-commerce a través del bot.

1.  **Sistema de Carritos:**
    *   Almacenamiento en Redis por usuario.
    *   Gestión de sesiones de compra.
    *   Cálculo de totales y disponibilidad.

2.  **Proceso de Pedidos:**
    *   Confirmación de pedidos vía bot.
    *   Generación de facturas.
    *   Notificaciones de estado.

---

### Fase 5: Optimización y Producción

**Objetivo:** Preparar el sistema para entorno de producción.

1.  **Mejoras de Performance:**
    *   Optimización de consultas a BD.
    *   Cache estratégico con Redis.
    *   Monitoreo y métricas.

2.  **Seguridad y Escalabilidad:**
    *   Autenticación robusta.
    *   Rate limiting.
    *   Documentación completa.

---

## Estado Actual ✅

### ✅ **Completado:**
- [x] **Infraestructura Docker:** PostgreSQL, Redis, Qdrant, PgAdmin configurados.
- [x] **API FastAPI:** Endpoints de productos, categorías, búsqueda semántica.
- [x] **Integración OpenAI:** Búsqueda inteligente y procesamiento de lenguaje natural.
- [x] **Bot de Telegram:** Configuración completa, webhook, procesamiento de mensajes.
- [x] **Búsqueda Semántica:** Qdrant indexado con embeddings de productos.

### 🚧 **En Progreso:**
- [ ] **Gestión de Carritos:** Sistema de carritos persistentes en Redis.
- [ ] **Proceso de Pedidos:** Flujo completo de compra vía bot.
- [ ] **Panel de Administración:** Interface web para gestión de productos.

### 📋 **Próximos Pasos:**
1. **Implementar sistema de carritos en Redis.**
2. **Crear flujo completo de pedidos.**
3. **Desarrollar panel de administración web.**
4. **Optimizar performance y añadir monitoreo.**
5. **Preparar deployment en producción.**

---

## Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │────│   FastAPI       │────│   PostgreSQL    │
│                 │    │   Backend       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │                         │
                       ┌───────┴────────┐               │
                       │                │               │
                ┌──────▼──────┐  ┌──────▼──────┐       │
                │   Qdrant    │  │    Redis    │       │
                │  (Vectores) │  │   (Cache)   │       │
                └─────────────┘  └─────────────┘       │
                               │                        │
                        ┌──────▼──────┐                │
                        │   OpenAI    │                │
                        │     API     │                │
                        └─────────────┘                │
                                                       │
                        ┌──────────────────────────────▼┐
                        │          PgAdmin             │
                        │     (Administración)         │
                        └──────────────────────────────┘
```

El sistema está completamente funcional con el bot de Telegram integrado directamente con FastAPI, eliminando la complejidad adicional y manteniendo un flujo de datos directo y eficiente.
