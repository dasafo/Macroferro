# Macroferro

## Visión General del Proyecto

Macroferro es un sistema de gestión y ventas mayorista B2B diseñado para una ferretería. El objetivo es crear una plataforma robusta que permita a los clientes (otras ferreterías) consultar productos y realizar pedidos a través de una interfaz conversacional (un bot de Telegram). A su vez, el sistema proporcionará al dueño herramientas para gestionar el inventario, los productos y los pedidos.

La arquitectura se basa en un enfoque moderno de servicios contenerizados para garantizar la escalabilidad y la mantenibilidad.

## Pila Tecnológica

-   **Contenerización:** Docker, Docker Compose
-   **Base de Datos Relacional:** PostgreSQL 16
-   **Gestión de BD:** PgAdmin 4
-   **Base de Datos Vectorial:** Qdrant (para búsquedas semánticas futuras)
-   **Caché en Memoria:** Redis (para sesiones y caché)
-   **Backend API:** FastAPI (Python 3.9)
-   **ORM:** SQLAlchemy 2.0 con modelos declarativos
-   **Validación:** Pydantic v2 para esquemas y validación de datos
-   **Orquestación/Workflow:** n8n (para el bot - fase futura)
-   **Interacción con Usuario:** Bot de Telegram (fase futura)
-   **IA (Embeddings & Consultas):** OpenAI API (fase futura)
-   **Exposición Local (Desarrollo):** ngrok (fase futura)

---

## Estado Actual del Proyecto: **FASE 1 COMPLETADA**

### ✅ **FASE 0: Cimientos del Entorno y Base de Datos** - **COMPLETADA**
1.  **Entorno Contenerizado Funcional:** Todos los servicios base están operativos
2.  **Base de Datos Inicializada:** Esquema completo creado e inicializado
3.  **Carga de Datos Exitosa:** Todos los datos CSV cargados correctamente
4.  **Relaciones de Datos Verificadas:** Integridad referencial funcionando

### ✅ **FASE 1: API Backend (FastAPI) – Lógica de Productos y Categorías** - **COMPLETADA**

#### Arquitectura Backend Implementada

**Estructura del Proyecto:**
```
backend/
├── app/
│   ├── main.py                 # Punto de entrada de FastAPI
│   │   ├── deps.py            # Dependencias de FastAPI
│   │   └── v1/
│   │       ├── api_router.py  # Router principal v1
│   │       └── endpoints/
│   │           ├── products.py    # Endpoints de productos
│   │           └── categories.py  # Endpoints de categorías
│   ├── core/
│   │   ├── config.py          # Configuración de la aplicación
│   │   └── database.py        # Configuración de base de datos
│   ├── crud/
│   │   ├── product_crud.py    # Operaciones CRUD productos
│   │   └── category_crud.py   # Operaciones CRUD categorías
│   ├── db/
│   │   ├── base.py           # Base para modelos
│   │   ├── database.py       # Configuración de SQLAlchemy
│   │   └── models.py         # Modelos de SQLAlchemy
│   ├── schemas/
│   │   ├── product.py        # Esquemas Pydantic productos
│   │   └── category.py       # Esquemas Pydantic categorías
│   └── services/
│       ├── product_service.py    # Lógica de negocio productos
│       └── category_service.py   # Lógica de negocio categorías
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

#### Patrones de Diseño Implementados

**🏗️ Arquitectura en Capas:**
- **API Layer:** Endpoints REST con FastAPI
- **Service Layer:** Lógica de negocio y validaciones
- **CRUD Layer:** Operaciones de base de datos
- **Model Layer:** Modelos de SQLAlchemy
- **Schema Layer:** Validación con Pydantic

**📋 Características Técnicas:**
- ✅ **Inyección de Dependencias:** Gestión automática de sesiones de BD
- ✅ **Validación Robusta:** Pydantic v2 con validaciones personalizadas
- ✅ **Manejo de Errores:** Respuestas HTTP consistentes
- ✅ **Documentación Automática:** OpenAPI/Swagger en `/docs`
- ✅ **Eager Loading:** Optimización de consultas N+1
- ✅ **Transacciones:** Consistencia de datos garantizada
- ✅ **Logging:** Configuración profesional con niveles

#### Validaciones de Negocio Implementadas

**🔍 Productos:**
- Unicidad de SKU
- Validación de precios (no negativos)
- Verificación de existencia de categorías
- Formato JSON para especificaciones técnicas
- Límites de paginación configurables

**📂 Categorías:**
- Validación de jerarquías padre-hijo
- Prevención de ciclos en la estructura
- Verificación de dependencias antes de eliminación

#### Base de Datos

**📊 Modelos Implementados:**
- ✅ `Product`: Catálogo de productos con relaciones
- ✅ `Category`: Sistema jerárquico de categorías
- ✅ `Image`: Gestión de imágenes de productos
- ✅ `ProductImage`: Relación many-to-many productos-imágenes
- ✅ `Client`: Información de clientes B2B
- ✅ `Warehouse`: Gestión de múltiples almacenes
- ✅ `Stock`: Inventario por producto y almacén
- ✅ `Invoice` e `InvoiceItem`: Sistema de facturación

**🔗 Relaciones Implementadas:**
- Productos ↔ Categorías (many-to-one)
- Productos ↔ Imágenes (many-to-many)
- Categorías jerárquicas (self-referential)
- Stock por producto y almacén
- Sistema completo de facturación

#### Datos de Prueba

**📈 Dataset Cargado:**
- **200 productos** con información completa
- **33 categorías** con estructura jerárquica
- **7 imágenes únicas** con 200 asociaciones producto-imagen
- **11 clientes B2B** con información de contacto
- **3 almacenes** con ubicaciones
- **600+ registros de stock** distribuidos
- **51 facturas** con 31 items de prueba

---

## Estado de Desarrollo por Módulos

### ✅ **Módulos Completados**
- [x] **Configuración de entorno** (Docker, Docker Compose)
- [x] **Base de datos** (PostgreSQL, modelos, relaciones)
- [x] **API de productos** (CRUD completo con validaciones)
- [x] **API de categorías** (CRUD completo con jerarquías)
- [x] **Capa de servicios** (lógica de negocio)
- [x] **Documentación de código** (comentarios exhaustivos)
- [x] **Manejo de errores** (respuestas HTTP consistentes)
- [x] **Validación de datos** (Pydantic schemas)

### 🚧 **Módulos en Preparación**
- [ ] **API de imágenes** (gestión de archivos)
- [ ] **API de inventario** (stock y almacenes)
- [ ] **API de clientes** (gestión B2B)
- [ ] **API de facturación** (órdenes y pagos)
- [ ] **Sistema de autenticación** (JWT, roles)
- [ ] **Búsqueda semántica** (Qdrant + OpenAI)
- [ ] **Bot de Telegram** (interfaz conversacional)
- [ ] **Dashboard administrativo** (gestión web)

---

## Instrucciones de Puesta en Marcha

### Prerrequisitos
- Docker Engine 20.10+
- Docker Compose v2.0+
- Git (para clonar el repositorio)

### Instalación

1. **Clonar el Repositorio:**
   ```bash
   git clone <url-del-repositorio>
   cd Macroferro
   ```

2. **Configurar Variables de Entorno:**
   
   Crear archivo `.env` en la raíz del proyecto:
   ```env
   # Configuración de PostgreSQL
   POSTGRES_USER=user
   POSTGRES_PASSWORD=password
   POSTGRES_DB=macroferro_db
   POSTGRES_HOST=macroferro_postgres
   POSTGRES_PORT=5432

   # Configuración de PgAdmin
   PGADMIN_EMAIL=admin@example.com
   PGADMIN_PASSWORD=admin

   # Configuración de FastAPI
   SECRET_KEY=tu_clave_secreta_super_segura_aqui
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30

   # APIs externas (para fases futuras)
   OPENAI_API_KEY=tu_clave_de_openai_aqui
   TELEGRAM_BOT_TOKEN=tu_token_de_telegram_aqui

   # Configuración de Redis
   REDIS_URL=redis://macroferro_redis:6379

   # Configuración de Qdrant
   QDRANT_HOST=macroferro_qdrant
   QDRANT_PORT=6333
   ```

3. **Levantar los Servicios:**
   ```bash
   docker compose up -d --build
   ```

4. **Verificar el Estado:**
   ```bash
   docker compose ps
   ```

### Acceso a los Servicios

Una vez levantados los servicios, están disponibles en:

- **🚀 API Backend (FastAPI):** http://localhost:8000
- **📖 Documentación API:** http://localhost:8000/docs
- **🐘 PgAdmin:** http://localhost:5050
- **🔍 Qdrant:** http://localhost:6333
- **⚡ Redis:** localhost:6379

### Verificación de la API

**Probar endpoints básicos:**
```bash
# Endpoint raíz (health check)
curl http://localhost:8000/

