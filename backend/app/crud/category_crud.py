# backend/app/crud/category_crud.py

"""
Operaciones CRUD (Create, Read, Update, Delete) para el modelo Category.

Este módulo abstrae el acceso a la tabla de categorías, manejando la lógica
de consultas, jerarquías (padre/hijo) y paginación.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.models.category_model import Category
from app.schemas import category_schema

# ========================================
# OPERACIONES DE LECTURA (READ)
# ========================================

async def get_category(db: AsyncSession, category_id: int) -> Optional[Category]:
    """Obtiene una categoría por su ID."""
    result = await db.execute(select(Category).filter(Category.category_id == category_id))
    return result.scalars().first()


async def get_category_by_name_and_parent(db: AsyncSession, name: str, parent_id: Optional[int]) -> Optional[Category]:
    """
    Obtiene una categoría por su nombre y parent_id.
    
    Útil para validar duplicados, ya que los nombres pueden repetirse
    en diferentes niveles jerárquicos.
    """
    query = select(Category).filter(Category.name == name)
    
    if parent_id is None:
        query = query.filter(Category.parent_id.is_(None))
    else:
        query = query.filter(Category.parent_id == parent_id)
    result = await db.execute(query)
    return result.scalars().first()


async def get_categories(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Category]:
    """Obtiene una lista paginada de todas las categorías."""
    result = await db.execute(select(Category).offset(skip).limit(limit))
    return result.scalars().all()


async def get_root_categories(db: AsyncSession) -> List[Category]:
    """Obtiene las categorías principales (aquellas sin un padre)."""
    result = await db.execute(select(Category).filter(Category.parent_id.is_(None)))
    return result.scalars().all()


async def get_subcategories(db: AsyncSession, parent_id: int) -> List[Category]:
    """Obtiene las subcategorías de una categoría padre dada."""
    result = await db.execute(select(Category).filter(Category.parent_id == parent_id))
    return result.scalars().all()


async def get_category_and_all_children_ids(db: AsyncSession, category_id: int) -> List[int]:
    """
    Obtiene el ID de la categoría dada y los IDs de toda su descendencia.
    Utiliza una consulta recursiva (CTE) para recorrer la jerarquía.
    """
    category_cte = select(Category.category_id).filter(Category.category_id == category_id).cte(name='category_cte', recursive=True)
    
    recursive_part = select(Category.category_id).join(category_cte, Category.parent_id == category_cte.c.category_id)
    
    full_cte = category_cte.union_all(recursive_part)
    
    result = await db.execute(select(full_cte.c.category_id))
    
    return [r[0] for r in result.fetchall()]


# ========================================
# OPERACIONES DE ESCRITURA (CREATE, UPDATE, DELETE)
# ========================================

async def create_category(db: AsyncSession, category: category_schema.CategoryCreate) -> Category:
    """
    Crea una nueva categoría.
    
    Asigna un ID predefinido en lugar de autoincrementar. Es importante
    validar duplicados y la existencia del padre antes de llamar a esta función.
    """
    db_category = Category(
        category_id=category.category_id,
        name=category.name, 
        parent_id=category.parent_id
    )
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return db_category


async def update_category(db: AsyncSession, category_id: int, category_update: category_schema.CategoryUpdate) -> Optional[Category]:
    """
    Actualiza una categoría existente.
    
    Realiza una actualización parcial: solo se modifican los campos
    presentes en el objeto `category_update`.
    """
    db_category = await get_category(db, category_id=category_id)
    if not db_category:
        return None
    
    update_data = category_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
    
    db.add(db_category)  # Marca el objeto como modificado
    await db.commit()  # Persiste los cambios
    await db.refresh(db_category)  # Recarga datos actualizados
    return db_category


async def delete_category(db: AsyncSession, category_id: int) -> Optional[Category]:
    """
    Elimina una categoría.
    
    Debido a las constraints de la BD (ON DELETE SET NULL), al eliminar:
    - Los productos asociados tendrán `category_id = NULL`.
    - Las subcategorías se convertirán en categorías raíz (`parent_id = NULL`).
    """
    db_category = await get_category(db, category_id)
    if db_category:
        await db.delete(db_category)
        await db.commit()
    return db_category

# ========================================
# FUNCIONES AUXILIARES
# ========================================

async def get_total_categories(db: AsyncSession) -> int:
    """Obtiene el número total de categorías, útil para paginación."""
    result = await db.execute(select(func.count(Category.category_id)))
    return result.scalar_one()