# backend/app/api/v1/endpoints/products.py

"""
Endpoints REST para operaciones CRUD y búsqueda de productos.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.api import deps
from app.schemas import product as product_schema
from app.services.product_service import product_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=product_schema.ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    *,
    db: Session = Depends(deps.get_db),
    product_in: product_schema.ProductCreate,
) -> product_schema.ProductResponse:
    """Crea un nuevo producto en el catálogo."""
    logger.info(f"🆕 PRODUCTO: Creando producto con SKU '{product_in.sku}'")
    
    existing_product = product_service.get_product_by_sku_details(db, sku=product_in.sku)
    if existing_product:
        logger.error(f"❌ ERROR: Product with SKU {product_in.sku} already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with SKU {product_in.sku} already exists."
        )
    
    product = product_service.create_new_product(db=db, product_in=product_in)
    
    created_product_details = product_service.get_product_by_sku_details(db, sku=product.sku)
    if not created_product_details:
        logger.error(f"❌ ERROR: Error creating product details for SKU {product.sku}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error creating product details"
        )
    
    logger.info(f"✅ PRODUCTO: Creado exitosamente SKU '{created_product_details.sku}'")
    return created_product_details


@router.put("/{sku}", response_model=product_schema.ProductResponse)
async def update_product(
    *,
    db: Session = Depends(deps.get_db),
    sku: str,
    product_in: product_schema.ProductUpdate,
) -> product_schema.ProductResponse:
    """Actualiza un producto existente."""
    logger.info(f"🔄 PRODUCTO: Actualizando producto SKU '{sku}'")
    
    updated_product = product_service.update_existing_product(db=db, sku=sku, product_in=product_in)
    if not updated_product:
        logger.error(f"❌ ERROR: No se pudo actualizar el producto SKU '{sku}'")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found for update")
    
    product_details = product_service.get_product_by_sku_details(db, sku=updated_product.sku)
    if not product_details:
        logger.error(f"❌ ERROR: Error fetching updated product details for SKU {updated_product.sku}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error fetching updated product details"
        )
    
    logger.info(f"✅ PRODUCTO: Actualizado exitosamente SKU '{sku}'")
    return product_details


@router.delete("/{sku}", response_model=product_schema.ProductResponse)
async def delete_product(
    *,
    db: Session = Depends(deps.get_db),
    sku: str,
) -> product_schema.ProductResponse:
    """Elimina un producto del sistema."""
    logger.info(f"🗑️ PRODUCTO: Eliminando producto SKU '{sku}'")
    
    deleted_product = product_service.delete_existing_product(db=db, sku=sku)
    if not deleted_product:
        logger.error(f"❌ ERROR: No se pudo eliminar el producto SKU '{sku}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Product not found for deletion or cannot be deleted."
        )
    
    logger.info(f"✅ PRODUCTO: Eliminado exitosamente SKU '{sku}'")
    return deleted_product


@router.get("/{sku}", response_model=product_schema.ProductResponse)
async def read_product(
    *,
    db: Session = Depends(deps.get_db),
    sku: str,
) -> product_schema.ProductResponse:
    """Obtiene los detalles de un producto por SKU."""
    logger.debug(f"🔍 PRODUCTO: Buscando producto SKU '{sku}'")
    
    product = product_service.get_product_by_sku_details(db=db, sku=sku)
    if not product:
        logger.warning(f"⚠️ PRODUCTO: No encontrado SKU '{sku}'")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    return product


@router.get("/", response_model=List[product_schema.ProductResponse])
async def read_products(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = Query(default=100, ge=1, le=200),
    category_id: Optional[int] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    name: Optional[str] = None
) -> List[product_schema.ProductResponse]:
    """Obtiene una lista filtrada y paginada de productos."""
    logger.debug(f"📋 PRODUCTOS: Listando con filtros - skip={skip}, limit={limit}")
    
    products = product_service.get_all_products_with_details(
        db=db, skip=skip, limit=limit, category_id=category_id, brand=brand,
        min_price=min_price, max_price=max_price, name_like=name
    )
    
    logger.debug(f"📋 PRODUCTOS: Encontrados {len(products)} resultados")
    return products


@router.post("/search", response_model=product_schema.ProductSearchResponse)
async def search_products(
    query: product_schema.ProductSearchQuery,
    db: Session = Depends(deps.get_db)
) -> product_schema.ProductSearchResponse:
    """Realiza una búsqueda semántica de productos."""
    logger.info(f"🎯 BÚSQUEDA: Iniciando búsqueda para '{query.query_text}' con top_k={query.top_k}")
    
    if not query.query_text.strip():
        logger.warning("⚠️ BÚSQUEDA: Consulta vacía recibida")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La consulta de búsqueda no puede estar vacía.")

    search_results = await product_service.search_products(
        query_text=query.query_text,
        top_k=query.top_k,
        db=db
    )

    if not search_results["main_results"] and not search_results["related_results"]:
        logger.info(f"🔍 BÚSQUEDA: Sin resultados para '{query.query_text}'")
        return product_schema.ProductSearchResponse(main_results=[], related_results=[])

    logger.info(f"✅ BÚSQUEDA: {len(search_results['main_results'])} principales, {len(search_results['related_results'])} relacionados")
    
    return product_schema.ProductSearchResponse(
        main_results=search_results["main_results"],
        related_results=search_results["related_results"]
    )