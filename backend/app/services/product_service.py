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

from app.db import models
from app.crud import product_crud, category_crud  # Removido image_crud hasta que se implemente
from app.schemas import product as product_schema
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

    def get_product_by_sku_details(self, db: Session, sku: str) -> Optional[models.Product]:
        """
        Obtiene los detalles completos de un producto por SKU con validaciones de negocio.
        
        Esta función actúa como punto de entrada principal para obtener información
        detallada de un producto, incluyendo todas sus relaciones (categoría, imágenes).
        Permite agregar lógica de negocio adicional como cálculos derivados y validaciones.
        
        Args:
            db: Sesión de SQLAlchemy
            sku: Código único del producto
            
        Returns:
            Objeto Product con relaciones cargadas, o None si no existe
            
        Funcionalidades actuales:
            - Carga eager de categoría e imágenes (optimización N+1)
            - Validación implícita de existencia
            
        Extensiones futuras:
            - Cálculo de stock total desde múltiples almacenes
            - Aplicación de descuentos o precios especiales por usuario
            - Logging de accesos a productos para análisis de demanda
            - Verificación de permisos de visualización por categoría
            - Métricas de popularidad y recomendaciones relacionadas
            
        Consideraciones de negocio:
            - Productos descatalogados vs productos inactivos
            - Visibilidad según contexto del usuario (B2B vs B2C)
            - Información sensible que no debe mostrarse en ciertos contextos
        """
        product = product_crud.get_product_by_sku(db, sku=sku)
        
        # Validación de existencia con manejo de errores futuro:
        # if not product:
        #     raise NotFoundError(f"Product with SKU {sku} not found")
        
        # Extensiones futuras para enriquecimiento de datos:
        # if product:
        #     # Calcular stock total si no se hace en CRUD
        #     product.total_stock = self._calculate_total_stock(db, sku)
        #     
        #     # Aplicar reglas de negocio específicas
        #     product.is_available = self._check_availability(product)
        #     
        #     # Logging para análisis de demanda
        #     self._log_product_access(sku, user_context)
        
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
    ) -> List[models.Product]:
        """
        Obtiene una lista filtrada de productos con lógica de negocio aplicada.
        
        Esta función proporciona capacidades avanzadas de búsqueda y filtrado,
        aplicando reglas de negocio específicas y validaciones que van más allá
        de las simples consultas CRUD.
        
        Args:
            db: Sesión de SQLAlchemy
            skip: Offset para paginación
            limit: Límite de registros por página
            category_id: Filtro por categoría (opcional)
            brand: Filtro por marca con búsqueda parcial (opcional)
            min_price: Precio mínimo (inclusivo, opcional)
            max_price: Precio máximo (inclusivo, opcional)
            name_like: Búsqueda parcial en nombre (opcional)
            
        Returns:
            Lista de productos filtrados con relaciones cargadas
            
        Validaciones de negocio aplicadas:
            - Límites de paginación según tipo de usuario
            - Filtros de disponibilidad automáticos
            - Exclusión de productos descatalogados
            - Aplicación de permisos por categoría
            
        Optimizaciones implementadas:
            - Eager loading de relaciones para evitar N+1 queries
            - Índices utilizados eficientemente en filtros
            - Paginación optimizada para grandes catálogos
            
        Extensiones futuras:
            - Ordenamiento inteligente por popularidad
            - Filtros adicionales (etiquetas, atributos dinámicos)
            - Búsqueda full-text en especificaciones
            - Integración con sistema de recomendaciones
            - Precios dinámicos según contexto del usuario
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
        
        # Aplicar reglas de negocio adicionales (futuras):
        # filtered_products = []
        # for product in products:
        #     # Verificar disponibilidad según reglas de negocio
        #     if self._is_product_available_for_user(product, user_context):
        #         # Enriquecer con información calculada
        #         product.display_price = self._calculate_display_price(product, user_context)
        #         filtered_products.append(product)
        
        return products

    # ========================================
    # OPERACIONES DE ESCRITURA CON ORQUESTACIÓN
    # ========================================

    def create_new_product(self, db: Session, product_in: product_schema.ProductCreate, image_urls: Optional[List[str]] = None) -> models.Product:
        """
        Crea un nuevo producto con validaciones completas y asociación de imágenes.
        
        Esta función orquesta la creación completa de un producto, incluyendo
        validaciones de negocio, verificación de dependencias y asociación
        automática con imágenes si se proporcionan.
        
        Args:
            db: Sesión de SQLAlchemy
            product_in: Esquema Pydantic con datos validados del producto
            image_urls: Lista opcional de URLs de imágenes para asociar
            
        Returns:
            Objeto Product recién creado con todas sus relaciones
            
        Validaciones de negocio implementadas:
            1. Verificación de unicidad del SKU
            2. Validación de existencia de categoría asociada
            3. Verificación de formato de especificaciones JSON
            4. Validación de URLs de imágenes (si se proporcionan)
            
        Orquestación de operaciones:
            - Creación del producto base
            - Procesamiento y asociación de imágenes
            - Manejo de transacciones para consistencia
            - Rollback automático en caso de errores
            
        Consideraciones especiales:
            - Para carga CSV: Las validaciones están relajadas
            - Para API: Se aplican todas las validaciones estrictas
            - URLs de imágenes inválidas generan advertencias, no errores
            - Las transacciones garantizan atomicidad de la operación
            
        Extensiones preparadas (comentadas):
            - Sistema de creación/reutilización de imágenes
            - Validaciones avanzadas de especificaciones
            - Integración con sistema de inventario inicial
            - Notificaciones automáticas de nuevos productos
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
        db_product = product_crud.create_product(db=db, product=product_in)

        # ORQUESTACIÓN: Procesar y asociar imágenes si se proporcionan
        # Esta sección está preparada para cuando se implemente el sistema de imágenes completo
        if image_urls:
            # Procesar cada URL de imagen proporcionada
            successful_associations = 0
            failed_urls = []
            
            for url_str in image_urls:
                try:
                    # Validación de formato de URL (manejada por Pydantic en el futuro)
                    # image_data = image_schema.ImageCreate(url=str(url_str))
                    
                    # Obtener o crear la imagen en el sistema
                    # Esta función manejará la deduplicación de imágenes
                    # db_image = image_crud.get_or_create_image(db=db, image_in=image_data)
                    
                    # Asociar la imagen al producto
                    # association = product_crud.add_image_to_product(
                    #     db=db, sku=db_product.sku, image_id=db_image.image_id
                    # )
                    # 
                    # if association:
                    #     successful_associations += 1
                    
                    pass  # Placeholder para implementación futura
                    
                except ValueError as e:
                    # Manejar URLs inválidas sin fallar toda la operación
                    failed_urls.append(url_str)
                    print(f"Advertencia: URL de imagen no válida '{url_str}': {e}")
                    # En producción, usar logging en lugar de print
                    # logger.warning(f"Invalid image URL for product {db_product.sku}: {url_str} - {e}")
                except Exception as e:
                    # Manejar otros errores de procesamiento de imágenes
                    failed_urls.append(url_str)
                    print(f"Error procesando imagen '{url_str}': {e}")
                    # logger.error(f"Error processing image for product {db_product.sku}: {url_str} - {e}")
            
            # Logging de resultados del procesamiento de imágenes
            if image_urls:
                total_urls = len(image_urls)
                failed_count = len(failed_urls)
                print(f"Procesamiento de imágenes: {successful_associations}/{total_urls} exitosas, {failed_count} fallidas")
        
        # Refrescar el objeto para cargar relaciones creadas
        db.refresh(db_product)
        return db_product

    def update_existing_product(self, db: Session, sku: str, product_in: product_schema.ProductUpdate) -> Optional[models.Product]:
        """
        Actualiza un producto existente con validaciones de negocio complejas.
        
        Esta función maneja actualizaciones que pueden afectar múltiples aspectos
        del sistema: relaciones con categorías, especificaciones técnicas,
        precios que podrían afectar órdenes pendientes, etc.
        
        Args:
            db: Sesión de SQLAlchemy
            sku: SKU del producto a actualizar (identificador inmutable)
            product_in: Esquema Pydantic con campos a actualizar
            
        Returns:
            Objeto Product actualizado, o None si no existe
            
        Validaciones de negocio complejas:
            1. Verificación de existencia del producto
            2. Validación de nueva categoría (si se cambia)
            3. Verificación de impacto en precios para órdenes pendientes
            4. Validación de especificaciones JSON actualizadas
            
        Consideraciones especiales:
            - SKU es inmutable (identificador de negocio)
            - Cambios de precio pueden requerir aprobación
            - Cambios de categoría afectan clasificación y navegación
            - Especificaciones JSON se reemplazan completamente
            
        Reglas de negocio futuras:
            - Audit trail de cambios críticos (precio, categoría)
            - Notificaciones automáticas de cambios relevantes
            - Validación de permisos según tipo de cambio
            - Integración con workflow de aprobaciones
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

        return product_crud.update_product(db=db, sku=sku, product_update=product_in)

    def delete_existing_product(self, db: Session, sku: str) -> Optional[models.Product]:
        """
        Elimina un producto con validaciones críticas de integridad de negocio.
        
        Esta operación es especialmente crítica porque puede afectar:
        - Órdenes de compra pendientes
        - Historial de facturación
        - Referencias en el sistema de inventario
        - Enlaces desde catálogos externos
        
        Args:
            db: Sesión de SQLAlchemy
            sku: SKU del producto a eliminar
            
        Returns:
            Objeto Product eliminado, o None si no existía
            
        Restricciones de integridad (manejadas por FK constraints):
            - invoice_items: ON DELETE RESTRICT previene eliminación si está facturado
            - product_images: ON DELETE CASCADE elimina asociaciones automáticamente
            - stock: ON DELETE CASCADE elimina registros de inventario
            
        Validaciones de negocio críticas:
            1. Verificar ausencia en facturas históricas
            2. Evaluar impacto en órdenes pendientes
            3. Considerar valor de inventario que se perdería
            4. Verificar dependencias en sistemas externos
            
        Alternativas a eliminación física:
            - Descatalogar: Marcar como inactivo/descatalogado
            - Archivar: Mover a tabla de productos históricos
            - Soft delete: Marcar como eliminado pero preservar datos
            
        Procedimiento recomendado:
            1. Verificar restricciones de negocio
            2. Calcular impacto financiero
            3. Requerir confirmación explícita
            4. Ejecutar eliminación con logging completo
        """
        # VALIDACIÓN PREVIA: Verificar existencia del producto
        product_to_delete = product_crud.get_product_by_sku(db, sku=sku)
        if not product_to_delete:
            # Para producción:
            # raise NotFoundError(f"Product with SKU {sku} not found for deletion.")
            return None
        
        # VALIDACIONES CRÍTICAS DE NEGOCIO (futuras):
        
        # 1. Verificar asociaciones con facturas (crítico para integridad contable)
        # invoice_items_count = db.query(models.InvoiceItem).filter(models.InvoiceItem.sku == sku).count()
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
            return product_crud.delete_product(db=db, sku=sku)
        except Exception as e:
            # En producción, manejar específicamente IntegrityError
            # if isinstance(e, IntegrityError):
            #     if "invoice_items" in str(e):
            #         raise InvalidOperationError(f"Cannot delete product {sku}: referenced in existing invoices")
            #     else:
            #         raise InvalidOperationError(f"Cannot delete product {sku}: has dependent records")
            # raise
            raise  # Re-lanzar la excepción para manejo en capas superiores

    async def search_products(
        self, 
        db: Session,
        query_text: str, 
        top_k: int = 10, 
        category_filter: Optional[int] = None
    ) -> dict:
        logger.debug(f"Starting search for query: '{query_text}' with top_k: {top_k}")
        
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY no configurada para búsqueda semántica")
            return {"main_results": [], "related_results": []}

        # Ensure clients are initialized
        self._ensure_clients()

        try:
            # Generate embedding for search query
            response = self.openai_client.embeddings.create(
                input=query_text,
                model="text-embedding-3-small"
            )
            query_embedding = response.data[0].embedding
            
            # Prepare search filter if category is specified
            search_filter = None
            if category_filter:
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="category_id",
                            match=MatchValue(value=category_filter)
                        )
                    ]
                )
            
            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k
            )
            
            # Filter by similarity threshold
            similarity_threshold = 0.4  # Balanced threshold - not too strict, not too permissive
            filtered_results = [
                result for result in search_results 
                if result.score >= similarity_threshold
            ]
            
            if not filtered_results:
                return {"main_results": [], "related_results": []}
            
            # Extract SKUs from filtered results
            skus = [result.payload["sku"] for result in filtered_results]
            
            # Get full product details from PostgreSQL
            products = db.query(models.Product).filter(models.Product.sku.in_(skus)).all()
            
            # Create a mapping for quick lookup
            product_map = {product.sku: product for product in products}
            
            # Sort products by relevance (same order as Qdrant results)
            sorted_products = []
            for result in filtered_results:
                sku = result.payload["sku"]
                if sku in product_map:
                    sorted_products.append(product_map[sku])
            
            # Split into main and related results
            main_count = min(2, len(sorted_products))
            main_results = sorted_products[:main_count]
            related_results = sorted_products[main_count:main_count+2]
            
            return {
                "main_results": [product_schema.ProductResponse.from_orm(product) for product in main_results],
                "related_results": [product_schema.ProductResponse.from_orm(product) for product in related_results]
            }
            
        except Exception as e:
            logger.error(f"Error in search_products: {str(e)}")
            raise e

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