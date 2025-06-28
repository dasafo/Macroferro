# backend/app/crud/conversation_crud.py
"""
Operaciones CRUD para el contexto conversacional del bot de Telegram.

Este módulo maneja el estado conversacional y el contexto del usuario utilizando
un único hash de Redis por usuario para garantizar la persistencia y la
atomicidad de los datos conversacionales.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from redis.asyncio import Redis
from sqlalchemy.orm import Session
from app.core.config import settings

logger = logging.getLogger(__name__)

# Conexión a Redis (se manejará de forma lazy)
_redis_client: Optional[Redis] = None

def _get_redis_client() -> Redis:
    """Inicializa y devuelve el cliente de Redis."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            f"redis://{settings.REDIS_HOST}",
            decode_responses=True
        )
    return _redis_client

def _get_user_context_key(chat_id: int) -> str:
    """Genera la clave de Redis para el hash de contexto de un usuario."""
    return f"user_context:{chat_id}"

# ===============================================
# Funciones Principales de Gestión de Contexto
# ===============================================

async def get_user_context(chat_id: int) -> Dict[str, Any]:
    """
    Obtiene el contexto completo de un usuario desde Redis.
    Si no existe, devuelve un contexto vacío.
    """
    redis = _get_redis_client()
    context_key = _get_user_context_key(chat_id)
    
    user_context_str = await redis.get(context_key)
    if user_context_str:
        try:
            return json.loads(user_context_str)
        except json.JSONDecodeError:
            logger.error(f"Error decodificando JSON para el contexto del chat {chat_id}")
            return {}
    
    return {}

async def update_user_context(chat_id: int, updates: Dict[str, Any]):
    """
    Actualiza el contexto de un usuario en Redis. Carga el contexto actual,
    lo actualiza con los nuevos datos y lo guarda de nuevo.
    """
    redis = _get_redis_client()
    context_key = _get_user_context_key(chat_id)
    
    # Obtenemos el contexto actual
    current_context = await get_user_context(chat_id)
    
    # Aplicamos las actualizaciones
    current_context.update(updates)
    
    # Guardamos el contexto completo actualizado
    await redis.set(context_key, json.dumps(current_context))

async def clear_user_context(chat_id: int):
    """
    Elimina completamente el contexto de un usuario de Redis.
    Ideal para usar al finalizar una compra o al hacer logout.
    """
    redis = _get_redis_client()
    context_key = _get_user_context_key(chat_id)
    await redis.delete(context_key)

# ===============================================
# Helpers para Campos Específicos del Contexto
# ===============================================

async def add_turn_to_history(chat_id: int, user_message: str, bot_message: str):
    """Añade un turno al historial de conversación dentro del contexto."""
    context = await get_user_context(chat_id)
    history = context.get("history", [])
    
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": bot_message})
    
    # Mantenemos solo los últimos 20 turnos (40 mensajes)
    history = history[-40:]
    
    await update_user_context(chat_id, {"history": history})

async def get_conversation_history(chat_id: int, limit_turns: int = 10) -> List[Dict[str, str]]:
    """Obtiene el historial de conversación del contexto del usuario."""
    context = await get_user_context(chat_id)
    history = context.get("history", [])
    limit_messages = limit_turns * 2
    return history[-limit_messages:]

async def add_recent_product(chat_id: int, product_data: Dict[str, Any]):
    """
    Añade un producto a la lista de productos recientes. Esta lista ahora
    contiene los datos completos del producto para evitar búsquedas en BD.
    """
    sku = product_data.get("sku")
    if not sku:
        return

    context = await get_user_context(chat_id)
    recent_products = context.get("recent_products", [])
    
    # Eliminar si ya existe para moverlo al frente
    recent_products = [p for p in recent_products if p.get("sku") != sku]
    
    # Añadimos el producto completo al principio
    recent_products.insert(0, product_data)
    
    # Mantenemos solo los 10 más recientes
    recent_products = recent_products[:10]
    
    await update_user_context(chat_id, {"recent_products": recent_products})

async def add_recent_products_batch(chat_id: int, products_data: List[Dict[str, Any]], preserve_order: bool = True):
    """
    Añade múltiples productos a la lista de productos recientes preservando el orden original.
    Esta función es especialmente útil para resultados de búsquedas por categoría o texto.
    
    Args:
        chat_id: ID del chat
        products_data: Lista de productos como diccionarios
        preserve_order: Si True, mantiene el orden de la lista. Si False, usa el comportamiento normal.
    """
    if not products_data:
        return

    context = await get_user_context(chat_id)
    recent_products = context.get("recent_products", [])
    
    if preserve_order:
        # Remover productos existentes que están en la nueva lista
        existing_skus = {p.get("sku") for p in products_data}
        recent_products = [p for p in recent_products if p.get("sku") not in existing_skus]
        
        # Añadir los nuevos productos al inicio en el orden correcto
        recent_products = products_data + recent_products
    else:
        # Comportamiento normal: añadir uno por uno al principio (orden inverso)
        for product_data in products_data:
            sku = product_data.get("sku")
            if sku:
                recent_products = [p for p in recent_products if p.get("sku") != sku]
                recent_products.insert(0, product_data)
    
    # Mantenemos solo los 10 más recientes
    recent_products = recent_products[:10]
    
    await update_user_context(chat_id, {"recent_products": recent_products})

async def get_recent_products(chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Obtiene la lista de productos recientes (como dicts) del contexto.
    """
    context = await get_user_context(chat_id)
    return context.get("recent_products", [])[:limit]

async def update_search_context(chat_id: int, search_query: str, results: List[Dict[str, Any]]):
    """Actualiza el contexto de la última búsqueda con resultados completos."""
    search_context = {
        "last_search_query": search_query,
        "last_search_results": results # Guardamos los productos completos
    }
    await update_user_context(chat_id, search_context)
    # También añadimos los resultados a los productos recientes
    for product in results:
        await add_recent_product(chat_id, product)

async def set_pending_action(chat_id: int, action: Optional[str], data: Optional[Dict[str, Any]] = None):
    """Establece o limpia la acción pendiente en el contexto del usuario."""
    redis = _get_redis_client()
    context_key = _get_user_context_key(chat_id)
    current_context = await get_user_context(chat_id)

    if action:
        current_context["pending_action"] = {"action": action, "data": data or {}}
    else:
        current_context.pop("pending_action", None)

    if not current_context:
        await redis.delete(context_key)
    else:
        await redis.set(context_key, json.dumps(current_context))

async def get_pending_action(chat_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene la acción pendiente del contexto del usuario."""
    context = await get_user_context(chat_id)
    return context.get("pending_action")

async def clear_pending_action(chat_id: int):
    """Limpia la acción pendiente del contexto de un usuario."""
    await set_pending_action(chat_id, None)

# Funciones dummy que ya no se usan en la nueva arquitectura
# Se mantienen por si algún módulo antiguo aún las llama, para evitar crashes.
def add_recent_intent(db: Session, chat_id: int, intent: str, confidence: float) -> None:
    logger.debug(f"Llamada a función obsoleta: add_recent_intent para chat {chat_id}")
    pass 