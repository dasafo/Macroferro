# backend/app/services/bot_components/product_handler.py
"""
Servicio de Productos para el Bot de Telegram.

Este componente encapsula toda la lógica de negocio relacionada con la
interacción del usuario con los productos del catálogo. Se encarga de:
- Interpretar y ejecutar búsquedas de productos.
- Gestionar consultas sobre el catálogo general.
"""
import logging
import json
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.services.product_service import ProductService
from app.services.context_service import context_service
from app.crud.product_crud import get_product_by_sku
from app.crud.conversation_crud import get_recent_products, add_recent_product, get_user_context, update_user_context
from app.api.deps import get_db
from app.crud import category_crud, product_crud

logger = logging.getLogger(__name__)

class ProductHandler:
    """
    Gestiona toda la lógica de negocio relacionada con productos.
    - Búsquedas de productos
    - Consultas de detalles
    - Preguntas técnicas
    - Resolución de referencias a productos en el contexto de una conversación
    """

    def __init__(self, product_service: ProductService, openai_client: Optional[Any] = None):
        """
        Inicializa el handler de productos.

        Args:
            product_service: Instancia del servicio de productos para acceso a la BD.
            openai_client: Cliente de OpenAI para consultas de IA (ej. preguntas técnicas).
        """
        self.product_service = product_service
        self.openai_client = openai_client

    async def handle_intent(self, db: AsyncSession, intent_type: str, analysis: Dict, message_text: str, chat_id: int) -> Dict[str, Any]:
        """
        Punto de entrada principal para gestionar intenciones relacionadas con productos.
        Delega a métodos específicos según la intención detectada por la IA.
        """
        search_terms = analysis.get("search_terms")
        query_text = " ".join(search_terms) if search_terms else message_text
        is_repetition = analysis.get("is_repetition", False)

        # Lógica de desambiguación: ¿La búsqueda es por una categoría?
        all_categories = await category_crud.get_categories(db, limit=1000) # Obtener todas las categorías
        
        matched_category = None
        for cat in all_categories:
            # Comprobación simple (se puede mejorar con fuzzy matching)
            if query_text.lower() in cat.name.lower() or cat.name.lower() in query_text.lower():
                matched_category = cat
                break

        if matched_category:
            logger.info(f"La consulta '{query_text}' coincide con la categoría '{matched_category.name}'. Buscando por categoría.")
            return await self._handle_category_search(db, chat_id, matched_category, is_repetition)

        # 1. Búsqueda explícita de productos (si no es una categoría)
        if intent_type == "product_search":
            terms_to_use = search_terms if search_terms else [message_text]
            logger.info(f"Manejando 'product_search' con términos: {terms_to_use}")
            return await self._handle_product_search(db, chat_id, terms_to_use, is_repetition)

        # 2. Petición de detalles de producto (contextual)
        if intent_type == "product_details":
            logger.info("Manejando 'product_details'.")
            
            # Prioridad 1: Usar el SKU si la IA lo extrajo directamente.
            sku_reference = analysis.get("specific_product_mentioned")
            if sku_reference and re.match(r'SKU\d{5}', sku_reference.strip(), re.IGNORECASE):
                sku = sku_reference.strip().upper()
                logger.info(f"SKU extraído directamente por la IA: {sku}")
            else:
                # Prioridad 2: Resolver referencia en lenguaje natural.
                logger.info("No se encontró SKU directo, intentando resolver referencia contextual.")
                sku = await self._resolve_product_reference(message_text, chat_id)

            if sku:
                product = await get_product_by_sku(db, sku)
                if product:
                    product_data = product.to_dict() # Convertir a dict
                    await add_recent_product(chat_id, product_data)
                    caption = self._format_product_details(product)
                    suggestions = await context_service.get_contextual_suggestions(chat_id, db)
                    return {
                        "type": "product_with_image",
                        "product": product,
                        "caption": caption,
                        "additional_messages": [suggestions]
                    }
            logger.warning(f"No se pudo resolver referencia para 'product_details' con texto: '{message_text}'. Fallback a búsqueda.")
            return await self._handle_product_search(db, chat_id, [message_text], is_repetition)
        
        # 3. Pregunta técnica (contextual)
        if intent_type == "technical_question":
            logger.info("Manejando 'technical_question'.")
            return await self._handle_technical_question(db, chat_id, analysis, message_text)

        # 4. Consulta de catálogo general
        if intent_type == "catalog_inquiry":
            logger.info("Manejando 'catalog_inquiry'.")
            return await self._handle_catalog_inquiry(db)

        # 5. Fallback para intenciones no manejadas
        logger.warning(f"Intención no manejada por ProductHandler: {intent_type}. Respondiendo genéricamente.")
        return await self._handle_catalog_inquiry(db)


    async def get_main_categories_formatted(self, db: AsyncSession) -> str:
        """
        Obtiene las categorías principales de la base de datos y las formatea en un string.
        """
        main_categories = await category_crud.get_root_categories(db)
        if not main_categories:
            return ""
        
        response_text = "Estas son nuestras categorías principales:\n"
        response_text += "\n".join([f"• {cat.name}" for cat in main_categories])
        return response_text
    
    async def _handle_catalog_inquiry(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Gestiona la consulta del catálogo de productos, mostrando las categorías principales.
        """
        categories_text = await self.get_main_categories_formatted(db)
        
        return {
            "type": "text_messages",
            "messages": [
                f"¡Claro! En Macroferro somos especialistas en productos industriales.\n{categories_text}",
                "💡 Puedes preguntarme por cualquiera de ellas (ej: 'qué tienes en tornillería') para ver más detalles."
            ]
        }
    
    async def _handle_category_search(self, db: AsyncSession, chat_id: int, category: Any, is_repetition: bool = False) -> Dict[str, Any]:
        """
        Realiza una búsqueda de productos filtrando por una categoría específica.
        """
        logger.info(f"Buscando productos para la categoría: '{category.name}'")
        
        # Usamos el product_crud directamente para buscar por category_id
        products = await product_crud.get_products(db, category_id=category.category_id, limit=10)
        
        # Guardar los productos encontrados en el contexto reciente del chat
        product_dicts = [p.to_dict() for p in products]
        for p_dict in product_dicts:
            await add_recent_product(chat_id, p_dict)

        if not products:
            return {
                "type": "text_messages",
                "messages": [
                    f"✅ Categoría: *{category.name}*\n\n🤔 No he encontrado productos específicos en esta categoría en este momento, pero seguimos añadiendo más a nuestro catálogo."
                ]
            }

        if is_repetition:
            response_text = f"Sí, como te comentaba, en la categoría *{category.name}* tenemos estos productos:\n\n"
        else:
            response_text = f"✅ Categoría: *{category.name}*\n\nHe encontrado {len(products)} productos:\n\n"

        for i, p in enumerate(products, 1):
            response_text += f"*{i}. {p.name}* ({p.sku})\n"
        
        suggestions = await context_service.get_contextual_suggestions(chat_id, db)
        response_text += f"\n{suggestions}"
        
        return {
            "type": "text_messages",
            "messages": [response_text]
        }
        
    async def _handle_product_search(self, db: AsyncSession, chat_id: int, search_terms: List[str], is_repetition: bool = False) -> Dict[str, Any]:
        """
        Realiza una búsqueda de productos y formatea la respuesta.
        """
        query = " ".join(search_terms)
        logger.info(f"Buscando productos para la consulta: '{query}'")
        
        products_dict = await self.product_service.search_products(db, query_text=query, top_k=5)
        products = products_dict.get("products", [])
        
        # Guardar los productos encontrados en el contexto reciente del chat
        product_dicts = [p.to_dict() for p in products]
        for p_dict in product_dicts:
            await add_recent_product(chat_id, p_dict)
            
        # Formatear la respuesta
        if not products:
            if is_repetition:
                return {
                    "type": "text_messages",
                    "messages": [
                        f"He buscado de nuevo, pero sigo sin encontrar nada para '{query}'.",
                        "Podríamos probar con otros términos, o quizás explorar una categoría. ¿Qué prefieres?"
                    ]
                }
            return {
                "type": "text_messages",
                "messages": [
                    f"🤔 No he encontrado resultados para '{query}'.",
                    "Intenta con otros términos. Por ejemplo, en lugar de 'destornillador de estrella', prueba 'destornillador Phillips'."
                ]
            }
        
        if len(products) == 1:
            product = products[0]
            caption = self._format_product_details(product)
            suggestions = await context_service.get_contextual_suggestions(chat_id, db)
            return {
                "type": "product_with_image",
                "product": product,
                "caption": caption,
                "additional_messages": [suggestions]
            }
        else:
            if is_repetition:
                response_text = f"Sí, claro. Como te comentaba, esto es lo que encontré para '{query}':\n\n"
            else:
                response_text = f"🔍 He encontrado {len(products)} productos relacionados con '{query}':\n\n"
            for i, p in enumerate(products, 1):
                response_text += f"*{i}. {p.name}* ({p.sku})\n"
            
            suggestions = await context_service.get_contextual_suggestions(chat_id, db)
            response_text += f"\n{suggestions}"
            
            return {
                "type": "text_messages",
                "messages": [response_text]
            }
    
    async def _handle_technical_question(self, db: AsyncSession, chat_id: int, analysis: Dict, question: str) -> Dict[str, Any]:
        """
        Responde a una pregunta técnica sobre un producto usando IA y el contexto.
        """
        sku_reference = analysis.get("specific_product_mentioned")
        
        # Resolver la referencia a un producto específico (SKU)
        if sku_reference and re.match(r'SKU\d{5}', sku_reference.strip(), re.IGNORECASE):
            sku = sku_reference.strip().upper()
        else:
            sku = await self._resolve_product_reference(question, chat_id)

        if not sku:
            return {
                "type": "text_messages",
                "messages": ["No estoy seguro de a qué producto te refieres. ¿Puedes ser más específico?"]
            }

        product = await get_product_by_sku(db, sku)
        if not product:
            return {
                "type": "text_messages",
                "messages": ["No pude encontrar los detalles para ese producto. Intenta buscarlo de nuevo."]
            }

        # Guardar en contexto reciente
        await add_recent_product(chat_id, product.to_dict())

        # Usar OpenAI para responder la pregunta técnica
        logger.info(f"Usando OpenAI para responder pregunta técnica sobre el producto {sku}.")
        
        # Crear el prompt para la IA
        system_prompt = (
            "Eres un asistente técnico experto de la ferretería Macroferro. "
            "Tu única tarea es responder preguntas técnicas sobre un producto específico usando la información proporcionada. "
            "Sé conciso y directo. Si la información no está disponible, indícalo claramente."
        )
        
        user_prompt = (
            f"Producto: {product.name} (SKU: {product.sku})\n"
            f"Descripción: {product.description}\n"
            f"Especificaciones: {json.dumps(product.spec_json, indent=2)}\n\n"
            f"Pregunta del cliente: '{question}'"
        )

        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )
            answer = response.choices[0].message.content
            
            # Formateo de la respuesta
            formatted_answer = f"Sobre el *{product.name}*:\n\n{answer}"
            
            return {
                "type": "text_messages",
                "messages": [formatted_answer]
            }
        except Exception as e:
            logger.error(f"Error llamando a la API de OpenAI: {e}")
            return {
                "type": "text_messages",
                "messages": ["Lo siento, no pude procesar la pregunta técnica en este momento."]
            }

    def _format_product_details(self, product) -> str:
        """
        Formatea los detalles de un producto en un string legible para el usuario.
        """
        price_str = f"{product.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        details = f"📦 *{product.name}*\n"
        details += f"🔖 SKU: `{product.sku}`\n"
        details += f"🔩 Marca: {product.brand}\n"
        details += f"💰 Precio: ${price_str}\n\n"
        if product.description:
            details += f"📝 *Descripción:*\n{product.description}\n\n"
        
        if product.spec_json:
            details += "📋 *Especificaciones técnicas:*\n"
            for key, value in product.spec_json.items():
                details += f"• {key.replace('_', ' ').capitalize()}: {value}\n"
        
        return details.strip()

    async def _resolve_product_reference(self, reference: str, chat_id: int) -> Optional[str]:
        """
        Resuelve una referencia en lenguaje natural a un SKU de producto, basándose en el
        contexto reciente. Prioriza referencias numéricas/ordinales y luego por keyword.

        Returns:
            El SKU del producto resuelto, o None si no se puede resolver.
        """
        logger.info(f"Resolviendo referencia: '{reference}' para el chat {chat_id}")
        
        user_context = await get_user_context(chat_id)
        recent_products = user_context.get("recent_products", [])
        
        if not recent_products:
            logger.warning(f"No hay productos recientes en el contexto para resolver la referencia '{reference}'")
            return None

        # Estrategia 1: Búsqueda por ordinales numéricos (ej: "el 2", "dame el 5to")
        # Busca un número aislado, opcionalmente precedido por palabras y/o artículos.
        match = re.search(r'(?:el|la|del|dame|ponme|número|producto|#)\s*(\d+)', reference, re.IGNORECASE)
        if not match:
             # Fallback para casos como "el 6" o "el 5" donde no hay espacio
            match = re.search(r'\b(\d+)\b', reference)

        if match:
            try:
                index = int(match.group(1)) - 1  # Convertir a índice base 0
                if 0 <= index < len(recent_products):
                    sku = recent_products[index]['sku']
                    logger.info(f"Referencia '{reference}' resuelta por ordinal numérico a SKU: {sku}")
                    return sku
            except (ValueError, IndexError):
                pass # El número encontrado no es un índice válido

        # Estrategia 2: Búsqueda por ordinales de texto ("el primero", "el último")
        ordinal_map = {"primero": 0, "segundo": 1, "tercero": 2, "cuarto": 3, "quinto": 4, "último": -1}
        for word, index in ordinal_map.items():
            if word in reference.lower():
                # Asegurarnos de que el índice sea válido para la lista actual de productos
                if -len(recent_products) <= index < len(recent_products):
                    sku = recent_products[index]['sku']
                    logger.info(f"Referencia '{reference}' resuelta por ordinal de texto a SKU: {sku}")
                    return sku
        
        # Estrategia 3: Búsqueda por palabras clave en nombre, marca o SKU (como fallback)
        for product in recent_products:
            if reference.lower() in product.get('name', '').lower() or \
               reference.lower() in product.get('brand', '').lower() or \
               reference.lower() == product.get('sku', '').lower():
                logger.info(f"Referencia '{reference}' resuelta por keyword a SKU: {product['sku']}")
                return product['sku']

        logger.warning(f"No se pudo resolver la referencia '{reference}' con las estrategias actuales.")
        return None