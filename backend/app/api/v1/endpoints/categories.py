"""
Endpoints REST para operaciones CRUD de categorías.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api import deps
from app.schemas import category_schema as category_schema
from app.services.category_service import category_service

router = APIRouter()

@router.post("/", response_model=category_schema.CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    *,
    db: Session = Depends(deps.get_db),
    category_in: category_schema.CategoryCreate
) -> category_schema.CategoryResponse:
    """Crea una nueva categoría en el sistema."""
    existing_category_by_id = category_service.get_category_by_id(db, category_id=category_in.category_id)
    if existing_category_by_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with ID {category_in.category_id} already exists."
        )
    
    category = category_service.create_new_category(db=db, category_in=category_in)
    return category

@router.put("/{category_id}", response_model=category_schema.CategoryResponse)
def update_category(
    *,
    db: Session = Depends(deps.get_db),
    category_id: int,
    category_in: category_schema.CategoryUpdate,
) -> category_schema.CategoryResponse:
    """Actualiza una categoría existente."""
    category = category_service.update_existing_category(db=db, category_id=category_id, category_in=category_in)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found for update")
    return category

@router.delete("/{category_id}", response_model=category_schema.CategoryResponse)
def delete_category(
    *,
    db: Session = Depends(deps.get_db),
    category_id: int,
) -> category_schema.CategoryResponse:
    """Elimina una categoría del sistema."""
    deleted_category = category_service.delete_existing_category(db=db, category_id=category_id)
    if not deleted_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found for deletion")
    return deleted_category

@router.get("/{category_id}", response_model=category_schema.CategoryResponse)
def read_category(
    *,
    db: Session = Depends(deps.get_db),
    category_id: int,
) -> category_schema.CategoryResponse:
    """Obtiene los detalles de una categoría específica por su ID."""
    category = category_service.get_category_by_id(db=db, category_id=category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category

@router.get("/", response_model=List[category_schema.CategoryResponse])
def read_categories(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    parent_id: Optional[int] = None,
    main_categories_only: bool = False
) -> List[category_schema.CategoryResponse]:
    """Obtiene una lista de categorías con filtros y paginación."""
    if main_categories_only and parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot use 'parent_id' and 'main_categories_only' filters simultaneously."
        )

    if main_categories_only:
        categories = category_service.get_main_categories(db=db, skip=skip, limit=limit)
    elif parent_id is not None:
        categories = category_service.get_subcategories(db=db, parent_id=parent_id, skip=skip, limit=limit)
    else:
        categories = category_service.get_all_categories(db=db, skip=skip, limit=limit)
    
    return categories