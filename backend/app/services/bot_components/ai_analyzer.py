# backend/app/services/bot_components/ai_analyzer.py
"""
Servicio de Análisis de IA para el Bot de Telegram.

Este componente se especializa en interactuar con la API de OpenAI
para analizar el texto del usuario y determinar su intención.
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self, openai_client: Optional[AsyncOpenAI]):
        """
        Inicializa el analizador de IA.

        Args:
            openai_client: Una instancia del cliente asíncrono de OpenAI.
        """
        self.openai_client = openai_client
        if self.openai_client:
            logger.info("Cliente OpenAI en AIAnalyzer configurado.")
        else:
            logger.warning("AIAnalyzer inicializado sin cliente OpenAI.")

    def _extract_json_from_markdown(self, content: str) -> str:
        """Extrae JSON de bloques de código markdown."""
        json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
        
        code_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        return content.strip()

    async def analyze_user_intent(self, message_text: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Analiza el mensaje del usuario usando OpenAI para extraer la intención,
        considerando el historial de la conversación.
        
        Args:
            message_text: El mensaje de texto del usuario.
            history: El historial reciente de la conversación.
            
        Returns:
            Un diccionario con el análisis de la intención.
        """
        if not self.openai_client:
            logger.warning("OpenAI no configurado, retornando intención por defecto.")
            return {"intent_type": "general_conversation", "confidence": 0.5}

        system_prompt = """
Eres un asistente de inteligencia artificial especializado en productos industriales de Macroferro.

Analiza el último mensaje del usuario y determina exactamente qué tipo de respuesta necesita, considerando el contexto de la conversación anterior.

Contexto empresarial:
- Macroferro vende productos industriales: tubos, válvulas, herramientas, conectores, tornillos, etc.
- Los clientes hacen consultas técnicas específicas sobre productos
- Los usuarios pueden estar preguntando por detalles de un producto que ya encontraron
- También pueden estar haciendo búsquedas nuevas de productos
- Los usuarios pueden querer gestionar su carrito de compras usando lenguaje natural

IMPORTANTE: 
1. Si el usuario menciona un producto específico (nombre, marca, o característica muy específica), probablemente quiere información detallada de ESE producto, no una búsqueda general.
2. Si el usuario quiere agregar, quitar, ver, vaciar o finalizar compra, es una acción de carrito.
3. Presta MUCHA atención al historial para entender referencias como "ese", "el último", "el de la foto", etc.

Responde ÚNICAMENTE con este JSON:
{{
    "intent_type": "product_details" | "product_search" | "technical_question" | "cart_action" | "catalog_inquiry" | "general_conversation",
    "confidence": 0.8,
    "is_repetition": true | false,
    "specific_product_mentioned": "nombre exacto del producto si se menciona" | null,
    "search_terms": ["término1", "término2"] | null,
    "technical_aspect": "aspecto técnico específico" | null,
    "cart_actions": [ 
        {{ 
            "action": "add" | "remove" | "view" | "clear" | "checkout",
            "product_reference": "referencia al producto", 
            "quantity": número 
        }}
    ] | null,
    "user_intent_description": "descripción clara de lo que quiere el usuario",
    "suggested_response_tone": "informative" | "conversational" | "technical"
}}

Tipos de intent:
- "product_details": Usuario pregunta por un producto específico que mencionó por nombre o SKU.
- "product_search": Usuario busca productos por categoría/tipo general 
- "technical_question": Pregunta técnica sobre especificaciones
- "cart_action": Usuario quiere gestionar su carrito (agregar, quitar, ver, vaciar, finalizar)
- "catalog_inquiry": El usuario pregunta de forma general qué productos se venden (ej: "qué vendes", "qué tienes").
- "general_conversation": Saludo, información general, otros temas

Ejemplos de cart_actions:
- "Agrega ese martillo al carrito" → "cart_actions": [{ "action": "add", "product_reference": "ese martillo", "quantity": 1 }]
- "Quiero agregar 5 tubos de PVC" → "cart_actions": [{ "action": "add", "product_reference": "tubos de PVC", "quantity": 5 }]
- "ponme 3 del 2 y 5 del SKU00024" → "cart_actions": [{ "action": "add", "product_reference": "el 2", "quantity": 3 }, { "action": "add", "product_reference": "SKU00024", "quantity": 5 }]
- "Quítalo del carrito" → "cart_actions": [{ "action": "remove", "product_reference": "eso", "quantity": null }]
- "Quita el martillo del carrito y 2 de esos tornillos" → "cart_actions": [{ "action": "remove", "product_reference": "el martillo", "quantity": null }, { "action": "remove", "product_reference": "esos tornillos", "quantity": 2 }]
- "Muéstrame mi carrito" → "cart_actions": [{ "action": "view" }]
- "Vacía mi carrito" → "cart_actions": [{ "action": "clear" }]
- "Quiero finalizar la compra" → "cart_actions": [{ "action": "checkout" }]
- "pasemos por caja" → "cart_actions": [{ "action": "checkout" }]
- "finalicemos la compra" → "cart_actions": [{ "action": "checkout" }]
- "quiero pasar ya por caja" → "cart_actions": [{ "action": "checkout" }]
- "Comprar" → "cart_actions": [{ "action": "checkout" }]
- "quita 1 guante del carrito" -> "cart_actions": [{ "action": "remove", "quantity": 1, "product_reference": "guante" }]
- "añade 5 guantes mas al carro" -> "cart_actions": [{ "action": "add", "quantity": 5, "product_reference": "guantes" }]

IMPORTANTE para product_reference:
- Mantén SIEMPRE la referencia en español exactamente como la dice el usuario
- **NUNCA incluyas números en este campo.** Los números van en el campo "quantity".
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
- "dame info del SKU00023" → intent_type: "product_details", specific_product_mentioned: "SKU00023"
- "SKU00023 detalles" → intent_type: "product_details", specific_product_mentioned: "SKU00023"
- "Busco tubos de PVC" → product_search  
- "¿Cuál es el diámetro de ese tubo?" → technical_question
- "Hola, ¿cómo están?" → general_conversation

IMPORTANTE sobre SKUs para detalles:
- Si el mensaje contiene un código SKU (ej: "SKU" seguido de 5 dígitos) y pide información ("info", "detalles", "dame"), el `intent_type` DEBE ser `product_details`.
- En este caso, el campo `specific_product_mentioned` DEBE contener únicamente el código SKU extraído.

IMPORTANTE sobre la repetición:
- Si la pregunta actual del usuario es semánticamente idéntica o muy similar a su pregunta inmediatamente anterior en el historial, establece "is_repetition" a true. En caso contrario, a false.
- Ejemplo: Si el historial es `[..., {{"role": "user", "content": "busco adhesivos"}}]` y el mensaje actual es `tienes adhesivos?`, entonces `is_repetition` debe ser `true`.

IMPORTANTE sobre búsquedas vagas:
- Si la búsqueda es MUY genérica y podría referirse a cientos de productos (ej: "cosas de metal", "productos", "herramientas"), clasifícalo como "general_conversation" para que el asistente pueda pedir más detalles.
- Una búsqueda válida debe tener un tipo de producto más o menos claro (ej: "tubos de PVC", "martillos percutores", "pintura para exteriores").

Ejemplos de búsquedas vagas:
- "tienes cosas de metal?" -> intent_type: "general_conversation"
- "qué vendes?" -> intent_type: "catalog_inquiry"
- "qué tipo de productos tenéis?" -> intent_type: "catalog_inquiry"
- "dame productos" -> intent_type: "general_conversation"

IMPORTANTE: Si la consulta menciona un tipo de producto concreto (ej: "guantes", "adhesivos", "alicates"), SIEMPRE debe ser "product_search", incluso si la pregunta es del tipo "¿qué tienes de...?".

Ejemplos de búsquedas que SÍ deben ser "product_search":
- "tienes guantes?" -> intent_type: "product_search", search_terms: ["guantes"]
- "qué tipo de adhesivos tienes" -> intent_type: "product_search", search_terms: ["adhesivos"]
- "y alicates?" -> intent_type: "product_search", search_terms: ["alicates"]

BAJO NINGUNA CIRCUNSTANCIA respondas con texto conversacional. Tu única salida debe ser el objeto JSON. Sin excepciones.
"""
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)
            
        messages.append({"role": "user", "content": message_text})

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=300,
                timeout=15.0
            )
            
            ai_content = response.choices[0].message.content
            logger.info(f"Análisis de IA desde AIAnalyzer: {ai_content}")
            
            json_content = self._extract_json_from_markdown(ai_content)
            analysis = json.loads(json_content)
            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando análisis de IA en AIAnalyzer: {e}")
            return {"intent_type": "general_conversation", "confidence": 0.5}
        except Exception as e:
            logger.error(f"Error llamando a OpenAI en AIAnalyzer: {e}")
            return {"intent_type": "general_conversation", "confidence": 0.5}

# La instancia singleton se creará en el TelegramBotService para una mejor gestión de dependencias.
# ai_analyzer = AIAnalyzer() 