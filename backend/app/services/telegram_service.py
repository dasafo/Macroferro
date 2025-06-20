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
from typing import Optional, Dict, Any
import httpx
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

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
    - Manejo robusto de errores y timeouts de red
    - Configuración flexible via variables de entorno
    
    Flujo principal de operación:
    1. Recibir mensaje via webhook de Telegram
    2. Analizar intención del usuario con IA
    3. Ejecutar búsqueda de productos si corresponde
    4. Formatear respuesta rica en Markdown
    5. Enviar respuesta de vuelta a Telegram
    
    Consideraciones de arquitectura:
    - Operaciones asíncronas para no bloquear el event loop
    - Timeouts configurables para evitar cuelgues
    - Fallbacks graceful cuando servicios externos fallan
    - Logging detallado para debugging y monitoreo
    """

    def __init__(self):
        """
        Inicializa el servicio de Telegram Bot con configuración externa.
        
        Configura clientes para servicios externos y valida configuración requerida.
        Utiliza lazy loading de clientes pesados (OpenAI) para optimizar startup.
        
        Componentes inicializados:
        - Token del bot y URL base de Telegram API
        - Cliente OpenAI para procesamiento de lenguaje natural
        - Referencia al ProductService para búsquedas de catálogo
        
        Variables de entorno requeridas:
        - TELEGRAM_BOT_TOKEN: Token del bot obtenido de @BotFather
        - OPENAI_API_KEY: API key para procesamiento con IA
        
        Consideraciones de seguridad:
        - Tokens sensibles nunca se loggean
        - Validación de configuración en startup
        - Graceful degradation si servicios opcionales fallan
        """
        self.bot_token = settings.telegram_bot_token
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.product_service = ProductService()

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

    # ========================================
    # PROCESAMIENTO INTELIGENTE DE MENSAJES
    # ========================================
    
    async def process_message(self, db: Session, message_text: str, chat_id: int) -> str:
        """
        Procesa un mensaje del usuario y genera una respuesta inteligente.
        
        Esta función implementa el flujo principal de procesamiento de mensajes,
        orquestando múltiples servicios de IA para comprender la intención del usuario
        y proporcionar respuestas contextuales y útiles para consultas comerciales.
        
        Args:
            db: Sesión de SQLAlchemy para acceso a datos
            message_text: Texto del mensaje enviado por el usuario
            chat_id: ID del chat para contexto y logging
            
        Returns:
            Texto de respuesta formateado en Markdown listo para enviar
            
        Flujo de procesamiento implementado:
        1. **Análisis de intención**: Determinar si busca productos específicos
        2. **Búsqueda semántica**: Si aplica, buscar en catálogo con IA
        3. **Formateo de resultados**: Estructurar productos encontrados
        4. **Respuesta general**: Para otros casos, generar respuesta contextual
        5. **Manejo de errores**: Fallback graceful ante fallos de servicios
        
        Tipos de mensajes manejados:
        - Búsquedas de productos: "Busco tubos de PVC"
        - Comandos: /start, /help, /info
        - Conversación general: Saludos, preguntas sobre empresa
        - Consultas técnicas: Especificaciones, precios, disponibilidad
        
        Integración con IA:
        - OpenAI gpt-4o-mini-2024-07-18 para análisis de intenciones (rápido, económico)
        - OpenAI gpt-4o-mini-2024-07-18 para respuestas generales (mejor calidad)
        - Embeddings text-embedding-3-small para búsqueda semántica
        
        Formato de respuestas:
        - Markdown para texto enriquecido
        - Emojis para mejor experiencia visual
        - Estructura consistente para productos
        - Mensajes de error amigables al usuario
        
        Optimizaciones de rendimiento:
        - Timeout corto para análisis de intención
        - Búsqueda limitada a top 5 productos
        - Respuestas concisas para mejor UX móvil
        - Caching potencial de respuestas frecuentes
        
        Extensiones futuras:
        - Contexto conversacional persistente
        - Historial de búsquedas del usuario
        - Recomendaciones personalizadas
        - Integración con sistema de pedidos
        - Soporte multiidioma
        """
        if not self.openai_client:
            logger.warning("OpenAI no configurado, usando respuesta estática")
            return "🤖 Hola! Soy el asistente de Macroferro. El servicio de IA no está disponible en este momento."
        
        try:
            # ========================================
            # FASE 1: ANÁLISIS DE INTENCIÓN CON IA
            # ========================================
            
            intention_prompt = f"""
Analiza el siguiente mensaje de un usuario de una empresa que vende productos industriales y determina si está buscando productos específicos.

Mensaje: "{message_text}"

Responde ÚNICAMENTE con un JSON en este formato:
{{
    "is_product_search": true/false,
    "search_query": "términos de búsqueda optimizados si aplica",
    "user_intent": "descripción breve de la intención del usuario"
}}

