from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Depends
from typing import Optional
import hmac
import hashlib
import logging
from sqlalchemy.orm import Session

from app.schemas.telegram import TelegramUpdate, TelegramResponse
from app.services.telegram_service import telegram_service
from app.core.config import settings
from app.api.deps import get_db

logger = logging.getLogger(__name__)
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
    update: TelegramUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    """
    Webhook para recibir actualizaciones de Telegram
    """
    if not telegram_service:
        raise HTTPException(status_code=503, detail="Telegram service not configured")
    
    try:
        # Verificar que la request viene de Telegram
        if settings.telegram_webhook_secret and not verify_telegram_webhook(
            body=b"",  # En producción, verificar el body completo
            secret_token=settings.telegram_webhook_secret,
            x_telegram_bot_api_secret_token=x_telegram_bot_api_secret_token
        ):
            logger.warning("Unauthorized webhook request")
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Procesar solo mensajes de texto
        if not update.message or not update.message.text:
            return {"status": "ok"}
        
        message = update.message
        user_message = message.text
        chat_id = message.chat.id
        
        logger.info(f"Mensaje recibido de chat {chat_id}: {user_message}")
        
        # Procesar mensaje en background para respuesta rápida
        background_tasks.add_task(
            process_and_respond, 
            db,
            user_message, 
            chat_id
        )
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error en webhook de Telegram: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def process_and_respond(db: Session, user_message: str, chat_id: int):
    """Procesar mensaje y enviar respuesta"""
    if not telegram_service:
        logger.error("Telegram service not configured")
        return
        
    try:
        # Procesar mensaje con IA
        response_text = await telegram_service.process_message(db, user_message, chat_id)
        
        # Enviar respuesta
        await telegram_service.send_message(chat_id, response_text)
        
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
async def telegram_health():
    """Health check para el bot de Telegram"""
    return {"status": "ok", "service": "telegram_bot"} 