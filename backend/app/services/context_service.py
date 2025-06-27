"""
Servicio para gestionar la lógica de contexto y fluidez de la conversación.

Este módulo se encarga de analizar el estado actual de la conversación
para proporcionar sugerencias proactivas y mejorar la naturalidad del bot.
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.crud import conversation_crud as crud

class ContextService:

    def get_contextual_suggestions(self, db: Session, chat_id: int) -> str:
        """
        Genera una cadena de texto con sugerencias contextuales basadas en la última acción del usuario.
        """
        last_intent = crud.get_last_user_intent(db, chat_id)
        
        suggestions = []
        
        if not last_intent:
            suggestions = ["Puedes buscar productos (ej: 'busco tornillos')", "ver las categorías principales"]
        
        elif last_intent == 'product_search':
            suggestions = ["puedes pedir más detalles de un producto", "añadir uno al carrito (ej: 'añade el 2')"]
        
        elif last_intent == 'product_details':
            suggestions = ["añadirlo al carrito", "preguntar por productos similares", "volver a buscar"]

        elif last_intent == 'technical_question':
            suggestions = ["añadir el producto analizado al carrito", "ver otros productos"]
            
        elif last_intent == 'cart_action':
            # Si la última acción fue sobre el carrito, las sugerencias son siempre las mismas
            return "Puedes seguir buscando productos, `ver tu carrito` o `finalizar la compra`."

        if not suggestions:
            return "Recuerda que puedes `ver el carrito` o pedir `ayuda`."
            
        # Formatear sugerencias en una sola línea
        return "💡 Ahora, " + " o ".join(suggestions) + "."

# Instancia singleton del servicio
context_service = ContextService()
