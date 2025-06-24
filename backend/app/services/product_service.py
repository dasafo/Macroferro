# backend/app/services/product_service.py

"""
Capa de servicios para operaciones de negocio relacionadas con productos.

Esta capa implementa el patrón Service Layer para el dominio de productos,
proporcionando una abstracción de alto nivel que orquesta operaciones CRUD
complejas, maneja validaciones de negocio y coordina interacciones entre
productos, categorías e imágenes.

Responsabilidades principales:
- Validaciones de negocio complejas (SKU únicos, relaciones válidas)
- Orquestación de operaciones multi-entidad (productos + imágenes)
- Gestión de relaciones many-to-many con imágenes
- Validación de especificaciones técnicas (JSON)
- Aplicación de reglas de negocio específicas del catálogo
- Manejo de errores de integridad referencial

Características del dominio de productos:
- SKU como identificador único inmutable
- Relaciones opcionales con categorías
- Asociaciones múltiples con imágenes
- Especificaciones técnicas flexibles (JSONB)
- Integración con sistema de inventario y facturación

Patrones implementados:
- Service Layer: Lógica de negocio centralizada
- Composition: Utiliza múltiples repositorios CRUD
- Validation Layer: Validaciones complejas de dominio
- Error Handling: Manejo específico de excepciones de negocio
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import asyncio
import logging

from app.db.models.product_model import Product # Actualizado
from app.crud import product_crud, category_crud  # Removido image_crud hasta que se implemente
from app.schemas import product_schema as product_schema
from openai import AsyncOpenAI, OpenAI # Usar cliente asíncrono
from qdrant_client import AsyncQdrantClient, QdrantClient, models as qdrant_models # Usar cliente asíncrono
from qdrant_client.models import Filter, FieldCondition, MatchValue
from app.core.config import settings # Para acceder a QDRANT_URL, etc.
# from app.schemas import image as image_schema  # Comentado hasta que se implemente image_schema
# from app.core.exceptions import NotFoundError, InvalidOperationError

# Configurar logger
logger = logging.getLogger(__name__)

# Futuras excepciones personalizadas para manejo específico de errores
# from app.core.exceptions import NotFoundError, InvalidOperationError, ValidationError

# NOTA: Algunas funcionalidades están preparadas para image_crud.py e image_schema.py
# que se crearán en fases posteriores. Por ahora, product_crud maneja las relaciones básicas.

class ProductService:
    """
    Servicio para operaciones de negocio relacionadas con productos.
    
    Esta clase encapsula toda la lógica de negocio para el manejo de productos,
    incluyendo validaciones complejas, gestión de relaciones con categorías e
    imágenes, y orquestación de operaciones que afectan múltiples entidades.
    
    Características principales:
    - Validación de SKUs únicos y formato
    - Gestión de relaciones opcionales con categorías
    - Coordinación de asociaciones producto-imagen
    - Validación de especificaciones técnicas JSON
    - Aplicación de reglas de negocio del catálogo
    - Preparación para manejo de stock e inventario
    """

    def __init__(self):
        """Initialize ProductService without database dependency."""
        self.openai_client = None
        self.qdrant_client = None
    
    def _ensure_clients(self):
        """Ensure OpenAI and Qdrant clients are initialized when needed."""
        if self.openai_client is None:
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        if self.qdrant_client is None:
            self.qdrant_client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT_GRPC
            )

    # ========================================
    # OPERACIONES DE CONSULTA AVANZADA
    # ========================================

    def get_product_by_sku_details(self, db: Session, sku: str) -> Optional[Product]:
        """
        Obtiene los detalles completos de un producto por SKU con validaciones de negocio.
        """
        product = product_crud.get_product_by_sku(db, sku=sku)
        return product

    def get_all_products_with_details(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        category_id: Optional[int] = None,
        brand: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        name_like: Optional[str] = None
    ) -> List[Product]:
        """
        Obtiene una lista filtrada de productos con lógica de negocio aplicada.
        """
        # Validación de límites de paginación (regla de negocio)
        max_limit = 1000  # Prevenir consultas excesivamente grandes
        if limit > max_limit:
            limit = max_limit
        
        # Validación de rangos de precio (regla de negocio)
        if min_price is not None and min_price < 0:
            min_price = 0  # No permitir precios negativos
        
        if max_price is not None and min_price is not None:
            if max_price < min_price:
                # En lugar de error, intercambiar valores para facilidad de uso
                min_price, max_price = max_price, min_price

        products = product_crud.get_products(
            db, skip=skip, limit=limit, category_id=category_id, brand=brand,
            min_price=min_price, max_price=max_price, name_like=name_like
        )
        return products

    # ========================================
    # OPERACIONES DE ESCRITURA CON ORQUESTACIÓN
    # ========================================

    def create_new_product(self, db: Session, product_in: product_schema.ProductCreate, image_urls: Optional[List[str]] = None) -> Product:
        """
        Crea un nuevo producto con validaciones completas y asociación de imágenes.
        """
        # VALIDACIÓN 1: Verificar unicidad del SKU
        existing_product = product_crud.get_product_by_sku(db, sku=product_in.sku)
        if existing_product:
            # Para producción, lanzar excepción específica:
            # raise DuplicateError(f"Product with SKU {product_in.sku} already exists.")
            
            # Para carga CSV (Fase 1), se permite continuar
            # Asumimos que el CSV no tiene duplicados internos
            pass

        # VALIDACIÓN 2: Verificar existencia de categoría asociada
        if product_in.category_id:
            category = category_crud.get_category(db, category_id=product_in.category_id)
            if not category:
                # Para producción:
                # raise NotFoundError(f"Category with id {product_in.category_id} not found.")
                
                # Para carga CSV, asumimos que las categorías fueron cargadas previamente
                pass

        # OPERACIÓN PRINCIPAL: Crear el producto
        new_product = product_crud.create_product(db=db, product=product_in, image_urls=image_urls)
        return new_product

    def update_existing_product(self, db: Session, sku: str, product_in: product_schema.ProductUpdate) -> Optional[Product]:
        """
        Actualiza un producto existente con orquestación de relaciones y validaciones.
        """
        # VALIDACIÓN PREVIA: Verificar existencia del producto
        product = product_crud.get_product_by_sku(db, sku=sku)
        if not product:
            # Para producción:
            # raise NotFoundError(f"Product with SKU {sku} not found for update.")
            return None

        # VALIDACIÓN DE CATEGORÍA: Verificar nueva categoría si se cambia
        if product_in.category_id and product_in.category_id != product.category_id:
            category = category_crud.get_category(db, category_id=product_in.category_id)
            if not category:
                # Para producción:
                # raise NotFoundError(f"New category with id {product_in.category_id} not found.")
                pass

        # VALIDACIONES DE NEGOCIO FUTURAS:
        
        # 1. Validar cambios de precio críticos
        # if product_in.price and product_in.price != product.price:
        #     price_change_pct = abs(product_in.price - product.price) / product.price * 100
        #     if price_change_pct > 20:  # Cambio mayor al 20%
        #         # Requerir aprobación para cambios significativos
        #         await self._request_price_change_approval(sku, product.price, product_in.price)
        
        # 2. Verificar impacto en órdenes pendientes
        # if product_in.price and product_in.price > product.price:
        #     pending_orders_count = await self._check_pending_orders(sku)
        #     if pending_orders_count > 0:
        #         logger.warning(f"Price increase for {sku} affects {pending_orders_count} pending orders")
        
        # 3. Validar especificaciones técnicas
        # if product_in.spec_json:
        #     validation_errors = self._validate_product_specifications(product_in.spec_json, product.category)
        #     if validation_errors:
        #         raise ValidationError(f"Invalid specifications: {validation_errors}")

        updated_product = product_crud.update_product(db=db, sku=sku, product=product_in)
        return updated_product

    def delete_existing_product(self, db: Session, sku: str) -> Optional[Product]:
        """
        Elimina un producto y maneja sus relaciones y dependencias.
        """
        # VALIDACIÓN PREVIA: Verificar existencia del producto
        product_to_delete = product_crud.get_product_by_sku(db, sku=sku)
        if not product_to_delete:
            # Para producción:
            # raise NotFoundError(f"Product with SKU {sku} not found for deletion.")
            return None
        
        # VALIDACIONES CRÍTICAS DE NEGOCIO (futuras):
        
        # 1. Verificar asociaciones con facturas (crítico para integridad contable)
        # if invoice_items_count > 0:
        #     raise InvalidOperationError(
        #         f"Cannot delete product SKU {sku}: referenced in {invoice_items_count} invoice items. "
        #         f"Consider marking as discontinued instead."
        #     )
        
        # 2. Verificar impacto en inventario actual
        # current_stock_value = self._calculate_total_stock_value(db, sku)
        # if current_stock_value > 1000:  # Umbral configurable
        #     logger.warning(f"Deleting product {sku} will write off ${current_stock_value:.2f} in inventory")
        #     # Requerir confirmación adicional para alto valor
        
        # 3. Verificar dependencias en órdenes pendientes
        # pending_references = await self._check_external_references(sku)
        # if pending_references:
        #     raise InvalidOperationError(f"Product {sku} has pending external references: {pending_references}")
        
        # 4. Logging crítico para auditoría
        # await self._log_product_deletion(sku, product_to_delete, deletion_reason="API_REQUEST")

        # OPERACIÓN DE ELIMINACIÓN
        # Las foreign key constraints manejarán automáticamente:
        # - product_images: CASCADE (elimina asociaciones con imágenes)
        # - stock: CASCADE (elimina registros de inventario)
        # - invoice_items: RESTRICT (previene eliminación si está facturado)
        # 
        # Si hay restricciones, SQLAlchemy lanzará IntegrityError que debe capturarse en la API
        try:
            deleted_product = product_crud.delete_product(db=db, sku=sku)
            return deleted_product
        except Exception as e:
            # En producción, manejar específicamente IntegrityError
            logger.error(f"Error al eliminar producto {sku}: {e}")
            # raise InvalidOperationError(f"Could not delete product {sku}. It might be referenced in an invoice.")
            return None

    async def search_products(
        self, 
        db: Session,
        query_text: str, 
        top_k: int = 10, 
        category_filter: Optional[int] = None
    ) -> dict:
        """
        Realiza una búsqueda semántica de productos usando embeddings y Qdrant,
        con un filtrado opcional por categoría.
        """
        self._ensure_clients()
        
        try:
            # 1. Generar embedding para la consulta del usuario
            query_embedding = await self.get_embedding(query_text)

            # 2. Construir filtro de Qdrant si se especifica una categoría
            qdrant_filter = None
            if category_filter is not None:
                qdrant_filter = qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="category_id",
                            match=qdrant_models.MatchValue(value=category_filter)
                        )
                    ]
                )

            # 3. Realizar búsqueda en Qdrant
            search_result = self.qdrant_client.search(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True
            )

            # 4. Procesar resultados y obtener SKUs
            found_skus = [point.payload['sku'] for point in search_result]
            
            if not found_skus:
                return {"main_results": [], "related_results": []}

            # 5. Recuperar productos de la base de datos
            # Usar una función optimizada para obtener múltiples productos por SKU
            products_db = product_crud.get_products_by_skus(db, skus=found_skus)
            
            # Mapear productos por SKU para fácil acceso
            products_map = {p.sku: p for p in products_db}
            
            # Ordenar los productos según el orden de Qdrant y separar
            ordered_products = [products_map[sku] for sku in found_skus if sku in products_map]
            
            main_results = ordered_products[:top_k//2]
            related_results = ordered_products[top_k//2:]

            return {"main_results": main_results, "related_results": related_results}

        except Exception as e:
            logger.error(f"Error en search_products: {e}")
            return {"main_results": [], "related_results": []}

    async def get_embedding(self, text: str) -> List[float]:
        """Genera embeddings para un texto usando el modelo de OpenAI."""
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY no configurada para búsqueda semántica")
            return []

        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error al generar embedding: {e}")
            return []

# ========================================
# INSTANCIA SINGLETON DEL SERVICIO
# ========================================

# Instancia única del servicio para ser usada en toda la aplicación
product_service = ProductService()

# ========================================
# EXTENSIONES Y MÉTODOS AUXILIARES FUTUROS
# ========================================

# Métodos auxiliares que se implementarían en versiones futuras:
#
# def _calculate_total_stock(self, db: Session, sku: str) -> int:
#     """Calcula el stock total del producto en todos los almacenes."""
#     pass
#
# def _check_availability(self, product: models.Product) -> bool:
#     """Determina disponibilidad según reglas de negocio complejas."""
#     pass
#
# def _validate_product_specifications(self, specs: Dict[str, Any], category: models.Category) -> List[str]:
#     """Valida especificaciones técnicas según reglas de la categoría."""
#     pass
#
# def _calculate_display_price(self, product: models.Product, user_context: Dict[str, Any]) -> float:
#     """Calcula precio de display considerando descuentos y contexto del usuario."""
#     pass
#
# def _is_product_available_for_user(self, product: models.Product, user_context: Dict[str, Any]) -> bool:
#     """Determina si el producto es visible/disponible para el usuario específico."""
#     pass
#
# def _log_product_access(self, sku: str, user_context: Dict[str, Any]) -> None:
#     """Registra acceso al producto para análisis de demanda."""
#     pass
#
# def _calculate_total_stock_value(self, db: Session, sku: str) -> float:
#     """Calcula el valor total del inventario para un producto."""
#     pass
#
# async def _check_external_references(self, sku: str) -> List[str]:
#     """Verifica referencias externas al producto (órdenes pendientes, catálogos, etc.)."""
#     pass
#
# async def _log_product_deletion(self, sku: str, product: models.Product, deletion_reason: str) -> None:
#     """Registra eliminación de producto para auditoría completa."""
#     pass
#
# async def _request_price_change_approval(self, sku: str, old_price: float, new_price: float) -> None:
#     """Solicita aprobación para cambios significativos de precio."""
#     pass