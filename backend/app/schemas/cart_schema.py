# backend/app/schemas/cart_schema.py
"""
Esquemas Pydantic para la gestión del carrito de la compra.
"""

from pydantic import BaseModel
from typing import Dict, Any

class CartItemCreate(BaseModel):
    """Esquema para añadir un item al carrito."""
    product_sku: str
    quantity: int = 1

class Cart(BaseModel):
    """Esquema que representa el estado completo del carrito."""
    items: Dict[str, Any] # La clave es el SKU del producto
    total_price: float 