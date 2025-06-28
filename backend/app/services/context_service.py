"""
Servicio para gestionar la lógica de contexto y fluidez de la conversación.

Este módulo se encarga de analizar el estado actual de la conversación
para proporcionar sugerencias proactivas y mejorar la naturalidad del bot.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.crud import conversation_crud as crud

class ContextService:

    async def get_contextual_suggestions(self, chat_id: int, db: AsyncSession) -> str:
        """
        Genera una cadena de texto con sugerencias contextuales basadas en las últimas acciones.
        """
        history = await crud.get_conversation_history(chat_id, limit_turns=2)
        last_bot_message = ""
        if history and history[-1]["role"] == "assistant":
            last_bot_message = history[-1]["content"].lower()

        suggestions = []

        # Lógica basada en el contenido del último mensaje del bot
        if "he añadido el producto a tu carrito" in last_bot_message:
            return "Puedes seguir buscando, `ver tu carrito` o `finalizar la compra`."
        elif "aquí están los detalles" in last_bot_message:
            suggestions = ["añadirlo al carrito", "preguntar por productos similares", "volver a buscar"]
        elif "encontré estos productos" in last_bot_message or "aquí tienes algunos productos de la categoría" in last_bot_message:
            suggestions = ["pedir más detalles de un producto (ej: 'dime más del 2')", "añadir uno al carrito (ej: 'añade el 1')"]
        elif "estos son los detalles de tu carrito" in last_bot_message:
            return "Puedes `eliminar` un producto, `vaciar` el carrito, `seguir comprando` o `finalizar la compra`."
        else: # Default
            suggestions = ["buscar productos (ej: 'busco tornillos')", "ver las categorías"]
            
        if not suggestions:
            return "Recuerda que puedes `ver el carrito` o pedir `ayuda`."
            
        # Formatear sugerencias en una sola línea
        return "💡 Ahora, puedes " + " o ".join(suggestions) + "."

# Instancia singleton del servicio
context_service = ContextService()
