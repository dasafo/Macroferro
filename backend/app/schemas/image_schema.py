# backend/app/schemas/image_schema.py
"""
Se encarga de definir los esquemas Pydantic para el modelo Image.
"""

from typing import Optional
from pydantic import BaseModel, HttpUrl, ConfigDict

# ========================================
# ESQUEMA BASE
# ========================================

class ImageBase(BaseModel):
    """Propiedades comunes compartidas entre esquemas de imagen."""
    url: HttpUrl  # URL de la imagen (validada automáticamente por Pydantic)
    alt_text: Optional[str] = None  # Texto alternativo para accesibilidad


# ========================================
# ESQUEMAS PARA OPERACIONES
# ========================================

class ImageCreate(ImageBase):
    """Esquema para crear una nueva imagen. El ID se provee externamente."""
    image_id: int  # El image_id se proporciona en el CSV


class ImageUpdate(ImageBase):
    """Esquema para actualizar una imagen. Todos los campos son opcionales."""
    url: Optional[HttpUrl] = None  # Todos los campos son opcionales en la actualización
    alt_text: Optional[str] = None
    # No permitimos cambiar el image_id (se identifica por la URL del endpoint)


# ========================================
# ESQUEMA DE RESPUESTA
# ========================================

class ImageResponse(ImageBase):
    """Esquema para las respuestas de la API al leer imágenes."""
    image_id: int  # ID único de la imagen (viene de la base de datos)

    model_config = ConfigDict(from_attributes=True)  # Permite que Pydantic lea datos directamente desde modelos SQLAlchemy 