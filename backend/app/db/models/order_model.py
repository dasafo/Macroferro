# backend/app/db/models/order_model.py
"""
Este archivo contiene el modelo de pedido para la aplicación.
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Numeric, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ENUM, TIMESTAMP

from app.db.database import Base

# Usar un enum de PostgreSQL explícito para evitar problemas de nombre
order_status_enum = ENUM(
    'pending', 'completed', 'cancelled', 'shipped',
    name='order_status_enum',
    create_type=False
)

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(50), primary_key=True, index=True)
    client_id = Column(String(50), ForeignKey("clients.client_id"), nullable=True)
    chat_id = Column(String(255), nullable=False)
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=False)
    shipping_address = Column(Text, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), nullable=False, default='pending')
    pdf_url = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    client = relationship("Client", back_populates="orders")

    def __repr__(self):
        return f"<Order(id={self.order_id}, chat_id='{self.chat_id}', status='{self.status}')>"

    def to_dict(self):
        """Convierte el objeto Order y sus items a un diccionario."""
        return {
            "id": self.order_id,
            "client_id": self.client_id,
            "chat_id": self.chat_id,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "shipping_address": self.shipping_address,
            "total_amount": float(self.total_amount),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [
                {
                    "product_sku": item.product_sku,
                    "name": item.product.name,  # Incluimos el nombre del producto
                    "quantity": item.quantity,
                    "price": float(item.price)
                } for item in self.items
            ]
        }


class OrderItem(Base):
    __tablename__ = "order_items"

    item_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), ForeignKey("orders.order_id"), nullable=False)
    product_sku = Column(String(50), ForeignKey("products.sku"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")

    def __repr__(self):
        return f"<OrderItem(id={self.item_id}, order_id={self.order_id}, product_sku='{self.product_sku}')>" 