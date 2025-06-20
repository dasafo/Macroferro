# 🏭 Macroferro - Sistema Mayorista B2B

**Plataforma completa de gestión mayorista para ferreterías con inteligencia artificial integrada.**

---

## 📖 Descripción del Proyecto

**Macroferro** es un sistema mayorista B2B diseñado para ferreterías que permite:
- **Consulta inteligente de productos** vía bot de Telegram con IA
- **Búsqueda semántica avanzada** utilizando embeddings vectoriales
- **Gestión completa de inventario** con múltiples almacenes
- **Procesamiento de pedidos** automatizado
- **Análisis de datos** y reportes detallados

## 🛠️ Stack Tecnológico

-   **Contenerización:** Docker & Docker Compose
-   **Base de Datos:** PostgreSQL + PgAdmin
-   **Búsqueda Vectorial:** Qdrant (embeddings)
-   **Caché:** Redis (sesiones, carritos)
-   **API Backend:** FastAPI (Python)
-   **Interacción:** Bot de Telegram con IA
-   **Inteligencia Artificial:** OpenAI API
-   **Exposición Local:** ngrok (para webhooks de Telegram)

## 🎯 Características Principales

-   **🤖 Bot de Telegram Inteligente:** Interfaz conversacional para búsqueda y pedidos
-   **🔍 Búsqueda Semántica:** Encuentra productos usando lenguaje natural
-   **📦 Gestión de Inventario:** Control de stock en tiempo real
-   **🚀 API REST Completa:** Documentación automática con FastAPI
-   **🔐 Seguridad Robusta:** Autenticación y autorización integradas

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

### ✅ **FASE 1.5: Indexación Semántica con IA** - **COMPLETADA**

Se ha desarrollado un script robusto para la indexación de productos en la base de datos vectorial Qdrant, sentando las bases para la búsqueda semántica.

**Funcionalidades Clave:**
- ✅ **Script de Indexación (`scripts/index_qdrant_data.py`):**
  - **Conexión multi-servicio:** PostgreSQL, Redis, Qdrant y OpenAI.
  - **Enriquecimiento con LLM:** Genera descripciones de marketing optimizadas para cada producto usando `gpt-4o-mini-2024-07-18`.
  - **Caché Inteligente:** Utiliza Redis para cachear las descripciones generadas, ahorrando costes y tiempo.
  - **Generación de Embeddings:** Convierte la información del producto en vectores semánticos con `text-embedding-3-small`.
  - **Indexación en Qdrant:** Almacena los productos como puntos vectoriales en la colección `macroferro_products`.
  - **Gestión de Estado:** Solo procesa productos nuevos o modificados desde la última ejecución.
- ✅ **Comando `Makefile` (`make update-catalog`):** Permite ejecutar todo el proceso de indexación con una sola instrucción.
- ✅ **Script de Prueba (`scripts/test_semantic_search.py`):** Permite realizar búsquedas semánticas directas para validar la calidad de los resultados.
- ✅ **Comandos `Makefile` (`make update-catalog`, `make search-test`):** Simplifican la ejecución de la indexación y las pruebas de búsqueda.

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
- [🚧] **Búsqueda semántica** (Qdrant + OpenAI)
  - **Completado:** Lógica de indexación, enriquecimiento y vectorización.
  - **Pendiente:** Endpoint en la API para realizar las búsquedas.
- [✅] **Bot de Telegram** (interfaz conversacional completamente integrada)
- [ ] **Dashboard administrativo** (gestión web)

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
- **OpenAI API Key** para funcionalidades de IA
- **Telegram Bot Token** para el bot
- **PostgreSQL** y **Qdrant** (ya configurados)

### **3. Inicio de servicios**
```bash
make up
```

### **4. Acceso a servicios**
- **API Backend:** http://localhost:8000
- **PgAdmin:** http://localhost:5433
- **Qdrant:** http://localhost:6333

---

## 🎯 **Próximos Pasos**

1. **Sistema de autenticación** (JWT, roles de usuario)
2. **API de inventario** (gestión de stock y almacenes)
3. **API de clientes** (gestión B2B completa)
4. **API de facturación** (órdenes, pagos y reportes)
5. **Dashboard administrativo** (interfaz web de gestión)
6. **Bot de Telegram avanzado** (comandos adicionales y funcionalidades)

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
│     PgAdmin     │    │     Qdrant      │    │    OpenAI      │
│   (Port 5050)   │    │   (Port 6333)   │    │    (IA)        │
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

## 👤 Author and Contact

**David Salas**
- Website: [dasafodata.com](https://dasafodata.com)
- GitHub: [@dasafo](https://github.com/dasafo)
- LinkedIn: [David Salas](https://www.linkedin.com/in/dasafodata/)

<p align="center">
  <sub>Created with ❤️ by David Salas - dasafodata</sub>
</p>