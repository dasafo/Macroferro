# backend/app/schemas/category_schema.py
"""
Esquemas Pydantic para el modelo Category.
"""

from typing import Optional, List
from pydantic import BaseModel, ConfigDict

# ========================================
# ESQUEMA BASE
# ========================================

class CategoryBase(BaseModel):
    """Propiedades comunes compartidas entre esquemas de categoría."""
    name: str
    parent_id: Optional[int] = None


# ========================================
# ESQUEMAS PARA OPERACIONES
# ========================================

class CategoryCreate(CategoryBase):
    """Esquema para crear una nueva categoría. El ID se provee externamente."""
    category_id: int


class CategoryUpdate(CategoryBase):
    """Esquema para actualizar una categoría. Todos los campos son opcionales."""
    name: Optional[str] = None
    parent_id: Optional[int] = None


# ========================================
# ESQUEMA DE RESPUESTA
# ========================================

class CategoryResponse(CategoryBase):
    """Esquema para las respuestas de la API al leer categorías."""
    category_id: int
    
    # Para incluir subcategorías anidadas en el futuro:
    # children: List["CategoryResponse"] = []

    model_config = ConfigDict(from_attributes=True)
