# Macroferro

## Visión General del Proyecto

Macroferro es un sistema de gestión y ventas mayorista B2B diseñado para una ferretería. El objetivo es crear una plataforma robusta que permita a los clientes (otras ferreterías) consultar productos y realizar pedidos a través de una interfaz conversacional (un bot de Telegram). A su vez, el sistema proporcionará al dueño herramientas para gestionar el inventario, los productos y los pedidos.

La arquitectura se basa en un enfoque moderno de servicios contenerizados para garantizar la escalabilidad y la mantenibilidad.

## Pila Tecnológica

-   **Contenerización:** Docker, Docker Compose
-   **Base de Datos Relacional:** PostgreSQL
-   **Gestión de BD:** PgAdmin
-   **Base de Datos Vectorial:** Qdrant
-   **Caché en Memoria:** Redis
-   **Backend API:** FastAPI (Python)
-   **Orquestación/Workflow:** n8n (para el bot)
-   **Interacción con Usuario:** Bot de Telegram
-   **IA (Embeddings & Consultas):** OpenAI API
-   **Exposición Local (Desarrollo):** ngrok

---

## Estado Actual del Proyecto: **FASE 0 COMPLETADA**

Actualmente, hemos finalizado con éxito la **Fase 0: Cimientos del Entorno y Base de Datos**.

#### Logros Principales:
1.  **Entorno Contenerizado Funcional:** Todos los servicios base (`postgres`, `pgadmin`, `redis`, `qdrant`) están definidos en `docker-compose.yml` y se levantan correctamente.
2.  **Base de Datos Inicializada:** Se ha creado y depurado el script `init_db_scripts/init.sql`. Este script crea todo el esquema de la base de datos relacional.
3.  **Carga de Datos Exitosa:** Todos los datos iniciales de los archivos CSV (`products`, `categories`, `clients`, `warehouses`, `stock`, `images`, etc.) se cargan correctamente en PostgreSQL durante el arranque.
4.  **Relaciones de Datos Verificadas:** Se ha validado la lógica de negocio clave, como la relación muchos a muchos entre `products` y `images`, que ahora funciona como se esperaba (200 relaciones en `product_images` a partir de 7 imágenes únicas).

En resumen, la infraestructura base del proyecto está sólidamente establecida y lista para ser consumida por un backend.

---

## Próximos Pasos: **INICIANDO FASE 1**

El siguiente gran paso es comenzar la **Fase 1: API Backend (FastAPI) – Lógica de Productos y Categorías**.

El objetivo de esta fase será construir los primeros endpoints de la API que permitirán consultar los datos que ya hemos cargado en la base de datos. Específicamente, se crearán rutas para:
-   Obtener la lista de productos.
-   Obtener los detalles de un producto específico por su SKU.
-   Listar las categorías de productos.

---

## Instrucciones de Puesta en Marcha

Para levantar el proyecto en su estado actual, sigue estos pasos:

1.  **Prerrequisitos:** Asegúrate de tener `Docker` y `Docker Compose` instalados en tu sistema.

2.  **Clonar el Repositorio (si aplica):**
    ```bash
    git clone <url-del-repositorio>
    cd Macroferro
    ```

3.  **Crear el archivo de entorno:**
    Crea un archivo llamado `.env` en la raíz del proyecto y añade las siguientes variables. Puedes ajustar los valores.
    ```env
    # Credenciales de PostgreSQL
    POSTGRES_USER=user
    POSTGRES_PASSWORD=password
    POSTGRES_DB=macroferro_db

    # Credenciales de PgAdmin
    PGADMIN_EMAIL=admin@example.com
    PGADMIN_PASSWORD=admin

    # Clave de API (requerida para fases futuras)
    OPENAI_API_KEY=tu_clave_de_openai_aqui
    ```

4.  **Levantar los servicios:**
    Abre una terminal en la raíz del proyecto y ejecuta:
    ```bash
    docker compose up -d --build
    ```
    Este comando construirá las imágenes si es necesario y arrancará todos los contenedores en segundo plano.

5.  **Verificar la Base de Datos:**
    -   Accede a PgAdmin en tu navegador: `http://localhost:5050`.
    -   Inicia sesión con las credenciales que definiste en el archivo `.env`.
    -   Añade un nuevo servidor para conectar a la base de datos de PostgreSQL usando `macroferro_postgres` como el "Host name/address" y las credenciales de la base de datos del archivo `.env`.
    -   Verifica que todas las tablas han sido creadas y pobladas con los datos.