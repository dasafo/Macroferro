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
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown") -> Dict[str, Any]:
        """
        Envía un mensaje a un chat específico a través del API de Telegram.
        
        Esta función maneja la comunicación saliente hacia usuarios de Telegram,
        con soporte para formateo rico en Markdown/HTML y manejo robusto de errores
        de red que son comunes en integraciones con APIs externas.
        
        Args:
            chat_id: ID único del chat donde enviar el mensaje
            text: Contenido del mensaje (puede incluir Markdown/HTML)
            parse_mode: Formato del texto ("Markdown", "HTML", o None)
            
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

    async def send_multiple_messages(self, chat_id: int, messages: List[str], delay_between_messages: float = 1.0) -> List[Dict[str, Any]]:
        """
        Envía múltiples mensajes de forma secuencial con delay entre cada uno.
        
        Esta función simula una conversación natural enviando mensajes en secuencia
        con pausas para que parezca que la persona está escribiendo cada respuesta.
        
        Args:
            chat_id: ID del chat donde enviar los mensajes
            messages: Lista de mensajes a enviar
            delay_between_messages: Tiempo en segundos entre mensajes
            
        Returns:
            Lista con las respuestas del API de Telegram para cada mensaje
        """
        results = []
        
        for i, message in enumerate(messages):
            if i > 0:  # No hacer delay antes del primer mensaje
                await asyncio.sleep(delay_between_messages)
            
            try:
                result = await self.send_message(chat_id, message)
                results.append(result)
                logger.info(f"Mensaje {i+1}/{len(messages)} enviado exitosamente")
            except Exception as e:
                logger.error(f"Error enviando mensaje {i+1}/{len(messages)}: {e}")
                # Continuar con los siguientes mensajes aunque uno falle
                results.append({"error": str(e)})
        
        return results

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
    
    async def process_message(self, db: Session, message_text: str, chat_id: int) -> List[str]:
        """
        Procesa un mensaje del usuario con inteligencia contextual avanzada.
        
        El bot ahora puede:
        1. Detectar referencias a productos específicos (por nombre, marca, característica)
        2. Consultar detalles exactos de productos en la base de datos
        3. Proporcionar información técnica específica
        4. Mantener conversaciones naturales y contextuales
        5. Manejar múltiples tipos de consulta de forma inteligente
        
        El procesamiento se hace con un LLM más potente para mejor comprensión contextual.
        """
        if not self.openai_client:
            logger.warning("OpenAI no configurado, usando respuesta estática")
            return ["🤖 Hola! Soy el asistente de Macroferro. El servicio de IA no está disponible en este momento."]
        
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

IMPORTANTE: Si el usuario menciona un producto específico (nombre, marca, o característica muy específica), probablemente quiere información detallada de ESE producto, no una búsqueda general.

Responde ÚNICAMENTE con este JSON:
{{
    "intent_type": "product_details" | "product_search" | "technical_question" | "general_conversation",
    "confidence": 0.8,
    "specific_product_mentioned": "nombre exacto del producto si se menciona" | null,
    "search_terms": ["término1", "término2"] | null,
    "technical_aspect": "aspecto técnico específico" | null,
    "user_intent_description": "descripción clara de lo que quiere el usuario",
    "suggested_response_tone": "informative" | "conversational" | "technical"
}}

Tipos de intent:
- "product_details": Usuario pregunta por un producto específico que mencionó por nombre
- "product_search": Usuario busca productos por categoría/tipo general 
- "technical_question": Pregunta técnica sobre especificaciones
- "general_conversation": Saludo, información general, otros temas

Ejemplos:
- "¿Qué especificaciones tiene el Esmalte para Exteriores Bahco?" → product_details
- "Busco tubos de PVC" → product_search  
- "¿Cuál es el diámetro de ese tubo?" → technical_question
- "Hola, ¿cómo están?" → general_conversation
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
            
            # ========================================
            # ENRUTAMIENTO INTELIGENTE SEGÚN INTENCIÓN
            # ========================================
            
            if intent_type == "product_details":
                return await self._handle_specific_product_inquiry(db, analysis, message_text)
            
            elif intent_type == "product_search":
                return await self._handle_product_search(db, analysis, message_text)
            
            elif intent_type == "technical_question":
                return await self._handle_technical_question(db, analysis, message_text)
            
            else:  # general_conversation
                return await self._handle_conversational_response(message_text, analysis)
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout procesando mensaje de chat {chat_id}")
            return ["⏱️ Lo siento, el procesamiento está tomando más tiempo del esperado. Por favor intenta nuevamente."]
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de chat {chat_id}: {e}")
            return ["❌ Lo siento, hubo un error procesando tu mensaje. Por favor intenta nuevamente."]

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
        
        # Si no hay bloques de código, devolver el contenido original
        return content.strip()

    async def _handle_specific_product_inquiry(self, db: Session, analysis: Dict, message_text: str) -> List[str]:
        """
        Maneja consultas específicas sobre un producto particular.
        
        Esta función busca primero por nombre exacto, luego por nombre parcial,
        y proporciona información detallada del producto específico.
        """
        specific_product = analysis.get("specific_product_mentioned")
        search_terms = analysis.get("search_terms", [])
        
        # Asegurar que search_terms sea una lista
        if search_terms is None:
            search_terms = []
        
        if specific_product:
            search_terms.insert(0, specific_product)
        
        logger.info(f"Buscando información específica de producto: {search_terms}")
        
        # Intentar encontrar el producto específico por nombre
        found_product = None
        
        # 1. Buscar por nombre exacto en la base de datos
        for term in search_terms:
            if not term:
                continue
                
            # Buscar por nombre parcial en la base de datos
            from app.crud import product_crud
            products = product_crud.get_products(
                db=db, 
                name_like=term.strip(),
                limit=1  # Solo necesitamos el primer resultado exacto
            )
            
            if products:
                found_product = products[0]
                logger.info(f"Producto encontrado por nombre: {found_product.name}")
                break
        
        # 2. Si no se encontró por nombre exacto, usar búsqueda semántica
        if not found_product and search_terms:
            search_query = " ".join(search_terms)
            search_results = await self.product_service.search_products(
                db=db,
                query_text=search_query,
                top_k=1  # Solo el más relevante
            )
            
            main_results = search_results.get("main_results", [])
            if main_results:
                found_product = main_results[0]
                logger.info(f"Producto encontrado por búsqueda semántica: {found_product.name}")
        
        if not found_product:
            return [
                "🔍 Hmm, no encontré información específica sobre ese producto.",
                "💡 ¿Podrías ser más específico con el nombre o modelo?\n\nTambién puedo ayudarte a buscar productos si me dices qué tipo de producto necesitas."
            ]
        
        # ========================================
        # GENERAR RESPUESTA DETALLADA DEL PRODUCTO
        # ========================================
        
        return await self._generate_detailed_product_response(found_product, message_text)

    async def _generate_detailed_product_response(self, product, original_question: str) -> List[str]:
        """
        Genera una respuesta conversacional y detallada sobre un producto específico.
        """
        # Preparar información del producto para el LLM
        product_info = {
            "sku": product.sku,
            "name": product.name,
            "description": product.description or "Sin descripción disponible",
            "price": float(product.price),
            "brand": product.brand or "Sin marca especificada",
            "category": product.category.name if product.category else "Sin categoría",
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
- Especificaciones técnicas: {json.dumps(product_info['specifications'], indent=2, ensure_ascii=False)}

INSTRUCCIONES:
1. Responde de forma conversacional y natural, como un vendedor experto que conoce bien el producto
2. Enfócate en lo que el cliente preguntó específicamente
3. Proporciona información técnica relevante de las especificaciones si las hay
4. Menciona aplicaciones típicas y beneficios del producto
5. Incluye el precio de forma natural en la conversación
6. Si hay especificaciones técnicas, resáltalas de forma clara
7. Mantén un tono profesional pero amigable
8. Usa emojis apropiados para hacer la respuesta más visual
9. Divide la respuesta en 2-3 mensajes naturales si es necesario (separa con "|||")
10. Termina invitando a hacer más preguntas específicas

Formato de respuesta:
- Usa *texto* para negrita
- Usa formato de lista con • para especificaciones
- Incluye emojis técnicos apropiados (🔧 ⚙️ 📐 💧 ⚡ 🏗️ etc.)

Responde en español de manera profesional y útil.
"""
        
        # Generar respuesta con LLM
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[{"role": "user", "content": response_prompt}],
            temperature=0.7,  # Temperatura moderada para naturalidad
            max_tokens=800,   # Espacio suficiente para respuesta detallada
            timeout=20.0
        )
        
        response_text = response.choices[0].message.content
        
        # Dividir respuesta si incluye el separador
        if "|||" in response_text:
            messages = [msg.strip() for msg in response_text.split("|||") if msg.strip()]
        else:
            messages = self.split_response_into_messages(response_text, 3800)
        
        return messages

    async def _handle_product_search(self, db: Session, analysis: Dict, message_text: str) -> List[str]:
        """
        Maneja búsquedas generales de productos con respuesta conversacional.
        """
        search_terms = analysis.get("search_terms", [])
        
        # Asegurar que search_terms sea una lista
        if search_terms is None:
            search_terms = []
            
        search_query = " ".join(search_terms) if search_terms else message_text
        
        logger.info(f"Realizando búsqueda general de productos para: {search_query}")
        
        # Búsqueda semántica usando ProductService
        search_results = await self.product_service.search_products(
            db=db,
            query_text=search_query,
            top_k=6  # Más productos para mejor selección
        )
        
        main_products = search_results.get("main_results", [])
        related_products = search_results.get("related_results", [])
        
        if not main_products and not related_products:
            return [
                f"🔍 Busqué productos relacionados con: *{search_query}*",
                "❌ No encontré productos específicos para esa búsqueda.\n\n💡 Puedes intentar con términos más generales como:\n• 'tubos'\n• 'válvulas'\n• 'conectores'\n• 'herramientas'\n• 'tornillos'\n• 'pinturas'"
            ]
        
        messages = []
        
        # Mensaje inicial más conversacional
        initial_message = f"🔍 ¡Perfecto! Encontré varios productos para tu búsqueda de *{search_query}*.\n\n✨ Aquí están las mejores opciones:"
        messages.append(initial_message)
        
        # Mostrar productos principales de forma más conversacional
        if main_products:
            for i, product in enumerate(main_products, 1):
                product_message = f"*{i}. {product.name}*\n"
                
                if product.description:
                    desc = product.description[:120] + "..." if len(product.description) > 120 else product.description
                    product_message += f"📝 {desc}\n\n"
                
                product_message += f"💰 Precio: *${product.price:,.0f}*\n"
                
                if product.category:
                    product_message += f"🏷️ {product.category.name}\n"
                
                if hasattr(product, 'brand') and product.brand:
                    product_message += f"🏭 {product.brand}\n"
                
                # Agregar especificaciones destacadas si existen
                if product.spec_json:
                    specs_preview = []
                    for key, value in list(product.spec_json.items())[:2]:  # Solo las primeras 2 specs
                        specs_preview.append(f"• {key}: {value}")
                    if specs_preview:
                        product_message += f"⚙️ Especificaciones:\n" + "\n".join(specs_preview) + "\n"
                
                messages.append(product_message)
        
        # Mostrar productos relacionados más brevemente
        if related_products:
            related_message = "🔗 *También podrían interesarte:*\n\n"
            for product in related_products:
                related_message += f"• *{product.name}* - ${product.price:,.0f}\n"
            messages.append(related_message)
        
        # Mensaje final conversacional
        follow_up = "💬 ¿Te interesa conocer más detalles de alguno de estos productos?\n\n🔍 Solo menciona el nombre del producto y te daré información técnica completa."
        messages.append(follow_up)
        
        return messages

    async def _handle_technical_question(self, db: Session, analysis: Dict, message_text: str) -> List[str]:
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

