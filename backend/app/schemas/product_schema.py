# backend/app/schemas/product.py
"""
Esquemas Pydantic para el modelo Product.

Este archivo contiene los esquemas Pydantic para el modelo Product.

Se encarga de definir los esquemas Pydantic para el modelo Product.
"""

from typing import Optional, List, Any, Dict
from pydantic import BaseModel, HttpUrl, validator, Field, ConfigDict
import json

from .category_schema import CategoryResponse # Importamos el schema de respuesta de categoría

# ========================================
# ESQUEMAS AUXILIARES
# ========================================

class ImageResponse(BaseModel):
    """Esquema anidado para representar imágenes asociadas a productos."""
    url: HttpUrl
    alt_text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ========================================
# ESQUEMA BASE
# ========================================

class ProductBase(BaseModel):
    """Propiedades comunes compartidas entre esquemas de producto."""
    name: str
    description: Optional[str] = None
    price: float
    brand: Optional[str] = None
    category_id: Optional[int] = None
    spec_json: Optional[Dict[str, Any]] = None


# ========================================
# ESQUEMAS PARA OPERACIONES
# ========================================

class ProductCreate(ProductBase):
    """Esquema para crear un nuevo producto, incluyendo el SKU."""
    sku: str
    
    @validator('spec_json', pre=True, allow_reuse=True)
    def parse_spec_json(cls, value):
        """Permite que spec_json se reciba como un string JSON y lo parsea."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string for spec_json")
        return value


class ProductUpdate(ProductBase):
    """Esquema para actualizar un producto. Todos los campos son opcionales."""
    name: Optional[str] = None
    price: Optional[float] = None
    
    @validator('spec_json', pre=True, allow_reuse=True)
    def parse_spec_json_optional(cls, value):
        """Validador de spec_json para actualizaciones parciales."""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string for spec_json")
        return value


# ========================================
# ESQUEMA DE RESPUESTA
# ========================================

class ProductResponse(ProductBase):
    """
    Esquema de respuesta para un producto, incluyendo relaciones anidadas
    como categoría e imágenes.
    """
    sku: str
    category: Optional[CategoryResponse] = None
    images: List[ImageResponse] = []
    
    # Campo potencial para el futuro:
    # total_stock: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ProductSearchQuery(BaseModel):
    """Esquema para una consulta de búsqueda de productos por texto."""
    query_text: str = Field(..., min_length=3, description="Texto de búsqueda.")
    top_k: int = Field(default=10, ge=1, le=50, description="Número de resultados a devolver.")


class ProductSearchResponse(BaseModel):
    """
    Esquema de respuesta para la búsqueda de productos, separando
    los resultados principales de los relacionados.
    """
    main_results: List[ProductResponse]
    related_results: List[ProductResponse]


# ========================================
# NOTAS SOBRE RENDIMIENTO
# ========================================

# Al usar esquemas con relaciones anidadas (category, images), es importante:
# 1. Usar joinedload() en SQLAlchemy para evitar consultas N+1
# 2. Considerar paginación para listas de productos
# 3. Implementar campos opcionales (?include_images=true) para controlar respuestas
# 4. Usar caché para categorías que cambian poco
# 5. Evaluar GraphQL para consultas muy específicas en el futuro