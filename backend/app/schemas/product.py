# backend/app/schemas/product.py

"""
Esquemas Pydantic para el modelo Product.

Este módulo define los esquemas para manejar productos en la API, incluyendo:
- Validación de datos de entrada y salida
- Manejo de relaciones anidadas (categorías, imágenes)
- Validación y parseado de JSON para especificaciones técnicas
- Integración con modelos SQLAlchemy mediante from_attributes

Los productos son el núcleo del catálogo, con relaciones complejas hacia:
- Categorías (many-to-one)
- Imágenes (many-to-many)
- Stock (one-to-many)
- Items de factura (one-to-many)
"""

from typing import Optional, List, Any, Dict
from pydantic import BaseModel, HttpUrl, validator, Field, ConfigDict
import json

from .category import CategoryResponse # Importamos el schema de respuesta de categoría

# ========================================
# ESQUEMAS AUXILIARES
# ========================================

class ImageResponse(BaseModel):
    """
    Esquema para representar imágenes asociadas a productos.
    
    Usado como esquema anidado dentro de ProductResponse para mostrar
    todas las imágenes de un producto en una sola respuesta.
    
    HttpUrl: Pydantic valida automáticamente que sea una URL válida
    """
    url: HttpUrl  # URL de la imagen (validación automática de formato)
    alt_text: Optional[str] = None  # Texto alternativo para accesibilidad

    model_config = ConfigDict(from_attributes=True)  # Permite conversión desde modelo SQLAlchemy Image


# ========================================
# ESQUEMA BASE
# ========================================

class ProductBase(BaseModel):
    """
    Esquema base que contiene las propiedades comunes de un producto.
    
    Implementa el principio DRY al centralizar los campos compartidos
    entre operaciones de creación, actualización y respuesta.
    
    Notas sobre tipos de datos:
    - price: float en Pydantic, pero Numeric(10,2) en SQLAlchemy para precisión
    - spec_json: Dict flexible para especificaciones técnicas variables
    """
    name: str  # Nombre del producto (requerido)
    description: Optional[str] = None  # Descripción detallada (opcional)
    price: float  # Precio - usar float para el precio en Pydantic, SQLAlchemy usa Numeric
    brand: Optional[str] = None  # Marca del producto (opcional)
    category_id: Optional[int] = None  # ID de la categoría padre (opcional)
    spec_json: Optional[Dict[str, Any]] = None  # Especificaciones técnicas en formato JSON


# ========================================
# ESQUEMAS PARA OPERACIONES
# ========================================

class ProductCreate(ProductBase):
    """
    Esquema para crear un nuevo producto.
    
    Usado en endpoints POST. Incluye el SKU que actúa como clave primaria.
    Implementa validación personalizada para spec_json que puede recibirse
    como string JSON y se parsea automáticamente.
    
    Ejemplo de uso:
    POST /api/v1/products/
    {
        "sku": "DRILL001",
        "name": "Taladro Eléctrico",
        "price": 89.99,
        "spec_json": "{\"potencia\": \"800W\", \"rpm\": \"3000\"}"
    }
    """
    sku: str  # Código único del producto (clave primaria)
    
    # Validador personalizado para spec_json
    @validator('spec_json', pre=True, allow_reuse=True)
    def parse_spec_json(cls, value):
        """
        Valida y parsea el campo spec_json.
        
        Permite recibir especificaciones como:
        1. Dict ya parseado: {"potencia": "800W"}
        2. String JSON: "{\"potencia\": \"800W\"}"
        
        Args:
            value: Valor a validar (puede ser str, dict, o None)
            
        Returns:
            Dict parseado o None
            
        Raises:
            ValueError: Si el string JSON es inválido
        """
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string for spec_json")
        return value


