## Proyecto Macroferro: Plan de Desarrollo Detallado

**Visión General:** Crear un sistema mayorista B2B para "Macroferro" que permita a los clientes (ferreterías) consultar productos, realizar pedidos a través de un bot de Telegram, y que permita al dueño gestionar el inventario y productos. El sistema utilizará una arquitectura moderna de microservicios contenerizada.

**Pila Tecnológica Principal:**

*   **Contenerización:** Docker, Docker Compose
*   **Base de Datos Relacional:** PostgreSQL
*   **Gestión de BD:** PgAdmin
*   **Base de Datos Vectorial:** Qdrant (para búsqueda semántica)
*   **Caché en Memoria:** Redis (para carritos de compra, sesiones)
*   **Backend API:** FastAPI (Python)
*   **Orquestación/Workflow:** n8n
*   **Interacción con Usuario:** Bot de Telegram
*   **IA (Embeddings & Consultas):** OpenAI API
*   **Exposición Local:** ngrok (para desarrollo del webhook de n8n)

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
    *   `core/config.py`: Cargar settings (API keys, DB URL) desde env.
    *   `db/database.py`: SQLAlchemy engine, `SessionLocal`, `get_db` dependency.
    *   `db/models.py`: Modelos SQLAlchemy para todas las tablas.
    *   `schemas/`: Directorio para Pydantic Schemas (e.g., `product.py`, `category.py`).
        *   `ProductBase`, `ProductCreate`, `ProductUpdate`, `ProductResponse` (con info de categoría, stock, imágenes).
        *   `CategoryBase`, `CategoryResponse` (quizás con subcategorías).
    *   `crud/`: Funciones de acceso directo a datos (e.g., `product_crud.py`, `category_crud.py`).
        *   `get_product_by_sku(db, sku)`, `get_products(db, skip, limit, category_id=None, brand=None)`.
        *   `get_category(db, category_id)`, `get_categories_by_parent(db, parent_id)`.
    *   `services/`: Lógica de negocio (e.g., `product_service.py`).
        *   `fetch_product_details(db, sku)`: Agrega info de stock total y lista de imágenes.
    *   `api/v1/endpoints/`: Routers específicos (e.g., `products.py`, `categories.py`).
        *   `GET /products`, `GET /products/{sku}`.
        *   `GET /categories`, `GET /categories/{category_id}`.
    *   Utilizar `async def` para endpoints y funciones de servicio que realicen I/O.

