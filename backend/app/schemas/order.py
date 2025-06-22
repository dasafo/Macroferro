# backend/app/schemas/order.py
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

from .product import Product # Importar el esquema del producto para anidarlo

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
    product: Optional[Product] = None # Anidar información del producto

    class Config:
        orm_mode = True

# Esquema para la orden de compra
class OrderBase(BaseModel):
    customer_name: str
    customer_email: EmailStr
    shipping_address: Optional[str] = None

class OrderCreate(OrderBase):
    items: List[OrderItemCreate]

class Order(OrderBase):
    id: int
    chat_id: str
    total_amount: float
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[OrderItem] = []

    class Config:
        orm_mode = True 