# ========================================
# INSTANCIA SINGLETON DEL SERVICIO
# ========================================

# Instancia única del servicio para ser usada en toda la aplicación
# Se crea solo si el token del bot está configurado para evitar errores en desarrollo
telegram_service = TelegramBotService() if settings.telegram_bot_token else None

# ========================================
# EXTENSIONES Y MÉTODOS AUXILIARES FUTUROS
# ========================================

# Métodos auxiliares que se implementarían en versiones futuras:
#
# async def _validate_user_permissions(self, user_id: int, chat_id: int) -> bool:
#     """Valida permisos del usuario para acceder a funcionalidades específicas."""
#     pass
#
# async def _log_user_interaction(self, user_id: int, message_text: str, response_text: str) -> None:
#     """Registra interacciones para análisis de uso y mejora del bot."""
#     pass
#
# async def _get_user_context(self, db: Session, user_id: int) -> Dict[str, Any]:
#     """Obtiene contexto conversacional persistente del usuario."""
#     pass
#
# async def _save_user_context(self, db: Session, user_id: int, context: Dict[str, Any]) -> None:
#     """Guarda contexto conversacional para futuras interacciones."""
#     pass
#
# async def _generate_product_recommendations(self, db: Session, user_id: int) -> List[models.Product]:
#     """Genera recomendaciones personalizadas basadas en historial del usuario."""
#     pass
#
# async def _format_product_details(self, product: models.Product) -> str:
#     """Formatea detalles completos de un producto para visualización rica."""
#     pass
#
# async def _handle_product_inquiry(self, db: Session, product_sku: str, user_id: int) -> str:
#     """Maneja consultas específicas sobre un producto (precio, stock, especificaciones)."""
#     pass
#
# async def _send_typing_action(self, chat_id: int) -> None:
#     """Envía acción de 'escribiendo...' para mejor UX durante procesamiento."""
#     pass
#
# async def _create_inline_keyboard(self, options: List[Dict[str, str]]) -> Dict[str, Any]:
#     """Crea teclado inline con botones para navegación interactiva."""
#     pass
#
# async def _handle_callback_query(self, callback_data: str, chat_id: int) -> str:
#     """Procesa respuestas de botones inline del usuario."""
#     pass
#
# async def _validate_webhook_secret(self, request_headers: Dict[str, str]) -> bool:
#     """Valida que el webhook viene realmente de Telegram usando el secret token."""
#     pass
#
# async def _retry_failed_message(self, chat_id: int, text: str, max_retries: int = 3) -> bool:
#     """Reintenta envío de mensajes fallidos con backoff exponencial."""
#     pass 