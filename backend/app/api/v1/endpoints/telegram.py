import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import hashlib
import hmac
import json

from app.core.config import settings
from app.api.deps import get_db
from app.schemas.telegram_schema import TelegramUpdate
from app.services.telegram_service import TelegramBotService

logger = logging.getLogger(__name__)

# Inicializar servicio de Telegram
telegram_service = TelegramBotService() if settings.telegram_bot_token else None

router = APIRouter()

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
        
        # Procesar CUALQUIER update válido en background.
        # La lógica de qué hacer con cada tipo de update (mensaje, callback, etc.)
        # ya está dentro del servicio.
        background_tasks.add_task(
            process_and_respond_multiple,
            update_data,
            telegram_service,
            db
        )
        logger.info(f"Update de Telegram agregado a la cola de procesamiento.")
        
        return {"status": "ok"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado en webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def process_and_respond_multiple(update_data: dict, bot_service: TelegramBotService, db: Session):
    """
    Procesa el update del usuario, obtiene una respuesta estructurada del servicio
    y se encarga de enviarla al chat correspondiente.
    """
    chat_id = None
    try:
        chat_id = (
            (update_data.get('message') or {}).get('chat', {}).get('id') or
            (update_data.get('callback_query', {}).get('message', {}).get('chat', {}).get('id'))
        )
        if not chat_id:
            logger.warning("No se pudo extraer chat_id del update. Ignorando.")
            return

        logger.info(f"Procesando update para chat {chat_id}...")
        
        # 1. Obtener la respuesta estructurada del servicio
        response_data = await bot_service.process_message(db, update_data)
        
        if not response_data:
            logger.info(f"El servicio determinó que no se necesita respuesta para el update del chat {chat_id}.")
            return

        # 2. Enviar la respuesta según su tipo
        response_type = response_data.get("type")
        
        if response_type == "product_with_image":
            await bot_service.send_product_with_image(
                chat_id=chat_id,
                product=response_data.get("product"),
                caption=response_data.get("caption", ""),
                additional_messages=response_data.get("additional_messages", []),
                reply_markup=response_data.get("reply_markup")
            )
        elif response_type == "text_messages":
            messages = response_data.get("messages", [])
            if not messages:
                return

            # El teclado solo se adjunta al primer mensaje de una secuencia
            first_message = messages[0]
            other_messages = messages[1:]
            
            await bot_service.send_message(
                chat_id,
                first_message,
                reply_markup=response_data.get("reply_markup")
            )
            if other_messages:
                await bot_service.send_multiple_messages(chat_id, other_messages)
        
        else:
            logger.warning(f"Tipo de respuesta no reconocido del servicio: '{response_type}' para chat {chat_id}")

    except Exception as e:
        logger.error(f"Error crítico en process_and_respond_multiple para chat {chat_id}: {e}", exc_info=True)
        try:
            if chat_id:
                await bot_service.send_message(
                    chat_id, 
                    "❌ Lo siento, hubo un error grave al procesar tu solicitud. El equipo técnico ha sido notificado."
                )
        except Exception as send_error:
            logger.error(f"Fallo definitivo: no se pudo enviar el mensaje de error al chat {chat_id}: {send_error}")

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

@router.get("/webhook/status")
async def webhook_status():
    """
    Verifica el estado del webhook actual.
    
    Returns:
        Dict con información sobre la configuración del webhook
    """
    return {
        "status": "webhook endpoint configured",
        "description": "Endpoint listo para recibir actualizaciones de Telegram",
        "webhook_url": settings.telegram_webhook_url or "not_configured"
    }

@router.post("/test")
async def test_webhook(
    request_data: dict,
    db: Session = Depends(get_db)
):
    """
    Endpoint de prueba para simular mensajes de Telegram sin validación de firma.
    Solo para testing y desarrollo.
    """
    if not telegram_service:
        raise HTTPException(status_code=503, detail="Telegram service not configured")
    
    try:
        # Procesar el mensaje directamente
        response_data = await telegram_service.process_message(db, request_data.get("message", {}))
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error en test endpoint: {e}")
        return {"error": str(e)} 