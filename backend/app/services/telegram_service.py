"""
Capa de servicios para operaciones de negocio del Bot de Telegram.

Esta capa implementa el patrón Service Layer para la integración con Telegram Bot API,
proporcionando una abstracción de alto nivel que orquesta la comunicación bidireccional
con usuarios de Telegram, procesamiento inteligente de mensajes con IA, y búsqueda
avanzada de productos en el catálogo de Macroferro.
"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, List, Tuple
import httpx
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import re
from fastapi import BackgroundTasks

from app.core.config import settings
from app.services.product_service import ProductService
from app.services.email_service import send_invoice_email
from app.services.context_service import context_service
from app.services.bot_components.ai_analyzer import AIAnalyzer
from app.services.bot_components.product_handler import ProductHandler
from app.crud.client_crud import get_client_by_email, create_client
from app.crud import order_crud
from app.schemas import order_schema
from app.api.deps import get_db
from app.crud.conversation_crud import (
    get_recent_products,
    add_recent_product,
    add_recent_intent,
    set_pending_action,
    clear_pending_action,
    get_pending_action,
    add_turn_to_history,
    get_conversation_history
)
from app.crud.product_crud import get_product_by_sku
from app.db.models.client_model import Client
from app.db.models.order_model import Order

logger = logging.getLogger(__name__)


class TelegramBotService:
    """
    Servicio que orquesta las operaciones del Bot de Telegram.
    Encapsula la lógica de negocio, delega tareas a componentes especializados
    (AI, Productos, Carrito) y gestiona la comunicación con la API de Telegram.
    """

    def __init__(self):
        """
        Inicializa el servicio, configurando el cliente de OpenAI y los handlers.
        """
        self.openai_client = None
        if settings.telegram_bot_token:
            self.api_base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
            logger.info("API de Telegram configurada.")
            if settings.OPENAI_API_KEY:
                self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("Cliente OpenAI configurado.")
            else:
                logger.warning("OpenAI API key no configurada.")
        else:
            self.api_base_url = None
            logger.warning("Telegram bot token no configurado.")

        # Inicializar servicios y handlers
        self.product_service = ProductService()
        self.ai_analyzer = AIAnalyzer(self.openai_client)
        self.product_handler = ProductHandler(self.product_service, self.openai_client)
        logger.info("Servicios y Handlers inicializados.")

    # ========================================
    # PROCESAMIENTO PRINCIPAL DE MENSAJES
    # ========================================

    async def process_message(self, db: Session, message_data: Dict[str, Any], background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """
        Procesa un mensaje entrante, orquestando análisis de IA y respuestas.
        """
        if 'callback_query' in message_data:
            # Lógica para manejar callbacks de botones (si se implementan)
            return await self._handle_callback_query(db, message_data['callback_query'])

        message = message_data.get('message') or message_data.get('edited_message')
        if not message:
            return {"status": "ignored", "reason": "unhandled_update_type"}

        message_text = message.get("text", "")
        chat_id = message["chat"]["id"]
        
        response_dict = {}
        
        try:
            # 1. Flujo de acciones pendientes (ej. checkout)
            pending_action_info = get_pending_action(db, chat_id)
            if pending_action_info:
                current_action = pending_action_info.get("action")
                action_data = pending_action_info.get("data", {})
                if current_action and current_action.startswith("checkout"):
                    # No interrumpir el checkout por preguntas normales
                    if not self._is_interrupting_message(message_text):
                        response_dict = await self._process_checkout_data_collection(
                            db, chat_id, message_text, current_action, action_data, background_tasks
                        )

            if not response_dict:
                # 2. Manejo de comandos y análisis de IA
                if message_text.startswith('/'):
                    response_dict = await self._handle_command(db, chat_id, message_text, message_data)
                else:
                    response_dict = await self._handle_natural_language(db, chat_id, message_text, message_data)
            
            # 4. Guardar turno y retornar
            bot_response_text = ""
            if response_dict and response_dict.get("type"):
                if response_dict.get("type") == "text_messages":
                    bot_response_text = "\n".join(response_dict.get("messages", []))
                elif response_dict.get("type") == "product_with_image":
                    caption = response_dict.get("caption", "")
                    additional = "\n".join(response_dict.get("additional_messages", []))
                    bot_response_text = f"{caption}\n{additional}".strip()
            
            if bot_response_text:
                add_turn_to_history(db, chat_id, message_text, bot_response_text)

            return response_dict
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout procesando mensaje de chat {chat_id}")
            return self._create_error_response(db, chat_id, message_text, "⏱️ Lo siento, el procesamiento está tomando más tiempo del esperado. Por favor intenta nuevamente.")
            
        except Exception as e:
            logger.exception(f"Error fatal procesando mensaje de chat {chat_id}")
            return self._create_error_response(db, chat_id, message_text, "❌ Lo siento, hubo un error grave procesando tu mensaje. Nuestro equipo ha sido notificado.")

    def _create_error_response(self, db: Session, chat_id: int, user_message: str, error_text: str) -> Dict[str, Any]:
        """Crea una respuesta de error estándar y la registra en el historial."""
        response_dict = {"type": "text_messages", "messages": [error_text]}
        add_turn_to_history(db, chat_id, user_message, error_text)
        return response_dict
        
    async def _handle_command(self, db: Session, chat_id: int, message_text: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maneja los comandos que empiezan con '/'."""
        parts = message_text.split()
        command = parts[0]
        args = parts[1:]
        
        if command == '/start' or command == '/help':
            return self.get_help_message()
        elif command == '/agregar':
            return await self._handle_add_to_cart_command(db, chat_id, args)
        elif command == '/ver_carrito':
            return await self._handle_view_cart(db, chat_id)
        elif command == '/eliminar':
            return await self._handle_remove_from_cart_command(chat_id, args)
        elif command == '/vaciar_carrito':
            return await self._handle_clear_cart(chat_id)
        elif command == '/finalizar_compra':
            return await self._handle_checkout(db, chat_id)
        else:
            return {"type": "text_messages", "messages": [f"😕 No reconozco el comando '{command}'. Escribe /help para ver la lista de comandos disponibles."]}

    async def _handle_natural_language(self, db: Session, chat_id: int, message_text: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maneja mensajes en lenguaje natural usando IA."""
        logger.info(f"Analizando mensaje de chat {chat_id}: '{message_text}'")
        
        history = get_conversation_history(db, chat_id, limit_turns=5)
        analysis = await self.ai_analyzer.analyze_user_intent(message_text, history=history)
        
        intent_type = analysis.get("intent_type", "general_conversation")
        confidence = analysis.get("confidence", 0.5)
        
        add_recent_intent(db, chat_id, intent_type, confidence)
        
        # Delegar a los handlers correspondientes
        if intent_type in ["product_details", "product_search", "technical_question", "catalog_inquiry"]:
            return await self.product_handler.handle_intent(db, intent_type, analysis, message_text, chat_id)
        elif intent_type == "cart_action":
            return await self._handle_cart_action(db, analysis, chat_id)
        else: # general_conversation
            is_simple_greeting = any(g in message_text.lower() for g in ['hola', 'gracias', 'buenos', 'buenas', 'ok', 'vale', 'adios'])
            if intent_type == "general_conversation" and not is_simple_greeting and confidence > 0.6:
                return {
                    "type": "text_messages",
                    "messages": [
                        "🤔 Entendido, pero tu consulta es un poco general.",
                        "Para poder ayudarte mejor, ¿podrías ser más específico? Por ejemplo, puedes decirme el tipo de producto que buscas (ej: 'tubos de acero') o la marca."
                    ]
                }
            return await self._handle_conversational_response(message_text)
            
    # ========================================
    # HANDLERS DE CARRITO Y CHECKOUT
    # ========================================

    async def _handle_cart_action(self, db: Session, analysis: Dict, chat_id: int) -> Dict[str, Any]:
        """Router para acciones de carrito detectadas por IA."""
        action = analysis.get("cart_action")
        
        if action == "view":
            return await self._handle_view_cart(db, chat_id)
        elif action == "clear":
            return await self._handle_clear_cart(chat_id)
        elif action == "checkout":
            return await self._handle_checkout(db, chat_id)
        elif action == "add":
            return await self._handle_natural_add_to_cart(db, analysis, chat_id)
        elif action == "remove":
            return await self._handle_natural_remove_from_cart(db, analysis, chat_id)
        else:
            return {"type": "text_messages", "messages": ["🤔 No estoy seguro de qué hacer con el carrito. Puedes probar con 'ver mi carrito', 'agregar [producto]' o 'finalizar compra'."]}

    async def _handle_add_to_cart_command(self, db: Session, chat_id: int, args: List[str]) -> Dict[str, Any]:
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

    async def _handle_natural_add_to_cart(self, db: Session, analysis: Dict, chat_id: int) -> Dict[str, Any]:
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

                return await self._create_cart_confirmation_response(
                    db, chat_id,
                    initial_message=f"✅ *¡Añadido!* {quantity} x {product_name}\n\n"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error de API al añadir al carrito para chat {chat_id}: {e}")
            return {"type": "text_messages", "messages": ["Lo siento, ocurrió un error al intentar añadir el producto al carrito."]}
        except Exception as e:
            logger.error(f"Error inesperado al añadir al carrito para chat {chat_id}: {e}")
            return {"type": "text_messages", "messages": ["Ocurrió un error inesperado. Por favor, intenta de nuevo."]}

    async def _handle_view_cart(self, db: Session, chat_id: int) -> Dict[str, Any]:
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

    async def _handle_remove_from_cart_command(self, chat_id: int, args: List[str]) -> Dict[str, Any]:
        """Maneja el comando /eliminar <SKU>."""
        if not args:
            return {"type": "text_messages", "messages": ["Uso: /eliminar <SKU> [cantidad]. Si no especificas cantidad, se elimina el producto completo."]}
        
        sku = args[0]
        try:
            quantity = int(args[1]) if len(args) > 1 else None
        except ValueError:
            return {"type": "text_messages", "messages": ["La cantidad debe ser un número."]}

        # Si se especifica cantidad, se reduce. Si no, se elimina.
        if quantity:
            return await self._add_item_to_cart(db, chat_id, sku, -quantity)
        else:
            return await self._remove_item_from_cart(chat_id, sku)

    async def _handle_natural_remove_from_cart(self, db: Session, analysis: Dict, chat_id: int) -> Dict[str, Any]:
        """Maneja quitar del carrito desde lenguaje natural."""
        product_reference = analysis.get("cart_product_reference", "")
        quantity_to_remove = analysis.get("cart_quantity")

        if not product_reference:
            return {"type": "text_messages", "messages": ["🤔 No pude identificar qué producto quieres quitar."]}
            
        sku = await self.product_handler._resolve_product_reference(db, product_reference, chat_id, action_context='remove')
        if not sku:
            return {"type": "text_messages", "messages": [f"🤔 No pude identificar '{product_reference}' en tu carrito."]}
        
        # Si la IA detectó una cantidad (ej: "quita uno..."), la usamos para reducir.
        if quantity_to_remove:
            return await self._add_item_to_cart(db, chat_id, sku, -int(quantity_to_remove))
        
        # Si no, se elimina el producto completo.
        return await self._remove_item_from_cart(chat_id, sku)

    async def _remove_item_from_cart(self, chat_id: int, sku: str) -> Dict[str, Any]:
        """Lógica central para quitar un item del carrito."""
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

    async def _handle_clear_cart(self, chat_id: int) -> Dict[str, Any]:
        """Maneja el vaciado completo del carrito."""
        try:
            async with self._get_api_client() as client:
                await client.delete(f"/cart/{chat_id}")
                return {"type": "text_messages", "messages": ["✅ Tu carrito ha sido vaciado."]}
        except httpx.HTTPError as e:
            logger.error(f"Error de API al vaciar el carrito: {e}")
            return {"type": "text_messages", "messages": ["Lo siento, ocurrió un error al vaciar tu carrito."]}

    async def _handle_checkout(self, db: Session, chat_id: int) -> Dict[str, Any]:
        """Inicia el flujo de checkout."""
        try:
            async with self._get_api_client() as client:
                get_response = await client.get(f"/cart/{chat_id}")
                get_response.raise_for_status()
                cart_data = get_response.json()
                if not cart_data.get("items"):
                    return {"type": "text_messages", "messages": ["🛒 Tu carrito está vacío."]}

                cart_summary = self._format_cart_data(cart_data)
                clear_pending_action(db, chat_id)
                set_pending_action(db, chat_id, "checkout_ask_if_recurrent", {})
                
                return {
                    "type": "text_messages",
                    "messages": [
                        f"✅ *Proceso de Compra Iniciado*\n\n{cart_summary}",
                        "👋 Antes de continuar, ¿ya eres cliente nuestro? (responde *sí* o *no*)"
                    ]
                }
        except httpx.HTTPError as e:
            logger.error(f"Error de API en checkout para chat {chat_id}: {e}")
            return {"type": "text_messages", "messages": ["❌ Lo siento, ocurrió un error al procesar tu pedido."]}

    # ========================================
    # FLUJO DE RECOLECCIÓN DE DATOS (CHECKOUT)
    # ========================================

    def _is_interrupting_message(self, text: str) -> bool:
        """Heurística para detectar si un mensaje es una nueva pregunta que interrumpe un flujo."""
        text_lower = text.strip().lower()
        if text_lower.startswith('/') or '?' in text:
            return True
        question_words = ['qué', 'cual', 'cuál', 'cómo', 'donde', 'dónde', 'quien', 'quién', 'cuánto', 'cuando', 'por qué']
        if text_lower.split() and text_lower.split()[0] in question_words:
            return True
        return False

    async def _process_checkout_data_collection(self, db: Session, chat_id: int, message_text: str, current_action: str, action_data: Dict[str, Any], background_tasks: BackgroundTasks) -> Optional[Dict[str, Any]]:
        """Procesa la recolección de datos del cliente paso a paso."""
        user_response = message_text.strip().lower()

        if current_action == "checkout_ask_if_recurrent":
            if 'sí' in user_response or 'si' in user_response:
                set_pending_action(db, chat_id, "checkout_get_recurrent_email", {})
                return {"type": "text_messages", "messages": ["¡Genial! Por favor, envíame tu *correo electrónico* para buscar tus datos."]}
            elif 'no' in user_response:
                set_pending_action(db, chat_id, "checkout_collect_name", {})
                return {"type": "text_messages", "messages": ["Entendido. Comencemos con el registro.\n\n👤 Por favor, envíame tu *nombre completo*:"]}
            else:
                return {"type": "text_messages", "messages": ["🤔 No entendí tu respuesta. Por favor, responde solo *sí* o *no*."]}

        elif current_action == "checkout_get_recurrent_email":
            email = user_response
            client = get_client_by_email(db, email)
            if client:
                action_data = {"name": client.name, "email": client.email, "phone": client.phone, "address": client.address}
                set_pending_action(db, chat_id, "checkout_confirm_recurrent_data", action_data)
                return {"type": "text_messages", "messages": [f"¡Hola de nuevo, *{client.name}*! 👋\n\nHe encontrado estos datos:\n📞 Teléfono: *{client.phone}*\n🏠 Dirección: *{client.address}*\n\n¿Son correctos para el envío? (*sí* o *no*)"]}
            else:
                set_pending_action(db, chat_id, "checkout_collect_name", {"email": email})
                return {"type": "text_messages", "messages": ["No encontré tus datos. Vamos a registrarlos.\n\n👤 Para empezar, ¿cuál es tu *nombre completo*?"]}

        elif current_action == "checkout_confirm_recurrent_data":
            if 'sí' in user_response or 'si' in user_response:
                return await self._finalize_checkout_with_customer_data(db, chat_id, action_data, background_tasks)
            else:
                set_pending_action(db, chat_id, "checkout_collect_name", {"email": action_data.get("email")})
                return {"type": "text_messages", "messages": ["Entendido, actualicemos tus datos.\n\n👤 Por favor, envíame tu *nombre completo*:"]}
        
        # Flujo de recolección para nuevos clientes
        elif current_action == "checkout_collect_name":
            action_data["name"] = message_text.strip()
            set_pending_action(db, chat_id, "checkout_collect_email", action_data)
            return {"type": "text_messages", "messages": [f"✅ Perfecto, *{action_data['name']}*.\n\n📧 Ahora envíame tu *correo electrónico*:"]}

        elif current_action == "checkout_collect_email":
            action_data["email"] = user_response
            set_pending_action(db, chat_id, "checkout_collect_phone", action_data)
            return {"type": "text_messages", "messages": [f"✅ Email guardado.\n\n📱 Ahora envíame tu *número de teléfono*:"]}
        
        elif current_action == "checkout_collect_phone":
            action_data["phone"] = message_text.strip()
            set_pending_action(db, chat_id, "checkout_collect_address", action_data)
            return {"type": "text_messages", "messages": [f"✅ Teléfono guardado.\n\n🏠 Por último, envíame tu *dirección de envío completa*:"]}

        elif current_action == "checkout_collect_address":
            action_data["address"] = message_text.strip()
            return await self._finalize_checkout_with_customer_data(db, chat_id, action_data, background_tasks)

        return {"type": "text_messages", "messages": ["❌ Error en el proceso de recolección de datos."]}

    async def _finalize_checkout_with_customer_data(self, db: Session, chat_id: int, customer_data: Dict[str, Any], background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """Finaliza la compra: crea pedido, limpia carrito, envía emails, y notifica al usuario."""
        try:
            async with self._get_api_client() as client:
                cart_response = await client.get(f"/cart/{chat_id}")
                cart_response.raise_for_status()
                cart_data = cart_response.json()

            if not cart_data.get("items"):
                clear_pending_action(db, chat_id)
                return {"type": "text_messages", "messages": ["🛒 Tu carrito está vacío. No se puede finalizar la compra."]}

            # Crear o actualizar cliente y crear el pedido
            client_obj, order_obj = await self._get_or_create_client_and_order(db, chat_id, cart_data, customer_data)

            # Limpiar carrito y acción pendiente
            async with self._get_api_client() as client:
                await client.delete(f"/cart/{chat_id}")
            clear_pending_action(db, chat_id)
            
            # Enviar email de confirmación en segundo plano
            background_tasks.add_task(send_invoice_email, email_to=client_obj.email, order_data=order_obj.to_dict())

            return {"type": "text_messages", "messages": [f"🎉 *¡Gracias por tu compra, {client_obj.name}!* \n\n✅ Tu pedido `#{order_obj.order_id}` ha sido confirmado.\nTe hemos enviado un email a *{client_obj.email}* con los detalles."]}

        except httpx.HTTPError as e:
            logger.error(f"Error de API en checkout final para chat {chat_id}: {e}")
            return {"type": "text_messages", "messages": ["❌ Lo siento, ocurrió un error con tu carrito."]}
        except Exception as e:
            logger.error(f"Error inesperado en checkout final para chat {chat_id}: {e}", exc_info=True)
            return {"type": "text_messages", "messages": ["❌ Ocurrió un error inesperado al procesar tu pedido."]}

    async def _get_or_create_client_and_order(self, db: Session, chat_id: int, cart_data: Dict, client_details: Dict) -> Tuple[Client, Order]:
        """Localiza o crea un cliente y luego crea un pedido a partir de los datos del carrito."""
        client = get_client_by_email(db, email=client_details["email"])
        if not client:
            client = create_client(db, name=client_details["name"], email=client_details["email"], phone=client_details.get("phone"), address=client_details.get("address"))
        else:
            # Actualizar datos si el cliente ya existía pero está proporcionando nuevos
            client.name = client_details["name"]
            client.phone = client_details.get("phone", client.phone)
            client.address = client_details.get("address", client.address)
            db.commit()
            db.refresh(client)
        
        order_items = [
            order_schema.OrderItemCreate(product_sku=sku, quantity=item["quantity"], price=json.loads(item["product"])["price"])
            for sku, item in cart_data["items"].items()
        ]
        
        order_to_create = order_schema.OrderCreate(
            client_id=client.client_id,
            chat_id=str(chat_id),
            customer_name=client.name,
            customer_email=client.email,
            shipping_address=client.address,
            total_amount=cart_data["total_price"],
            items=order_items
        )
        
        order = order_crud.create_order(db, order=order_to_create)
        return client, order

    # ========================================
    # RESPUESTAS Y FORMATO
    # ========================================

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

    async def _handle_conversational_response(self, message_text: str) -> Dict[str, Any]:
        """Maneja respuestas conversacionales generales con personalidad de vendedor experto."""
        messages = []
        if any(g in message_text.lower() for g in ['hola', 'buenos', 'buenas']):
            messages = [
                "¡Hola! 👋 Soy el asistente técnico de Macroferro.",
                "🔧 Estoy aquí para ayudarte con información sobre nuestros productos industriales. ¿En qué puedo ayudarte hoy?"
            ]
        else:
            messages = ["Entendido. ¿Hay algo más en lo que pueda ayudarte?"]
        
        return {"type": "text_messages", "messages": messages}
        
    def get_help_message(self) -> Dict[str, Any]:
        """Devuelve el mensaje de ayuda con la lista de comandos."""
        return {
            "type": "text_messages",
            "messages": [
                "🤖 *Comandos disponibles en Macroferro Bot:*\n\n"
                "*Búsqueda de productos:*\n"
                "• Escribe cualquier consulta en lenguaje natural\n"
                "• Ejemplo: \"Busco martillos\" o \"¿Tienen tubos de 110mm?\"\n\n"
                "*Carrito de compras:*\n"
                "🛒 `/agregar <SKU> [cantidad]` - Agregar al carrito\n"
                "📋 `/ver_carrito` - Ver mi carrito\n"
                "🗑️ `/eliminar <SKU>` - Quitar producto\n"
                "🧹 `/vaciar_carrito` - Vaciar carrito\n"
                "✅ `/finalizar_compra` - Hacer pedido\n\n"
                "*Información:*\n"
                "🏠 `/start` - Mensaje de bienvenida\n"
                "❓ `/help` - Esta ayuda"
            ]
        }

    # ========================================
    # COMUNICACIÓN CON TELEGRAM API
    # ========================================

    def _get_api_client(self) -> httpx.AsyncClient:
        """Crea un cliente HTTP para comunicarse con la propia API del backend."""
        base_url = f"http://localhost:{settings.PORT}{settings.API_V1_STR}"
        return httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown", reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Envía un mensaje de texto a un chat de Telegram."""
        if not self.api_base_url:
            raise ValueError("Telegram bot token no configurado")
        url = f"{self.api_base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP enviando mensaje a chat {chat_id}: {e.response.status_code} - {e.response.text}")
            raise

    async def send_photo(self, chat_id: int, photo_url: str, caption: str = "", parse_mode: str = "Markdown", reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Envía una foto a un chat de Telegram."""
        if not self.api_base_url:
            raise ValueError("Telegram bot token no configurado")
        url = f"{self.api_base_url}/sendPhoto"
        payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP enviando foto a chat {chat_id}: {e.response.status_code} - {e.response.text}")
            raise
    
    async def send_multiple_messages(self, chat_id: int, messages: List[str], delay_between_messages: float = 1.0) -> List[Dict[str, Any]]:
        """
        Envía una secuencia de mensajes a un chat con un retraso natural.
        """
        sent_messages = []
        for i, message in enumerate(messages):
            try:
                sent_message = await self.send_message(chat_id, message)
                sent_messages.append(sent_message)
                if i < len(messages) - 1:
                    await asyncio.sleep(delay_between_messages)
            except Exception as e:
                logger.error(f"Error enviando mensaje múltiple (mensaje {i+1}) a chat {chat_id}: {e}")
        return sent_messages

    async def send_product_with_image(self, chat_id: int, product, caption: str, additional_messages: List[str] = None, delay_between_messages: float = 1.5, reply_markup: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Envía un producto con su imagen principal, caption y mensajes adicionales.
        """
        responses = []
        photo_url = product.images[0].url if product.images else None

        if photo_url:
            try:
                photo_response = await self.send_photo(chat_id, photo_url, caption, reply_markup=reply_markup)
                responses.append(photo_response)
            except Exception as e:
                logger.error(f"Error enviando foto del producto {product.sku} a chat {chat_id}: {e}")
                try:
                    caption_response = await self.send_message(chat_id, caption, reply_markup=reply_markup)
                    responses.append(caption_response)
                except Exception as e_text:
                    logger.error(f"Fallo al enviar caption como texto para producto {product.sku}: {e_text}")
        else:
            try:
                caption_response = await self.send_message(chat_id, caption, reply_markup=reply_markup)
                responses.append(caption_response)
            except Exception as e:
                logger.error(f"Error enviando caption sin foto para producto {product.sku}: {e}")

        if additional_messages:
            await self.send_multiple_messages(chat_id, additional_messages, delay_between_messages)
        
        return responses

    async def set_webhook(self, webhook_url: str, secret_token: str) -> Dict[str, Any]:
        """Configura el webhook de Telegram para recibir actualizaciones."""
        if not self.api_base_url:
            raise ValueError("Telegram bot token no configurado")
        url = f"{self.api_base_url}/setWebhook"
        payload = {"url": webhook_url, "secret_token": secret_token}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                logger.info(f"Webhook configurado exitosamente: {webhook_url}")
            else:
                logger.error(f"Error configurando webhook: {result}")
            return result

# ========================================
# INSTANCIA SINGLETON DEL SERVICIO
# ========================================
telegram_service = TelegramBotService() if settings.telegram_bot_token else None