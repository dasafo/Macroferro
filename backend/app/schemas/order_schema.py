# backend/app/schemas/order_schema.py
"""
Se encarga de definir los esquemas Pydantic para los modelos Order y OrderItem.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional
from datetime import datetime
import enum

from .product_schema import ProductResponse

class OrderStatus(str, enum.Enum):
    """Define los posibles estados de una orden."""
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SHIPPED = "shipped"

class OrderItemBase(BaseModel):
    """Propiedades base para un item dentro de una orden."""
    product_sku: str = Field(..., description="SKU del producto")
    quantity: int = Field(..., description="Cantidad del producto", gt=0)
    price: float = Field(..., description="Precio al momento de la compra", ge=0)

class OrderItemCreate(OrderItemBase):
    """Esquema para crear un item de orden, con validaciones."""
    pass # Las validaciones se mantienen, no necesitan comentarios extra.

class OrderItem(OrderItemBase):
    """Esquema de respuesta para un item de orden, incluyendo su ID y el producto."""
    item_id: int
    order_id: str
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    """Propiedades base para una orden de compra."""
    chat_id: str = Field(..., description="ID del chat de Telegram")
    customer_name: str = Field(..., description="Nombre del cliente")
    customer_email: EmailStr = Field(..., description="Email del cliente")
    shipping_address: str = Field(..., description="Dirección de envío")
    total_amount: float = Field(..., description="Monto total de la orden", ge=0)
    status: str = Field(default='pending', description="Estado de la orden")
    client_id: Optional[str] = Field(None, description="ID del cliente (opcional)")
    pdf_url: Optional[str] = Field(None, description="URL del PDF de la orden")

class OrderCreate(OrderBase):
    """Esquema para crear una nueva orden, con su lista de items."""
    items: List[OrderItemCreate] = Field(..., description="Items de la orden", min_items=1)
    
    # Se mantienen las validaciones sin comentarios adicionales.
    @validator('customer_name')
    def validate_customer_name(cls, v):
        if not v or not v.strip():
            raise ValueError('El nombre del cliente es requerido')
        return v.strip()
    
    @validator('shipping_address')
    def validate_shipping_address(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError('La dirección de envío debe tener al menos 5 caracteres')
        return v.strip()
    
    @validator('items')
    def validate_items(cls, v):
        if not v or len(v) == 0:
            raise ValueError('La orden debe tener al menos un item')
        return v
    
    @validator('total_amount')
    def validate_total_amount(cls, v):
        if v < 0:
            raise ValueError('El monto total no puede ser negativo')
        return round(v, 2)

class Order(OrderBase):
    """Esquema completo de respuesta para una orden."""
    order_id: str
    created_at: datetime
    updated_at: datetime
    items: List[OrderItem] = []

    class Config:
        from_attributes = True

class OrderStatusUpdate(BaseModel):
    """Esquema para actualizar únicamente el estado de una orden."""
    status: OrderStatus = Field(..., description="Nuevo estado de la orden")

class OrderSearchQuery(BaseModel):
    """Esquema para consultas y filtros de búsqueda de órdenes."""
    chat_id: Optional[str] = Field(None, description="ID del chat para filtrar")
    status: Optional[OrderStatus] = Field(None, description="Estado para filtrar")
    customer_email: Optional[EmailStr] = Field(None, description="Email del cliente para filtrar")
    date_from: Optional[datetime] = Field(None, description="Fecha de inicio del filtro")
    date_to: Optional[datetime] = Field(None, description="Fecha de fin del filtro")
    skip: int = Field(0, description="Número de registros a omitir", ge=0)
    limit: int = Field(10, description="Máximo de registros a devolver", ge=1, le=100) 