# Listar productos
curl http://localhost:8000/api/v1/products/

# Obtener producto específico
curl http://localhost:8000/api/v1/products/SKU001

# Listar categorías
curl http://localhost:8000/api/v1/categories/
```

### Gestión del Entorno

**Comandos útiles:**
```bash
# Parar todos los servicios
docker compose down

# Ver logs del backend
docker logs macroferro_backend

# Reconstruir solo el backend
docker compose up --build backend

# Acceso al contenedor del backend
docker exec -it macroferro_backend bash

# Reiniciar un servicio específico
docker compose restart backend
```

---

## Próximos Pasos: **FASE 2**

### 🎯 **Objetivos de la Fase 2: Gestión de Inventario y Stock**

1. **API de Stock y Almacenes:**
   - Endpoints para consulta de inventario
   - Gestión de múltiples almacenes
   - Histórico de movimientos de stock
   - Alertas de stock mínimo

2. **API de Gestión de Imágenes:**
   - Upload y almacenamiento de imágenes
   - Redimensionado automático
   - Asociación con productos
   - Optimización de carga

3. **Sistema de Autenticación:**
   - JWT para autenticación
   - Roles y permisos
   - Gestión de sesiones
   - Integración con Redis

4. **Optimizaciones y Mejoras:**
   - Caché de consultas frecuentes
   - Índices de base de datos
   - Paginación avanzada
   - Filtros complejos

---

## Arquitectura Técnica

### Diagrama de Servicios
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   PostgreSQL    │    │     Redis       │
│   Backend       │◄──►│   Database      │    │     Cache       │
│   (Port 8000)   │    │   (Port 5432)   │    │   (Port 6379)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                                              ▲
         │                                              │
         ▼                                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     PgAdmin     │    │     Qdrant      │    │    n8n Future  │
│   (Port 5050)   │    │   (Port 6333)   │    │  (Port 5678)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Stack de Desarrollo
- **Lenguaje:** Python 3.9
- **Framework:** FastAPI 0.104+
- **ORM:** SQLAlchemy 2.0
- **Validación:** Pydantic v2
- **Base de Datos:** PostgreSQL 16
- **Contenerización:** Docker + Docker Compose
- **Documentación:** OpenAPI 3.0 (Swagger)

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

## Contacto y Soporte

Para preguntas técnicas o contribuciones, revisar la documentación en `/docs` o consultar los comentarios exhaustivos en el código fuente.

**Estado del proyecto:** 🟢 **Activo - Fase 1 Completada**

