"""
Handler del Flujo de Checkout para el Bot de Telegram.

Este componente encapsula la máquina de estados y la lógica de negocio
para el proceso de finalización de compra, desde que el usuario decide
pagar hasta que el pedido se confirma.
"""
import logging
from typing import Dict, Any, Tuple, Optional
import json
import re

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select

from app.core.config import settings
from app.services.email_service import send_invoice_email
from app.services.bot_components.cart_handler import CartHandler
from app.crud import client_crud, order_crud
from app.crud.conversation_crud import get_user_context, set_pending_action, clear_user_context
from app.schemas import order_schema
from app.db.models.client_model import Client
from app.db.models.order_model import Order, OrderItem

logger = logging.getLogger(__name__)

class CheckoutHandler:
    """
    Gestiona el proceso de checkout de varios pasos.
    """

    def __init__(self, cart_handler: CartHandler):
        """
        Inicializa el handler de checkout.

        Args:
            cart_handler: Instancia del handler de carrito para interactuar con el carrito.
        """
        self.cart_handler = cart_handler

    async def start_checkout(self, db: AsyncSession, chat_id: int) -> Dict[str, Any]:
        """
        Inicia el flujo de checkout, mostrando el resumen del carrito y la primera pregunta.
        """
        context = await get_user_context(chat_id)
        cart_data = context.get("cart")

        if not cart_data or not cart_data.get("items"):
            return {"type": "text_messages", "messages": ["🛒 Tu carrito está vacío."]}

        cart_summary = self.cart_handler._format_cart_data(cart_data)
        await set_pending_action(chat_id, "checkout_ask_if_recurrent", {})
        
        return {
            "type": "text_messages",
            "messages": [
                f"✅ *Proceso de Compra Iniciado*\n\n{cart_summary}",
                "👋 Antes de continuar, ¿ya eres cliente nuestro? (responde *sí* o *no*)"
            ]
        }

    def is_interrupting_message(self, text: str) -> bool:
        """
        Heurística para detectar si un mensaje es una nueva pregunta que interrumpe un flujo.
        """
        text_lower = text.strip().lower()
        if text_lower.startswith('/') or '?' in text:
            return True
        question_words = ['qué', 'cual', 'cuál', 'cómo', 'donde', 'dónde', 'quien', 'quién', 'cuánto', 'cuando', 'por qué']
        if text_lower.split() and text_lower.split()[0] in question_words:
            return True
        return False

    async def process_step(self, db: AsyncSession, chat_id: int, message_text: str, current_action: str, action_data: Dict[str, Any], background_tasks: BackgroundTasks) -> Optional[Dict[str, Any]]:
        """
        Procesa la recolección de datos del cliente paso a paso.
        """
        user_response = message_text.strip().lower()

        if current_action == "checkout_ask_if_recurrent":
            if 'sí' in user_response or 'si' in user_response:
                await set_pending_action(chat_id, "checkout_get_recurrent_email", {})
                return {"type": "text_messages", "messages": ["¡Genial! Por favor, envíame tu *correo electrónico* para buscar tus datos."]}
            elif 'no' in user_response:
                await set_pending_action(chat_id, "checkout_collect_name", {})
                return {"type": "text_messages", "messages": ["Entendido. Comencemos con el registro.\n\n👤 Por favor, envíame tu *nombre completo*:"]}
            else:
                return {"type": "text_messages", "messages": ["🤔 No entendí tu respuesta. Por favor, responde solo *sí* o *no*."]}

        elif current_action == "checkout_get_recurrent_email":
            email = user_response
            client = await client_crud.get_client_by_email(db, email)
            if client:
                action_data = {"name": client.name, "email": client.email, "phone": client.phone, "address": client.address}
                await set_pending_action(chat_id, "checkout_confirm_recurrent_data", action_data)
                return {"type": "text_messages", "messages": [f"¡Hola de nuevo, *{client.name}*! 👋\n\nHe encontrado estos datos:\n📞 Teléfono: *{client.phone}*\n🏠 Dirección: *{client.address}*\n\n¿Son correctos para el envío? (*sí* o *no*)"]}
            else:
                await set_pending_action(chat_id, "checkout_collect_name", {"email": email})
                return {"type": "text_messages", "messages": ["No encontré tus datos. Vamos a registrarlos.\n\n👤 Para empezar, ¿cuál es tu *nombre completo*?"]}

        elif current_action == "checkout_confirm_recurrent_data":
            if 'sí' in user_response or 'si' in user_response:
                return await self._finalize_checkout(db, chat_id, action_data, background_tasks)
            else:
                await set_pending_action(chat_id, "checkout_collect_name", {"email": action_data.get("email")})
                return {"type": "text_messages", "messages": ["Entendido, actualicemos tus datos.\n\n👤 Por favor, envíame tu *nombre completo*:"]}
        
        elif current_action == "checkout_collect_name":
            action_data["name"] = message_text.strip()
            await set_pending_action(chat_id, "checkout_collect_email", action_data)
            return {"type": "text_messages", "messages": [f"✅ Perfecto, *{action_data['name']}*.\n\n📧 Ahora envíame tu *correo electrónico*:"]}

        elif current_action == "checkout_collect_email":
            # Validación simple de email usando regex
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, user_response):
                return {"type": "text_messages", "messages": ["❌ El formato del correo electrónico no parece válido. Por favor, inténtalo de nuevo (ej: `usuario@dominio.com`)."]}
            
            action_data["email"] = user_response
            await set_pending_action(chat_id, "checkout_collect_phone", action_data)
            return {"type": "text_messages", "messages": [f"✅ Email guardado.\n\n📱 Ahora envíame tu *número de teléfono*:"]}
        
        elif current_action == "checkout_collect_phone":
            # Validación de teléfono: al menos 9 dígitos, permitiendo espacios opcionales
            phone_cleaned = re.sub(r'\s+', '', message_text.strip())
            if not (phone_cleaned.isdigit() and len(phone_cleaned) >= 9):
                 return {"type": "text_messages", "messages": ["❌ El número de teléfono no parece válido. Por favor, introduce un número de al menos 9 dígitos."]}

            action_data["phone"] = message_text.strip()
            await set_pending_action(chat_id, "checkout_collect_address", action_data)
            return {"type": "text_messages", "messages": [f"✅ Teléfono guardado.\n\n🏠 Por último, envíame tu *dirección de envío completa*:"]}

        elif current_action == "checkout_collect_address":
            # Validación de dirección: no vacía y con una longitud mínima
            address = message_text.strip()
            if len(address) < 10:
                return {"type": "text_messages", "messages": ["❌ La dirección parece demasiado corta. Por favor, introduce una dirección de envío completa."]}

            action_data["address"] = address
            return await self._finalize_checkout(db, chat_id, action_data, background_tasks)

        logger.warning(f"Se alcanzó un estado de checkout no manejado: {current_action}")
        return {"type": "text_messages", "messages": ["❌ Error en el proceso de recolección de datos."]}

    async def _finalize_checkout(self, db: AsyncSession, chat_id: int, customer_data: Dict[str, Any], background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """
        Finaliza la compra: crea pedido, limpia carrito, envía emails, y notifica al usuario.
        """
        try:
            context = await get_user_context(chat_id)
            cart_data = context.get("cart")

            if not cart_data or not cart_data.get("items"):
                await set_pending_action(chat_id, None)
                return {"type": "text_messages", "messages": ["🛒 Tu carrito está vacío. No se puede finalizar la compra."]}

            client_obj, order_obj = await self._get_or_create_client_and_order(db, chat_id, cart_data, customer_data)

            # Limpiamos todo el contexto del usuario, incluido el carrito
            await clear_user_context(chat_id)
            
            background_tasks.add_task(send_invoice_email, email_to=client_obj.email, order_data=order_obj.to_dict())

            return {"type": "text_messages", "messages": [f"🎉 *¡Gracias por tu compra, {client_obj.name}!* \n\n✅ Tu pedido `#{order_obj.order_id}` ha sido confirmado.\nTe hemos enviado un email a *{client_obj.email}* con los detalles."]}

        except Exception as e:
            logger.error(f"Error inesperado en checkout final para chat {chat_id}: {e}", exc_info=True)
            return {"type": "text_messages", "messages": ["❌ Ocurrió un error inesperado al procesar tu pedido."]}

    async def _get_or_create_client_and_order(self, db: AsyncSession, chat_id: int, cart_data: Dict, client_details: Dict) -> Tuple[Client, Order]:
        """
        Localiza o crea un cliente y luego crea un pedido a partir de los datos del carrito.
        """
        client = await client_crud.get_client_by_email(db, email=client_details["email"])
        if not client:
            client = await client_crud.create_client(db, name=client_details["name"], email=client_details["email"], phone=client_details.get("phone"), address=client_details.get("address"))
        else:
            # Actualizar datos si el cliente ya existía
            client.name = client_details["name"]
            client.phone = client_details.get("phone", client.phone)
            client.address = client_details.get("address", client.address)
            await db.commit()
            await db.refresh(client)
        
        order_items = [
            order_schema.OrderItemCreate(product_sku=sku, quantity=item["quantity"], price=item["product"]["price"])
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
        
        order = await order_crud.create_order(db, order=order_to_create)

        # Volver a cargar el pedido pero esta vez con los items para evitar lazy loading en el background task
        result = await db.execute(
            select(Order).filter(Order.order_id == order.order_id).options(
                joinedload(Order.items).joinedload(OrderItem.product)
            )
        )
        order_with_items = result.unique().scalars().one()
        
        return client, order_with_items 