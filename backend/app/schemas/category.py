# backend/app/schemas/category.py

"""
Esquemas Pydantic para el modelo Category.

Los esquemas definen la estructura de datos que fluye a través de la API:
- Validación automática de tipos de datos
- Serialización/deserialización JSON
- Documentación automática en OpenAPI/Swagger
- Separación entre modelo de base de datos y API

Patrón de esquemas utilizado:
- CategoryBase: Propiedades comunes compartidas
- CategoryCreate: Para crear nuevas categorías (POST)
- CategoryUpdate: Para actualizar categorías existentes (PUT/PATCH)
- CategoryResponse: Para respuestas de la API (GET)
"""

from typing import Optional, List
from pydantic import BaseModel

# ========================================
# ESQUEMA BASE
# ========================================

class CategoryBase(BaseModel):
    """
    Esquema base que contiene las propiedades comunes de una categoría.
    
    Este esquema sirve como base para otros esquemas, implementando el principio DRY.
    Contiene solo los campos que son compartidos entre operaciones de creación,
    actualización y respuesta.
    """
    name: str  # Nombre de la categoría (requerido en todas las operaciones)
    parent_id: Optional[int] = None  # ID de la categoría padre (None para categorías raíz)


# ========================================
# ESQUEMAS PARA OPERACIONES
# ========================================

class CategoryCreate(CategoryBase):
    """
    Esquema para crear una nueva categoría.
    
    Usado en endpoints POST. Incluye el category_id porque en este proyecto
    las categorías se cargan desde un CSV que ya proporciona IDs específicos,
    en lugar de usar auto-incremento.
    
    Ejemplo de uso:
    POST /api/v1/categories/
    {
        "category_id": 1,
        "name": "Herramientas",
        "parent_id": null
    }
    """
    category_id: int  # El category_id se proporciona en el CSV, así que lo incluimos en la creación


class CategoryUpdate(CategoryBase):
    """
    Esquema para actualizar una categoría existente.
    
    Usado en endpoints PUT/PATCH. Todos los campos son opcionales para permitir
    actualizaciones parciales. El category_id no se puede cambiar (se pasa en la URL).
    
    Ejemplo de uso:
    PATCH /api/v1/categories/1
    {
        "name": "Herramientas Eléctricas"  # Solo actualizar el nombre
    }
    """
    name: Optional[str] = None  # Todos los campos son opcionales en la actualización
    parent_id: Optional[int] = None
    # No permitimos cambiar el category_id (se identifica por la URL del endpoint)


# ========================================
# ESQUEMA DE RESPUESTA
# ========================================

class CategoryResponse(CategoryBase):
    """
    Esquema para las respuestas de la API al leer categorías.
    
    Usado en endpoints GET. Incluye todos los campos que se devuelven al cliente,
    incluyendo el category_id que se genera/lee desde la base de datos.
    
    La configuración orm_mode=True permite que Pydantic convierta automáticamente
    objetos SQLAlchemy a JSON, facilitando la integración entre el ORM y la API.
    
    Ejemplo de respuesta:
    GET /api/v1/categories/1
    {
        "category_id": 1,
        "name": "Herramientas",
        "parent_id": null
    }
    """
    category_id: int  # ID único de la categoría (viene de la base de datos)
    
    # Extensión futura: categorías anidadas
    # Si quisiéramos incluir las subcategorías directamente en la respuesta:
    # children: List["CategoryResponse"] = []  # Requiere forward reference y orm_mode

    class Config:
        """
        Configuración de Pydantic para este esquema.
        
        orm_mode = True: Permite que Pydantic lea datos directamente desde 
        modelos SQLAlchemy sin necesidad de convertir manualmente a diccionario.
        
        Esto significa que podemos hacer:
        category_orm = db.query(Category).first()
        return CategoryResponse.from_orm(category_orm)
        """
        orm_mode = True  # Permite que Pydantic lea datos directamente desde modelos SQLAlchemy

# ========================================
# RESOLUCIÓN DE REFERENCIAS FUTURAS
# ========================================

# Para manejar la recursividad en la respuesta si mostramos hijos anidados
# Esto se necesitaría si descomentáramos el campo 'children' en CategoryResponse
# CategoryResponse.update_forward_refs()

# Nota: La recursividad en esquemas puede causar problemas de rendimiento
# en categorías con muchos niveles. Para casos complejos, considerar:
# 1. Endpoints separados para obtener hijos: GET /categories/{id}/children
# 2. Parámetros de consulta para controlar profundidad: ?include_children=true&max_depth=2
# 3. Paginación en subcategorías si hay muchas