# backend/app/services/cart_service.py
"""
Servicio de Carrito de Compras para la aplicación.

Este servicio se encarga de gestionar el carrito de compras de un usuario en memoria.
"""
import json
from typing import Dict, Optional

import redis.asyncio as redis
from app.core.config import Settings
from app.schemas.product_schema import ProductResponse as ProductSchema

# Usaremos un diccionario en memoria para simular la base de datos de carritos.
# En un entorno de producción real, se usaría una base de datos como Redis o PostgreSQL.
_carts: Dict[str, Dict[str, Dict]] = {}

class CartService:
    """
    Servicio para gestionar el carrito de compras de un usuario en memoria.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        # No se necesita cliente Redis en esta implementación
    
    def _get_cart_key(self, chat_id: str) -> str:
        """Genera la clave para un carrito de usuario (solo por consistencia de nombres)."""
        return str(chat_id)

    async def add_product_to_cart(self, chat_id: str, product: ProductSchema, quantity: int = 1):
        """
        Añade un producto al carrito de un usuario.
        Si el producto ya existe, actualiza la cantidad.
        """
        cart_key = self._get_cart_key(chat_id)
        product_sku = str(product.sku)

        if cart_key not in _carts:
            _carts[cart_key] = {}

        current_cart = _carts[cart_key]
        
        if product_sku in current_cart:
            current_item = current_cart[product_sku]
            new_quantity = current_item['quantity'] + quantity
        else:
            if quantity <= 0:
                return
            new_quantity = quantity

        if new_quantity < 0:
            raise ValueError(f"No puedes eliminar más unidades de las que tienes. Tienes {current_cart.get(product_sku, {}).get('quantity', 0)} en el carrito.")

        if new_quantity == 0:
            await self.remove_product_from_cart(chat_id, product_sku)
            return

        product_data = {
            "quantity": new_quantity,
            "product": product.model_dump() # Usamos model_dump para Pydantic v2
        }
        
        current_cart[product_sku] = product_data

    async def get_cart_contents(self, chat_id: str) -> Dict[str, Dict]:
        """
        Obtiene todos los productos y sus cantidades del carrito de un usuario.
        """
        cart_key = self._get_cart_key(chat_id)
        return _carts.get(cart_key, {})

    async def remove_product_from_cart(self, chat_id: str, product_sku: str) -> Optional[int]:
        """
        Elimina un producto del carrito de un usuario.
        """
        cart_key = self._get_cart_key(chat_id)
        if cart_key in _carts and product_sku in _carts[cart_key]:
            del _carts[cart_key][product_sku]
            return 1
        return 0

    async def clear_cart(self, chat_id: str):
        """
        Vacía completamente el carrito de un usuario.
        """
        cart_key = self._get_cart_key(chat_id)
        if cart_key in _carts:
            _carts[cart_key] = {}

    async def get_cart_total_price(self, chat_id: str) -> float:
        """
        Calcula el precio total de todos los productos en el carrito.
        """
        cart_contents = await self.get_cart_contents(chat_id)
        total_price = 0.0

        for sku, data in cart_contents.items():
            product_info = data['product'] # Ya no es un JSON, es un dict
            price = product_info.get('price', 0)
            quantity = data.get('quantity', 0)
            total_price += price * quantity
            
        return total_price 