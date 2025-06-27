"""
Handler del Carrito para el Bot de Telegram.

Este componente encapsula toda la lógica de negocio relacionada con la
interacción del usuario con el carrito de compras. Se encarga de:
- Interpretar y ejecutar acciones de carrito (añadir, quitar, ver, etc.).
- Formatear las respuestas del carrito.
- Interactuar con la API del carrito de compras.
"""
import logging
import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import httpx

from app.core.config import settings
from app.services.context_service import context_service
from app.services.bot_components.product_handler import ProductHandler
from app.crud.conversation_crud import add_recent_product

logger = logging.getLogger(__name__)

class CartHandler:
    """
    Gestiona toda la lógica de negocio relacionada con el carrito de compras.
    """

    def __init__(self, product_handler: ProductHandler):
        """
        Inicializa el handler del carrito.

        Args:
            product_handler: Instancia del handler de productos para resolver referencias.
        """
        self.product_handler = product_handler

    def _get_api_client(self) -> httpx.AsyncClient:
        """Crea un cliente HTTP para comunicarse con la propia API del backend."""
        base_url = f"http://localhost:{settings.PORT}{settings.API_V1_STR}"
        return httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def handle_action(self, db: Session, analysis: Dict, chat_id: int) -> Dict[str, Any]:
        """
        Punto de entrada principal para gestionar una acción de carrito detectada por la IA.
        Delega a métodos específicos según la acción.
        """
        action = analysis.get("cart_action")
        
        # Nota: La acción 'checkout' se inicia desde aquí, pero su flujo de varios pasos
        # se gestiona en telegram_service.py porque está muy ligado al estado de la conversación.
        # En una futura refactorización, esto se movería a su propio CheckoutHandler.
        
        if action == "view":
            return await self.view_cart(db, chat_id)
        elif action == "clear":
            return await self.clear_cart(chat_id)
        elif action == "add":
            return await self.natural_add_to_cart(db, analysis, chat_id)
        elif action == "remove":
            return await self.natural_remove_from_cart(db, analysis, chat_id)
        else:
            logger.warning(f"Acción de carrito desconocida o no manejable: {action}")
            return {"type": "text_messages", "messages": ["🤔 No estoy seguro de qué hacer con el carrito. Puedes probar con 'ver mi carrito', 'agregar [producto]' o 'finalizar compra'."]}

    async def add_item_by_command(self, db: Session, chat_id: int, args: List[str]) -> Dict[str, Any]:
        """Maneja el comando /agregar <SKU> [cantidad]."""
        if not args:
            return {"type": "text_messages", "messages": ["Uso: /agregar <SKU> [cantidad]"]}
        
        sku = args[0]
        try:
            quantity = int(args[1]) if len(args) > 1 else 1
            if quantity <= 0:
                raise ValueError
        except ValueError:
            return {"type": "text_messages", "messages": ["La cantidad debe ser un número positivo."]}

        return await self._add_item_to_cart(db, chat_id, sku, quantity)

    async def natural_add_to_cart(self, db: Session, analysis: Dict, chat_id: int) -> Dict[str, Any]:
        """Maneja añadir al carrito desde lenguaje natural."""
        product_reference = analysis.get("cart_product_reference", "")
        quantity = analysis.get("cart_quantity", 1)
        
        if not product_reference:
            return {"type": "text_messages", "messages": ["🤔 No pude identificar qué producto quieres agregar. ¿Podrías ser más específico?"]}
        
        sku = await self.product_handler._resolve_product_reference(db, product_reference, chat_id, action_context='add')
        
        if not sku:
            return {"type": "text_messages", "messages": [f"🤔 No pude identificar un producto para '{product_reference}'. ¿Podrías ser más específico o usar el SKU?"]}
            
        return await self._add_item_to_cart(db, chat_id, sku, quantity)

    async def _add_item_to_cart(self, db: Session, chat_id: int, sku: str, quantity: int) -> Dict[str, Any]:
        """Lógica central para añadir un item al carrito y devolver la confirmación."""
        try:
            async with self._get_api_client() as client:
                response = await client.post(f"/cart/{chat_id}/items", json={"product_sku": sku, "quantity": quantity})
                
                if response.status_code == 404:
                    return {"type": "text_messages", "messages": [f"😕 No se encontró ningún producto con el SKU: {sku}"]}
                if response.status_code == 409:
                    error_detail = response.json().get("detail", "No hay suficiente stock.")
                    return {"type": "text_messages", "messages": [f"⚠️ ¡Atención! {error_detail}"]}

                response.raise_for_status()
                add_recent_product(db, chat_id, sku)
                
                cart_data = response.json()
                product_name = json.loads(cart_data['items'][sku]['product']).get('name', sku)
                
                message = f"✅ *¡Añadido!* {quantity} x {product_name}" if quantity > 0 else f"➖ *¡Reducido!* Se quitaron {-quantity} x {product_name}"

                return await self._create_cart_confirmation_response(
                    db, chat_id,
                    initial_message=f"{message}\n\n"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error de API al añadir al carrito para chat {chat_id}: {e}")
            return {"type": "text_messages", "messages": ["Lo siento, ocurrió un error al intentar añadir el producto al carrito."]}
        except Exception as e:
            logger.error(f"Error inesperado al añadir al carrito para chat {chat_id}: {e}")
            return {"type": "text_messages", "messages": ["Ocurrió un error inesperado. Por favor, intenta de nuevo."]}

    async def view_cart(self, db: Session, chat_id: int) -> Dict[str, Any]:
        """Maneja la visualización del carrito."""
        try:
            async with self._get_api_client() as client:
                response = await client.get(f"/cart/{chat_id}")
                response.raise_for_status()
                cart_data = response.json()
                
                if not cart_data.get("items"):
                    return {"type": "text_messages", "messages": ["🛒 Tu carrito está vacío."]}
                
                for sku in cart_data.get("items", {}).keys():
                    add_recent_product(db, chat_id, sku)
                
                return await self._create_cart_confirmation_response(db, chat_id)

        except httpx.HTTPError as e:
            logger.error(f"Error de API al ver el carrito para chat {chat_id}: {e}")
            return {"type": "text_messages", "messages": ["Lo siento, ocurrió un error al recuperar tu carrito."]}

    async def remove_item_by_command(self, db: Session, chat_id: int, args: List[str]) -> Dict[str, Any]:
        """Maneja el comando /eliminar <SKU> [cantidad]."""
        if not args:
            return {"type": "text_messages", "messages": ["Uso: /eliminar <SKU> [cantidad]. Si no especificas cantidad, se elimina el producto completo."]}
        
        sku = args[0]
        try:
            quantity_str = args[1] if len(args) > 1 else None
            quantity = int(quantity_str) if quantity_str else None
        except ValueError:
            return {"type": "text_messages", "messages": ["La cantidad debe ser un número."]}

        if quantity and quantity > 0:
            return await self._add_item_to_cart(db, chat_id, sku, -quantity)
        else:
            return await self._remove_item_from_cart(chat_id, sku)

    async def natural_remove_from_cart(self, db: Session, analysis: Dict, chat_id: int) -> Dict[str, Any]:
        """Maneja quitar del carrito desde lenguaje natural."""
        product_reference = analysis.get("cart_product_reference", "")
        quantity_to_remove = analysis.get("cart_quantity")

        if not product_reference:
            return {"type": "text_messages", "messages": ["🤔 No pude identificar qué producto quieres quitar."]}
            
        sku = await self.product_handler._resolve_product_reference(db, product_reference, chat_id, action_context='remove')
        if not sku:
            return {"type": "text_messages", "messages": [f"🤔 No pude identificar '{product_reference}' en tu carrito."]}
        
        if quantity_to_remove:
            return await self._add_item_to_cart(db, chat_id, sku, -int(quantity_to_remove))
        
        return await self._remove_item_from_cart(chat_id, sku)

    async def _remove_item_from_cart(self, chat_id: int, sku: str) -> Dict[str, Any]:
        """Lógica central para quitar un item completo del carrito."""
        try:
            async with self._get_api_client() as client:
                response = await client.delete(f"/cart/{chat_id}/items/{sku}")
                
                if response.status_code == 404:
                    return {"type": "text_messages", "messages": [f"El producto `{sku}` no estaba en tu carrito."]}

                response.raise_for_status()
                
                return {"type": "text_messages", "messages": [f"🗑️ Producto `{sku}` eliminado del carrito."]}

        except httpx.HTTPError as e:
            logger.error(f"Error de API al eliminar del carrito: {e}")
            return {"type": "text_messages", "messages": [f"Lo siento, ocurrió un error al quitar el producto `{sku}`."]}

    async def clear_cart(self, chat_id: int) -> Dict[str, Any]:
        """Maneja el vaciado completo del carrito."""
        try:
            async with self._get_api_client() as client:
                await client.delete(f"/cart/{chat_id}")
                return {"type": "text_messages", "messages": ["✅ Tu carrito ha sido vaciado."]}
        except httpx.HTTPError as e:
            logger.error(f"Error de API al vaciar el carrito: {e}")
            return {"type": "text_messages", "messages": ["Lo siento, ocurrió un error al vaciar tu carrito."]}

    def _format_cart_data(self, cart_data: Dict[str, Any]) -> str:
        """Formatea los datos del carrito para una respuesta clara en Telegram."""
        items = cart_data.get("items", {})
        total_price = cart_data.get("total_price", 0.0)

        response_text = "🛒 *Tu Carrito de Compras*\n\n"
        for sku, item_details in items.items():
            product_info = json.loads(item_details['product'])
            price_str = f"{product_info.get('price', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            subtotal_str = f"{item_details.get('quantity', 0) * product_info.get('price', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            response_text += f"▪️ *{product_info.get('name', sku)}* ({sku})\n"
            response_text += f"    `{item_details.get('quantity', 0)} x {price_str} € = {subtotal_str} €`\n\n"
        
        total_str = f"{total_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        response_text += f"\n*Total: {total_str} €*"
        return response_text

    async def _create_cart_confirmation_response(self, db: Session, chat_id: int, initial_message: str = "") -> Dict[str, Any]:
        """Crea una respuesta estándar post-actualización de carrito, incluyendo sugerencias."""
        try:
            async with self._get_api_client() as client:
                response = await client.get(f"/cart/{chat_id}")
                response.raise_for_status()
                cart_content = self._format_cart_data(response.json())
        except Exception as e:
            logger.error(f"No se pudo obtener el carrito para la confirmación: {e}")
            cart_content = "No pude mostrar tu carrito actualizado."
        
        suggestions = context_service.get_contextual_suggestions(db, chat_id)
        final_message = f"{initial_message}{cart_content}\n\n{suggestions}"
        
        return {"type": "text_messages", "messages": [final_message]} 