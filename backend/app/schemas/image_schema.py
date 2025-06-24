"""
Esquemas Pydantic para el modelo Image.

Los esquemas definen la estructura de datos que fluye a través de la API:
- Validación automática de tipos de datos
- Serialización/deserialización JSON
- Documentación automática en OpenAPI/Swagger
- Separación entre modelo de base de datos y API

Patrón de esquemas utilizado:
- ImageBase: Propiedades comunes compartidas
- ImageCreate: Para crear nuevas imágenes (POST)
- ImageUpdate: Para actualizar imágenes existentes (PUT/PATCH)
- ImageResponse: Para respuestas de la API (GET)
"""

from typing import Optional
from pydantic import BaseModel, HttpUrl, ConfigDict

# ========================================
# ESQUEMA BASE
# ========================================

class ImageBase(BaseModel):
    """
    Esquema base que contiene las propiedades comunes de una imagen.
    
    Este esquema sirve como base para otros esquemas, implementando el principio DRY.
    Contiene solo los campos que son compartidos entre operaciones de creación,
    actualización y respuesta.
    """
    url: HttpUrl  # URL de la imagen (validada automáticamente por Pydantic)
    alt_text: Optional[str] = None  # Texto alternativo para accesibilidad


# ========================================
# ESQUEMAS PARA OPERACIONES
# ========================================

class ImageCreate(ImageBase):
    """
    Esquema para crear una nueva imagen.
    
    Usado en endpoints POST. En este proyecto las imágenes se cargan desde un CSV
    que ya proporciona IDs específicos, por lo que incluimos el image_id.
    
    Ejemplo de uso:
    POST /api/v1/images/
    {
        "image_id": 1,
        "url": "https://example.com/imagen.jpg",
        "alt_text": "Descripción de la imagen"
    }
    """
    image_id: int  # El image_id se proporciona en el CSV


class ImageUpdate(ImageBase):
    """
    Esquema para actualizar una imagen existente.
    
    Usado en endpoints PUT/PATCH. Todos los campos son opcionales para permitir
    actualizaciones parciales. El image_id no se puede cambiar (se pasa en la URL).
    
    Ejemplo de uso:
    PATCH /api/v1/images/1
    {
        "alt_text": "Nueva descripción"  # Solo actualizar el texto alternativo
    }
    """
    url: Optional[HttpUrl] = None  # Todos los campos son opcionales en la actualización
    alt_text: Optional[str] = None
    # No permitimos cambiar el image_id (se identifica por la URL del endpoint)


# ========================================
# ESQUEMA DE RESPUESTA
# ========================================

class ImageResponse(ImageBase):
    """
    Esquema para las respuestas de la API al leer imágenes.
    
    Usado en endpoints GET. Incluye todos los campos que se devuelven al cliente,
    incluyendo el image_id que se genera/lee desde la base de datos.
    
    La configuración from_attributes=True permite que Pydantic convierta automáticamente
    objetos SQLAlchemy a JSON, facilitando la integración entre el ORM y la API.
    
    Ejemplo de respuesta:
    GET /api/v1/images/1
    {
        "image_id": 1,
        "url": "https://example.com/imagen.jpg",
        "alt_text": "Descripción de la imagen"
    }
    """
    image_id: int  # ID único de la imagen (viene de la base de datos)

    model_config = ConfigDict(from_attributes=True)  # Permite que Pydantic lea datos directamente desde modelos SQLAlchemy 