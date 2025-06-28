"""
Handler de Productos para el Bot de Telegram.

Este componente encapsula toda la lógica de negocio relacionada con la
interacción del usuario con los productos del catálogo. Se encarga de:
- Interpretar y ejecutar búsquedas de productos.
- Gestionar consultas sobre el catálogo general.
- Proporcionar detalles específicos de un producto.
- Responder a preguntas técnicas usando IA.
- Resolver referencias ambiguas a productos (ej: "ese de ahí", "el segundo").
"""
import logging
import json
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import httpx

from app.core.config import settings
from app.services.product_service import ProductService
from app.services.context_service import context_service
from app.crud.product_crud import get_product_by_sku
from app.crud.conversation_crud import get_recent_products, add_recent_product, get_user_context, update_user_context
from app.api.deps import get_db
from app.crud import category_crud

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

    async def handle_intent(self, db: Session, intent_type: str, analysis: Dict, message_text: str, chat_id: int) -> Dict[str, Any]:
        """
        Punto de entrada principal para gestionar intenciones relacionadas con productos.
        Delega a métodos específicos según la intención detectada por la IA.
        """
        search_terms = analysis.get("search_terms")
        query_text = " ".join(search_terms) if search_terms else message_text
        is_repetition = analysis.get("is_repetition", False)

        # Lógica de desambiguación: ¿La búsqueda es por una categoría?
        all_categories = category_crud.get_categories(db, limit=1000) # Obtener todas las categorías
        
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
                product = get_product_by_sku(db, sku)
                if product:
                    product_data = product.to_dict() # Convertir a dict
                    await add_recent_product(chat_id, product_data)
                    caption = self._format_product_details(product)
                    suggestions = await context_service.get_contextual_suggestions(chat_id)
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
            return self._handle_catalog_inquiry(db)

        # 5. Fallback para intenciones no manejadas
        logger.warning(f"Intención no manejada por ProductHandler: {intent_type}. Respondiendo genéricamente.")
        return self._handle_catalog_inquiry(db)


    def get_main_categories_formatted(self, db: Session) -> str:
        """
        Obtiene las categorías principales de la base de datos y las formatea en un string.
        """
        main_categories = category_crud.get_root_categories(db)
        if not main_categories:
            return ""
        
        response_text = "Estas son nuestras categorías principales:\n"
        response_text += "\n".join([f"• {cat.name}" for cat in main_categories])
        return response_text
    
    def _handle_catalog_inquiry(self, db: Session) -> Dict[str, Any]:
        """
        Gestiona la consulta del catálogo de productos, mostrando las categorías principales.
        """
        categories_text = self.get_main_categories_formatted(db)
        
        return {
            "type": "text_messages",
            "messages": [
                f"¡Claro! En Macroferro somos especialistas en productos industriales.\n{categories_text}",
                "💡 Puedes preguntarme por cualquiera de ellas (ej: 'qué tienes en tornillería') para ver más detalles."
            ]
        }
    
    async def _handle_category_search(self, db: Session, chat_id: int, category: Any, is_repetition: bool = False) -> Dict[str, Any]:
        """
        Realiza una búsqueda de productos filtrando por una categoría específica.
        """
        logger.info(f"Buscando productos para la categoría: '{category.name}'")
        
        # Usamos el product_crud directamente para buscar por category_id
        from app.crud import product_crud
        products = product_crud.get_products(db, category_id=category.category_id, limit=10)
        
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
        
        suggestions = await context_service.get_contextual_suggestions(chat_id)
        response_text += f"\n{suggestions}"
        
        return {
            "type": "text_messages",
            "messages": [response_text]
        }
        
    async def _handle_product_search(self, db: Session, chat_id: int, search_terms: List[str], is_repetition: bool = False) -> Dict[str, Any]:
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
            suggestions = await context_service.get_contextual_suggestions(chat_id)
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
            
            suggestions = await context_service.get_contextual_suggestions(chat_id)
            response_text += f"\n{suggestions}"
            
            return {
                "type": "text_messages",
                "messages": [response_text]
            }
    
    async def _handle_technical_question(self, db: Session, chat_id: int, analysis: Dict, question: str) -> Dict[str, Any]:
        """
        Responde a una pregunta técnica sobre un producto usando IA y el contexto.
        """
        product_reference = analysis.get("specific_product_mentioned", "el producto")
        
        # Primero, intenta resolver la referencia a un producto concreto
        sku = await self._resolve_product_reference(product_reference, chat_id)
        if not sku:
            return {"type": "text_messages", "messages": [f"No estoy seguro de a qué producto te refieres con '{product_reference}'. ¿Podrías ser más específico?"]}
            
        # El producto debería estar en el contexto reciente, no necesitamos ir a la BD
        context = await get_user_context(chat_id)
        product_data = next((p for p in context.get("recent_products", []) if p.get("sku") == sku), None)

        if not product_data:
            return {"type": "text_messages", "messages": [f"No encontré los detalles del producto con SKU {sku} en el contexto reciente."]}
            
        # Ahora, con el producto, consulta a OpenAI
        if not self.openai_client:
            return {"type": "text_messages", "messages": ["Lo siento, la función de análisis técnico no está disponible en este momento."]}
            
        prompt = f"""
        Eres un experto técnico de Macroferro. Un cliente pregunta sobre el producto '{product_data.get('name')}' (SKU: {product_data.get('sku')}).
        Descripción del producto: {product_data.get('description')}
        Características: {product_data.get('spec_json')}
        
        Pregunta del cliente: "{question}"
        
        Basándote en la información que tienes, responde a la pregunta de forma clara y concisa. Si no tienes la respuesta, indícalo amablemente.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.2,
                max_tokens=250
            )
            answer = response.choices[0].message.content
            
            suggestions = await context_service.get_contextual_suggestions(chat_id)
            return {"type": "text_messages", "messages": [answer, suggestions]}
            
        except Exception as e:
            logger.error(f"Error consultando a OpenAI para pregunta técnica: {e}")
            return {"type": "text_messages", "messages": ["Lo siento, tuve un problema al generar la respuesta técnica."]}

    def _format_product_details(self, product) -> str:
        """
        Formatea los detalles de un solo producto para una presentación clara.
        """
        price_str = f"{product.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        details = (
            f"*{product.name}*\n"
            f"`SKU: {product.sku}`\n\n"
            f"{product.description}\n\n"
            f"Brand: {product.brand if product.brand else 'N/A'}\n"
            f"Categoría: {product.category.name if product.category else 'N/A'}\n"
            f"*Precio: {price_str} €*\n"
        )
        
        if product.spec_json:
            features = "\n".join([f"• *{key.replace('_', ' ').capitalize()}:* {value}" for key, value in product.spec_json.items()])
            if features:
                details += f"\n*Características:*\n{features}"
            
        return details

    async def _resolve_product_reference(self, reference: str, chat_id: int, action_context: str = None) -> Optional[str]:
        """
        Resuelve una referencia textual a un producto (ej: "ese martillo", "el número 2")
        basándose en el contexto de la conversación.
        """
        reference_lower = reference.lower()
        context = await get_user_context(chat_id)
        
        # Unificar todas las listas de productos relevantes en una sola para la búsqueda
        # Damos prioridad a los productos del carrito
        product_pool = []
        product_skus_in_pool = set()

        # 1. Añadir productos del carrito
        cart_data = context.get("cart", {})
        cart_items = cart_data.get("items", {})
        if cart_items:
            for item in cart_items.values():
                if item.get("product") and item["product"].get("sku") not in product_skus_in_pool:
                    product_pool.append(item["product"])
                    product_skus_in_pool.add(item["product"]["sku"])

        # 2. Añadir productos recientes (que no estén ya en el pool desde el carrito)
        recent_products = context.get("recent_products", [])
        if recent_products:
            for product in recent_products:
                if product.get("sku") not in product_skus_in_pool:
                    product_pool.append(product)
                    product_skus_in_pool.add(product["sku"])
        
        # Si no hay productos en el contexto, no podemos resolver nada
        if not product_pool:
            return None

        # --- INICIO DE LÓGICA DE RESOLUCIÓN ---
        
        # Caso A: Referencia numérica (ej: "el 2", "número 3")
        # Esto debe usar la lista de productos recientes en el orden en que se vieron
        match = re.search(r'(?:del|el|número|la)\s+(\d+)', reference_lower)
        if match:
            try:
                index = int(match.group(1)) - 1
                
                # Para referencias numéricas, usamos SÓLO los productos recientes en orden inverso
                ordered_recent = list(recent_products)
                ordered_recent.reverse()

                if 0 <= index < len(ordered_recent):
                    sku = ordered_recent[index].get("sku")
                    logger.info(f"Referencia numérica '{reference}' resuelta a SKU {sku} del historial.")
                    return sku
            except (ValueError, IndexError):
                logger.warning(f"No se pudo resolver la referencia numérica: '{reference}'")
                # No retornamos None, permitimos que caiga a la búsqueda por texto

        # Caso B: Referencia directa al último producto visto (ej: "este", "esa", "el último")
        demonstratives = ["este", "esta", "ese", "esa", "eso", "el último", "la última"]
        if any(word in demonstratives for word in reference_lower.split()):
            if recent_products:
                sku = recent_products[0].get("sku")
                logger.info(f"Referencia demostrativa '{reference}' resuelta al último SKU visto: {sku}.")
                return sku
        
        # Caso C: Búsqueda por coincidencia de texto en todo el pool de productos
        return self._search_reference_in_product_list(reference, product_pool)

    def _search_reference_in_product_list(self, reference: str, product_list: List[Any]) -> Optional[str]:
        """Busca la referencia en una lista de productos y devuelve el SKU del mejor match."""
        if not product_list:
            return None

        best_match_score = 0
        best_match_sku = None
        
        reference_words = set(re.findall(r'\b\w+\b', reference.lower()))
        
        for product in product_list:
            # Esta función puede recibir objetos de producto (de la BD) o dicts (del carrito).
            # Hay que manejar ambos casos.
            is_dict = isinstance(product, dict)
            name = product.get('name', '') if is_dict else getattr(product, 'name', '')
            description = product.get('description', '') if is_dict else getattr(product, 'description', '')
            sku = product.get('sku') if is_dict else getattr(product, 'sku', None)
            
            if not sku:
                continue

            product_text = f"{name} {description}".lower()
            product_words = set(re.findall(r'\b\w+\b', product_text))
            
            score = len(reference_words.intersection(product_words))
            
            if score > best_match_score:
                best_match_score = score
                best_match_sku = sku

        if best_match_sku:
            logger.info(f"Referencia '{reference}' resuelta a SKU {best_match_sku} con puntuación {best_match_score}.")
        else:
            logger.warning(f"No se pudo encontrar un match para la referencia '{reference}'.")
            
        return best_match_sku