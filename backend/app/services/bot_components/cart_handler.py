# backend/app/services/bot_components/cart_handler.py
"""
Handler del Carrito para el Bot de Telegram.

Este componente encapsula toda la lógica de negocio relacionada con la
interacción del usuario con el carrito de compras. Se encarga de:
- Interpretar y ejecutar acciones de carrito (añadir, quitar, ver, etc.).
- Formatear las respuestas del carrito.
"""
import logging
import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.context_service import context_service
from app.services.bot_components.product_handler import ProductHandler
from app.crud.conversation_crud import get_user_context, update_user_context, add_recent_product
from app.crud.product_crud import get_product_by_sku

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

    async def handle_action(self, db: AsyncSession, analysis: Dict, chat_id: int) -> Dict[str, Any]:
        """
        Punto de entrada principal para gestionar una acción de carrito detectada por la IA.
        Delega a métodos específicos según la acción.
        """
        actions = analysis.get("cart_actions")
        if not actions:
            logger.warning("No se encontraron 'cart_actions' en el análisis de la IA.")
            return {"type": "text_messages", "messages": ["🤔 No estoy seguro de qué hacer con el carrito. Puedes probar con 'ver mi carrito', 'agregar [producto]' o 'finalizar compra'."]}

        # Procesamos todas las acciones en secuencia
        final_response = {}
        processed_action = False
        for action_details in actions:
            action = action_details.get("action")
            
            # Nota: La acción 'checkout' se inicia desde aquí, pero su flujo de varios pasos
            # se gestiona en CheckoutHandler.
            # Por simplicidad, asumimos que checkout, view y clear vienen solas.
            if action == "view":
                return await self.view_cart(chat_id, db)
            elif action == "clear":
                return await self.clear_cart(chat_id)
            elif action == "add":
                final_response = await self.natural_add_to_cart(db, action_details, chat_id)
                processed_action = True
            elif action == "remove":
                final_response = await self.natural_remove_from_cart(db, action_details, chat_id)
                processed_action = True
            else:
                logger.warning(f"Acción de carrito desconocida o no manejable: {action}")
                if not processed_action:
                    return {"type": "text_messages", "messages": ["🤔 No estoy seguro de qué hacer con el carrito."]}
        
        # Devolvemos la respuesta de la última acción, que contiene el estado final del carrito
        return final_response

    async def add_item_by_command(self, db: AsyncSession, chat_id: int, args: List[str]) -> Dict[str, Any]:
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

    async def natural_add_to_cart(self, db: AsyncSession, action_details: Dict, chat_id: int) -> Dict[str, Any]:
        """Maneja añadir al carrito desde lenguaje natural."""
        product_reference = action_details.get("product_reference", "")
        quantity = action_details.get("quantity", 1)
        
        if not product_reference:
            return {"type": "text_messages", "messages": ["🤔 No pude identificar qué producto quieres agregar. ¿Podrías ser más específico?"]}
        
        sku = await self.product_handler._resolve_product_reference(product_reference, chat_id)
        
        if not sku:
            return {"type": "text_messages", "messages": [f"🤔 No pude identificar un producto para '{product_reference}'. ¿Podrías ser más específico o usar el SKU?"]}
            
        return await self._add_item_to_cart(db, chat_id, sku, quantity)

    async def _add_item_to_cart(self, db: AsyncSession, chat_id: int, sku: str, quantity: int) -> Dict[str, Any]:
        """Lógica central para añadir un item al carrito y devolver la confirmación."""
        
        product = await get_product_by_sku(db, sku)

        if not product:
            return {"type": "text_messages", "messages": [f"😕 No se encontró ningún producto con el SKU: {sku}."]}

        product_data = product.to_dict()

        # Lógica de carrito directamente en el contexto
        context = await get_user_context(chat_id)
        cart = context.get("cart", {"items": {}, "total_price": 0.0})
        
        current_quantity = cart["items"].get(sku, {}).get("quantity", 0)
        new_quantity = current_quantity + quantity

        if new_quantity > 0:
            cart["items"][sku] = {"quantity": new_quantity, "product": product_data}
        else:
            cart["items"].pop(sku, None) # Eliminar si la cantidad es 0 o menos

        # Recalcular el total
        cart["total_price"] = sum(item["product"]["price"] * item["quantity"] for item in cart["items"].values())

        await update_user_context(chat_id, {"cart": cart})
        await add_recent_product(chat_id, product_data)

        product_name = product_data.get('name', sku)
        message = f"✅ *¡Añadido!* {quantity} x {product_name}" if quantity > 0 else f"➖ *¡Reducido!* Se quitaron {-quantity} x {product_name}"
        
        return await self._create_cart_confirmation_response(chat_id, db, initial_message=f"{message}\n\n")

    async def view_cart(self, chat_id: int, db: AsyncSession = None) -> Dict[str, Any]:
        """Maneja la visualización del carrito."""
        context = await get_user_context(chat_id)
        cart = context.get("cart", {})
        
        if not cart.get("items"):
            return {"type": "text_messages", "messages": ["🛒 Tu carrito está vacío."]}
        
        if db is None:
            # Si no hay db, crear respuesta simple sin sugerencias
            cart_content = self._format_cart_data(cart)
            return {"type": "text_messages", "messages": [cart_content]}
        
        return await self._create_cart_confirmation_response(chat_id, db)

    async def remove_item_by_command(self, db: AsyncSession, chat_id: int, args: List[str]) -> Dict[str, Any]:
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

    async def natural_remove_from_cart(self, db: AsyncSession, action_details: Dict, chat_id: int) -> Dict[str, Any]:
        """Maneja quitar del carrito desde lenguaje natural."""
        product_reference = action_details.get("product_reference", "")
        quantity_to_remove = action_details.get("quantity")
        
        logger.info(f"natural_remove_from_cart - product_reference: '{product_reference}', quantity: {quantity_to_remove}, type: {type(quantity_to_remove)}")

        if not product_reference:
            return {"type": "text_messages", "messages": ["🤔 No pude identificar qué producto quieres quitar."]}
        
        # Primero buscar específicamente en el carrito
        context = await get_user_context(chat_id)
        cart = context.get("cart", {})
        items = cart.get("items", {})
        
        if not items:
            return {"type": "text_messages", "messages": ["🛒 Tu carrito está vacío."]}
        
        # Buscar el producto en el carrito por referencia
        sku = await self._resolve_product_reference_in_cart(product_reference, items)
        
        # Si no se encuentra en el carrito, usar la resolución general
        if not sku:
            sku = await self.product_handler._resolve_product_reference(product_reference, chat_id)
            
        if not sku:
            return {"type": "text_messages", "messages": [f"🤔 No pude identificar '{product_reference}' en tu carrito."]}
        
        logger.info(f"Producto resuelto: SKU {sku}")
        
        # Verificar que el producto está en el carrito
        if sku not in items:
            return {"type": "text_messages", "messages": [f"🤔 El producto no está en tu carrito actualmente."]}
        
        current_quantity = items[sku].get("quantity", 0)
        logger.info(f"Cantidad actual en carrito para {sku}: {current_quantity}")
        
        if quantity_to_remove is not None:
            try:
                quantity_to_remove = int(quantity_to_remove)
                logger.info(f"Intentando quitar {quantity_to_remove} unidades de {sku}")
                
                if quantity_to_remove <= 0:
                    return {"type": "text_messages", "messages": ["❌ La cantidad a quitar debe ser mayor que cero."]}
                
                if quantity_to_remove > current_quantity:
                    return {"type": "text_messages", "messages": [f"❌ No puedes quitar {quantity_to_remove} unidades. Solo tienes {current_quantity} en el carrito."]}
                
                return await self._add_item_to_cart(db, chat_id, sku, -quantity_to_remove)
            except (ValueError, TypeError) as e:
                logger.error(f"Error convirtiendo quantity_to_remove a int: {e}")
                return {"type": "text_messages", "messages": ["❌ La cantidad especificada no es válida."]}
        
        # Si no se especifica cantidad, eliminar todo el producto
        logger.info(f"No se especificó cantidad, eliminando todo el producto {sku}")
        return await self._remove_item_from_cart(chat_id, sku)

    async def _resolve_product_reference_in_cart(self, reference: str, cart_items: Dict) -> str:
        """Resuelve una referencia de producto específicamente en los items del carrito."""
        reference = reference.lower()
        reference_words = reference.split()
        
        best_match = None
        best_score = 0
        
        for sku, item_data in cart_items.items():
            product = item_data.get("product", {})
            product_name = product.get('name', '').lower()
            product_brand = product.get('brand', '').lower()
            
            # Búsqueda exacta por SKU
            if reference == sku.lower():
                logger.info(f"Referencia '{reference}' resuelta por SKU exacto en carrito: {sku}")
                return sku
            
            # Búsqueda de coincidencia completa en nombre
            if reference in product_name:
                logger.info(f"Referencia '{reference}' resuelta por coincidencia completa en carrito: {sku}")
                return sku
            
            # Calcular score de coincidencia
            score = 0
            for word in reference_words:
                if word in product_name:
                    score += 2
                elif word in product_brand:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = sku
        
        # Si encontramos una buena coincidencia parcial
        if best_match and best_score >= len(reference_words):
            logger.info(f"Referencia '{reference}' resuelta por coincidencia parcial en carrito (score: {best_score}): {best_match}")
            return best_match
            
        return None

    async def _remove_item_from_cart(self, chat_id: int, sku: str) -> Dict[str, Any]:
        """Lógica central para quitar un item completo del carrito."""
        context = await get_user_context(chat_id)
        cart = context.get("cart", {})
        
        if sku not in cart.get("items", {}):
            return {"type": "text_messages", "messages": [f"El producto `{sku}` no estaba en tu carrito."]}

        # Eliminar el producto y recalcular el total
        cart["items"].pop(sku, None)
        cart["total_price"] = sum(item["product"]["price"] * item["quantity"] for item in cart["items"].values())

        await update_user_context(chat_id, {"cart": cart})
        
        return {"type": "text_messages", "messages": [f"🗑️ Producto `{sku}` eliminado del carrito."]}

    async def clear_cart(self, chat_id: int) -> Dict[str, Any]:
        """Maneja el vaciado completo del carrito."""
        await update_user_context(chat_id, {"cart": {"items": {}, "total_price": 0.0}})
        return {"type": "text_messages", "messages": ["✅ Tu carrito ha sido vaciado."]}

    def _format_cart_data(self, cart_data: Dict[str, Any]) -> str:
        """Formatea los datos del carrito para una respuesta clara en Telegram."""
        items = cart_data.get("items", {})
        total_price = cart_data.get("total_price", 0.0)

        response_text = "🛒 *Tu Carrito de Compras*\n\n"
        for sku, item_details in items.items():
            product_info = item_details['product']
            price_str = f"{product_info.get('price', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            subtotal_str = f"{item_details.get('quantity', 0) * product_info.get('price', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            response_text += f"▪️ *{product_info.get('name', sku)}* ({sku})\n"
            response_text += f"    `{item_details.get('quantity', 0)} x {price_str} € = {subtotal_str} €`\n\n"
        
        total_str = f"{total_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        response_text += f"\n*Total: {total_str} €*"
        return response_text

    async def _create_cart_confirmation_response(self, chat_id: int, db: AsyncSession, initial_message: str = "") -> Dict[str, Any]:
        """Crea una respuesta estándar post-actualización de carrito, incluyendo sugerencias."""
        context = await get_user_context(chat_id)
        cart_content = self._format_cart_data(context.get("cart", {}))
        
        suggestions = await context_service.get_contextual_suggestions(chat_id, db)
        final_message = f"{initial_message}{cart_content}\n\n{suggestions}"
        
        return {"type": "text_messages", "messages": [final_message]} 