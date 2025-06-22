# backend/app/db/models/business.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Numeric, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base_class import Base
from .product import Product # Importar Product para la relación

class Client(Base):
    __tablename__ = "clients"
    
    client_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    
    invoices = relationship("Invoice", back_populates="client")


class Warehouse(Base):
    __tablename__ = "warehouses"
    
    warehouse_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    
    stock_levels = relationship("Stock", back_populates="warehouse")


class Stock(Base):
    __tablename__ = "stock"
    
    stock_id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("products.sku", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(String(50), ForeignKey("warehouses.warehouse_id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="stock_levels")
    warehouse = relationship("Warehouse", back_populates="stock_levels")
    
    __table_args__ = (UniqueConstraint('sku', 'warehouse_id', name='_sku_warehouse_uc'),)


class Invoice(Base):
    __tablename__ = "invoices"
    
    invoice_id = Column(String(50), primary_key=True, index=True)
    client_id = Column(String(50), ForeignKey("clients.client_id", ondelete="SET NULL"), nullable=True)
    total = Column(Numeric(10, 2), nullable=False)
    pdf_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(String(50), ForeignKey("invoices.invoice_id", ondelete="CASCADE"), nullable=False)
    sku = Column(String(50), ForeignKey("products.sku", ondelete="RESTRICT"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price_at_purchase = Column(Numeric(10, 2), nullable=False)

    invoice = relationship("Invoice", back_populates="items")
    product = relationship("Product", back_populates="invoice_items")
