# backend/app/api/v1/api_router.py

"""
Router principal para la API versión 1.

Este módulo actúa como el punto central de composición para todos los
routers de endpoints de la API v1, organizando las rutas por dominio
de negocio y configurando metadatos comunes para la documentación.

Responsabilidades del router principal:
- Composición modular de routers de diferentes dominios
- Configuración de prefijos y tags para organización
- Preparación para versionado de API (v1, v2, etc.)
- Centralización de configuración común de routing
- Organización jerárquica de endpoints por funcionalidad

Arquitectura de routing implementada:
- Modular Composition: Cada dominio tiene su propio router
- Domain-Driven Organization: Agrupación por contexto de negocio
- Hierarchical Routing: Prefijos anidados para organización clara
- Tag-Based Documentation: Agrupación lógica en documentación
- Versioned API: Preparado para múltiples versiones

Patrones de organización:
- Aggregator Pattern: Combina múltiples routers especializados
- Namespace Pattern: Organización clara por dominio y funcionalidad
- Configuration Centralization: Metadatos comunes en un lugar
- Separation of Concerns: Cada router maneja su dominio específico

Estructura de URLs resultante:
- /api/v1/categories/* → Gestión de categorías
- /api/v1/products/*   → Gestión de productos
- /api/v1/.../*        → Futuras extensiones por dominio
"""

from fastapi import APIRouter

# Importación de routers especializados por dominio de negocio
from app.api.v1.endpoints import products, categories, telegram  # Routers de endpoints específicos

# ========================================
# CONFIGURACIÓN DEL ROUTER PRINCIPAL V1
# ========================================

# Crear router principal para la versión 1 de la API
# Este router actuará como contenedor para todos los sub-routers de la v1
api_router_v1 = APIRouter()

# ========================================
# REGISTRO DE ROUTERS POR DOMINIO DE NEGOCIO
# ========================================

# ROUTER DE CATEGORÍAS
# Maneja operaciones CRUD para el catálogo de categorías jerárquicas
api_router_v1.include_router(
    categories.router,              # Router con endpoints de categorías
    prefix="/categories",           # Prefijo: /api/v1/categories
    tags=["Categories"]             # Tag para documentación OpenAPI/Swagger
)

# ROUTER DE PRODUCTOS
# Maneja operaciones CRUD para el catálogo de productos con filtros avanzados
api_router_v1.include_router(
    products.router,                # Router con endpoints de productos
    prefix="/products",             # Prefijo: /api/v1/products
    tags=["Products"]               # Tag para documentación OpenAPI/Swagger
)

# ROUTER DE TELEGRAM BOT
# Maneja webhook y operaciones del bot de Telegram
api_router_v1.include_router(
    telegram.router,                # Router con endpoints de Telegram
    prefix="/telegram",             # Prefijo: /api/v1/telegram
    tags=["Telegram Bot"]           # Tag para documentación OpenAPI/Swagger
)

# ========================================
# ROUTERS FUTUROS - PREPARACIÓN PARA EXTENSIÓN
# ========================================

# Los siguientes routers se agregarán a medida que se desarrollen
# más módulos del sistema de gestión de Macroferro:

# GESTIÓN DE INVENTARIO
# api_router_v1.include_router(
#     stock.router,
#     prefix="/stock",
#     tags=["Stock", "Inventory"]
# )

# SISTEMA DE FACTURACIÓN
# api_router_v1.include_router(
#     invoices.router,
#     prefix="/invoices",
#     tags=["Invoices", "Billing"]
# )

# GESTIÓN DE IMÁGENES
# api_router_v1.include_router(
#     images.router,
#     prefix="/images",
#     tags=["Images", "Media"]
# )

# CARRITO DE COMPRAS (si se implementa funcionalidad e-commerce)
# api_router_v1.include_router(
#     cart.router,
#     prefix="/cart",
#     tags=["Cart", "Shopping"]
# )

# ÓRDENES Y PEDIDOS
# api_router_v1.include_router(
#     orders.router,
#     prefix="/orders",
#     tags=["Orders", "Sales"]
# )

# GESTIÓN DE USUARIOS Y AUTENTICACIÓN
# api_router_v1.include_router(
#     auth.router,
#     prefix="/auth",
#     tags=["Authentication", "Users"]
# )

# PANEL ADMINISTRATIVO
# api_router_v1.include_router(
#     admin.router,
#     prefix="/admin",
#     tags=["Administration", "Management"]
# )

# REPORTES Y ANALYTICS
# api_router_v1.include_router(
#     reports.router,
#     prefix="/reports",
#     tags=["Reports", "Analytics"]
# )

# CONFIGURACIÓN DEL SISTEMA
# api_router_v1.include_router(
#     config.router,
#     prefix="/config",
#     tags=["Configuration", "Settings"]
# )

# ========================================
# CONFIGURACIÓN DE METADATOS Y DOCUMENTACIÓN
# ========================================

# Configuración adicional para documentación automática:
# - Los tags agrupan endpoints en la documentación Swagger
# - Los prefijos organizan las URLs de manera jerárquica
# - Cada router mantiene su propia documentación detallada

# Beneficios de esta organización:
# 1. **Modularidad**: Cada dominio se desarrolla independientemente
# 2. **Escalabilidad**: Fácil agregar nuevos módulos sin afectar existentes
# 3. **Mantenibilidad**: Separación clara de responsabilidades
# 4. **Documentación**: Agrupación lógica en Swagger UI
# 5. **Testing**: Posibilidad de testear cada router independientemente
# 6. **Versionado**: Preparado para múltiples versiones de API

# ========================================
# VERSIONADO DE API - ESTRATEGIA FUTURA
# ========================================

# Esta estructura permite manejar versiones de API de manera elegante:
# 
# api_router_v2 = APIRouter()  # Para futura versión 2
# api_router_v2.include_router(products_v2.router, prefix="/products", tags=["Products V2"])
# 
# Esto permitiría:
# - /api/v1/products → Versión estable actual
# - /api/v2/products → Nueva versión con cambios breaking
# - Migración gradual entre versiones
# - Soporte simultáneo de múltiples versiones