import json
from typing import Dict, Optional

import redis.asyncio as redis
from app.core.config import Settings
from app.schemas.product_schema import ProductResponse as ProductSchema

class CartService:
    """
    Servicio para gestionar el carrito de compras de un usuario en Redis.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self._redis_client = None
        self.cart_prefix = "cart:"

    async def _get_redis_client(self):
        """Obtiene o crea la conexión Redis de forma lazy."""
        if self._redis_client is None:
            self._redis_client = redis.Redis.from_url(
                f"redis://{self.settings.REDIS_HOST}",
                decode_responses=True  # Decodificar respuestas a UTF-8
            )
        return self._redis_client

    def _get_cart_key(self, chat_id: str) -> str:
        """Genera la clave de Redis para un carrito de usuario."""
        return f"{self.cart_prefix}{chat_id}"

    async def add_product_to_cart(self, chat_id: str, product: ProductSchema, quantity: int = 1):
        """
        Añade un producto al carrito de un usuario.
        Si el producto ya existe, actualiza la cantidad.
        """
        redis_client = await self._get_redis_client()
        cart_key = self._get_cart_key(chat_id)
        product_sku = str(product.sku)

        # Usamos un hash de Redis. Cada SKU es un campo en el hash.
        # El valor es un JSON con cantidad y los detalles del producto.
        
        current_item_json = await redis_client.hget(cart_key, product_sku)
        
        if current_item_json:
            current_item = json.loads(current_item_json)
            new_quantity = current_item['quantity'] + quantity
        else:
            # Si el item es nuevo, y la cantidad es negativa o cero, no hacemos nada
            if quantity <= 0:
                return
            new_quantity = quantity

        # Validación para no permitir cantidades negativas
        if new_quantity < 0:
            raise ValueError(f"No puedes eliminar más unidades de las que tienes. Tienes {current_item['quantity']} en el carrito.")

        # Si la nueva cantidad es cero, eliminamos el producto del carrito
        if new_quantity == 0:
            await self.remove_product_from_cart(chat_id, product_sku)
            return

        product_data = {
            "quantity": new_quantity,
            "product": product.model_dump_json() # Usar model_dump_json para Pydantic v2
        }
        
        await redis_client.hset(cart_key, product_sku, json.dumps(product_data))

    async def get_cart_contents(self, chat_id: str) -> Dict[str, Dict]:
        """
        Obtiene todos los productos y sus cantidades del carrito de un usuario.
        """
        redis_client = await self._get_redis_client()
        cart_key = self._get_cart_key(chat_id)
        cart_items = await redis_client.hgetall(cart_key)
        
        # Deserializar los datos de cada producto
        return {sku: json.loads(data) for sku, data in cart_items.items()}

    async def remove_product_from_cart(self, chat_id: str, product_sku: str) -> Optional[int]:
        """
        Elimina un producto del carrito de un usuario.
        """
        redis_client = await self._get_redis_client()
        cart_key = self._get_cart_key(chat_id)
        return await redis_client.hdel(cart_key, product_sku)

    async def clear_cart(self, chat_id: str):
        """
        Vacía completamente el carrito de un usuario.
        """
        redis_client = await self._get_redis_client()
        cart_key = self._get_cart_key(chat_id)
        await redis_client.delete(cart_key)

    async def get_cart_total_price(self, chat_id: str) -> float:
        """
        Calcula el precio total de todos los productos en el carrito.
        """
        cart_contents = await self.get_cart_contents(chat_id)
        total_price = 0.0

        for sku, data in cart_contents.items():
            product_info = json.loads(data['product'])
            price = product_info.get('price', 0)
            quantity = data.get('quantity', 0)
            total_price += price * quantity
            
        return total_price 