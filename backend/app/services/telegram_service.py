"""
Capa de servicios para operaciones de negocio del Bot de Telegram.

Esta capa implementa el patrón Service Layer para la integración con Telegram Bot API,
proporcionando una abstracción de alto nivel que orquesta la comunicación bidireccional
con usuarios de Telegram, procesamiento inteligente de mensajes con IA, y búsqueda
avanzada de productos en el catálogo de Macroferro.

Responsabilidades principales:
- Comunicación asíncrona con Telegram Bot API (webhook y sending)
- Procesamiento inteligente de mensajes usando OpenAI GPT
- Orquestación de búsquedas de productos con embedding vectorial
- Gestión de contexto conversacional y estado del usuario
- Formateo de respuestas rica en Markdown para mejor UX
- Manejo robusto de errores de red y timeouts

Características del dominio de Telegram Bot:
- Comunicación asíncrona y no bloqueante requerida
- Procesamiento de diferentes tipos de mensajes (texto, comandos, media)
- Integración con servicios de IA para comprensión de intenciones
- Búsqueda semántica avanzada en catálogo de productos
- Respuestas formateadas en Markdown para mejor presentación
- Gestión de webhooks para recepción en tiempo real

Patrones implementados:
- Service Layer: Lógica de negocio centralizada para Telegram
- Async/Await: Operaciones no bloqueantes para alta concurrencia
- AI Integration: Procesamiento de lenguaje natural con OpenAI
- Error Handling: Manejo robusto de fallos de red y servicios externos
- Composition: Utiliza ProductService para búsquedas avanzadas

Integraciones externas:
- Telegram Bot API: Comunicación bidireccional con usuarios
- OpenAI API: Procesamiento de lenguaje natural e intenciones
- Qdrant Vector DB: Búsqueda semántica de productos (vía ProductService)
- PostgreSQL: Datos de productos y contexto conversacional
"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, List
import httpx
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import re
import os

from app.core.config import settings
from app.services.product_service import ProductService
from app.crud.product_crud import get_product_by_sku, get_products
from app.db.models.product_model import Product
from app.db.models.category_model import Category
from app.crud.conversation_crud import (
    get_recent_products, 
    add_recent_product, 
    update_conversation_context, 
    update_search_context, 
    add_recent_intent, 
    set_pending_action, 
    clear_pending_action,
    get_pending_action
)
from app.crud.stock_crud import get_total_stock_by_sku, get_stock_by_sku
from app.db.models.stock_model import Stock, Warehouse

logger = logging.getLogger(__name__)

class TelegramBotService:
    """
    Servicio para operaciones de negocio del Bot de Telegram.
    
    Esta clase encapsula toda la lógica de negocio para la comunicación con usuarios
    de Telegram, incluyendo procesamiento inteligente de mensajes, búsqueda de productos
    con IA, y orquestación de respuestas personalizadas para consultas comerciales.
    
    Características principales:
    - Comunicación asíncrona con Telegram Bot API
    - Análisis de intenciones usando OpenAI GPT-3.5/4
    - Búsqueda semántica de productos con embeddings vectoriales
    - Formateo rico de respuestas en Markdown
    - División inteligente de respuestas largas en múltiples mensajes
    - Manejo robusto de errores y timeouts de red
    - Configuración flexible via variables de entorno
    
    Flujo principal de operación:
    1. Recibir mensaje via webhook de Telegram
    2. Analizar intención del usuario con IA
    3. Ejecutar búsqueda de productos si corresponde
    4. Formatear respuesta rica en Markdown
    5. Dividir respuesta en mensajes naturales
    6. Enviar mensajes secuencialmente a Telegram
    
    Consideraciones de arquitectura:
    - Operaciones asíncronas para no bloquear el event loop
    - Timeouts configurables para evitar cuelgues
    - Fallbacks graceful cuando servicios externos fallan
    - Logging detallado para debugging y monitoreo
    """

    def __init__(self):
        """
        Inicializa el servicio de Telegram Bot con configuración desde variables de entorno.
        
        Configura:
        - Cliente OpenAI para procesamiento de IA
        - URL base del API de Telegram
        - Servicio de productos para búsquedas
        - Logging para monitoreo
        
        Variables de entorno requeridas:
        - TELEGRAM_BOT_TOKEN: Token del bot de Telegram
        - OPENAI_API_KEY: API key de OpenAI
        
        Raises:
            ValueError: Si faltan configuraciones críticas
        """
        # Configurar cliente OpenAI
        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("Cliente OpenAI configurado exitosamente")
        else:
            self.openai_client = None
            logger.warning("OpenAI API key no configurado - funciones de IA limitadas")
        
        # Configurar API de Telegram
        if settings.telegram_bot_token:
            self.api_base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
            logger.info("API de Telegram configurado exitosamente")
        else:
            self.api_base_url = None
            logger.warning("Telegram bot token no configurado")
        
        # Inicializar servicio de productos
        self.product_service = ProductService()
        logger.info("Servicio de productos inicializado")

    # ========================================
    # COMUNICACIÓN CON TELEGRAM API
    # ========================================
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown", reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Envía un mensaje a un chat específico a través del API de Telegram.
        
        Esta función maneja la comunicación saliente hacia usuarios de Telegram,
        con soporte para formateo rico en Markdown/HTML y manejo robusto de errores
        de red que son comunes en integraciones con APIs externas.
        
        Args:
            chat_id: ID único del chat donde enviar el mensaje
            text: Contenido del mensaje (puede incluir Markdown/HTML)
            parse_mode: Formato del texto ("Markdown", "HTML", o None)
            reply_markup: Teclado interactivo para adjuntar al mensaje (opcional)
            
        Returns:
            Respuesta JSON del API de Telegram con detalles del mensaje enviado
            
        Características implementadas:
        - Timeout configurado para evitar cuelgues indefinidos
        - Retry logic implícito via httpx para fallos transitorios
        - Logging detallado de errores para debugging
        - Validación automática de respuesta HTTP
        
        Formato Markdown soportado:
        - *texto en negrita*
        - _texto en cursiva_
        - `código en línea`
        - [enlace](https://example.com)
        - Listas con - o números
        
        Manejo de errores típicos:
        - NetworkError: Problemas de conectividad
        - HTTPError: Errores del API de Telegram (rate limits, etc.)
        - Timeout: Respuesta lenta del servidor
        
        Extensiones futuras:
        - Retry automático con backoff exponencial
        - Queue de mensajes para rate limiting
        - Soporte para inline keyboards y botones
        - Métricas de éxito/fallo de envío
        - Validación de longitud de mensaje (4096 chars max)
        """
        if not self.api_base_url:
            logger.error("Bot token no configurado, no se puede enviar mensaje")
            raise ValueError("Telegram bot token not configured")
            
        url = f"{self.api_base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Mensaje enviado exitosamente a chat {chat_id}")
                return result
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout enviando mensaje a chat {chat_id}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP enviando mensaje a chat {chat_id}: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado enviando mensaje de Telegram a chat {chat_id}: {e}")
            raise

    async def send_photo(self, chat_id: int, photo_url: str, caption: str = "", parse_mode: str = "Markdown", reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Envía una foto a un chat específico a través del API de Telegram.
        
        Esta función permite enviar imágenes directamente desde URLs, con soporte
        para captions formateados y manejo robusto de errores específicos de imágenes.
        
        Args:
            chat_id: ID único del chat donde enviar la foto
            photo_url: URL de la imagen a enviar (debe ser accesible públicamente)
            caption: Texto descriptivo de la imagen (opcional, máximo 1024 caracteres)
            parse_mode: Formato del caption ("Markdown", "HTML", o None)
            reply_markup: Teclado interactivo para adjuntar al mensaje (opcional)
            
        Returns:
            Respuesta JSON del API de Telegram con detalles de la foto enviada
            
        Características:
        - Soporte para URLs públicas de imágenes
        - Caption con formato Markdown/HTML
        - Validación automática de formato de imagen
        - Manejo específico de errores de media
        
        Formatos de imagen soportados por Telegram:
        - JPG, PNG, GIF, BMP, WEBP
        - Tamaño máximo: 10MB para fotos
        - Resolución máxima: 1280x1280 píxeles
        
        Limitaciones del caption:
        - Máximo 1024 caracteres
        - Mismo formato Markdown que mensajes de texto
        
        Casos de uso:
        - Mostrar imágenes de productos en catálogo
        - Enviar fotos de referencia técnica
        - Compartir diagramas o esquemas
        
        Manejo de errores específicos:
        - URL inaccesible o imagen corrupta
        - Formato de imagen no soportado
        - Imagen demasiado grande
        - Problemas de conectividad
        """
        if not self.api_base_url:
            logger.error("Bot token no configurado, no se puede enviar foto")
            raise ValueError("Telegram bot token not configured")
            
        url = f"{self.api_base_url}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:  # Mayor timeout para imágenes
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Foto enviada exitosamente a chat {chat_id} desde URL: {photo_url}")
                return result
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout enviando foto a chat {chat_id} desde {photo_url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP enviando foto a chat {chat_id} desde {photo_url}: {e.response.status_code} - {e.response.text}")
            # Los errores comunes incluyen:
            # - 400 Bad Request: URL de imagen inválida o inaccesible
            # - 413 Payload Too Large: Imagen demasiado grande
            # - 415 Unsupported Media Type: Formato no soportado
            raise
        except Exception as e:
            logger.error(f"Error inesperado enviando foto de Telegram a chat {chat_id} desde {photo_url}: {e}")
            raise

    async def send_multiple_messages(self, chat_id: int, messages: List[str], delay_between_messages: float = 1.0) -> List[Dict[str, Any]]:
        """
        Envía una secuencia de mensajes a un chat con un retraso natural.
        
        Esta función simula una conversación natural enviando mensajes en secuencia
        con pausas para que parezca que la persona está escribiendo cada respuesta.
        
        Args:
            chat_id: ID del chat donde enviar los mensajes
            messages: Lista de mensajes a enviar
            delay_between_messages: Tiempo en segundos entre mensajes
            
        Returns:
            Lista con las respuestas del API de Telegram para cada mensaje
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
                # Continuar con el siguiente mensaje
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
            for i, message in enumerate(additional_messages):
                await asyncio.sleep(delay_between_messages)
                try:
                    result = await self.send_message(chat_id, message)
                    responses.append(result)
                except Exception as e:
                    logger.error(f"Error enviando mensaje adicional {i+1} para producto {product.sku}: {e}")
                    responses.append({"error": str(e)})
        
        return responses

    def split_response_into_messages(self, response_text: str, max_length: int = 4000) -> List[str]:
        """
        Divide una respuesta larga en múltiples mensajes naturales.
        
        Esta función analiza el contenido de la respuesta y la divide en puntos
        lógicos para crear una conversación más natural y fluida.
        
        Args:
            response_text: Texto completo de la respuesta
            max_length: Longitud máxima por mensaje (límite de Telegram es 4096)
            
        Returns:
            Lista de mensajes divididos de forma natural
        """
        if len(response_text) <= max_length:
            return [response_text]
        
        messages = []
        
        # Dividir por secciones principales (marcadas con títulos en negrita)
        sections = re.split(r'\n\n(?=\*[^*]+\*)', response_text)
        
        current_message = ""
        
        for section in sections:
            # Si agregar esta sección excede el límite
            if len(current_message) + len(section) + 2 > max_length:  # +2 por \n\n
                if current_message:
                    messages.append(current_message.strip())
                    current_message = section
                else:
                    # La sección es muy larga, dividir por párrafos
                    paragraphs = section.split('\n\n')
                    for paragraph in paragraphs:
                        if len(current_message) + len(paragraph) + 2 > max_length:
                            if current_message:
                                messages.append(current_message.strip())
                                current_message = paragraph
                            else:
                                # Párrafo muy largo, dividir por líneas
                                lines = paragraph.split('\n')
                                for line in lines:
                                    if len(current_message) + len(line) + 1 > max_length:
                                        if current_message:
                                            messages.append(current_message.strip())
                                            current_message = line
                                        else:
                                            # Línea muy larga, cortar por caracteres
                                            messages.append(line[:max_length-3] + "...")
                                    else:
                                        current_message += ("\n" if current_message else "") + line
                        else:
                            current_message += ("\n\n" if current_message else "") + paragraph
            else:
                current_message += ("\n\n" if current_message else "") + section
        
        if current_message:
            messages.append(current_message.strip())
        
        return messages

    # ========================================
    # PROCESAMIENTO INTELIGENTE DE MENSAJES
    # ========================================
    
    async def process_message(self, db: Session, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa un mensaje entrante de Telegram, orquestando análisis de IA y respuestas.
        Esta es la función principal que maneja toda la lógica del bot.
        """
        # Primero, verificar si es un callback de un botón
        if 'callback_query' in message_data:
            return await self._handle_callback_query(db, message_data['callback_query'])

        # Si no, procesar como un mensaje normal o editado
        message = message_data.get('message') or message_data.get('edited_message')

        if not message:
            logger.warning(f"Update recibido sin contenido procesable (message/callback). Keys: {list(message_data.keys())}. Ignorando.")
            return {"status": "ignored", "reason": "unhandled_update_type"}

        message_text = message.get("text", "")
        chat_id = message["chat"]["id"]
        
        # Verificar si hay una acción pendiente (como recolección de datos del checkout)
        pending_action_info = get_pending_action(db, chat_id)
        if pending_action_info:
            current_action = pending_action_info.get("action")
            action_data = pending_action_info.get("data", {})
            
            # Si es una acción de recolección de datos del checkout, procesarla
            if current_action and current_action.startswith("checkout_collect"):
                return await self._process_checkout_data_collection(
                    db, chat_id, message_text, current_action, action_data
                )
        
        # --- INICIO DE LÓGICA DE PRE-PROCESAMIENTO ---
        # Si el mensaje sigue un patrón de "qué [producto] tienes/ofreces",
        # se convierte en una búsqueda para evitar ambigüedad en la IA.
        verbs = "tienes|ten[eé]is|tiene|tienen|ofreces|ofrec[eé]is|ofrece|ofrecen|vendes|vend[eé]is|vende|venden"
        match = re.search(rf"qu[eé]\s+(.+)\s+({verbs})\b", message_text, re.IGNORECASE)
        if match:
            product_query = match.group(1).strip()
            
            # Limpiar "productos de" si existe para una búsqueda más limpia
            if product_query.lower().startswith("productos de "):
                product_query = product_query[13:].strip()
            
            # Evitar que una pregunta vacía se convierta en una búsqueda
            if product_query and len(product_query.split()) < 5: # Límite para evitar frases muy complejas
                # Reemplazar el texto del mensaje por una búsqueda explícita
                original_message = message_text
                message_text = f"Búsqueda de producto: {product_query}"
                logger.info(f"Mensaje original '{original_message}' transformado a '{message_text}' para desambiguación.")
        # --- FIN DE LÓGICA DE PRE-PROCESAMIENTO ---

        # 1. Manejo de comandos directos (sin IA)
        if message_text.startswith('/'):
            parts = message_text.split()
            command = parts[0]
            args = parts[1:]

            if command == '/start':
                response_text = (
                    "🏭 *¡Bienvenido a Macroferro Bot!* 🏭\n\n"
                    "Soy tu asistente virtual para consultar productos industriales.\n\n"
                    "*¿Qué puedo hacer?*\n"
                    "• Buscar productos por nombre o categoría\n"
                    "• Responder preguntas técnicas sobre productos\n"
                    "• Gestionar tu carrito de compras\n\n"
                    "*Comandos del carrito:*\n"
                    "🛒 `/agregar <SKU> [cantidad]` - Agregar producto al carrito\n"
                    "📋 `/ver_carrito` - Ver contenido del carrito\n"
                    "🗑️ `/eliminar <SKU>` - Eliminar producto del carrito\n"
                    "🧹 `/vaciar_carrito` - Vaciar todo el carrito\n"
                    "✅ `/finalizar_compra` - Realizar pedido\n\n"
                    "*Otros comandos:*\n"
                    "❓ `/help` - Ver todos los comandos\n\n"
                    "*¡También puedes hacer preguntas como:*\n"
                    "\"Busco tubos de PVC de 110mm\"\n"
                    "\"¿Qué herramientas Bahco tienen?\"\n"
                    "\"Necesito conectores para electricidad\""
                )
                return {
                    "type": "text_messages",
                    "messages": [response_text]
                }
            elif command == '/help':
                response_text = (
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
                    "❓ `/help` - Esta ayuda\n\n"
                    "💡 *Tip:* También puedes preguntarme directamente sobre productos usando lenguaje natural."
                )
                return {
                    "type": "text_messages",
                    "messages": [response_text]
                }
            elif command == '/agregar':
                return await self._handle_add_to_cart(chat_id, args, db)
            elif command == '/ver_carrito':
                return await self._handle_view_cart(db, chat_id)
            elif command == '/eliminar':
                return await self._handle_remove_from_cart(chat_id, args)
            elif command == '/vaciar_carrito':
                return await self._handle_clear_cart(chat_id)
            elif command == '/finalizar_compra':
                return await self._handle_checkout(db, chat_id, message_data)

        # 2. Si no es un comando, proceder con el análisis de IA (código existente)
        # ... (resto del código de process_message que llama a la IA) ...

        logger.info(f"Analizando mensaje de chat {chat_id}: '{message_text}'")

        if not self.openai_client:
            logger.warning("OpenAI no configurado, usando respuesta estática")
            return {
                "type": "text_messages",
                "messages": ["🤖 Hola! Soy el asistente de Macroferro. El servicio de IA no está disponible en este momento."]
            }
        
        try:
            # ========================================
            # ANÁLISIS INTELIGENTE CON GPT-4
            # ========================================
            
            # Usar GPT-4 para un análisis más sofisticado de la intención
            analysis_prompt = f"""
Eres un asistente de inteligencia artificial especializado en productos industriales de Macroferro.

Analiza este mensaje del usuario y determina exactamente qué tipo de respuesta necesita:

Mensaje del usuario: "{message_text}"

Contexto empresarial:
- Macroferro vende productos industriales: tubos, válvulas, herramientas, conectores, tornillos, etc.
- Los clientes hacen consultas técnicas específicas sobre productos
- Los usuarios pueden estar preguntando por detalles de un producto que ya encontraron
- También pueden estar haciendo búsquedas nuevas de productos
- Los usuarios pueden querer gestionar su carrito de compras usando lenguaje natural

IMPORTANTE: 
1. Si el usuario menciona un producto específico (nombre, marca, o característica muy específica), probablemente quiere información detallada de ESE producto, no una búsqueda general.
2. Si el usuario quiere agregar, quitar, ver, vaciar o finalizar compra, es una acción de carrito.

Responde ÚNICAMENTE con este JSON:
{{
    "intent_type": "product_details" | "product_search" | "technical_question" | "cart_action" | "catalog_inquiry" | "general_conversation",
    "confidence": 0.8,
    "specific_product_mentioned": "nombre exacto del producto si se menciona" | null,
    "search_terms": ["término1", "término2"] | null,
    "technical_aspect": "aspecto técnico específico" | null,
    "cart_action": "add" | "remove" | "view" | "clear" | "checkout" | null,
    "cart_product_reference": "referencia al producto a agregar/quitar" | null,
    "cart_quantity": número | null,
    "user_intent_description": "descripción clara de lo que quiere el usuario",
    "suggested_response_tone": "informative" | "conversational" | "technical"
}}

Tipos de intent:
- "product_details": Usuario pregunta por un producto específico que mencionó por nombre
- "product_search": Usuario busca productos por categoría/tipo general 
- "technical_question": Pregunta técnica sobre especificaciones
- "cart_action": Usuario quiere gestionar su carrito (agregar, quitar, ver, vaciar, finalizar)
- "catalog_inquiry": El usuario pregunta de forma general qué productos se venden (ej: "qué vendes", "qué tienes").
- "general_conversation": Saludo, información general, otros temas

Ejemplos de cart_action:
- "Agrega ese martillo al carrito" → cart_action: "add", cart_product_reference: "ese martillo"
- "Quiero agregar 5 tubos de PVC" → cart_action: "add", cart_quantity: 5, cart_product_reference: "tubos de PVC"
- "Agrega el último producto que me mostraste" → cart_action: "add", cart_product_reference: "el último producto"
- "Agrega esos tornillos UNC al carrito" → cart_action: "add", cart_product_reference: "esos tornillos UNC"
- "Agrega 2 de esos tornillos métricos al carrito" → cart_action: "add", cart_quantity: 2, cart_product_reference: "esos tornillos métricos"
- "Agrega el taladro Hilti al carrito" → cart_action: "add", cart_product_reference: "el taladro Hilti"
- "dame 4 del número 5" → cart_action: "add", cart_quantity: 4, cart_product_reference: "número 5"
- "ponme 3 del 2" → cart_action: "add", cart_quantity: 3, cart_product_reference: "el 2"
- "agrega 2 del número 3" → cart_action: "add", cart_quantity: 2, cart_product_reference: "número 3"
- "quiero 5 del 1" → cart_action: "add", cart_quantity: 5, cart_product_reference: "el 1"
- "Quítalo del carrito" → cart_action: "remove", cart_product_reference: "eso"
- "Quita el martillo del carrito" → cart_action: "remove", cart_product_reference: "el martillo"
- "Quita los tornillos UNC del carrito" → cart_action: "remove", cart_product_reference: "los tornillos UNC"
- "Muéstrame mi carrito" → cart_action: "view"
- "Vacía mi carrito" → cart_action: "clear"
- "Quiero finalizar la compra" → cart_action: "checkout"
- "Comprar" → cart_action: "checkout"
- "Quita 1 guante del carrito" -> cart_action: "remove", cart_quantity: 1, cart_product_reference: "guante"
- "elimina dos de esos" -> cart_action: "remove", cart_quantity: 2, cart_product_reference: "esos"
- "saca un adhesivo" -> cart_action: "remove", cart_quantity: 1, cart_product_reference: "un adhesivo"
- "quita mejor 32 pinturas del carro" -> cart_action: "remove", cart_quantity: 32, cart_product_reference: "pinturas"
- "si añade 3 adhesivos de montaje Facom al carro" -> cart_action: "add", cart_quantity: 3, cart_product_reference: "adhesivos de montaje Facom"
- "6 de Adhesivo Profesional Hilti" -> cart_action: "add", cart_quantity: 6, cart_product_reference: "Adhesivo Profesional Hilti"
- "añade 5 guantes mas al carro" -> cart_action: "add", cart_quantity: 5, cart_product_reference: "guantes", "is_update": true

IMPORTANTE para cart_product_reference:
- Mantén SIEMPRE la referencia en español exactamente como la dice el usuario
- **NUNCA incluyas números en este campo.** Los números van en el campo "cart_quantity".
- Para referencias por orden número (ej: "del número 5", "del 2"), usa "número X" o "el X" según el usuario diga
- Si dice "esos tornillos UNC", pon exactamente "esos tornillos UNC"
- Si dice "el taladro Hilti", pon exactamente "el taladro Hilti"
- Si dice "ese martillo", pon exactamente "ese martillo"
- Si dice "del número 5", pon exactamente "número 5"
- Si dice "del 3", pon exactamente "el 3"
- NO traduzcas al inglés
- Incluye marca, tipo y adjetivos demostrativos (ese, esos, el, la, etc.)

Ejemplos de otros tipos:
- "¿Qué especificaciones tiene el Esmalte para Exteriores Bahco?" → product_details
- "Busco tubos de PVC" → product_search  
- "¿Cuál es el diámetro de ese tubo?" → technical_question
- "Hola, ¿cómo están?" → general_conversation

IMPORTANTE sobre búsquedas vagas:
- Si la búsqueda es MUY genérica y podría referirse a cientos de productos (ej: "cosas de metal", "productos", "herramientas"), clasifícalo como "general_conversation" para que el asistente pueda pedir más detalles.
- Una búsqueda válida debe tener un tipo de producto más o menos claro (ej: "tubos de PVC", "martillos percutores", "pintura para exteriores").

Ejemplos de búsquedas vagas:
- "tienes cosas de metal?" -> intent_type: "general_conversation"
- "qué vendes?" -> intent_type: "catalog_inquiry"
- "qué tipo de productos tenéis?" -> intent_type: "catalog_inquiry"
- "dame productos" -> intent_type: "general_conversation"
"""
            
            # Usar gpt-4o-mini para análisis más sofisticado
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.1,
                max_tokens=300,
                timeout=15.0
            )
            
            # Procesar respuesta de IA
            try:
                ai_content = response.choices[0].message.content
                logger.info(f"Análisis de IA: {ai_content}")
                
                # Extraer JSON
                json_content = self._extract_json_from_markdown(ai_content)
                analysis = json.loads(json_content)
                logger.info(f"Análisis parseado: {analysis}")
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando análisis de IA: {e}")
                analysis = {"intent_type": "general_conversation", "confidence": 0.5}
            
            intent_type = analysis.get("intent_type", "general_conversation")
            confidence = analysis.get("confidence", 0.5)
            
            # FORZAR ACLARACIÓN PARA PREGUNTAS VAGAS
            # Si la IA lo ha clasificado como 'general_conversation' y no es un saludo,
            # significa que la consulta es demasiado abierta.
            is_simple_greeting = any(
                greeting in message_text.lower() 
                for greeting in ['hola', 'gracias', 'buenos', 'buenas', 'ok', 'vale', 'adios']
            )
            
            if intent_type == "general_conversation" and not is_simple_greeting:
                logger.info(f"La consulta es demasiado general. Pidiendo aclaración al usuario.")
                return {
                    "type": "text_messages",
                    "messages": [
                        "🤔 Entendido, pero tu consulta es un poco general.",
                        "Para poder ayudarte mejor, ¿podrías ser más específico? Por ejemplo, puedes decirme el tipo de producto que buscas (ej: 'tubos de acero', 'tornillos para madera') o la marca."
                    ]
                }

            # ========================================
            # ENRUTAMIENTO INTELIGENTE SEGÚN INTENCIÓN
            # ========================================
            
            if intent_type == "product_details":
                return await self._handle_specific_product_inquiry(db, analysis, message_text, chat_id)
            
            elif intent_type == "catalog_inquiry":
                return await self._handle_catalog_inquiry(db)
            
            elif intent_type == "product_search":
                messages = await self._handle_product_search(db, analysis, message_text, chat_id)
                return {"type": "text_messages", "messages": messages}
            
            elif intent_type == "technical_question":
                messages = await self._handle_technical_question(db, analysis, message_text, chat_id)
                return {"type": "text_messages", "messages": messages}
            
            elif intent_type == "cart_action":
                return await self._handle_cart_action(db, analysis, message_text, chat_id, message_data)
            
            else:  # general_conversation (ahora solo para saludos)
                messages = await self._handle_conversational_response(message_text, analysis)
                return {"type": "text_messages", "messages": messages}
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout procesando mensaje de chat {chat_id}")
            return {
                "type": "text_messages",
                "messages": ["⏱️ Lo siento, el procesamiento está tomando más tiempo del esperado. Por favor intenta nuevamente."]
            }
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de chat {chat_id}: {e}")
            return {
                "type": "text_messages", 
                "messages": ["❌ Lo siento, hubo un error procesando tu mensaje. Por favor intenta nuevamente."]
            }

    def _extract_json_from_markdown(self, content: str) -> str:
        """Extrae JSON de bloques de código markdown."""
        # Buscar bloques de código JSON
        json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
        
        # Buscar bloques de código genéricos
        code_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Si no hay bloques de código, devolver el contenido completo
        return content.strip()

    async def _handle_specific_product_inquiry(self, db: Session, analysis: Dict, message_text: str, chat_id: int) -> Dict[str, Any]:
        """Maneja consultas sobre un producto específico identificado por IA."""
        logger.info(f"Análisis de OpenAI para consulta específica: {analysis}")
        
        # Extraer el SKU del producto de la consulta
        product_reference = analysis.get('product_reference', message_text)
        sku = await self._resolve_product_reference(db, product_reference, chat_id, action_context='product_inquiry')
        
        if not sku:
            # Si no se pudo resolver, devolver un mensaje de texto claro al usuario.
            return {
                "type": "text_messages",
                "messages": [
                    f"🤔 No estoy seguro de a qué producto te refieres con \"{product_reference}\".",
                    "Para darte la información correcta, ¿podrías ser un poco más específico? Intenta incluir la marca, el modelo o alguna característica clave."
                ]
            }

        # Obtener el producto de la base de datos
        product = get_product_by_sku(db, sku=sku)
        if not product:
            return {
                "type": "text_messages",
                "messages": [f"No encontré ningún producto con la referencia '{sku}'. ¿Podrías verificarla?"]
            }

        # Guardar este producto como el más reciente en el contexto del usuario
        add_recent_product(db, chat_id, product.sku)

        # Generar la respuesta detallada
        response_content = await self._generate_detailed_product_response(product, message_text, db)
        
        # Devolver la estructura completa de la respuesta para que el endpoint la envíe
        return {
            "type": "product_with_image",
            "product": product,
            "caption": response_content["caption"],
            "additional_messages": response_content["additional_messages"],
            "photo_url": product.images[0].url if product.images else None,
        }

    async def _generate_detailed_product_response(self, product, original_question: str, db: Session) -> Dict[str, Any]:
        """Genera una respuesta conversacional y detallada sobre un producto específico."""
        # Obtener información del stock
        total_stock = get_total_stock_by_sku(db, product.sku)
        stock_status = self._get_stock_status(total_stock)

        # Preparar información del producto para el LLM
        product_info = {
            "sku": product.sku,
            "name": product.name,
            "description": product.description or "Sin descripción disponible",
            "price": float(product.price),
            "brand": product.brand or "Sin marca especificada",
            "category": product.category.name if product.category else "Sin categoría",
            "stock_status": stock_status, # Nuevo campo de stock
            "specifications": product.spec_json or {}
        }
        
        # Prompt para generar respuesta conversacional inteligente
        response_prompt = f"""
Eres un asistente experto en productos industriales de Macroferro. Un cliente te preguntó:

"{original_question}"

Y encontraste exactamente este producto en tu catálogo:

PRODUCTO ENCONTRADO:
- Nombre: {product_info['name']}
- SKU: {product_info['sku']}
- Descripción: {product_info['description']}
- Precio: ${product_info['price']:,.2f}
- Marca: {product_info['brand']}
- Categoría: {product_info['category']}
- Stock: {product_info['stock_status']}
- Especificaciones técnicas: {json.dumps(product_info['specifications'], indent=2, ensure_ascii=False)}

INSTRUCCIONES:
Vas a enviar la información en dos partes:

1. CAPTION DE IMAGEN (máximo 800 caracteres):
   - Información básica y atractiva del producto
   - INCLUYE SIEMPRE el estado del stock de forma prominente.
   - Incluye nombre, precio, marca de forma visual
   - Usa emojis apropiados (ej: ✅, ⚠️, ❌ para el stock)

2. MENSAJES ADICIONALES (separa con "|||"):
   - Detalles técnicos específicos
   - Especificaciones importantes
   - Aplicaciones recomendadas
   - Invitación a más preguntas

Formato de respuesta:
CAPTION:
[Tu caption de máximo 800 caracteres]

ADDITIONAL:
[Mensaje 1]|||[Mensaje 2]|||[Mensaje 3]

Usa *texto* para negrita, formato de lista con • para especificaciones, y emojis técnicos apropiados.
Responde en español de manera profesional y útil.
"""
        
        # Generar respuesta con LLM
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "user", "content": response_prompt}],
            temperature=0.7,  # Temperatura moderada para naturalidad
            max_tokens=1000,   # Espacio para caption + mensajes adicionales
            timeout=20.0
        )
        
        response_text = response.choices[0].message.content
        
        # Separar caption y mensajes adicionales
        if "CAPTION:" in response_text and "ADDITIONAL:" in response_text:
            parts = response_text.split("ADDITIONAL:")
            caption = parts[0].replace("CAPTION:", "").strip()
            additional_text = parts[1].strip()
            
            # Dividir mensajes adicionales
            additional_messages = [msg.strip() for msg in additional_text.split("|||") if msg.strip()]
        else:
            # Fallback si el formato no es el esperado
            messages = self.split_response_into_messages(response_text, 800)
            caption = messages[0] if messages else f"*{product.name}*\n💰 ${product.price:,.2f}"
            additional_messages = messages[1:] if len(messages) > 1 else []
        
        # Añadir el prompt de cómo añadir al carrito
        cart_prompt = "\n🛒 Para añadir al carrito, indica la cantidad que deseas (ej: 'añade 5 de estos' o 'agrega este producto')."
        additional_messages.append(cart_prompt)

        # Esta función SOLO devuelve el contenido de texto.
        return {
            "caption": caption,
            "additional_messages": additional_messages
        }

    async def _handle_catalog_inquiry(self, db: Session) -> Dict[str, Any]:
        """Maneja la solicitud general del catálogo mostrando las categorías principales."""
        logger.info("Manejando consulta de catálogo general.")
        try:
            top_level_categories = db.query(Category).filter(Category.parent_id.is_(None)).order_by(Category.name).all()

            if not top_level_categories:
                return {
                    "type": "text_messages",
                    "messages": ["Manejamos una gran variedad de productos industriales, pero no pude cargar las categorías en este momento. ¿Te interesa algún tipo de producto en particular?"]
                }

            category_names = [f"• {cat.name}" for cat in top_level_categories]
            message = (
                "¡Claro! En Macroferro somos especialistas en productos industriales. Estas son nuestras categorías principales:\n\n"
                + "\n".join(category_names)
                + "\n\n💡 Puedes preguntarme por cualquiera de ellas (ej: 'qué tienes en tornillería') para ver más detalles."
            )

            return {
                "type": "text_messages",
                "messages": [message]
            }
        except Exception as e:
            logger.error(f"Error al obtener las categorías principales: {e}")
            return {
                "type": "text_messages",
                "messages": ["Lo siento, tuve un problema al consultar nuestro catálogo. Por favor, intenta preguntando por un producto específico."]
            }

    async def _validate_search_relevance(self, query: str, result_names: List[str]) -> bool:
        """
        Valida si los resultados de búsqueda son relevantes para la consulta original.
        """
        if not self.openai_client or not result_names:
            return True # Asumir relevancia si no hay IA o resultados

        names_list = "\\n - ".join(result_names)
        prompt = f"""
        El usuario buscó: "{query}"
        Los resultados principales de la búsqueda fueron:
         - {names_list}

        ¿Son estos resultados una coincidencia directa y relevante para la búsqueda del usuario?
        Por ejemplo, si buscó "destornilladores" y los resultados son "tornillos", la respuesta es NO.
        Si buscó "herramientas" y el resultado es "taladro", la respuesta es SÍ.
        
        Responde únicamente con "SI" o "NO".
        """
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=5,
                timeout=10.0
            )
            answer = response.choices[0].message.content.strip().upper()
            logger.info(f"Validación de relevancia para '{query}': {answer}")
            return "SI" in answer
        except Exception as e:
            logger.error(f"Error en validación de relevancia con IA: {e}")
            return True # En caso de error, ser optimista para no bloquear al usuario

    async def _handle_product_search(self, db: Session, analysis: Dict, message_text: str, chat_id: int) -> List[str]:
        """
        Maneja búsquedas generales de productos con respuesta conversacional.
        Aplica umbrales de similitud para evitar resultados irrelevantes.
        """
        search_terms = analysis.get("search_terms", [])
        
        # Asegurar que search_terms sea una lista
        if search_terms is None:
            search_terms = []
            
        search_query = " ".join(search_terms) if search_terms else message_text
        
        logger.info(f"Realizando búsqueda general de productos para: {search_query}")
        
        # Búsqueda semántica usando ProductService con umbral moderado
        search_results = await self.product_service.search_products(
            db=db,
            query_text=search_query,
            top_k=5  # Limitar a 5 resultados potenciales
        )
        
        main_products = search_results.get("main_results", [])
        related_products = search_results.get("related_results", [])
        
        messages = []
        
        is_relevant = True
        if main_products:
            main_product_names = [p.name for p in main_products]
            is_relevant = await self._validate_search_relevance(search_query, main_product_names)

        # Si los resultados no son relevantes, tratarlos como si fueran "relacionados"
        if not is_relevant:
            # Mover todos los productos a la lista de relacionados y limpiar los principales
            related_products = main_products + related_products
            main_products = []
        
        # Unificar todos los productos en una sola lista para simplificar la presentación
        all_products = main_products + related_products
        
        # Eliminar duplicados por SKU, manteniendo el primero que aparece
        unique_products = []
        seen_skus = set()
        for product in all_products:
            if product.sku not in seen_skus:
                unique_products.append(product)
                seen_skus.add(product.sku)

        # Comprobar si hay resultados.
        if not unique_products:
             return [
                f"🔍 Busqué productos para: *{search_query}*",
                "❌ No encontré ningún producto que coincida con tu búsqueda.\n\n💡 Intenta con otros términos o sé más general."
            ]

        # Formatear la respuesta
        initial_message = f"🔍 Encontré estos productos para tu búsqueda de *{search_query}*:"
        messages.append(initial_message)
        
        # Registrar productos como vistos recientemente
        for product in unique_products:
            add_recent_product(db, chat_id, product.sku)
        
        # Mostrar productos
        for i, product in enumerate(unique_products, 1):
            product_message = f"*{i}. {product.name}*\n"
            if product.description:
                desc = product.description[:120] + "..." if len(product.description) > 120 else product.description
                product_message += f"📝 {desc}\n"
            product_message += f"💰 Precio: *${product.price:,.0f}*\n"
            if product.category:
                product_message += f"🏷️ {product.category.name}\n"
            if hasattr(product, 'brand') and product.brand:
                product_message += f"🏭 {product.brand}\n"
            
            messages.append(product_message)

        # Mensaje final conversacional
        follow_up = (
            "\n💬 ¿Te interesa conocer más detalles de alguno de estos productos?\n\n"
            "💡 Para añadir al carrito, indica el producto y la cantidad (ej: 'añade 5 de esos tornillos')."
        )
        messages.append(follow_up)
        
        return messages

    async def _handle_technical_question(self, db: Session, analysis: Dict, message_text: str, chat_id: int) -> List[str]:
        """
        Maneja preguntas técnicas específicas sobre especificaciones de productos.
        
        Esta función analiza preguntas técnicas y trata de proporcionar respuestas
        precisas basadas en las especificaciones de productos relevantes.
        """
        search_terms = analysis.get("search_terms", [])
        technical_aspect = analysis.get("technical_aspect", "")
        
        # Asegurar que search_terms sea una lista
        if search_terms is None:
            search_terms = []
        
        # Si no hay términos de búsqueda específicos, extraer del mensaje
        if not search_terms:
            search_terms = message_text.split()
        
        search_query = " ".join(search_terms) if search_terms else message_text
        
        logger.info(f"Analizando pregunta técnica: {technical_aspect} para búsqueda: {search_query}")
        
        # Buscar productos relevantes para la pregunta técnica
        search_results = await self.product_service.search_products(
            db=db,
            query_text=search_query,
            top_k=3  # Pocos productos pero relevantes
        )
        
        main_products = search_results.get("main_results", [])
        
        if not main_products:
            return [
                f"🔍 Busqué información técnica sobre: *{search_query}*",
                "❌ No encontré productos con especificaciones técnicas específicas para esa consulta.\n\n💡 ¿Podrías ser más específico sobre el producto que te interesa?"
            ]
        
        # Registrar productos como vistos recientemente
        for product in main_products:
            add_recent_product(db, chat_id, product.sku)
        
        # Analizar especificaciones técnicas con IA
        technical_analysis = await self._analyze_technical_specifications(
            main_products, 
            technical_aspect or message_text, 
            message_text
        )
        
        # Dividir respuesta técnica en mensajes naturales
        messages = self.split_response_into_messages(technical_analysis, 3800)
        
        return messages

    async def _handle_conversational_response(self, message_text: str, analysis: Dict) -> List[str]:
        """
        Maneja respuestas conversacionales generales con personalidad de vendedor experto.
        """
        logger.info(f"Generando respuesta conversacional para: {analysis.get('user_intent_description', 'unknown')}")
        
        conversation_prompt = f"""
Eres un asistente especializado de Macroferro, una empresa que vende productos industriales de alta calidad.

El usuario te escribió: "{message_text}"

CONTEXTO DE MACROFERRO:
- Vendemos productos industriales: tuberías, válvulas, herramientas eléctricas, conectores, tornillos, pinturas industriales, etc.
- Atendemos principalmente clientes profesionales (electricistas, plomeros, constructores, talleres)
- Tenemos un catálogo amplio con especificaciones técnicas detalladas
- Brindamos asesoría técnica especializada
- Somos expertos en compatibilidad y aplicaciones de productos

TU PERSONALIDAD:
- Profesional pero amigable y conversacional
- Experto técnico que conoce bien los productos
- Orientado a ayudar y resolver problemas
- Proactivo en sugerir soluciones

INSTRUCCIONES:
1. Responde de manera natural y conversacional
2. Si es un saludo, salúdalo cordialmente y preséntate como experto en productos industriales
3. Si pregunta sobre la empresa, comparte información relevante
4. Si la consulta es vaga, haz preguntas específicas para ayudar mejor
5. Siempre orienta hacia productos específicos cuando sea posible
6. Usa emojis apropiados para hacer la conversación más amigable
7. Divide en 2-3 mensajes si es necesario (separa con "|||")
8. Invita a hacer consultas específicas sobre productos
9. Mantén un tono experto pero accesible

Responde de manera útil y orientada a la acción.
"""
        
        if not self.openai_client:
            # Respuesta estática si no hay OpenAI configurado
            if any(greeting in message_text.lower() for greeting in ['hola', 'buenos', 'buenas', 'hello', 'hi', 'saludos']):
                return [
                    "¡Hola! 👋 Soy el asistente técnico de Macroferro.",
                    "🔧 Estoy aquí para ayudarte con información sobre nuestros productos industriales: tuberías, válvulas, herramientas, conectores, pinturas y más.\n\n💬 ¿En qué puedo ayudarte hoy?"
                ]
            else:
                return [
                    "👋 ¡Hola! Soy el asistente de Macroferro.",
                    "🔍 Puedo ayudarte a encontrar productos industriales y responder preguntas técnicas.\n\n💡 Prueba preguntándome por algún producto específico o tipo de material que necesites."
                ]
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[{"role": "user", "content": conversation_prompt}],
                temperature=0.8,    # Temperatura más alta para conversación natural
                max_tokens=500,
                timeout=15.0
            )
            
            response_text = response.choices[0].message.content
            
            # Dividir si incluye separador
            if "|||" in response_text:
                messages = [msg.strip() for msg in response_text.split("|||") if msg.strip()]
            else:
                messages = self.split_response_into_messages(response_text, 3800)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error generando respuesta conversacional: {e}")
            return [
                "👋 ¡Hola! Soy el asistente de Macroferro.",
                "🔍 Estoy aquí para ayudarte con información sobre productos industriales.\n\n💬 ¿En qué puedo ayudarte?"
            ]

    # ========================================
    # ANÁLISIS TÉCNICO DE ESPECIFICACIONES
    # ========================================
    
    async def _analyze_technical_specifications(
        self, 
        products: List, 
        technical_aspect: str, 
        original_question: str
    ) -> str:
        """
        Analiza las especificaciones técnicas de productos y genera respuesta inteligente.
        
        Esta función examina el campo spec_json de cada producto para encontrar
        información técnica relevante y generar respuestas detalladas usando IA.
        
        Args:
            products: Lista de productos relevantes encontrados
            technical_aspect: Aspecto técnico específico (diámetro, presión, etc.)
            original_question: Pregunta original del usuario para contexto
            
        Returns:
            Respuesta formateada con información técnica detallada
        """
        try:
            # Recopilar información técnica de todos los productos
            technical_info = []
            for product in products:
                product_info = {
                    "name": product.name,
                    "sku": product.sku,
                    "brand": product.brand,
                    "category": product.category.name if product.category else "Sin categoría",
                    "price": float(product.price),
                    "specifications": product.spec_json or {}
                }
                technical_info.append(product_info)
            
            # Crear prompt para análisis técnico con IA
            technical_prompt = f"""
El usuario preguntó: "{original_question}"

Se identificó que busca información sobre: {technical_aspect}

Aquí están los productos relevantes con sus especificaciones técnicas:

{json.dumps(technical_info, indent=2, ensure_ascii=False)}

Tu tarea es analizar estas especificaciones y responder la pregunta técnica del usuario de manera clara y profesional.

Instrucciones:
1. Busca en las especificaciones (campo "specifications") información relacionada con la pregunta
2. Si encuentras datos relevantes, preséntalos de forma clara y organizada
3. Compara entre productos si hay múltiples opciones
4. Si no hay información específica en las especificaciones, indícalo honestamente
5. Usa formato Markdown para mejor presentación
6. Incluye emojis técnicos apropiados (⚙️ 📐 🔧 💧 ⚡ etc.)
7. Mantén un tono profesional pero accesible
8. Si es posible, da recomendaciones basadas en la información disponible

Responde en español de manera concisa pero completa.
"""
            
            # Generar respuesta técnica con IA
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[{"role": "user", "content": technical_prompt}],
                temperature=0.3,    # Baja temperatura para precisión técnica
                max_tokens=800,     # Más espacio para respuestas técnicas detalladas
                timeout=20.0        # Timeout generoso para análisis complejo
            )
            
            ai_response = response.choices[0].message.content
            
            # Agregar footer con productos analizados
            footer = f"\n\n*📋 Productos analizados:*\n"
            for i, product in enumerate(products, 1):
                footer += f"{i}. {product.name} (SKU: {product.sku})\n"
            
            footer += "\n💬 ¿Necesitas más detalles específicos de algún producto?"
            
            return ai_response + footer
            
        except Exception as e:
            logger.error(f"Error analizando especificaciones técnicas: {e}")
            
            # Fallback: respuesta básica con información disponible
            response_text = f"🔧 *Información técnica encontrada:*\n\n"
            
            for i, product in enumerate(products, 1):
                response_text += f"*{i}. {product.name}*\n"
                response_text += f"📦 SKU: {product.sku}\n"
                if product.brand:
                    response_text += f"🏭 Marca: {product.brand}\n"
                if product.category:
                    response_text += f"🏷️ Categoría: {product.category.name}\n"
                
                # Mostrar especificaciones si existen
                if product.spec_json:
                    response_text += f"⚙️ *Especificaciones disponibles:*\n"
                    for key, value in product.spec_json.items():
                        response_text += f"  • {key}: {value}\n"
                else:
                    response_text += f"📝 No hay especificaciones técnicas detalladas disponibles\n"
                
                response_text += "\n"
            
            response_text += "💬 Para información técnica más específica, puedes contactar directamente con nuestro equipo técnico."
            
            return response_text

    # ========================================
    # CONFIGURACIÓN DE WEBHOOK
    # ========================================
    
    async def set_webhook(self, webhook_url: str, secret_token: str) -> Dict[str, Any]:
        """
        Configura el webhook de Telegram para recibir actualizaciones en tiempo real.
        
        Esta función establece la URL donde Telegram enviará todas las actualizaciones
        del bot (mensajes, comandos, etc.) usando el mecanismo de webhook en lugar
        de polling, lo cual es más eficiente para aplicaciones en producción.
        
        Args:
            webhook_url: URL completa donde Telegram enviará las actualizaciones
            secret_token: Token secreto para validar que las actualizaciones vienen de Telegram
            
        Returns:
            Respuesta JSON del API de Telegram confirmando la configuración
            
        Consideraciones de seguridad:
        - webhook_url debe usar HTTPS en producción
        - secret_token debe ser único y seguro (min 1-256 caracteres)
        - Telegram validará el certificado SSL de la URL
        - La URL debe ser públicamente accesible desde servidores de Telegram
        
        Configuración típica para producción:
        - webhook_url: "https://api.macroferro.com/api/v1/telegram/webhook"
        - secret_token: Token generado aleatoriamente y guardado en variables de entorno
        
        Ventajas del webhook vs polling:
        - Latencia mucho menor (instantáneo vs 1-30 segundos)
        - Menor uso de ancho de banda
        - No requiere conexiones persistentes
        - Escalabilidad horizontal mejor
        
        Consideraciones de infraestructura:
        - Requiere HTTPS válido en producción
        - Load balancer debe enrutar al contenedor correcto
        - Manejo de reintentos si el webhook falla temporalmente
        - Monitoreo de salud del endpoint del webhook
        
        Extensiones futuras:
        - Validación automática del secret_token en el endpoint
        - Métricas de latencia y éxito de webhooks
        - Fallback a polling si webhook falla persistentemente
        - Configuración de allowed_updates para filtrar tipos de eventos
        """
        if not self.api_base_url:
            logger.error("Bot token no configurado, no se puede configurar webhook")
            raise ValueError("Telegram bot token not configured")
            
        url = f"{self.api_base_url}/setWebhook"
        payload = {
            "url": webhook_url,
            "secret_token": secret_token,
            # Futuras configuraciones opcionales:
            # "allowed_updates": ["message", "callback_query"],  # Filtrar tipos de eventos
            # "drop_pending_updates": True,  # Limpiar actualizaciones pendientes
            # "max_connections": 100,  # Límite de conexiones concurrentes
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                if result.get("ok"):
                    logger.info(f"Webhook configurado exitosamente: {webhook_url}")
                else:
                    logger.error(f"Error configurando webhook: {result}")
                    
                return result
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout configurando webhook: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP configurando webhook: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado configurando webhook: {e}")
            raise

    # --- NUEVOS HANDLERS PARA EL CARRITO ---

    def _get_api_client(self) -> httpx.AsyncClient:
        """Crea un cliente HTTP para comunicarse con la propia API del backend."""
        # La API se ejecuta en el mismo host, por lo que podemos usar localhost
        base_url = f"http://localhost:{settings.PORT}{settings.API_V1_STR}"
        return httpx.AsyncClient(base_url=base_url, timeout=10.0)

    def _format_cart_data(self, cart_data: Dict[str, Any]) -> str:
        """Formatea los datos del carrito para una respuesta clara en Telegram."""
        items = cart_data.get("items", {})
        total_price = cart_data.get("total_price", 0.0)

        if not items:
            return "🛒 Tu carrito está vacío."

        response_text = "🛒 *Tu Carrito de Compras*\n\n"
        for sku, item_details in items.items():
            product_info = json.loads(item_details['product'])
            product_name = product_info.get("name", "Producto desconocido")
            quantity = item_details.get("quantity", 0)
            price = product_info.get("price", 0)
            subtotal = quantity * price
            response_text += f"▪️ *{product_name}* ({sku})\n"
            response_text += f"    `{quantity} x ${price:,.2f} = ${subtotal:,.2f}`\n\n"
        
        response_text += f"\n*Total: ${total_price:,.2f}*"
        response_text += "\n\n💡 Puedes seguir *buscando productos*, *ver tu carrito* (o con `/ver_carrito`)"
        response_text +=" o indicar que quieres ya *finalizar la compra* (o con `/finalizar_compra`)."

        return response_text

    async def _handle_add_to_cart(self, chat_id: int, args: List[str], db: Session) -> Dict[str, Any]:
        """Maneja el comando /agregar."""
        if not args:
            return {
                "type": "text_messages",
                "messages": ["Uso: /agregar <SKU> [cantidad]"]
            }
        
        sku = args[0]
        try:
            quantity = int(args[1]) if len(args) > 1 else 1
            if quantity <= 0:
                return {
                    "type": "text_messages",
                    "messages": ["La cantidad debe ser un número positivo."]
                }
        except ValueError:
            return {
                "type": "text_messages",
                "messages": ["La cantidad debe ser un número."]
            }

        try:
            async with self._get_api_client() as client:
                response = await client.post(
                    f"/cart/{chat_id}/items",
                    json={"product_sku": sku, "quantity": quantity}
                )
                
                if response.status_code == 404:
                    return {
                        "type": "text_messages",
                        "messages": [f"😕 No se encontró ningún producto con el SKU: {sku}"]
                    }
                
                response.raise_for_status()
                
                # Registrar el producto agregado como visto recientemente
                add_recent_product(db, chat_id, sku)
                
                cart_data = response.json()
                response_text = "✅ *Producto añadido*\n\n"
                response_text += self._format_cart_data(cart_data)
                
                return {
                    "type": "text_messages",
                    "messages": [response_text]
                }

        except httpx.HTTPError as e:
            logger.error(f"Error de API al añadir al carrito para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["Lo siento, ocurrió un error al intentar añadir el producto al carrito."]
            }
        except Exception as e:
            logger.error(f"Error inesperado al añadir al carrito para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["Ocurrió un error inesperado. Por favor, intenta de nuevo."]
            }

    async def _handle_view_cart(self, db: Session, chat_id: int) -> Dict[str, Any]:
        """Maneja el comando /ver_carrito."""
        try:
            async with self._get_api_client() as client:
                response = await client.get(f"/cart/{chat_id}")
                response.raise_for_status()
                cart_data = response.json()
                
                # Registrar productos del carrito como vistos recientemente
                items = cart_data.get("items", {})
                for sku in items.keys():
                    add_recent_product(db, chat_id, sku)
                
                response_text = self._format_cart_data(cart_data)
                
                return {
                    "type": "text_messages",
                    "messages": [response_text]
                }

        except httpx.HTTPError as e:
            logger.error(f"Error de API al ver el carrito para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["Lo siento, ocurrió un error al recuperar tu carrito."]
            }
        except Exception as e:
            logger.error(f"Error inesperado al ver el carrito para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["Ocurrió un error inesperado. Por favor, intenta de nuevo."]
            }

    async def _handle_remove_from_cart(self, chat_id: int, args: List[str]) -> Dict[str, Any]:
        """Maneja el comando /eliminar."""
        if not args:
            return {
                "type": "text_messages",
                "messages": ["Uso: /eliminar <SKU>"]
            }
        
        sku = args[0]
        try:
            async with self._get_api_client() as client:
                response = await client.delete(f"/cart/{chat_id}/items/{sku}")
                
                if response.status_code == 404: # El endpoint devuelve 204 si tiene éxito, no 404 si no encuentra el item.
                    # Esta lógica puede que no sea necesaria dependiendo de la implementación de la API.
                    # Asumimos que si no lo encuentra, no hay error.
                    pass

                response.raise_for_status()
                
                return {
                    "type": "text_messages",
                    "messages": [f"🗑️ Producto `{sku}` eliminado del carrito."]
                }

        except httpx.HTTPError as e:
            logger.error(f"Error de API al eliminar del carrito para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": [f"Lo siento, ocurrió un error al intentar eliminar el producto `{sku}`."]
            }
        except Exception as e:
            logger.error(f"Error inesperado al eliminar del carrito para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["Ocurrió un error inesperado. Por favor, intenta de nuevo."]
            }

    async def _handle_clear_cart(self, chat_id: int) -> Dict[str, Any]:
        """Maneja el comando /vaciar_carrito."""
        try:
            async with self._get_api_client() as client:
                # Obtenemos el carrito para saber qué items borrar
                get_response = await client.get(f"/cart/{chat_id}")
                get_response.raise_for_status()
                cart_data = get_response.json()
                items_to_delete = cart_data.get("items", {}).keys()

                if not items_to_delete:
                    return {
                        "type": "text_messages",
                        "messages": ["Tu carrito ya está vacío."]
                    }

                # Borramos cada item
                for sku in items_to_delete:
                    await client.delete(f"/cart/{chat_id}/items/{sku}")
                
                return {
                    "type": "text_messages",
                    "messages": ["✅ Tu carrito ha sido vaciado."]
                }

        except httpx.HTTPError as e:
            logger.error(f"Error de API al vaciar el carrito para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["Lo siento, ocurrió un error al intentar vaciar tu carrito."]
            }
        except Exception as e:
            logger.error(f"Error inesperado al vaciar el carrito para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["Ocurrió un error inesperado. Por favor, intenta de nuevo."]
            }
        
    async def _handle_checkout(self, db: Session, chat_id: int, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Maneja el comando /finalizar_compra con recolección de datos del cliente."""
        try:
            async with self._get_api_client() as client:
                # 1. Verificar si el carrito está vacío
                get_response = await client.get(f"/cart/{chat_id}")
                get_response.raise_for_status()
                cart_data = get_response.json()
                if not cart_data.get("items"):
                    return {
                        "type": "text_messages",
                        "messages": ["🛒 Tu carrito está vacío. No puedes finalizar una compra."]
                    }

                # 2. Mostrar resumen del carrito y comenzar recolección de datos
                cart_summary = self._format_cart_data(cart_data)
                
                # Limpiar cualquier acción pendiente anterior
                clear_pending_action(db, chat_id)
                
                # Iniciar el proceso de recolección de datos
                set_pending_action(db, chat_id, "checkout_collect_name", {})
                
                initial_message = (
                    f"✅ *Proceso de Compra Iniciado*\n\n"
                    f"{cart_summary}\n\n"
                    f"📋 *Ahora necesito algunos datos para completar tu pedido:*\n\n"
                    f"👤 Por favor, envíame tu *nombre completo*:"
                )
                
                return {
                    "type": "text_messages",
                    "messages": [initial_message]
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                return {
                    "type": "text_messages",
                    "messages": ["🛒 Tu carrito está vacío, no se puede finalizar la compra."]
                }
            else:
                logger.error(f"Error de API en checkout para chat {chat_id}: {e}")
                return {
                    "type": "text_messages",
                    "messages": ["❌ Lo siento, ocurrió un error al procesar tu pedido."]
                }
        except Exception as e:
            logger.error(f"Error inesperado en checkout para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["❌ Ocurrió un error inesperado. Por favor, intenta de nuevo."]
            }

    async def _process_checkout_data_collection(self, db: Session, chat_id: int, message_text: str, current_action: str, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa la recolección de datos del cliente paso a paso."""
        
        if current_action == "checkout_collect_name":
            # Validar nombre
            name = message_text.strip()
            if len(name) < 2:
                return {
                    "type": "text_messages",
                    "messages": ["❌ Por favor, ingresa un nombre válido (mínimo 2 caracteres):"]
                }
            
            # Guardar nombre y pedir email
            action_data["name"] = name
            set_pending_action(db, chat_id, "checkout_collect_email", action_data)
            
            return {
                "type": "text_messages",
                "messages": [f"✅ Perfecto, *{name}*\n\n📧 Ahora envíame tu *correo electrónico*:"]
            }
            
        elif current_action == "checkout_collect_email":
            # Validar email
            email = message_text.strip().lower()
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                return {
                    "type": "text_messages",
                    "messages": ["❌ Por favor, ingresa un correo electrónico válido:"]
                }
            
            # Guardar email y pedir teléfono
            action_data["email"] = email
            set_pending_action(db, chat_id, "checkout_collect_phone", action_data)
            
            return {
                "type": "text_messages",
                "messages": [f"✅ Email guardado: *{email}*\n\n📱 Ahora envíame tu *número de teléfono*:"]
            }
            
        elif current_action == "checkout_collect_phone":
            # Validar teléfono
            phone = message_text.strip()
            # Remover espacios y caracteres especiales para validación
            phone_clean = re.sub(r'[^\d+]', '', phone)
            if len(phone_clean) < 8:
                return {
                    "type": "text_messages",
                    "messages": ["❌ Por favor, ingresa un número de teléfono válido:"]
                }
            
            # Guardar teléfono y pedir dirección
            action_data["phone"] = phone
            set_pending_action(db, chat_id, "checkout_collect_address", action_data)
            
            return {
                "type": "text_messages",
                "messages": [f"✅ Teléfono guardado: *{phone}*\n\n🏠 Por último, envíame tu *dirección de envío completa*:"]
            }
            
        elif current_action == "checkout_collect_address":
            # Validar dirección
            address = message_text.strip()
            if len(address) < 10:
                return {
                    "type": "text_messages",
                    "messages": ["❌ Por favor, ingresa una dirección más completa (mínimo 10 caracteres):"]
                }
            
            # Guardar dirección y finalizar compra
            action_data["address"] = address
            
            # Finalizar la compra con todos los datos recolectados
            return await self._finalize_checkout_with_customer_data(db, chat_id, action_data)
        
        return {
            "type": "text_messages",
            "messages": ["❌ Error en el proceso de recolección de datos."]
        }

    async def _handle_cart_action(self, db: Session, analysis: Dict, message_text: str, chat_id: int, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maneja acciones de carrito (agregar, quitar, ver, vaciar, finalizar)
        
        Args:
            db: Sesión de base de datos
            analysis: Análisis de IA del mensaje
            message_text: Texto original del mensaje
            chat_id: ID del chat
            message_data: Datos completos del mensaje
            
        Returns:
            Dict con tipo de respuesta y mensajes
        """
        action = analysis.get("cart_action", "unknown")
        confidence = analysis.get("confidence", 0.5)
        
        logger.info(f"Acción de carrito detectada: {action} con confianza {confidence}")
        
        # Si la confianza es muy baja, solicitar aclaración
        if confidence < 0.6:
            return {
                "type": "text_messages",
                "messages": ["🤔 No estoy seguro de entender qué quieres hacer con el carrito. Puedes usar comandos como:\n\n• **Ver carrito**: 'muéstrame mi carrito'\n• **Agregar**: 'agrega [producto] al carrito'\n• **Quitar**: 'quita [producto] del carrito'\n• **Vaciar**: 'vacía mi carrito'\n• **Finalizar**: 'finalizar compra'"]
            }
        
        try:
            if action == "view":
                return await self._handle_view_cart(db, chat_id)
            elif action == "clear":
                return await self._handle_clear_cart(chat_id)
            elif action == "checkout":
                return await self._handle_checkout(db, chat_id, message_data)
            elif action == "add":
                return await self._handle_natural_add_to_cart(db, analysis, chat_id)
            elif action == "remove":
                return await self._handle_natural_remove_from_cart(db, analysis, chat_id)
            else:
                return {
                    "type": "text_messages",
                    "messages": [f"🤖 Detecté que quieres hacer algo con el carrito, pero no pude entender exactamente qué. ¿Podrías ser más específico?"]
                }
                
        except Exception as e:
            logger.error(f"Error al procesar acción de carrito {action}: {e}")
            return {
                "type": "text_messages",
                "messages": ["❌ Lo siento, ocurrió un error al procesar tu solicitud del carrito. Por favor, intenta de nuevo."]
            }

    def _parse_quantity_from_text(self, text: str) -> (Optional[int], str):
        """
        Extrae cantidad numérica del texto y devuelve el texto limpio.
        Maneja patrones como:
        - "5 tornillos" -> (5, "tornillos")
        - "Dame 4 del número 5" -> (4, "número 5")
        - "Ponme 3 del 2" -> (3, "2")
        - "Agrega 10 de esos" -> (10, "esos")
        """
        if not text:
            return None, ""
        
        # Patrón para capturar cantidad + referencia por número de orden
        # Ejemplos: "dame 4 del número 5", "ponme 3 del 2", "agrega 2 del numero 1"
        order_pattern = r'(?:dame|ponme|agrega|añade|quiero)\s*(\d+)\s*(?:del?|de)\s*(?:número|numero)?\s*(\d+)'
        order_match = re.search(order_pattern, text.lower())
        
        if order_match:
            quantity = int(order_match.group(1))
            order_number = order_match.group(2)
            # Construir referencia limpia
            reference = f"número {order_number}"
            logger.info(f"Patrón de cantidad + orden detectado: {quantity} del {reference}")
            return quantity, reference
        
        # Patrón general para cantidad seguida de producto
        # Ejemplos: "5 tornillos", "10 de esos", "3 martillos"
        general_pattern = r'(?:dame|ponme|agrega|añade|quiero)?\s*(\d+)\s*(?:de\s+)?(.+)'
        general_match = re.search(general_pattern, text.lower())
        
        if general_match:
            quantity_str = general_match.group(1)
            remaining_text = general_match.group(2).strip()
            
            try:
                quantity = int(quantity_str)
                logger.info(f"Cantidad extraída: {quantity}, texto restante: '{remaining_text}'")
                return quantity, remaining_text
            except ValueError:
                pass
        
        # Si no se encuentra patrón específico, buscar el primer número
        number_match = re.search(r'\b(\d+)\b', text)
        if number_match:
            try:
                quantity = int(number_match.group(1))
                # Remover el número del texto
                cleaned_text = re.sub(r'\b' + re.escape(number_match.group(1)) + r'\b', '', text, count=1).strip()
                # Limpiar espacios extra y palabras comunes al inicio
                cleaned_text = re.sub(r'^(?:de|del|la|el|los|las)\s+', '', cleaned_text.strip())
                logger.info(f"Número encontrado: {quantity}, texto limpio: '{cleaned_text}'")
                return quantity, cleaned_text
            except ValueError:
                pass
        
        logger.info(f"No se encontró cantidad en: '{text}'")
        return None, text

    async def _handle_natural_add_to_cart(self, db: Session, analysis: Dict, chat_id: int) -> Dict[str, Any]:
        """
        Maneja añadir productos al carrito usando lenguaje natural.
        """
        product_reference = analysis.get("cart_product_reference", "")
        quantity = analysis.get("cart_quantity")

        # Si la IA no extrajo la cantidad, intentar parsearla desde el texto
        if not quantity and product_reference:
            parsed_quantity, cleaned_reference = self._parse_quantity_from_text(product_reference)
            if parsed_quantity:
                quantity = parsed_quantity
                product_reference = cleaned_reference

        # Si no se especifica cantidad, usar 1 por defecto
        if not quantity or not isinstance(quantity, (int, str)) or str(quantity).strip() == "":
            quantity = 1
        else:
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    quantity = 1
            except (ValueError, TypeError):
                quantity = 1
        
        is_update_request = analysis.get("is_update", False)
        action_context = 'update' if is_update_request else 'add'

        # Resolver la referencia del producto a un SKU
        if product_reference:
            sku = await self._resolve_product_reference(db, product_reference, chat_id, action_context=action_context)
            if not sku:
                # Mensaje de error específico si se intentaba actualizar algo que no está en el carro
                if is_update_request:
                    return {
                        "type": "text_messages",
                        "messages": [f"🤔 No encontré '{product_reference}' en tu carrito para añadir más. ¿Quizás quisiste decir otro producto?"]
                    }
                return {
                    "type": "text_messages",
                    "messages": [f"🤔 No pude identificar qué producto quieres agregar: '{product_reference}'. ¿Podrías ser más específico o usar el SKU del producto?"]
                }
        else:
            # Si no hay referencia específica, intentar usar el producto más reciente
            recent_products_skus = get_recent_products(db, chat_id)
            if recent_products_skus:
                sku = recent_products_skus[0] # Se asume el más reciente
            else:
                return {
                    "type": "text_messages",
                    "messages": ["🤔 No pude identificar qué producto quieres agregar. ¿Podrías especificar el producto o usar su SKU?"]
                }
        
        # Usar la función existente de agregar al carrito
        response = await self._handle_add_to_cart(chat_id, [sku, str(quantity)], db)
        
        # NO usar _create_cart_confirmation_response porque _handle_add_to_cart ya retorna un mensaje completo
        # Solo añadir las instrucciones adicionales al final del mensaje existente
        if response.get("type") == "text_messages" and response.get("messages"):
            # Agregar las instrucciones al final del mensaje existente
            original_message = response["messages"][0]
            instructions = (
                "\n\n💡 Puedes seguir *buscando productos*, *ver tu carrito* (o con `/ver_carrito`)"
                " o indicar que quieres ya *finalizar la compra* (o con `/finalizar_compra`)."
            )
            response["messages"][0] = original_message + instructions
        
        return response

    async def _handle_natural_remove_from_cart(self, db: Session, analysis: Dict, chat_id: int) -> Dict[str, Any]:
        """
        Maneja quitar productos o reducir su cantidad del carrito usando lenguaje natural.
        """
        product_reference = analysis.get("cart_product_reference", "")
        quantity_to_remove = analysis.get("cart_quantity")

        # Si la IA no extrajo la cantidad, intentar parsearla desde el texto
        if not quantity_to_remove and product_reference:
            parsed_quantity, cleaned_reference = self._parse_quantity_from_text(product_reference)
            if parsed_quantity:
                quantity_to_remove = parsed_quantity
                product_reference = cleaned_reference

        if not product_reference:
            return {
                "type": "text_messages",
                "messages": ["🤔 No pude identificar qué producto quieres quitar. Por favor, sé más específico."]
            }
            
        sku = await self._resolve_product_reference(db, product_reference, chat_id, action_context='remove')
        if not sku:
            return {
                "type": "text_messages",
                "messages": [f"🤔 No pude identificar qué producto quieres quitar: '{product_reference}'. ¿Podrías ser más específico o usar el SKU del producto?"]
            }
        
        # Si se especifica una cantidad, reducirla
        if quantity_to_remove and isinstance(quantity_to_remove, (int, float)) and quantity_to_remove > 0:
            try:
                async with self._get_api_client() as client:
                    # Llamar al endpoint de agregar con cantidad negativa para reducir
                    response = await client.post(
                        f"/cart/{chat_id}/items",
                        json={"product_sku": sku, "quantity": -int(quantity_to_remove)}
                    )
                    
                    if response.status_code == 404:
                        return {"type": "text_messages", "messages": [f"😕 El producto con SKU {sku} no se encontró en tu carrito."]}
                    
                    response.raise_for_status()
                    cart_data = response.json()
                    
                    product_name = "producto"
                    if sku in cart_data.get("items", {}):
                         product_info = json.loads(cart_data["items"][sku]['product'])
                         product_name = product_info.get("name", sku)
                    
                    # Verificar si el producto fue eliminado completamente
                    if sku not in cart_data.get("items", {}):
                        response_text = f"🗑️ Se ha eliminado completamente el producto *{product_name}* ({sku}) del carrito."
                    else:
                        response_text = f"✅ Se han eliminado {int(quantity_to_remove)} unidad(es) de *{product_name}*."
                    
                    response_text += "\n\n" + self._format_cart_data(cart_data)

                    return await self._create_cart_confirmation_response(
                        chat_id=chat_id,
                        initial_message="", # El mensaje ya está completo
                        cart_content=response_text
                    )

            except httpx.HTTPError as e:
                logger.error(f"Error de API al reducir cantidad para chat {chat_id}: {e}")
                error_msg = "Lo siento, ocurrió un error al actualizar el carrito."
                if e.response.status_code == 400: # Por si la API devuelve un error específico
                    try:
                        error_detail = e.response.json().get("detail")
                        if error_detail:
                            error_msg = f"😕 Error: {error_detail}"
                    except:
                        pass
                return {"type": "text_messages", "messages": [error_msg]}
            except Exception as e:
                logger.error(f"Error inesperado al reducir cantidad para chat {chat_id}: {e}")
                return {"type": "text_messages", "messages": ["Ocurrió un error inesperado. Por favor, intenta de nuevo."]}
        else:
            # Si no se especifica cantidad, debemos resolver la referencia
            sku_or_ambiguous = await self._resolve_product_reference(db, product_reference, chat_id, action_context='remove')

            if not sku_or_ambiguous:
                return {
                    "type": "text_messages",
                    "messages": [f"🤔 No pude identificar qué producto quieres quitar: '{product_reference}'. ¿Podrías ser más específico o usar el SKU del producto?"]
                }

            if sku_or_ambiguous.startswith("AMBIGUOUS_REFERENCE|"):
                parts = sku_or_ambiguous.split("|")[1]
                products_info = [p.split(":", 1) for p in parts.split(";")]
                
                message = f"🤔 Encontré varios productos en tu carrito que coinciden con '{product_reference}'. ¿A cuál te refieres?\n"
                for sku, name in products_info:
                    message += f"\n• *{name}* (SKU: `{sku}`)"
                message += "\n\n💡 Por favor, intenta de nuevo usando el SKU para ser más preciso (ej: `/eliminar {products_info[0][0]}`)."
                return {"type": "text_messages", "messages": [message]}

            # Si llegamos aquí, es un SKU único y se elimina el producto completo.
            sku = sku_or_ambiguous
            response = await self._handle_remove_from_cart(chat_id, [sku])
            if response.get("type") == "text_messages":
                 return await self._create_cart_confirmation_response(
                    chat_id=chat_id,
                    initial_message=f"🗑️ Producto `{sku}` eliminado del carrito.\n",
                    cart_content="" # El carrito se mostrará a continuación
                )
            return response

    async def _resolve_product_reference(self, db: Session, reference: str, chat_id: int, action_context: str = 'search') -> str:
        """
        Resuelve una referencia de producto a un SKU. La estrategia cambia según el contexto de la acción.
        - 'remove'/'update': Busca la referencia EXCLUSIVAMENTE dentro del carrito.
        - 'add'/'product_inquiry'/'search': Busca primero en el contexto (carrito + recientes) para resolver referencias relativas, luego semánticamente.
        """
        if not reference:
            return ""

        # --- PASO 0: MANEJO DE REFERENCIAS POR NÚMERO DE ORDEN ---
        # Detectar referencias como "número 5", "el 5", "del 5", etc.
        import re
        number_pattern = r'(?:número|numero|del|el)\s*(\d+)|^(\d+)$'
        number_match = re.search(number_pattern, reference.lower().strip())
        
        if number_match:
            order_number = int(number_match.group(1) or number_match.group(2))
            logger.info(f"Referencia por número de orden detectada: {order_number}")
            
            # Obtener productos recientes en orden
            recent_skus = get_recent_products(db, chat_id, limit=20)
            if recent_skus and 1 <= order_number <= len(recent_skus):
                selected_sku = recent_skus[order_number - 1]  # Convertir a índice 0-based
                product = get_product_by_sku(db, selected_sku)
                if product:
                    logger.info(f"Referencia por número {order_number} resuelta a: {product.name} ({selected_sku})")
                    return selected_sku
            else:
                logger.warning(f"Número de orden {order_number} fuera de rango. Productos disponibles: {len(recent_skus) if recent_skus else 0}")
                return ""

        # --- PASO 1: MANEJO DE REFERENCIAS CONTEXTUALES DIRECTAS ---
        # Palabras que casi siempre se refieren al último producto visto.
        demonstrative_references = [
            "este", "esta", "estos", "estas",
            "ese", "esa", "esos", "esas",
            "aquel", "aquella", "aquellos", "aquellas",
            "eso", "esto", "el último", "la última", "los últimos", "las últimas",
            "ese producto", "este producto", "el producto", "del producto"
        ]
        
        # Limpiar la referencia de palabras comunes para una comparación más limpia.
        clean_reference = reference.lower().replace("de ", "").strip()
        
        # Si la referencia es una de estas palabras, buscar el producto más reciente
        if clean_reference in demonstrative_references:
            logger.info(f"Referencia contextual directa detectada: '{reference}'. Resolviendo al producto más reciente.")
            recent_skus = get_recent_products(db, chat_id, limit=1)
            if recent_skus:
                # Para acciones que requieren verificación de existencia
                if action_context in ['add', 'product_inquiry']:
                    product = get_product_by_sku(db, recent_skus[0])
                    if product:
                        logger.info(f"Referencia '{reference}' resuelta a producto reciente: {product.name} ({recent_skus[0]})")
                        return recent_skus[0]
                else:
                    # Para otras acciones, confiar en que el contexto es correcto
                    return recent_skus[0]
            logger.warning(f"No hay productos recientes disponibles para resolver la referencia '{reference}'")
            return ""

        # --- PASO 2: BÚSQUEDA EXACTA POR SKU ---
        if reference.upper().startswith(('PET', 'HAR', 'HIL', 'BOA', 'DEW')):  # Prefijos comunes de SKU
            product = get_product_by_sku(db, reference.upper())
            if product:
                logger.info(f"SKU exacto encontrado: {product.name} ({reference.upper()})")
                return reference.upper()

        # --- PASO 3: BÚSQUEDA EN EL CARRITO (para remove/update) ---
        if action_context in ['remove', 'update']:
            try:
                async with self._get_api_client() as client:
                    cart_response = await client.get(f"/cart/{chat_id}")
                    cart_response.raise_for_status()
                    cart_data = cart_response.json()
                    cart_items = cart_data.get("items", {})
                    
                    if not cart_items:
                        logger.info(f"Carrito vacío para acción {action_context}")
                        return ""
                    
                    # Buscar en productos del carrito
                    cart_products = []
                    for sku, item_details in cart_items.items():
                        try:
                            product_info = json.loads(item_details['product'])
                            # Crear un objeto similar a Product para reutilizar _matches_reference
                            pseudo_product = type('Product', (), {
                                'sku': sku,
                                'name': product_info.get('name', ''),
                                'brand': product_info.get('brand', ''),
                                'category_name': product_info.get('category_name', ''),
                                'description': product_info.get('description', '')
                            })()
                            cart_products.append(pseudo_product)
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(f"Error parseando producto del carrito {sku}: {e}")
                            continue
                    
                    # Buscar coincidencias en el carrito
                    matching_cart_products = []
                    for product in cart_products:
                        if self._matches_reference(product, reference):
                            matching_cart_products.append(product)
                            logger.info(f"Coincidencia en carrito: {product.name} ({product.sku}) para '{reference}'")
                    
                    if len(matching_cart_products) == 1:
                        return matching_cart_products[0].sku
                    elif len(matching_cart_products) > 1:
                        return self._resolve_ambiguous_reference(matching_cart_products, reference)
                    else:
                        logger.info(f"No se encontraron coincidencias para '{reference}' en el carrito")
                        return ""
                        
            except Exception as e:
                logger.error(f"Error accediendo al carrito para resolución de referencia: {e}")
                return ""

        # --- PASO 4: BÚSQUEDA EN PRODUCTOS RECIENTES ---
        if action_context in ['add', 'search', 'product_inquiry']:
            recent_skus = get_recent_products(db, chat_id, limit=10)
            if recent_skus:
                recent_products = []
                for sku in recent_skus:
                    product = get_product_by_sku(db, sku)
                    if product:
                        recent_products.append(product)
                
                # Buscar coincidencias en productos recientes
                matching_recent = []
                for product in recent_products:
                    if self._matches_reference(product, reference):
                        matching_recent.append(product)
                        logger.info(f"Coincidencia en recientes: {product.name} ({product.sku}) para '{reference}'")
                
                if len(matching_recent) == 1:
                    logger.info(f"Producto resuelto desde recientes: {matching_recent[0].name} ({matching_recent[0].sku})")
                    return matching_recent[0].sku
                elif len(matching_recent) > 1:
                    # Para múltiples coincidencias en recientes, usar el más reciente (primera posición)
                    logger.info(f"Múltiples coincidencias en recientes, usando el más reciente: {matching_recent[0].name}")
                    return matching_recent[0].sku

        # --- PASO 5: BÚSQUEDA SEMÁNTICA EN TODA LA BASE DE DATOS ---
        if action_context in ['add', 'search', 'product_inquiry']:
            logger.info(f"Iniciando búsqueda semántica para '{reference}'")
            try:
                # Buscar productos que coincidan semánticamente
                search_terms = reference.lower().split()
                
                # Filtrar términos muy cortos o comunes que no son útiles para búsqueda
                filtered_terms = [term for term in search_terms if len(term) > 2 and term not in ['de', 'del', 'la', 'el', 'los', 'las', 'para', 'con', 'en']]
                
                if not filtered_terms:
                    logger.warning(f"No hay términos útiles para búsqueda en '{reference}'")
                    return ""
                
                # Usar ILIKE para búsqueda semántica más flexible
                from sqlalchemy import or_
                conditions = []
                for term in filtered_terms:
                    conditions.extend([
                        Product.name.ilike(f"%{term}%"),
                        Product.description.ilike(f"%{term}%"),
                        Product.brand.ilike(f"%{term}%"),
                        Product.sku.ilike(f"%{term}%")
                    ])
                
                if not conditions:
                    return ""
                
                semantic_products = db.query(Product).filter(or_(*conditions)).limit(20).all()
                
                if not semantic_products:
                    logger.info(f"No se encontraron productos semánticamente para '{reference}'")
                    return ""
                
                # Filtrar usando _matches_reference para encontrar las mejores coincidencias
                matching_semantic = []
                for product in semantic_products:
                    if self._matches_reference(product, reference):
                        matching_semantic.append(product)
                        logger.info(f"Coincidencia semántica: {product.name} ({product.sku}) para '{reference}'")
                
                if len(matching_semantic) == 1:
                    logger.info(f"Producto resuelto semánticamente: {matching_semantic[0].name} ({matching_semantic[0].sku})")
                    return matching_semantic[0].sku
                elif len(matching_semantic) > 1:
                    # Si hay múltiples coincidencias semánticas, requerir más especificidad
                    logger.info(f"Múltiples coincidencias semánticas encontradas para '{reference}', requiere mayor especificidad")
                    return self._resolve_ambiguous_reference(matching_semantic, reference)
                else:
                    logger.info(f"Productos encontrados semánticamente pero ninguno coincide con '{reference}'")
                    return ""
                    
            except Exception as e:
                logger.error(f"Error en búsqueda semántica para '{reference}': {e}")
                return ""

        logger.warning(f"No se pudo resolver la referencia '{reference}' en contexto '{action_context}'")
        return ""

    def _resolve_ambiguous_reference(self, candidates: List[Product], reference: str) -> str:
        """
        Resuelve referencias ambiguas cuando hay múltiples productos que coinciden.
        Aplica un sistema de puntuación para elegir el más apropiado.
        """
        reference_lower = reference.lower()
        reference_words = set([word for word in reference_lower.split() 
                               if word not in ["el", "la", "los", "las", "de", "del", "para", "con", "sin"]])

        if not candidates:
            return ""

        scored_candidates = []
        for product in candidates:
            score = 0
            product_text = f"{product.name} {product.description or ''} {product.brand or ''}".lower()
            
            # Calcular puntuación de coincidencia
            for word in reference_words:
                if word in product_text:
                    score += 1
            
            # Bonificación por coincidencia de marca si se menciona explícitamente
            if product.brand and product.brand.lower() in reference_words:
                score += 2
            
            scored_candidates.append({"product": product, "score": score, "price": product.price})

        # Si no hay coincidencias, no podemos resolver la referencia
        if not any(c['score'] > 0 for c in scored_candidates):
            return ""

        # Ordenar candidatos: primero por puntuación (desc), luego por precio (desc)
        candidates_sorted = sorted(scored_candidates, key=lambda x: (x['score'], x['price']), reverse=True)
        
        # Devolver el SKU del mejor candidato
        return candidates_sorted[0]['product'].sku
    
    def _matches_reference(self, product, reference: str) -> bool:
        """
        Verifica si un producto coincide con una referencia textual.
        Mejorado para manejar mejor las coincidencias de marca y tipo.
        """
        reference_lower = reference.lower().strip()
        
        # Casos especiales: referencias demostrativas
        demonstrative_only = [
            "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
            "aquel", "aquella", "aquellos", "aquellas", "eso", "esto",
            "el último", "la última", "los últimos", "las últimas"
        ]
        
        # Si la referencia es solo un demostrativo, coincide con cualquier producto
        if reference_lower in demonstrative_only:
            logger.info(f"Referencia demostrativa '{reference}' coincide con cualquier producto: {product.name}")
            return True
        
        # Limpiar la referencia de artículos y preposiciones
        reference_words = [word for word in reference_lower.split() 
                          if word not in ["el", "la", "los", "las", "de", "del", "para", "con", "sin", 
                                         "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas"]]
        
        # Si después de limpiar no quedan palabras significativas, coincide con cualquier producto
        if not reference_words:
            logger.info(f"Referencia '{reference}' sin palabras significativas, coincide con: {product.name}")
            return True

        product_text = f"{product.name} {product.description or ''} {getattr(product, 'brand', '') or ''}".lower()
        
        # Verificar si las palabras clave coinciden
        matches = 0
        total_words = len(reference_words)
        
        for word in reference_words:
            # Comprobar si la palabra original está en el texto del producto
            if word in product_text:
                matches += 1
                continue
            
            # Intentar con una forma singular simple
            if word.endswith('s') and len(word) > 3 and word[:-1] in product_text:
                matches += 1
                continue
            
            if word.endswith('es') and len(word) > 4 and word[:-2] in product_text:
                matches += 1
                continue
        
        # Calcular el porcentaje de coincidencia
        match_ratio = matches / total_words if total_words > 0 else 0
        
        # Para referencias cortas (1-2 palabras), requerir al menos 1 coincidencia
        # Para referencias más largas, requerir al menos 50% de coincidencia
        if total_words <= 2:
            result = matches >= 1
        else:
            result = match_ratio >= 0.5
        
        logger.info(f"Coincidencia para '{reference}' con {product.name}: {matches}/{total_words} palabras ({match_ratio:.2%}) = {'SÍ' if result else 'NO'}")
        return result

    def _get_stock_status(self, total_quantity: int) -> str:
        if total_quantity > 10:
            return "✅ Disponible"
        elif 0 < total_quantity <= 10:
            return "⚠️ ¡Últimas unidades!"
        else:
            return "❌ Agotado"

    # ========================================
    # LÓGICA DE CONFIRMACIÓN DE CARRITO
    # ========================================

    async def _create_cart_confirmation_response(self, chat_id: int, initial_message: str, cart_content: str = "") -> Dict[str, Any]:
        """Crea una respuesta estándar post-actualización de carrito."""
        if not cart_content:
            # Si no se provee contenido, obtener el carrito actual
            try:
                async with self._get_api_client() as client:
                    response = await client.get(f"/cart/{chat_id}")
                    response.raise_for_status()
                    cart_data = response.json()
                    cart_content = self._format_cart_data(cart_data)
            except Exception as e:
                logger.error(f"No se pudo obtener el carrito para la confirmación: {e}")
                cart_content = "No pude mostrar tu carrito actualizado."

        final_message = initial_message + cart_content

        # Instrucciones en texto en lugar de botones
        instructions = (
            "\n\n💡 Puedes seguir *buscando productos*, *ver tu carrito* (o con `/ver_carrito`)"
            " o indicar que quieres ya *finalizar la compra* (o con `/finalizar_compra`)."
        )
        final_message += instructions
        
        return {
            "type": "text_messages",
            "messages": [final_message]
        }

    async def _finalize_checkout_with_customer_data(self, db: Session, chat_id: int, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """Finaliza la compra con los datos del cliente recolectados."""
        try:
            async with self._get_api_client() as client:
                # 1. Verificar si el carrito está vacío
                get_response = await client.get(f"/cart/{chat_id}")
                get_response.raise_for_status()
                cart_data = get_response.json()
                if not cart_data.get("items"):
                    clear_pending_action(db, chat_id)
                    return {
                        "type": "text_messages",
                        "messages": ["🛒 Tu carrito está vacío. No se puede finalizar la compra."]
                    }

                # 2. Validar que tenemos todos los datos necesarios
                required_fields = ["name", "email", "phone", "address"]
                for field in required_fields:
                    if field not in action_data:
                        clear_pending_action(db, chat_id)
                        return {
                            "type": "text_messages",
                            "messages": ["❌ Faltan datos del cliente. Por favor, inicia el proceso de compra nuevamente."]
                        }

                # 3. Construir el payload del pedido
                order_items = []
                for sku, item_details in cart_data["items"].items():
                    product_info = json.loads(item_details['product'])
                    order_items.append({
                        "product_sku": sku,
                        "quantity": item_details["quantity"],
                        "price": product_info["price"]
                    })

                order_payload = {
                    "chat_id": str(chat_id),
                    "customer_name": action_data["name"],
                    "customer_email": action_data["email"],
                    "customer_phone": action_data["phone"],
                    "shipping_address": action_data["address"],
                    "items": order_items
                }

                # 4. Llamar al endpoint de checkout
                checkout_response = await client.post(f"/cart/{chat_id}/checkout", json=order_payload)
                checkout_response.raise_for_status()
                order_data = checkout_response.json()

                # 5. Limpiar acción pendiente y confirmar al usuario
                clear_pending_action(db, chat_id)
                
                order_id = order_data.get("id")
                total = order_data.get("total_amount", 0.0)
                
                response_text = (
                    f"🎉 *¡Gracias por tu compra!* 🎉\n\n"
                    f"✅ *Pedido confirmado para:* {action_data['name']}\n\n"
                    f"📄 *Detalles del Pedido:*\n"
                    f"   • *ID:* `{order_id}`\n"
                    f"   • *Total:* `${total:,.2f}`\n\n"
                    f"📧 *Confirmación enviada a:* {action_data['email']}\n"
                    f"📱 *Teléfono de contacto:* {action_data['phone']}\n"
                    f"🏠 *Dirección de envío:* {action_data['address']}\n\n"
                    f"📦 *Tu pedido será procesado y enviado pronto.*\n"
                    f"¡Gracias por confiar en nosotros!"
                )
                
                return {
                    "type": "text_messages",
                    "messages": [response_text]
                }

        except httpx.HTTPStatusError as e:
            clear_pending_action(db, chat_id)
            if e.response.status_code == 400:
                return {
                    "type": "text_messages",
                    "messages": ["🛒 Error en el carrito. Por favor, revisa tus productos y vuelve a intentar."]
                }
            else:
                logger.error(f"Error de API en checkout final para chat {chat_id}: {e}")
                return {
                    "type": "text_messages",
                    "messages": ["❌ Lo siento, ocurrió un error al procesar tu pedido. Intenta de nuevo."]
                }
        except Exception as e:
            clear_pending_action(db, chat_id)
            logger.error(f"Error inesperado en checkout final para chat {chat_id}: {e}")
            return {
                "type": "text_messages",
                "messages": ["❌ Ocurrió un error inesperado. Por favor, intenta de nuevo."]
            }

# ========================================
# INSTANCIA SINGLETON DEL SERVICIO
# ========================================

# Instancia única del servicio para ser usada en toda la aplicación
# Se crea solo si el token del bot está configurado para evitar errores en desarrollo
telegram_service = TelegramBotService() if settings.telegram_bot_token else None
