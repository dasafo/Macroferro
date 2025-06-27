# backend/app/schemas/order.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional
from datetime import datetime
import enum

from .product_schema import ProductResponse # Importar el esquema de respuesta del producto

# Enum para el estado del pedido, debe coincidir con el del modelo
class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SHIPPED = "shipped"

# Esquema para los items del pedido
class OrderItemBase(BaseModel):
    """
    Esquema base para items de pedido.
    
    Contiene los campos básicos necesarios para representar
    un producto dentro de una orden de compra.
    """
    product_sku: str = Field(..., description="SKU del producto", min_length=1)
    quantity: int = Field(..., description="Cantidad del producto", gt=0)
    price: float = Field(..., description="Precio al momento de la compra", ge=0)

class OrderItemCreate(OrderItemBase):
    """
    Esquema para crear items de pedido.
    
    Incluye validaciones adicionales para asegurar que los datos
    sean válidos antes de crear el item en la base de datos.
    """
    
    @validator('product_sku')
    def validate_product_sku(cls, v):
        """Valida que el SKU tenga un formato válido."""
        if not v or not v.strip():
            raise ValueError('El SKU del producto no puede estar vacío')
        return v.strip().upper()
    
    @validator('quantity')
    def validate_quantity(cls, v):
        """Valida que la cantidad sea positiva."""
        if v <= 0:
            raise ValueError('La cantidad debe ser mayor a 0')
        return v
    
    @validator('price')
    def validate_price(cls, v):
        """Valida que el precio sea positivo."""
        if v < 0:
            raise ValueError('El precio no puede ser negativo')
        return round(v, 2)  # Redondear a 2 decimales

class OrderItem(OrderItemBase):
    """
    Esquema de respuesta para items de pedido.
    
    Incluye información adicional como el ID del item
    y los datos del producto anidados.
    """
    item_id: int
    order_id: str
    product: Optional[ProductResponse] = None # Anidar información del producto

    class Config:
        from_attributes = True

# Esquema para la orden de compra
class OrderBase(BaseModel):
    """
    Esquema base para órdenes de compra.
    
    Contiene los campos comunes entre creación y respuesta de órdenes.
    """
    chat_id: str = Field(..., description="ID del chat de Telegram")
    customer_name: str = Field(..., description="Nombre del cliente", min_length=1)
    customer_email: EmailStr = Field(..., description="Email del cliente")
    shipping_address: str = Field(..., description="Dirección de envío", min_length=5)
    total_amount: float = Field(..., description="Monto total de la orden", ge=0)
    status: str = Field(default='pending', description="Estado de la orden")
    client_id: Optional[str] = Field(None, description="ID del cliente (opcional)")
    pdf_url: Optional[str] = Field(None, description="URL del PDF de la orden")

class OrderCreate(OrderBase):
    """
    Esquema para crear nuevas órdenes.
    
    Incluye validaciones para asegurar que todos los datos
    necesarios estén presentes y sean válidos.
    """
    items: List[OrderItemCreate] = Field(..., description="Items de la orden", min_items=1)
    
    @validator('customer_name')
    def validate_customer_name(cls, v):
        """Valida que el nombre del cliente sea válido."""
        if not v or not v.strip():
            raise ValueError('El nombre del cliente es requerido')
        return v.strip()
    
    @validator('shipping_address')
    def validate_shipping_address(cls, v):
        """Valida que la dirección de envío sea válida."""
        if not v or len(v.strip()) < 5:
            raise ValueError('La dirección de envío debe tener al menos 5 caracteres')
        return v.strip()
    
    @validator('items')
    def validate_items(cls, v):
        """Valida que haya al menos un item en la orden."""
        if not v or len(v) == 0:
            raise ValueError('La orden debe tener al menos un item')
        return v
    
    @validator('total_amount')
    def validate_total_amount(cls, v):
        """Valida que el monto total sea positivo."""
        if v < 0:
            raise ValueError('El monto total no puede ser negativo')
        return round(v, 2)  # Redondear a 2 decimales

class Order(OrderBase):
    """
    Esquema de respuesta para órdenes.
    
    Incluye información completa de la orden incluyendo
    timestamps y items anidados.
    """
    order_id: str
    created_at: datetime
    updated_at: datetime
    items: List[OrderItem] = []

    class Config:
        from_attributes = True

# Esquemas adicionales para operaciones específicas
class OrderStatusUpdate(BaseModel):
    """
    Esquema para actualizar el estado de una orden.
    """
    status: OrderStatus = Field(..., description="Nuevo estado de la orden")

class OrderSearchQuery(BaseModel):
    """
    Esquema para consultas de búsqueda de órdenes.
    """
    chat_id: Optional[str] = Field(None, description="ID del chat para filtrar órdenes")
    status: Optional[OrderStatus] = Field(None, description="Estado para filtrar órdenes")
    customer_email: Optional[EmailStr] = Field(None, description="Email del cliente para filtrar")
    date_from: Optional[datetime] = Field(None, description="Fecha de inicio para filtrar")
    date_to: Optional[datetime] = Field(None, description="Fecha de fin para filtrar")
    skip: int = Field(0, description="Número de registros a omitir", ge=0)
    limit: int = Field(10, description="Número máximo de registros a devolver", ge=1, le=100) 