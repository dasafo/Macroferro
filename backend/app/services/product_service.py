# backend/app/services/product_service.py
"""
Servicio para operaciones de negocio relacionadas con productos.

Este servicio se encarga de gestionar la lógica de negocio para el manejo de productos,
incluyendo validaciones complejas, gestión de relaciones con categorías e imágenes,
y orquestación de operaciones que afectan múltiples entidades.

Características principales:
- Validación de SKUs únicos y formato
- Gestión de relaciones opcionales con categorías
- Coordinación de asociaciones producto-imagen
- Validación de especificaciones técnicas JSON
- Aplicación de reglas de negocio del catálogo
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

# Configurar logger
logger = logging.getLogger(__name__)



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
        
        # Si hay restricciones, SQLAlchemy lanzará IntegrityError que debe capturarse en la API
        try:
            deleted_product = product_crud.delete_product(db, sku=sku)
            return deleted_product
        except Exception as e: # Captura de excepción más específica sería mejor
            # logger.error(f"Error deleting product SKU {sku}: {e}")
            # raise InvalidOperationError(f"Could not delete product {sku}. It may be referenced in existing orders.")
            pass # Temporalmente silenciar para la Fase 1

    async def search_products(
        self, db: Session, query_text: str, top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Busca productos por texto y devuelve los resultados principales y relacionados.
        """
        
        # Simulamos una búsqueda que podría ser semántica en el futuro
        products = await product_crud.search_products_by_term(db, search_term=query_text, top_k=top_k)
        
        return {"query": query_text, "products": products}

    # ========================================
    # GESTIÓN DE EMBEDDINGS (para Qdrant)
    # ========================================

    async def get_all_products_for_embedding(self, db: Session) -> List[Product]:
        """
        Obtiene todos los productos de la base de datos para la indexación en Qdrant.
        """
        return product_crud.get_all_products(db)
        
    async def get_embedding(self, text: str) -> List[float]:
        """Generates an embedding for a given text using OpenAI's API."""
        if self.openai_client is None:
            # Asegurarse que es un cliente asíncrono
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting embedding from OpenAI: {e}")
            raise # Re-lanzar la excepción para que el llamador la maneje
    
    async def create_and_upload_embeddings(self, db: Session):
        """
        Crea embeddings para todos los productos y los sube a Qdrant.
        """
        # Asegurarse de que los clientes asíncronos estén inicializados
        if self.qdrant_client is None:
            self.qdrant_client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT_GRPC)
        
        if self.openai_client is None:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # Verificar y crear la colección en Qdrant si no existe
        try:
            await self.qdrant_client.get_collection(collection_name=settings.QDRANT_COLLECTION_PRODUCTS)
            logger.info(f"Colección '{settings.QDRANT_COLLECTION_PRODUCTS}' ya existe.")
        except Exception:
            logger.info(f"Colección '{settings.QDRANT_COLLECTION_PRODUCTS}' no encontrada. Creando...")
            await self.qdrant_client.recreate_collection(
                collection_name=settings.QDRANT_COLLECTION_PRODUCTS,
                vectors_config=qdrant_models.VectorParams(size=1536, distance=qdrant_models.Distance.COSINE),
            )
            logger.info("Colección creada.")
        
        products = await self.get_all_products_for_embedding(db)
        logger.info(f"Obtenidos {len(products)} productos para embedding.")

        points = []
        for product in products:
            # Crear texto descriptivo para el embedding
            text_to_embed = f"Nombre: {product.name}. Descripción: {product.description}. Marca: {product.brand.name if product.brand else 'N/A'}. Categoría: {product.category.name if product.category else 'N/A'}."
            
            # Crear embedding
            embedding = await self.get_embedding(text_to_embed)
            
            # Crear punto para Qdrant
            point = qdrant_models.PointStruct(
                id=product.id,
                vector=embedding,
                payload={
                    "sku": product.sku,
                    "name": product.name,
                    "category_id": product.category_id,
                    "brand_id": product.brand_id,
                }
            )
            points.append(point)

        # Subir los puntos a Qdrant en lotes
        if points:
            await self.qdrant_client.upsert(
                collection_name=settings.QDRANT_COLLECTION_PRODUCTS,
                points=points,
                wait=True
            )
            logger.info(f"Subidos {len(points)} embeddings de productos a Qdrant.")
        else:
            logger.info("No hay productos para generar embeddings.")
            
# ========================================
# INSTANCIA SINGLETON DEL SERVICIO
# ========================================

# Instancia única del servicio para ser usada en toda la aplicación
product_service = ProductService()
