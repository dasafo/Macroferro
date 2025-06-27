# Macroferro – Descripción detallada de la estructura de carpetas y archivos

A continuación encontrarás una explicación pormenorizada del propósito de **cada carpeta y archivo** dentro del proyecto `Macroferro`. El objetivo es que puedas orientarte rápidamente y sepas dónde añadir o modificar código, datos o documentación.

---

## 1. Raíz del proyecto (`/`)

| Elemento             | Descripción                                                                                                              | Cuándo lo tocarás                                                                   |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `docker-compose.yml` | Orquesta todos los servicios (PostgreSQL, Redis, Qdrant, backend). Define redes, volúmenes y variables de entorno. | Cuando quieras levantar / parar todos los contenedores o cambiar puertos/volúmenes. |
| `LICENSE`            | Licencia de uso del código (p. ej. MIT, Apache 2).                                                                       | Solo si cambias la licencia.                                                        |
| `README.md`          | Introducción general, instrucciones de uso rápido y enlaces.                                                             | Mantenla al día para onboarding de colaboradores.                                   |
| `docs/`              | Documentación de alto nivel.                                                                                             | Añadir tutoriales, diagramas, etc.                                                  |
| `init_db_scripts/`   | Scripts y CSV para poblar PostgreSQL al iniciar.                                                                         | Agregar/editar datos de ejemplo o cambiar el esquema inicial.                       |
| `scripts/`           | Utilidades/automatizaciones (p. ej. indexar Qdrant).                                                                     | Ejecutar scripts one‑off desde la línea de comandos.                                |

---

## 2. Backend (`backend/`)

Contiene **todo el código** del micro‑servicio FastAPI.

### 2.1 `backend/Dockerfile`

Imagen Docker que compila los requisitos e inicia Uvicorn. Cambia aquí la versión de Python o librerías del sistema.

### 2.2 `backend/requirements.txt`

Lista de dependencias Python para `pip install -r`. Alinear con `poetry`/`pip-tools` si los usas.

### 2.3 `backend/logs/`

Directorio donde se almacenan los logs del backend cuando se ejecuta en producción.

### 2.4 Código fuente (`backend/app/`)

```
backend/app/
├── main.py            # Punto de entrada FastAPI (crea app, incluye routers)
├── __pycache__/       # Byte‑code compilado (se genera solo)
├── api/               # Capa de presentación (routers)
├── core/              # Configuración global y utilidades compartidas
├── crud/              # Acceso 100 % CRUD a BD (SQLAlchemy puro)
├── db/                # Conexión y modelos de BD
├── schemas/           # Esquemas Pydantic (entrada/salida de la API)
└── services/          # Lógica de negocio de alto nivel
```

#### 2.4.1 `main.py`

* Crea la instancia `FastAPI`.
* Incluye los routers de `api.v1`.
* Monta la versión y el título desde `settings`.

#### 2.4.2 `api/`

* `deps.py`: dependencias comunes (p. ej. `get_db`, `verify_admin`).
* `v1/`: versiónada para futuras breaking‑changes.

  * `endpoints/`: rutas específicas separadas por dominio.

    * `products.py`: endpoints **GET /products** y **GET /products/{sku}**.
    * `categories.py`: endpoints de categorías.

#### 2.4.3 `core/`

* `config.py`: carga y valida variables de entorno (ya analizado).
* `__init__.py`: expone `settings`.

#### 2.4.4 `crud/`

* Operaciones CRUD puras (sin reglas de negocio):

  * `product_crud.py`: `get_product`, `list_products`, etc.
  * `category_crud.py`: idem para categorías.

#### 2.4.5 `db/`

* `database.py`: motor y sesiones SQLAlchemy.
* `models.py`: mapeo de todas las tablas (ya detallado).

#### 2.4.6 `schemas/`

* `product.py`: clases Pydantic (`ProductBase`, `ProductResponse…`).
* `category.py`: esquemas equivalentes para categorías.

#### 2.4.7 `services/`

Aquí reside la **lógica de negocio principal**. Esta capa orquesta las operaciones CRUD y añade la lógica compleja que define lo que hace la aplicación. Tras la refactorización, la estructura es:

*   `telegram_service.py`: Actúa como el **orquestador principal** del bot. Recibe las peticiones del webhook, las pasa al `AIAnalyzer` para entender la intención, y luego delega la tarea al `Handler` correspondiente.
*   `bot_components/`: Un directorio que contiene **componentes especializados y modulares**, cada uno con una única responsabilidad:
    *   `ai_analyzer.py`: Se comunica con la API de OpenAI para interpretar el lenguaje natural del usuario y extraer la `intención` y las `entidades`.
    *   `product_handler.py`: Gestiona todo lo relacionado con la búsqueda de productos, ya sea por texto, semántica o SKU.
    *   `cart_handler.py`: Encapsula toda la lógica para gestionar el carrito de la compra en Redis (añadir, ver, eliminar, vaciar).
    *   `checkout_handler.py`: Orquesta el proceso de finalización de la compra, guiando al usuario para recoger sus datos y crear el pedido.
*   `email_service.py`: (En desarrollo) Gestionará el envío de correos transaccionales, como las confirmaciones de pedido.

---

## 3. Datos iniciales (`init_db_scripts/`)

| Archivo/Carpeta  | Descripción                                                                            |
| ---------------- | -------------------------------------------------------------------------------------- |
| `init.sql`       | Crea el esquema y ejecuta `\COPY …` para cargar CSV.                                   |
| `csv_data/*.csv` | Datos de ejemplo (productos, stock, etc.). Modifica o añade registros aquí para tests. |

> **Tip** – Si añades columnas nuevas, recuerda reflejarlo en `models.py` y `init.sql`.

---

## 4. Scripts auxiliares (`scripts/`)

| Archivo                | Propósito                                                                                                                                                                               |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `index_qdrant_data.py` | Lee productos de PostgreSQL, genera embeddings vía OpenAI y los sube a Qdrant para la búsqueda semántica. Ejecuta con `docker-compose run backend python scripts/index_qdrant_data.py`. |

---

## 5. Documentación (`docs/`)

| Archivo        | Contenido                                                                        |
| -------------- | -------------------------------------------------------------------------------- |
| `hoja_ruta.md` | Roadmap en fases (del entorno hasta notificaciones). Úsalo para marcar progreso. |

---

## 6. Otros

| Elemento                                             | Descripción                                                                                          |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `__pycache__/`                                       | Carpetas generadas automáticamente por Python; no deberían subirse a Git (añadidas en `.gitignore`). |
| Volúmenes Docker (`postgres_data`, `qdrant_storage`) | Se crean al levantar `docker-compose`; almacenan datos persistentes fuera de los contenedores.       |

---

### Flujo típico de desarrollador

1. Clonas el repo y creas tu `.env` (copiando de `.env.example`).
2. `docker-compose up -d --build` para levantar todo.
3. Abres Swagger en `http://localhost:8000/docs` y pruebas `/products`.
4. Si añades lógica nueva:

   * Modelos: `backend/app/db/models.py`
   * Esquemas: `backend/app/schemas/`
   * CRUD: `backend/app/crud/`
   * Servicios: `backend/app/services/`
   * Rutas: `backend/app/api/v1/endpoints/`
5. Tests / scripts manuales en `scripts/`.

---

> **¡Listo!** Ahora tienes un mapa de referencia rápido para saber dónde está cada pieza de Macroferro.