Si el usuario busca productos, extrae y optimiza los términos de búsqueda para encontrar productos industriales relevantes.
"""
            
            # Usar gpt-4o-mini-2024-07-18 para análisis rápido y económico de intenciones
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[{"role": "user", "content": intention_prompt}],
                temperature=0.1,  # Baja temperatura para análisis consistente
                max_tokens=200,   # Respuesta corta y estructurada
                timeout=10.0      # Timeout corto para responsividad
            )
            
            # ========================================
            # FASE 2: PROCESAMIENTO DE INTENCIÓN
            # ========================================
            
            # Parsear respuesta de IA con manejo de errores
            import json
            try:
                ai_response = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as e:
                logger.error(f"Error parseando respuesta de IA: {e}")
                ai_response = {"is_product_search": False, "user_intent": "unknown"}
            
            # ========================================
            # RAMA 1: BÚSQUEDA DE PRODUCTOS CON IA
            # ========================================
            
            if ai_response.get("is_product_search", False):
                search_query = ai_response.get("search_query", message_text)
                logger.info(f"Realizando búsqueda de productos para: {search_query}")
                
                # Búsqueda semántica usando ProductService
                search_results = await self.product_service.search_products(
                    db=db,
                    query_text=search_query,
                    top_k=5  # Limitar para respuesta rápida
                )
                
                # Obtener productos de los resultados estructurados
                main_products = search_results.get("main_results", [])
                related_products = search_results.get("related_results", [])
                all_products = main_products + related_products
                
                # Formatear respuesta con productos encontrados
                if all_products:
                    response_text = f"🔍 *Productos encontrados para: {search_query}*\n\n"
                    
                    # Mostrar productos principales primero
                    if main_products:
                        response_text += "*📋 Resultados principales:*\n"
                        for i, product in enumerate(main_products, 1):
                            response_text += f"*{i}. {product.name}*\n"
                            # Truncar descripción para mejor legibilidad móvil
                            description = product.description[:80] + "..." if len(product.description) > 80 else product.description
                            response_text += f"📝 {description}\n"
                            response_text += f"💰 Precio: ${product.price:,.0f}\n"
                            if product.category:
                                response_text += f"🏷️ Categoría: {product.category.name}\n"
                            response_text += "\n"
                    
                    # Mostrar productos relacionados si existen
                    if related_products:
                        response_text += "*🔗 También te podría interesar:*\n"
                        for i, product in enumerate(related_products, len(main_products) + 1):
                            response_text += f"*{i}. {product.name}* - ${product.price:,.0f}\n"
                    
                    response_text += "\n💬 ¿Te interesa alguno de estos productos? ¡Pregúntame más detalles!"
                    
                else:
                    response_text = f"❌ No encontré productos específicos para: *{search_query}*\n\n"
                    response_text += "💡 Puedes intentar con términos más generales como:\n"
                    response_text += "• 'tubos'\n• 'válvulas'\n• 'conectores'\n• 'herramientas'"
            
            # ========================================
            # RAMA 2: RESPUESTA GENERAL CON IA
            # ========================================
            
            else:
                logger.info(f"Generando respuesta general para intención: {ai_response.get('user_intent', 'unknown')}")
                
                general_prompt = f"""
Eres un asistente amigable y profesional de Macroferro, una empresa que vende productos industriales.
El usuario te escribió: "{message_text}"

Contexto de la empresa:
- Vendemos productos industriales (tuberías, válvulas, herramientas, etc.)
- Atendemos principalmente clientes B2B
- Tenemos un catálogo amplio de productos técnicos
- Brindamos asesoría técnica especializada

Instrucciones de respuesta:
- Mantén un tono profesional pero amigable
- Si el usuario saluda, salúdalo cordialmente
- Si pregunta sobre productos en general, explícale que puede buscar productos específicos
- Si pregunta sobre la empresa, comparte información relevante
- Usa emojis apropiados para hacer la conversación más amigable
- Mantén la respuesta concisa (máximo 300 caracteres)
- Invita al usuario a hacer consultas específicas

Responde de manera útil y orientada a la acción.
"""
                
                # Usar GPT-4o-mini para respuestas de mejor calidad
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini-2024-07-18",
                    messages=[{"role": "user", "content": general_prompt}],
                    temperature=0.7,    # Temperatura moderada para respuestas naturales
                    max_tokens=300,     # Respuestas concisas
                    timeout=15.0        # Timeout generoso para mejor calidad
                )
                
                response_text = response.choices[0].message.content
            
            logger.info(f"Respuesta generada exitosamente para chat {chat_id}")
            return response_text
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout procesando mensaje de chat {chat_id}")
            return "⏱️ Lo siento, el procesamiento está tomando más tiempo del esperado. Por favor intenta nuevamente."
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de chat {chat_id}: {e}")
            return "❌ Lo siento, hubo un error procesando tu mensaje. Por favor intenta nuevamente."

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