class ProductUpdate(ProductBase):
    """
    Esquema para actualizar un producto existente.
    
    Usado en endpoints PUT/PATCH. Todos los campos del ProductBase son opcionales
    para permitir actualizaciones parciales. El SKU no se puede modificar
    (se identifica por la URL del endpoint).
    
    Ejemplo de uso:
    PATCH /api/v1/products/DRILL001
    {
        "price": 79.99,  # Solo actualizar el precio
        "spec_json": {"potencia": "900W"}  # Actualizar especificaciones
    }
    """
    name: Optional[str] = None  # Todos los campos son opcionales en actualización
    price: Optional[float] = None
    # SKU no se actualiza (se identifica por la URL del endpoint)
    
    @validator('spec_json', pre=True, allow_reuse=True)
    def parse_spec_json_optional(cls, value):
        """
        Validador de spec_json para actualizaciones.
        
        Similar al validador de ProductCreate, pero maneja explícitamente
        el caso None para actualizaciones parciales.
        """
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
    Esquema para las respuestas de la API al leer productos.
    
    Usado en endpoints GET. Incluye todos los campos del producto más
    las relaciones anidadas (categoría e imágenes) para proporcionar
    una respuesta completa en una sola petición.
    
    Características:
    - Incluye SKU (viene de la base de datos)
    - Categoría anidada completa (no solo el ID)
    - Lista de imágenes asociadas
    - Extensible para incluir stock total si se necesita
    
    Ejemplo de respuesta:
    GET /api/v1/products/DRILL001
    {
        "sku": "DRILL001",
        "name": "Taladro Eléctrico",
        "price": 89.99,
        "category": {
            "category_id": 5,
            "name": "Herramientas Eléctricas",
            "parent_id": 1
        },
        "images": [
            {
                "url": "https://example.com/drill1.jpg",
                "alt_text": "Taladro eléctrico vista frontal"
            }
        ],
        "spec_json": {
            "potencia": "800W",
            "rpm": "3000"
        }
    }
    """
    sku: str  # Código único del producto (viene de la base de datos)
    category: Optional[CategoryResponse] = None  # Categoría anidada completa
    images: List[ImageResponse] = []  # Lista de imágenes anidadas
    
    # Extensión futura: información de stock
    # Si quisiéramos incluir el stock total agregado de todos los almacenes:
    # total_stock: Optional[int] = None 
    # 
    # Esto requeriría lógica adicional en el endpoint para calcular:
    # total_stock = sum(stock.quantity for stock in product.stock_levels)

    model_config = ConfigDict(from_attributes=True)  # Permite que Pydantic lea datos directamente desde modelos SQLAlchemy


class ProductSearchQuery(BaseModel):
    """
    Esquema para una consulta de búsqueda de productos por texto.
    """
    query_text: str = Field(..., min_length=3, description="Texto de búsqueda para encontrar productos.")
    top_k: int = Field(default=10, ge=1, le=50, description="Número de resultados a devolver.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query_text": "Taladro",
                "top_k": 10
            }
        }
    )


class ProductSearchResponse(BaseModel):
    """
    Esquema de respuesta para la búsqueda de productos, separando
    los resultados principales de los relacionados.
    """
    main_results: List[ProductResponse] = Field(..., description="Los resultados más relevantes para la búsqueda.")
    related_results: List[ProductResponse] = Field(..., description="Resultados secundarios o sugerencias adicionales.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "main_results": [
                    {
                        "sku": "DRILL001",
                        "name": "Taladro Eléctrico",
                        "price": 89.99,
                        "category": {"category_id": 5, "name": "Herramientas Eléctricas"},
                        "images": [{"url": "https://example.com/drill.jpg", "alt_text": "Taladro"}],
                        "spec_json": {"potencia": "800W"}
                    }
                ],
                "related_results": [
                    {
                        "sku": "DRILL002",
                        "name": "Taladro Inalámbrico",
                        "price": 120.00,
                        "category": {"category_id": 5, "name": "Herramientas Eléctricas"},
                        "images": [],
                        "spec_json": {"potencia": "600W", "bateria": "12V"}
                    }
                ]
            }
        }
    )


# ========================================
# NOTAS SOBRE RENDIMIENTO
# ========================================

# Al usar esquemas con relaciones anidadas (category, images), es importante:
# 1. Usar joinedload() en SQLAlchemy para evitar consultas N+1
# 2. Considerar paginación para listas de productos
# 3. Implementar campos opcionales (?include_images=true) para controlar respuestas
# 4. Usar caché para categorías que cambian poco
# 5. Evaluar GraphQL para consultas muy específicas en el futuro