2.  **Acciones:**
    *   Implementar la estructura y los endpoints.
    *   Añadir dependencias (`fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `pydantic`, `python-dotenv`) a `backend/requirements.txt`.
    *   Probar endpoints con Swagger UI (`http://localhost:8000/docs`).

---

### Fase 2: Inteligencia – Búsqueda Semántica con Qdrant

**Objetivo:** Implementar la búsqueda de productos basada en embeddings de OpenAI.

1.  **Indexación de Productos en Qdrant:**
    *   Crear un script `scripts/index_qdrant_data.py` (puede ejecutarse con `docker-compose run backend python scripts/index_qdrant_data.py`).
    *   Este script:
        *   Lee productos de PostgreSQL.
        *   Para cada producto, construye un texto descriptivo (e.g., `nombre + " " + descripción + " " + marca + " " + nombre_categoría + " " + " ".join(spec_json.keys())`).
        *   Genera embeddings usando OpenAI API (`text-embedding-ada-002` o similar).
        *   Conecta con Qdrant (`qdrant-client`).
        *   Crea una colección (e.g., `macroferro_products`) si no existe, con la dimensionalidad correcta.
        *   Inserta los vectores en Qdrant, usando `sku` como `id` del punto y el texto original como `payload` para referencia.
    *   Añadir `openai`, `qdrant-client` a `requirements.txt`.

2.  **Endpoint de Búsqueda Semántica en FastAPI:**
    *   En `api/v1/endpoints/products.py`:
        *   `POST /products/search`
        *   Recibe: `query: str` en el body.
        *   `product_service.py`:
            *   Función `semantic_search_products(db, query_text, openai_client, qdrant_client, top_k=5)`:
                *   Genera embedding para `query_text`.
                *   Busca en Qdrant los `top_k` SKUs más similares.
                *   Recupera los detalles completos de estos productos desde PostgreSQL.
                *   Devuelve lista de `ProductResponse`.

3.  **Acciones:**
    *   Desarrollar y ejecutar el script de indexación.
    *   Implementar el endpoint de búsqueda.
    *   Probar la búsqueda.

---

### Fase 3: Interfaz Conversacional – Telegram, n8n y Recomendaciones

**Objetivo:** Permitir a los usuarios interactuar con el bot para obtener información y recomendaciones.

1.  **Configuración de n8n:**
    *   Opcional: Añadir n8n al `docker-compose.yml`.
    *   Configurar ngrok para exponer n8n localmente: `ngrok http 5678` (puerto por defecto de n8n).
    *   Crear bot en Telegram con `@BotFather`, obtener token.
    *   Configurar webhook del bot: `/setwebhook` apuntando a `https://<ngrok_url>/webhook/telegram-macroferro`.

2.  **Flujo de n8n – Consulta de Productos:**
    *   **Trigger:** `Telegram Trigger` (con token y path del webhook).
    *   **Switch/IF Node:** Para diferentes tipos de comandos/mensajes.
    *   **HTTP Request Node:**
        *   Para consultas: Llama al endpoint `POST /products/search` de FastAPI.
        *   Para pedir info de un SKU específico: Llama a `GET /products/{sku}`.
    *   **Code/Set Node:** Formatea la respuesta de FastAPI (lista de productos, detalles) en un mensaje amigable para Telegram (incluyendo precios, URLs de imágenes si se recuperan).
    *   **Telegram Send Message Node:** Envía la respuesta.
    *   **Recomendaciones:**
        *   Si un usuario pide un producto, después de mostrarlo, el bot podría preguntar "¿Te gustaría ver productos similares?".
        *   Si responde "sí", n8n podría:
            1.  Tomar la descripción/nombre del producto actual.
            2.  Llamar de nuevo a `POST /products/search` con ese texto, pidiendo `top_k+1` resultados y excluyendo el SKU actual.
            3.  Mostrar los resultados.

3.  **Acciones:**
    *   Configurar n8n, ngrok, bot.
    *   Crear el flujo básico en n8n para búsqueda y visualización de productos.
    *   Implementar lógica de recomendaciones.

¡Pillo la idea perfectamente! Es un plan fantástico y muy ambicioso, la evolución natural y más potente de todo lo que hemos construido. Pasar de una API a un asistente de ventas conversacional es el objetivo final.

Me encanta la visión. Para que no nos perdamos y construyamos sobre cimientos sólidos, he preparado una **hoja de ruta detallada**, dividida en fases lógicas. Iremos implementando paso a paso.

Esta es la estrategia que te propongo (Cursor):

### **Hoja de Ruta: Del Chat a la Venta**

#### 📍 **FASE 1: El Cerebro de la Búsqueda (El Endpoint que Falta)**

Antes de que `n8n` pueda hacer algo, necesita una "puerta de entrada" inteligente en nuestra API. Actualmente, no tenemos un endpoint que acepte una frase en lenguaje natural y devuelva resultados semánticos. **Este es el primer paso y el más crítico.**

-   **Tarea 1.1: Crear el Endpoint.**
    -   Definir una nueva ruta en `backend/app/v1/endpoints/products.py`: `POST /api/v1/products/search`.
    -   ¿Por qué `POST`? Porque las consultas de búsqueda pueden ser largas y es más limpio enviarlas en el cuerpo de la petición.
    -   Aceptará un JSON con un campo: `{"query": "lo que el usuario escribió"}`.

-   **Tarea 1.2: Implementar la Lógica en el Servicio.**
    -   En `backend/app/services/product_service.py`, crearemos la función `semantic_product_search`.
    -   Esta función tomará el texto del usuario, usará el modelo de OpenAI (`text-embedding-3-small`) para convertirlo en un vector.
    -   Consultará Qdrant con ese vector para obtener los `sku` de los productos más relevantes.

-   **Tarea 1.3: Enriquecer los Resultados.**
    -   Con los `sku` devueltos por Qdrant, la función consultará nuestra base de datos PostgreSQL para obtener los detalles completos de cada producto (nombre, precio, imagen, etc.).

-   **Tarea 1.4: Devolver Resultados Principales y Relacionados.**
    -   El endpoint no solo devolverá una lista. Devolverá un objeto con dos claves:
        -   `main_results`: Los 3-4 productos más relevantes.
        -   `related_results`: Los siguientes 2-3, como sugerencias.

#### 🚀 **FASE 2: El Flujo Básico de Conversación en n8n**

Una vez que la API sea capaz de "pensar", construiremos el esqueleto del flujo en `n8n`.

-   **Tarea 2.1: El Disparador (Trigger).**
    -   Usar el nodo `Telegram Trigger` para que el flujo se inicie cada vez que un usuario envía un mensaje.

-   **Tarea 2.2: La Inteligencia (LLM).**
    -   Conectar un nodo `OpenAI` (o `HTTP Request` a la API de OpenAI).
    -   Le enviaremos el mensaje del usuario con un prompt simple: *"Analiza esta frase de un cliente: '{mensaje_usuario}'. ¿Está buscando un producto? Si es así, extrae el objeto que busca. Responde solo en formato JSON con la estructura `{'intent': 'search', 'query': 'objeto'}` o `{'intent': 'other'}`."*

-   **Tarea 2.3: El "Switch" Lógico.**
    -   Usar un nodo `Switch` que evalúe el `intent` devuelto por el LLM.
    -   **Camino 1 (`search`):** Continúa el flujo de búsqueda.
    -   **Camino 2 (`other`):** Por ahora, responde con un "No te he entendido, prueba a buscar un producto como 'martillos' o 'tornillos de acero'".

-   **Tarea 2.4: La Llamada a la API.**
    -   En el camino `search`, usar un nodo `HTTP Request` para llamar a nuestro nuevo endpoint `POST /api/v1/products/search` con el `query` extraído por el LLM.

-   **Tarea 2.5: La Respuesta Simple.**
    -   Usar un nodo `Telegram` para enviar los resultados. Al principio, será una lista de texto simple formateada con los nombres y precios de los productos.

#### ✨ **FASE 3: Mejorando la Experiencia de Usuario (Hacerlo Bonito)**

Con el flujo funcionando, lo puliremos para que sea más visual e interactivo.

-   **Tarea 3.1: Respuestas Enriquecidas.**
    -   En lugar de una lista de texto, iterar sobre los resultados y enviar cada producto como un mensaje separado que incluya su **imagen**, nombre, precio y una breve descripción.

-   **Tarea 3.2: Botones Interactivos.**
    -   Añadir a cada mensaje de producto un **botón de "Añadir al carrito"** usando los `Inline Keyboards` de Telegram. Aunque todavía no funcione, prepara la interfaz para la siguiente fase.

-   **Tarea 3.3: Manejo de "No Hay Resultados".**
    -   Mejorar el mensaje cuando la búsqueda no devuelve nada, sugiriendo alternativas o pidiendo al usuario que reformule su búsqueda.




### Fase 4: Lógica Transaccional – Carrito y Pedidos

**Objetivo:** Permitir añadir productos al carrito y "finalizar" un pedido (simulando el pago).

1.  **API para Carrito (FastAPI + Redis):**
    *   `schemas/cart.py`: `CartItem(sku: str, quantity: int)`, `CartResponse(items: List[CartItem], total_price: float)`.
    *   `services/cart_service.py`:
        *   Clave Redis: `cart:<telegram_chat_id>`. Usar Hashes de Redis para `sku -> quantity`.
        *   `add_to_cart(chat_id, sku, quantity, db, redis_client)`: Verifica existencia del producto y stock disponible (en `stock_service`) antes de añadir.
        *   `get_cart_details(chat_id, db, redis_client)`: Recupera items, obtiene precios actuales de `products`, calcula total.
        *   `clear_cart(chat_id, redis_client)`.
    *   `api/v1/endpoints/cart.py`: `POST /cart/{chat_id}/items`, `GET /cart/{chat_id}`, `DELETE /cart/{chat_id}`.

2.  **API para Pedidos (FastAPI):**
    *   `schemas/order.py`: `OrderCreate(client_email: str)`, `OrderResponse(...)`.
    *   `services/order_service.py`:
        *   `process_order(chat_id, client_email, db, redis_client, stock_service)`:
            1.  Recupera/Crea cliente en `clients`.
            2.  Recupera carrito (`cart_service.get_cart_details`). Si está vacío, error.
            3.  **Transacción de Base de Datos:**
                *   Crea `invoice` con total.
                *   Para cada item del carrito:
                    *   Crea `invoice_item` (con `price_at_purchase`).
                    *   Llama a `stock_service.decrease_stock(sku, quantity, warehouse_id_strategy)` (ver Fase 5).
                *   Commit. Si algo falla, rollback.
            4.  Genera PDF simulado URL: `https://example.com/invoices/INVXXXX.pdf`.
            5.  Limpia carrito (`cart_service.clear_cart`).
            6.  Devuelve `OrderResponse`.
    *   `api/v1/endpoints/orders.py`: `POST /orders/{chat_id}`.

3.  **Flujo de n8n – Compra:**
    *   Detectar comandos como "añadir SKU001 al carrito", "ver carrito", "finalizar compra".
    *   Al finalizar:
        *   Preguntar email.
        *   Llamar a `POST /orders/{chat_id}`.
        *   Enviar confirmación con detalles y link de factura PDF (simulado) por Telegram.
        *   Enviar email de confirmación (usando SendGrid Node o similar) con la misma info.

4.  **Acciones:**
    *   Implementar APIs de carrito y pedidos.
    *   Actualizar flujo de n8n.

---

### Fase 5: Gestión de Stock y Alertas

**Objetivo:** Actualizar el stock tras una venta y notificar al dueño sobre niveles bajos.

1.  **Servicio de Stock (`services/stock_service.py`):**
    *   `get_total_stock(db, sku)`: Suma de `quantity` de todos los almacenes para un SKU.
    *   `decrease_stock(db, sku, quantity_to_decrease, warehouse_strategy="largest_first")`:
        *   Lógica para decidir de qué almacén(es) restar (e.g., el que más tiene, uno específico, o distribuir).
        *   Actualiza la tabla `stock`.
        *   Si el stock total post-venta cae por debajo del umbral (e.g., 5):
            *   Llama a `notification_service.send_low_stock_email(product_name, sku, new_total_stock)`.

2.  **Servicio de Notificaciones (`services/notification_service.py`):**
    *   `send_low_stock_email(product_name, sku, stock_level)`:
        *   Formatea un email.
        *   Envía usando `smtplib` (configurar con Gmail App Password o un servicio como SendGrid). Requiere variables de entorno para credenciales SMTP.

3.  **Acciones:**
    *   Refinar `stock_service` e implementar `notification_service`.
    *   Integrar la llamada de alerta en `order_service`.

---

### Fase 6: Panel de Administración (CRUD para el Dueño)

**Objetivo:** Proporcionar una forma para que el dueño gestione productos, categorías y stock.

1.  **Autenticación de Admin:**
    *   Mecanismo simple: Header `X-Admin-Token` con un token secreto definido en variables de entorno.
    *   Crear una dependencia FastAPI `verify_admin_token`.

2.  **Endpoints de Admin en FastAPI (protegidos por `verify_admin_token`):**
    *   `api/v1/endpoints/admin_products.py`:
        *   `POST /admin/products` (usa `ProductCreateSchema`)
        *   `PUT /admin/products/{sku}` (usa `ProductUpdateSchema`)
        *   `DELETE /admin/products/{sku}`
    *   `api/v1/endpoints/admin_stock.py`:
        *   `PUT /admin/stock/{sku}/{warehouse_id}` (actualiza cantidad)
    *   (Opcional) CRUD para categorías, almacenes.

3.  **Interfaz de Admin (Recomendación: Frontend Web Simple):**
    *   **Opción A (Recomendada):** Crear una aplicación web separada y simple (ej. Streamlit, o FastAPI sirviendo HTML con forms básicos) que consuma estos endpoints de admin.
        *   Esto evita la complejidad de parsear comandos de texto en Telegram para CRUD.
        *   El frontend pediría el `X-Admin-Token` para interactuar con la API.
    *   **Opción B (Telegram):** Si se insiste en Telegram:
        *   n8n necesitaría un flujo complejo para:
            *   Autenticar al admin (ej. `/admin_login <token>`).
            *   Parsear comandos como `/add_product name="X" price="Y" ...`.
            *   Llamar a los endpoints de admin de FastAPI con el token.
        *   **Desventaja:** Mucha lógica de parseo en n8n, propenso a errores.

4.  **Acciones:**
    *   Implementar endpoints de admin y autenticación en FastAPI.
    *   Desarrollar la interfaz de admin elegida (recomiendo Streamlit para rapidez).

---

### Fase 7: Pruebas, Refinamiento y Despliegue

**Objetivo:** Asegurar la calidad, robustez y preparar para un entorno (pseudo)productivo.

1.  **Pruebas Exhaustivas:**
    *   **Unitarias:** Para funciones en `crud` y `services` (usando `pytest`).
    *   **Integración:** Para los endpoints de FastAPI (usando `TestClient` de FastAPI).
    *   **Manual:** Flujo completo a través de Telegram.
2.  **Manejo de Errores y Logging:**
    *   Usar `HTTPException` de FastAPI para errores de API.
    *   Implementar logging estructurado en FastAPI.
    *   n8n debe manejar errores de las llamadas a la API y notificar al usuario (o al admin) de forma apropiada.
3.  **Seguridad:**
    *   Todas las claves y secretos en variables de entorno (`.env` localmente, secretos en producción).
    *   Validación de entrada en todos los endpoints.
4.  **Optimización:**
    *   Revisar consultas a BD para eficiencia.
    *   Asegurar que Qdrant está configurado para el rendimiento esperado.
5.  **Documentación:**
    *   Swagger UI (`/docs`) para la API de FastAPI.
    *   Notas sobre el flujo de n8n.
6.  **Despliegue (más allá de ngrok):**
    *   Considerar un VPS o plataforma PaaS para Docker.
    *   Configurar un proxy inverso (Nginx) para HTTPS y dominios.
    *   Actualizar el webhook de Telegram a la URL pública.
    *   Para el envío de emails en "producción", usar un servicio transaccional (SendGrid, Mailgun, AWS SES).

---

Este plan es más detallado y aborda posibles puntos de fricción. Recuerda que es un proyecto iterativo; puedes ajustar las fases y funcionalidades según progreses. ¡Mucha suerte con "Macroferro"!
