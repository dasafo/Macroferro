# backend/app/crud/product_crud.py
"""
Operaciones CRUD para el modelo Product.

Este módulo proporciona funciones para consultar y actualizar el stock de productos en diferentes almacenes.
"""

from sqlalchemy.orm import Session, joinedload, subqueryload,selectinload
from typing import List, Optional, Dict, Any
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product_model import Product, ProductImage, Image
from app.schemas import product_schema as product_schema # Schemas Pydantic para productos
from . import category_crud

import logging

logger = logging.getLogger(__name__)

# ========================================
# OPERACIONES DE LECTURA (READ)
# ========================================

async def get_product_by_sku(db: AsyncSession, sku: str) -> Optional[Product]:
    """Obtiene un producto por su SKU de forma asíncrona, con relaciones precargadas."""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.images))
        .filter(Product.sku == sku)
    )
    return result.scalars().first()


async def get_products(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 10,
    category_id: Optional[int] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    name_like: Optional[str] = None,
    skus: Optional[List[str]] = None
) -> List[Product]:
    """
    Obtiene una lista filtrada y paginada de productos de forma asíncrona.
    """
    query = select(Product).options(
        selectinload(Product.category),
        selectinload(Product.images)
    )

    if category_id is not None:
        all_category_ids = await category_crud.get_category_and_all_children_ids(db, category_id)
        if all_category_ids:
            query = query.filter(Product.category_id.in_(all_category_ids))
        else:
            return []

    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if name_like:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{name_like}%"),
                Product.description.ilike(f"%{name_like}%")
            )
        )
    if skus:
        query = query.filter(Product.sku.in_(skus))
        
    query = query.order_by(Product.sku).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_products_by_skus(db: AsyncSession, skus: List[str]) -> List[Product]:
    """Obtiene una lista de productos a partir de una lista de SKUs de forma asíncrona."""
    if not skus:
        return []
    
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.images))
        .filter(Product.sku.in_(skus))
    )
    return result.scalars().all()


async def search_products_by_term(db: AsyncSession, search_term: str, top_k: int = 10) -> List[Product]:
    """
    Realiza una búsqueda simple de productos por un término en nombre o descripción.
    """
    query = select(Product).filter(
        or_(
            Product.name.ilike(f"%{search_term}%"),
            Product.description.ilike(f"%{search_term}%")
        )
    ).limit(top_k)
    
    result = await db.execute(query)
    products = result.scalars().all()
    logger.info(f"Búsqueda por término '{search_term}' encontró {len(products)} productos.")
    return products
    

# ========================================
# OPERACIONES DE ESCRITURA (CREATE, UPDATE, DELETE)
# ========================================

async def create_product(
    db: AsyncSession, 
    product_data: product_schema.ProductCreate, 
    image_urls: Optional[List[str]] = None
) -> Product:
    """Crea un nuevo producto en la base de datos de forma asíncrona."""
    
    db_product = Product(
        sku=product_data.sku,
        name=product_data.name,
        description=product_data.description,
        price=product_data.price,
        brand=product_data.brand,
        category_id=product_data.category_id,
        spec_json=product_data.spec_json
    )
    
    if image_urls:
        for url in image_urls:
            image = await db.execute(select(Image).filter_by(url=url))
            db_image = image.scalar_one_or_none()
            if not db_image:
                db_image = Image(url=url)
                db.add(db_image)
            db_product.images.append(db_image)
            
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product

async def update_product(db: AsyncSession, sku: str, product_update: product_schema.ProductUpdate) -> Optional[Product]:
    """Actualiza un producto existente de forma asíncrona."""
    db_product = await get_product_by_sku(db, sku)
    if not db_product:
        return None
        
    update_data = product_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)
        
    await db.commit()
    await db.refresh(db_product)
    return db_product

async def delete_product(db: AsyncSession, sku: str) -> Optional[Product]:
    """Elimina un producto de la base de datos de forma asíncrona."""
    db_product = await get_product_by_sku(db, sku)
    if db_product:
        await db.delete(db_product)
        await db.commit()
    return db_product

async def add_image_to_product(db: AsyncSession, sku: str, image_url: str) -> Optional[Product]:
    """Añade una imagen a un producto de forma asíncrona."""
    product = await get_product_by_sku(db, sku)
    if not product:
        return None
    
    image_result = await db.execute(select(Image).filter_by(url=image_url))
    image = image_result.scalar_one_or_none()
    
    if not image:
        image = Image(url=image_url)
        db.add(image)
    
    if image not in product.images:
        product.images.append(image)
    
    await db.commit()
    await db.refresh(product)
    return product

async def remove_image_from_product(db: AsyncSession, sku: str, image_url: str) -> Optional[Product]:
    """Elimina una imagen de un producto de forma asíncrona."""
    product = await get_product_by_sku(db, sku)
    if not product:
        return None
        
    image_result = await db.execute(select(Image).filter_by(url=image_url))
    image = image_result.scalar_one_or_none()
    
    if image and image in product.images:
        product.images.remove(image)
        await db.commit()
        await db.refresh(product)
        
    return product

async def get_product_images(db: AsyncSession, sku: str) -> List[Image]:
    """Obtiene todas las imágenes de un producto de forma asíncrona."""
    product = await db.execute(
        select(Product).options(selectinload(Product.images)).filter_by(sku=sku)
    )
    db_product = product.scalar_one_or_none()
    return db_product.images if db_product else []

