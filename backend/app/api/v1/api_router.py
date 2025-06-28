# backend/app/api/v1/api_router.py
"""
Este archivo contiene el router principal para la API versión 1.

Se encarga de registrar y configurar todos los routers de la versión 1 de la API.
"""

from fastapi import APIRouter

# Importación de routers especializados por dominio de negocio
from app.api.v1.endpoints import (
    products, 
    categories,
    telegram,
    cart
)

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
    products.router,                
    prefix="/products",             
    tags=["Products"]               
)

# ROUTER DE TELEGRAM BOT
# Maneja webhook y operaciones del bot de Telegram
api_router_v1.include_router(
    telegram.router,                
    prefix="/telegram",             
    tags=["Telegram Bot"]        
)

# ROUTER DEL CARRITO
# Maneja las operaciones del carrito de compras
api_router_v1.include_router(
    cart.router,
    prefix="/cart",
    tags=["Cart"]
)