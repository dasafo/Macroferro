# backend/app/services/telegram_service.py
"""
Servicio de Bot de Telegram para la aplicación.

Este servicio se encarga de gestionar la comunicación con el Bot de Telegram,
incluyendo procesamiento de mensajes, manejo de comandos, búsqueda de productos,
y envío de respuestas. Utiliza la API de Telegram Bot para interactuar con el usuario.

Características principales:
- Procesamiento de mensajes de texto y comandos
- Búsqueda de productos y envío de respuestas
- Gestión de carrito de compras
- Integración con API de Telegram
- Manejo de errores y excepciones
"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, List, Tuple
import httpx
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
import re
from fastapi import BackgroundTasks

from app.core.config import settings
from app.services.product_service import ProductService
from app.services.email_service import send_invoice_email
from app.services.context_service import context_service
from app.services.bot_components.ai_analyzer import AIAnalyzer
from app.services.bot_components.product_handler import ProductHandler
from app.services.bot_components.cart_handler import CartHandler
from app.services.bot_components.checkout_handler import CheckoutHandler
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
        self.cart_handler = CartHandler(self.product_handler)
        self.checkout_handler = CheckoutHandler(self.cart_handler)
        logger.info("Servicios y Handlers inicializados.")

    # ========================================
    # PROCESAMIENTO PRINCIPAL DE MENSAJES
    # ========================================
    
    async def process_message(self, db: AsyncSession, message_data: Dict[str, Any], background_tasks: BackgroundTasks) -> Dict[str, Any]:
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
            pending_action_info = await get_pending_action(chat_id)
            if pending_action_info:
                current_action = pending_action_info.get("action")
                action_data = pending_action_info.get("data", {})
                if current_action and current_action.startswith("checkout"):
                        # No interrumpir el checkout por preguntas normales
                        if not self.checkout_handler.is_interrupting_message(message_text):
                            response_dict = await self.checkout_handler.process_step(
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
                await add_turn_to_history(chat_id, message_text, bot_response_text)

            return response_dict
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout procesando mensaje de chat {chat_id}")
            return await self._create_error_response(chat_id, message_text, "⏱️ Lo siento, el procesamiento está tomando más tiempo del esperado. Por favor intenta nuevamente.")
            
        except Exception as e:
            logger.exception(f"Error fatal procesando mensaje de chat {chat_id}")
            return await self._create_error_response(chat_id, message_text, "❌ Lo siento, hubo un error grave procesando tu mensaje. Nuestro equipo ha sido notificado.")

    async def _create_error_response(self, chat_id: int, user_message: str, error_text: str) -> Dict[str, Any]:
        """Crea una respuesta de error estándar y la registra en el historial."""
        response_dict = {"type": "text_messages", "messages": [error_text]}
        await add_turn_to_history(chat_id, user_message, error_text)
        return response_dict
        
    async def _handle_command(self, db: AsyncSession, chat_id: int, message_text: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maneja los comandos que empiezan con '/'."""
        parts = message_text.split()
        command = parts[0]
        args = parts[1:]

        if command == '/start' or command == '/help':
            return self.get_help_message()
        elif command == '/agregar':
            return await self.cart_handler.add_item_by_command(db, chat_id, args)
        elif command == '/ver_carrito':
            return await self.cart_handler.view_cart(db, chat_id)
        elif command == '/eliminar':
            return await self.cart_handler.remove_item_by_command(db, chat_id, args)
        elif command == '/vaciar_carrito':
            return await self.cart_handler.clear_cart(chat_id)
        elif command == '/finalizar_compra':
            return await self.checkout_handler.start_checkout(db, chat_id)
        else:
            return {"type": "text_messages", "messages": [f"😕 No reconozco el comando '{command}'. Escribe /help para ver la lista de comandos disponibles."]}

    async def _handle_natural_language(self, db: AsyncSession, chat_id: int, message_text: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maneja mensajes en lenguaje natural usando IA."""
        logger.info(f"Analizando mensaje de chat {chat_id}: '{message_text}'")

        history = await get_conversation_history(chat_id, limit_turns=5)
        analysis = await self.ai_analyzer.analyze_user_intent(message_text, history=history)
            
        intent_type = analysis.get("intent_type", "general_conversation")
        confidence = analysis.get("confidence", 0.5)
        
        add_recent_intent(db, chat_id, intent_type, confidence)
        
        # Delegar a los handlers correspondientes
        if intent_type in ["product_details", "product_search", "technical_question", "catalog_inquiry"]:
            return await self.product_handler.handle_intent(db, intent_type, analysis, message_text, chat_id)
        elif intent_type == "cart_action":
            # La acción 'checkout' es una acción de carrito que inicia un flujo más complejo.
            # Comprobamos si alguna de las acciones solicitadas es 'checkout'.
            cart_actions = analysis.get("cart_actions", [])
            is_checkout = any(action.get("action") == "checkout" for action in cart_actions)

            if is_checkout:
                return await self.checkout_handler.start_checkout(db, chat_id)
            
            return await self.cart_handler.handle_action(db, analysis, chat_id)
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
            return await self._handle_conversational_response(db, message_text)

    # ========================================
    # RESPUESTAS Y FORMATO
    # ========================================
            
    async def _handle_conversational_response(self, db: AsyncSession, message_text: str) -> Dict[str, Any]:
        """Maneja respuestas conversacionales generales con personalidad de vendedor experto."""
        messages = []
        if any(g in message_text.lower() for g in ['hola', 'buenos', 'buenas']):
            
            categories_text = await self.product_handler.get_main_categories_formatted(db)
            
            messages = [
                "¡Hola! 👋 Soy el asistente técnico de Macroferro.",
                "🔧 Estoy aquí para ayudarte con información sobre nuestros productos industriales. ¿En qué puedo ayudarte hoy?",
                f"\n{categories_text}\n\n💡 Puedes preguntarme por cualquiera de ellas (ej: 'qué tienes en tornillería') para ver más detalles."
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

    async def _handle_callback_query(self, db: AsyncSession, callback_query: Dict[str, Any]) -> Dict[str, Any]:
        """Maneja las pulsaciones de botones inline."""
        chat_id = callback_query['message']['chat']['id']
        data = callback_query['data']
        
        # Aquí puedes añadir lógica para diferentes tipos de callbacks
        # Por ahora, un ejemplo simple
        if data.startswith("category_"):
            category_id = int(data.split('_')[1])
            # Lógica para mostrar productos de esa categoría...
            # Esta es una implementación de ejemplo
            response_text = f"Has seleccionado una categoría. ID: {category_id}. ¡Próximamente más funciones!"
            await self.send_message(chat_id, response_text)

        return {"status": "ok"}

# ========================================
# INSTANCIA SINGLETON DEL SERVICIO
# ========================================
telegram_service = TelegramBotService() if settings.telegram_bot_token else None