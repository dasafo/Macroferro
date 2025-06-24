# backend/app/schemas/order.py
from pydantic import BaseModel, EmailStr
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
    product_sku: str
    quantity: int
    price: float # Precio al momento de la compra

class OrderItemCreate(OrderItemBase):
    pass

class OrderItem(OrderItemBase):
    id: int
    order_id: int
    product: Optional[ProductResponse] = None # Anidar información del producto

    class Config:
        from_attributes = True

# Esquema para la orden de compra
class OrderBase(BaseModel):
    chat_id: str
    customer_name: str
    customer_email: EmailStr
    shipping_address: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING

class OrderCreate(OrderBase):
    items: List[OrderItemCreate]

class Order(OrderBase):
    id: int
    total_amount: float
    status: OrderStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[OrderItem] = []

    class Config:
        from_attributes = True 