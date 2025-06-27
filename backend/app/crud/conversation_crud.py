"""
Operaciones CRUD para el contexto conversacional del bot de Telegram.

Este módulo maneja el estado conversacional y productos recientes vistos por los usuarios,
proporcionando funcionalidades para mejorar la experiencia del chat bot.
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
from datetime import datetime, timedelta

# Por ahora usaremos un almacenamiento en memoria para estas funciones
# En una implementación completa, estas deberían estar en base de datos
_conversation_contexts: Dict[int, Dict[str, Any]] = {}
_recent_products: Dict[int, List[str]] = {}
_user_intents: Dict[int, List[Dict[str, Any]]] = {}
_pending_actions: Dict[int, Dict[str, Any]] = {}
_conversation_histories: Dict[int, List[Dict[str, str]]] = {}

def add_turn_to_history(db: Session, chat_id: int, user_message: str, bot_message: str):
    """
    Añade un turno de conversación (pregunta de usuario y respuesta del bot) al historial.
    """
    if chat_id not in _conversation_histories:
        _conversation_histories[chat_id] = []
    
    _conversation_histories[chat_id].append({"role": "user", "content": user_message})
    _conversation_histories[chat_id].append({"role": "assistant", "content": bot_message})
    
    # Mantener solo los últimos 10 turnos (20 mensajes) para no exceder el límite de tokens de la IA
    _conversation_histories[chat_id] = _conversation_histories[chat_id][-20:]

def get_conversation_history(db: Session, chat_id: int, limit_turns: int = 5) -> List[Dict[str, str]]:
    """
    Obtiene los últimos N turnos del historial de conversación.
    """
    if chat_id not in _conversation_histories:
        return []
        
    # Multiplicamos por 2 porque cada turno son 2 mensajes (user y assistant)
    limit_messages = limit_turns * 2
    return _conversation_histories[chat_id][-limit_messages:]

def add_recent_product(db: Session, chat_id: int, sku: str) -> None:
    """
    Añade un producto a la lista de productos recientes del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        sku: SKU del producto
    """
    if chat_id not in _recent_products:
        _recent_products[chat_id] = []
    
    # Eliminar el SKU si ya existe para evitar duplicados
    if sku in _recent_products[chat_id]:
        _recent_products[chat_id].remove(sku)
    
    # Añadir al principio de la lista
    _recent_products[chat_id].insert(0, sku)
    
    # Mantener solo los últimos 10 productos
    _recent_products[chat_id] = _recent_products[chat_id][:10]

def get_recent_products(db: Session, chat_id: int, limit: int = 5) -> List[str]:
    """
    Obtiene la lista de productos recientes del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        limit: Número máximo de productos a devolver
        
    Returns:
        Lista de SKUs de productos recientes
    """
    if chat_id not in _recent_products:
        return []
    
    return _recent_products[chat_id][:limit]

def update_conversation_context(db: Session, chat_id: int, context: Dict[str, Any]) -> None:
    """
    Actualiza el contexto conversacional del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        context: Contexto conversacional
    """
    _conversation_contexts[chat_id] = context

def get_conversation_context(db: Session, chat_id: int) -> Dict[str, Any]:
    """
    Obtiene el contexto conversacional del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        
    Returns:
        Contexto conversacional
    """
    return _conversation_contexts.get(chat_id, {})

def update_search_context(db: Session, chat_id: int, search_query: str, results: List[str]) -> None:
    """
    Actualiza el contexto de búsqueda del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        search_query: Consulta de búsqueda
        results: Lista de SKUs de resultados
    """
    context = get_conversation_context(db, chat_id)
    context['last_search'] = {
        'query': search_query,
        'results': results,
        'timestamp': datetime.now().isoformat()
    }
    update_conversation_context(db, chat_id, context)

def add_recent_intent(db: Session, chat_id: int, intent: str, confidence: float) -> None:
    """
    Añade una intención reciente del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        intent: Tipo de intención
        confidence: Confianza de la intención
    """
    if chat_id not in _user_intents:
        _user_intents[chat_id] = []
    
    intent_data = {
        'intent': intent,
        'confidence': confidence,
        'timestamp': datetime.now().isoformat()
    }
    
    _user_intents[chat_id].insert(0, intent_data)
    
    # Mantener solo las últimas 20 intenciones
    _user_intents[chat_id] = _user_intents[chat_id][:20]

def get_recent_intents(db: Session, chat_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Obtiene las intenciones recientes del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        limit: Número máximo de intenciones a devolver
        
    Returns:
        Lista de intenciones recientes
    """
    if chat_id not in _user_intents:
        return []
    
    return _user_intents[chat_id][:limit]

def get_last_user_intent(db: Session, chat_id: int) -> Optional[str]:
    """
    Obtiene la intención más reciente del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        
    Returns:
        La intención más reciente o None
    """
    intents = get_recent_intents(db, chat_id, limit=1)
    if intents:
        return intents[0].get('intent')
    return None

def set_pending_action(db: Session, chat_id: int, action: str, data: Dict[str, Any] = None) -> None:
    """
    Establece una acción pendiente para el usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        action: Tipo de acción pendiente
        data: Datos adicionales de la acción
    """
    _pending_actions[chat_id] = {
        'action': action,
        'data': data or {},
        'timestamp': datetime.now().isoformat()
    }

def get_pending_action(db: Session, chat_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene la acción pendiente del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
        
    Returns:
        Acción pendiente o None
    """
    return _pending_actions.get(chat_id)

def clear_pending_action(db: Session, chat_id: int) -> None:
    """
    Limpia la acción pendiente del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
    """
    if chat_id in _pending_actions:
        del _pending_actions[chat_id]

def clear_user_context(db: Session, chat_id: int) -> None:
    """
    Limpia todo el contexto del usuario.
    
    Args:
        db: Sesión de base de datos
        chat_id: ID del chat
    """
    if chat_id in _conversation_contexts:
        del _conversation_contexts[chat_id]
    if chat_id in _recent_products:
        del _recent_products[chat_id]
    if chat_id in _user_intents:
        del _user_intents[chat_id]
    if chat_id in _pending_actions:
        del _pending_actions[chat_id]
    if chat_id in _conversation_histories:
        del _conversation_histories[chat_id] 