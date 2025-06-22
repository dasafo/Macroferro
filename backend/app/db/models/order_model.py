# backend/app/db/models/order.py
from sqlalchemy import (
    Column, Integer, String, DateTime, Numeric, Enum as SQLAlchemyEnum, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.db.base_class import Base

class OrderStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SHIPPED = "shipped"

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, nullable=False, index=True) # ID de chat de Telegram
    
    # Datos del cliente
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False, index=True)
    shipping_address = Column(Text, nullable=True)

    # Detalles del pedido
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(SQLAlchemyEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relación con OrderItem
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order(id={self.id}, chat_id='{self.chat_id}', status='{self.status.value}')>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    
    # Claves foráneas
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)

    # Detalles del item
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False) # Precio al momento de la compra

    # Relaciones
    order = relationship("Order", back_populates="items")
    product = relationship("Product")

    def __repr__(self):
        return f"<OrderItem(id={self.id}, order_id={self.order_id}, product_sku='{self.product_sku}')>" 