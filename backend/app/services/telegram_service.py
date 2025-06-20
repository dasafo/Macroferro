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
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.product_service = ProductService()
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown") -> Dict[str, Any]:
        """Enviar mensaje a través del API de Telegram"""
        url = f"{self.api_base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error enviando mensaje de Telegram: {e}")
            raise
    
    async def process_message(self, db: Session, message_text: str, chat_id: int) -> str:
        """Procesar mensaje del usuario y generar respuesta"""
        try:
            # 1. Analizar la intención del usuario con OpenAI
            intention_prompt = f"""
Analiza el siguiente mensaje de un usuario y determina si está buscando productos específicos.

Mensaje: "{message_text}"

Responde ÚNICAMENTE con un JSON en este formato:
{{
    "is_product_search": true/false,
    "search_query": "términos de búsqueda si aplica",
    "user_intent": "descripción breve de la intención"
}}
"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": intention_prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            # Parsear respuesta de OpenAI
            import json
            ai_response = json.loads(response.choices[0].message.content)
            
            # 2. Si es búsqueda de productos, realizar búsqueda
            if ai_response.get("is_product_search", False):
                search_query = ai_response.get("search_query", message_text)
                search_results = await self.product_service.search_products(
                    db=db,
                    query_text=search_query,
                    top_k=5
                )
                
                # Obtener productos de los resultados
                main_products = search_results.get("main_results", [])
                related_products = search_results.get("related_results", [])
                all_products = main_products + related_products
                
                # 3. Formatear respuesta con productos
                if all_products:
                    response_text = f"🔍 *Productos encontrados para: {search_query}*\n\n"
                    for i, product in enumerate(all_products, 1):
                        response_text += f"*{i}. {product.name}*\n"
                        response_text += f"📋 {product.description[:100]}...\n"
                        response_text += f"💰 Precio: ${product.price}\n"
                        if product.category:
                            response_text += f"🏷️ Categoría: {product.category.name}\n"
                        response_text += "\n"
                else:
                    response_text = f"❌ No encontré productos para: {search_query}"
            
            else:
                # 4. Respuesta general con OpenAI
                general_prompt = f"""
Eres un asistente de una empresa que vende productos industriales (Macroferro).
El usuario te escribió: "{message_text}"

Responde de manera amable y profesional. Si el usuario saluda, salúdalo de vuelta.
Si pregunta sobre productos pero no específicamente, explícale que puede buscar productos específicos.
Mantén la respuesta breve y útil.
"""
                
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini-2024-07-18",
                    messages=[{"role": "user", "content": general_prompt}],
                    temperature=0.7,
                    max_tokens=300
                )
                
                response_text = response.choices[0].message.content
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            return "❌ Lo siento, hubo un error procesando tu mensaje. Por favor intenta nuevamente."
    
    async def set_webhook(self, webhook_url: str, secret_token: str) -> Dict[str, Any]:
        """Configurar webhook de Telegram"""
        url = f"{self.api_base_url}/setWebhook"
        payload = {
            "url": webhook_url,
            "secret_token": secret_token
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error configurando webhook: {e}")
            raise

# Instancia global del servicio (solo si está configurado)
telegram_service = TelegramBotService() if settings.telegram_bot_token else None 