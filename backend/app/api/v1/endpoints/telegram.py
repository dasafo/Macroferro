import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from typing import Optional
import hashlib
import hmac
import json

from app.core.config import settings
from app.api.deps import get_db
from app.schemas.telegram import TelegramUpdate
from app.services.telegram_service import TelegramBotService

logger = logging.getLogger(__name__)

# Inicializar servicio de Telegram
telegram_service = TelegramBotService() if settings.telegram_bot_token else None

router = APIRouter()

def verify_telegram_webhook(
    body: bytes, 
    secret_token: str, 
    x_telegram_bot_api_secret_token: Optional[str] = None
) -> bool:
    """Verificar que la request viene de Telegram"""
    if not x_telegram_bot_api_secret_token:
        return False
    return hmac.compare_digest(secret_token, x_telegram_bot_api_secret_token)

@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Webhook para recibir actualizaciones de Telegram.
    
    Este endpoint procesa mensajes entrantes de Telegram de forma asíncrona
    para proporcionar respuestas rápidas y naturales a los usuarios.
    
    Características:
    - Validación de autenticidad del webhook (opcional)
    - Procesamiento en background para no bloquear Telegram
    - Manejo robusto de errores
    - Logging detallado para monitoreo
    
    Flow:
    1. Validar webhook secret si está configurado
    2. Parsear update de Telegram
    3. Procesar mensaje en background
    4. Retornar 200 inmediatamente para evitar timeouts
    """
    try:
        # Obtener cuerpo de la request
        body = await request.body()
        
        # Validar webhook secret si está configurado
        if settings.telegram_webhook_secret:
            signature = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if not signature:
                logger.warning("Webhook sin signature, rechazando")
                raise HTTPException(status_code=401, detail="Missing signature")
            
            # Validar signature
            expected_signature = settings.telegram_webhook_secret
            if signature != expected_signature:
                logger.warning("Webhook con signature inválida, rechazando")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parsear update de Telegram
        try:
            update_data = json.loads(body.decode())
            update = TelegramUpdate(**update_data)
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON del webhook: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        except Exception as e:
            logger.error(f"Error validando update de Telegram: {e}")
            raise HTTPException(status_code=400, detail="Invalid update format")
        
        # Procesar mensaje en background
        if update.message and update.message.text:
            background_tasks.add_task(
                process_and_respond_multiple,
                db,
                update.message.text,
                update.message.chat.id
            )
            logger.info(f"Mensaje de chat {update.message.chat.id} agregado a cola de procesamiento")
        else:
            logger.info("Update sin mensaje de texto, ignorando")
        
        return {"status": "ok"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado en webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def process_and_respond_multiple(db: Session, user_message: str, chat_id: int):
    """
    Procesar mensaje y enviar múltiples respuestas naturales.
    
    Esta función orquesta el procesamiento inteligente del mensaje
    y el envío secuencial de respuestas para crear una experiencia
    de conversación más natural y fluida.
    
    Args:
        db: Sesión de base de datos
        user_message: Mensaje del usuario
        chat_id: ID del chat donde responder
        
    Características:
    - Procesamiento inteligente con IA
    - División automática de respuestas largas
    - Envío secuencial con delays naturales
    - Manejo robusto de errores
    - Fallback para errores de envío individual
    """
    if not telegram_service:
        logger.error("Telegram service not configured")
        return
        
    try:
        # Procesar mensaje con IA para obtener múltiples respuestas
        response_messages = await telegram_service.process_message(db, user_message, chat_id)
        
        if not response_messages:
            logger.warning(f"No se generaron respuestas para chat {chat_id}")
            response_messages = ["❌ Lo siento, hubo un problema procesando tu mensaje."]
        
        # Enviar mensajes secuencialmente con delays naturales
        delay = 1.5 if len(response_messages) > 1 else 0
        await telegram_service.send_multiple_messages(
            chat_id=chat_id,
            messages=response_messages,
            delay_between_messages=delay
        )
        
        logger.info(f"Conversación completada para chat {chat_id}: {len(response_messages)} mensajes enviados")
        
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")
        # Enviar mensaje de error al usuario
        try:
            await telegram_service.send_message(
                chat_id, 
                "❌ Lo siento, hubo un error procesando tu mensaje. Por favor intenta nuevamente."
            )
        except:
            logger.error(f"No se pudo enviar mensaje de error a chat {chat_id}")

# Mantener función original para compatibilidad
async def process_and_respond(db: Session, user_message: str, chat_id: int):
    """Procesar mensaje y enviar respuesta (versión original para compatibilidad)"""
    if not telegram_service:
        logger.error("Telegram service not configured")
        return
        
    try:
        # Procesar mensaje con IA
        response_messages = await telegram_service.process_message(db, user_message, chat_id)
        
        # Enviar solo el primer mensaje para mantener compatibilidad
        if response_messages:
            await telegram_service.send_message(chat_id, response_messages[0])
        
        logger.info(f"Respuesta enviada a chat {chat_id}")
        
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")
        # Enviar mensaje de error al usuario
        try:
            await telegram_service.send_message(
                chat_id, 
                "❌ Lo siento, hubo un error procesando tu mensaje."
            )
        except:
            logger.error(f"No se pudo enviar mensaje de error a chat {chat_id}")

@router.post("/set-webhook")
async def set_webhook():
    """
    Configurar webhook de Telegram (solo para desarrollo/testing)
    """
    if not telegram_service:
        raise HTTPException(status_code=503, detail="Telegram service not configured")
        
    try:
        if not settings.telegram_webhook_url:
            raise HTTPException(
                status_code=400, 
                detail="TELEGRAM_WEBHOOK_URL no configurada"
            )
        
        result = await telegram_service.set_webhook(
            webhook_url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret
        )
        
        return {"status": "success", "result": result}
        
    except Exception as e:
        logger.error(f"Error configurando webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """
    Endpoint de health check para verificar que el bot está funcionando.
    
    Returns:
        Status del servicio y configuración básica
    """
    return {
        "status": "ok",
        "service": "telegram_bot",
        "configured": telegram_service is not None,
        "webhook_url": settings.telegram_webhook_url or "not_configured"
    } 