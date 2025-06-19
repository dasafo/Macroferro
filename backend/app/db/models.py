# backend/app/db/models.py

from sqlalchemy import Column, Integer, String, ForeignKey, Text, Numeric, JSON, UniqueConstraint, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB # Usar JSONB para PostgreSQL
from sqlalchemy.sql import func # Para CURRENT_TIMESTAMP

from .database import Base # Importamos la Base de database.py

# ========================================
# MODELOS PRINCIPALES DEL CATÁLOGO
# ========================================

class Category(Base):
    """
    Modelo de categorías jerárquicas para organizar productos.
    Permite crear una estructura de árbol con categorías padre e hijas.
    Ejemplo: Herramientas > Eléctricas > Taladros
    """
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    # parent_id permite crear jerarquías: categorías pueden tener una categoría padre
    parent_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)

    # Relaciones bidireccionales para navegación jerárquica
    # Relación para acceder a los hijos de una categoría
    children = relationship("Category", back_populates="parent", cascade="all, delete-orphan")
    # Relación para acceder al padre de una categoría
    parent = relationship("Category", remote_side=[category_id], back_populates="children")
    
    # Relación con productos de esta categoría
    products = relationship("Product", back_populates="category")

    __table_args__ = (
        # Constraint para evitar categorías duplicadas bajo el mismo padre
        UniqueConstraint('name', 'parent_id', name='uq_category_name_parent'),
    )


class Product(Base):
    """
    Modelo principal de productos del catálogo.
    Cada producto tiene un SKU único, pertenece a una categoría y puede tener múltiples imágenes.
    """
    __tablename__ = "products"

    sku = Column(String(50), primary_key=True, index=True)  # SKU como clave primaria
    category_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False, index=True)  # Indexado para búsquedas rápidas
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)  # Precisión decimal para precios
    brand = Column(String(100), nullable=True, index=True)  # Marca indexada para filtros
    spec_json = Column(JSONB, nullable=True)  # Especificaciones técnicas en formato JSON

    # Relaciones
    category = relationship("Category", back_populates="products")
    
    # Relación con imágenes a través de tabla de unión
    images_association = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    
    # Relación con niveles de stock en diferentes almacenes
    stock_levels = relationship("Stock", back_populates="product", cascade="all, delete-orphan")

    # Relación con items de facturas
    invoice_items = relationship("InvoiceItem", back_populates="product")


class Image(Base):
    """
    Modelo para almacenar información de imágenes.
    Una imagen puede estar asociada a múltiples productos y viceversa (relación many-to-many).
    """
    __tablename__ = "images"

    image_id = Column(Integer, primary_key=True, autoincrement=True)  # SERIAL se maneja con autoincrement=True
    url = Column(Text, unique=True, nullable=False, index=True)  # URL única e indexada
    alt_text = Column(String(255), nullable=True)  # Texto alternativo para accesibilidad

    # Relación con productos a través de tabla de unión
    products_association = relationship("ProductImage", back_populates="image", cascade="all, delete-orphan")


class ProductImage(Base):
    """
    Tabla de unión para la relación many-to-many entre productos e imágenes.
    Permite que un producto tenga múltiples imágenes y una imagen pueda usarse en múltiples productos.
    """
    __tablename__ = "product_images"

    # Clave primaria compuesta
    sku = Column(String(50), ForeignKey("products.sku", ondelete="CASCADE"), primary_key=True)
    image_id = Column(Integer, ForeignKey("images.image_id", ondelete="CASCADE"), primary_key=True)

    # Relaciones hacia ambas entidades
    product = relationship("Product", back_populates="images_association")
    image = relationship("Image", back_populates="products_association")


# ========================================
# MODELOS PARA FASES POSTERIORES
# ========================================
# Incluidos ahora para mantener integridad del esquema

class Client(Base):
    """
    Modelo de clientes para el sistema de facturación.
    Almacena información básica de contacto y se relaciona con facturas.
    """
    __tablename__ = "clients"
    
    client_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)  # Email único e indexado
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    
    # Relación con facturas del cliente
    invoices = relationship("Invoice", back_populates="client")


class Warehouse(Base):
    """
    Modelo de almacenes para gestión de inventario.
    Cada almacén puede tener diferentes niveles de stock para los mismos productos.
    """
    __tablename__ = "warehouses"
    
    warehouse_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    
    # Relación con niveles de stock
    stock_levels = relationship("Stock", back_populates="warehouse")


class Stock(Base):
    """
    Modelo para control de inventario.
    Registra la cantidad disponible de cada producto en cada almacén.
    """
    __tablename__ = "stock"
    
    stock_id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("products.sku", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(String(50), ForeignKey("warehouses.warehouse_id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)  # Cantidad por defecto: 0

    # Relaciones
    product = relationship("Product", back_populates="stock_levels")
    warehouse = relationship("Warehouse", back_populates="stock_levels")
    
    # Constraint único: un producto solo puede tener un registro de stock por almacén
    __table_args__ = (UniqueConstraint('sku', 'warehouse_id', name='_sku_warehouse_uc'),)


class Invoice(Base):
    """
    Modelo de facturas para el sistema de ventas.
    Cada factura pertenece a un cliente y contiene múltiples items.
    """
    __tablename__ = "invoices"
    
    invoice_id = Column(String(50), primary_key=True, index=True)
    client_id = Column(String(50), ForeignKey("clients.client_id", ondelete="SET NULL"), nullable=True)
    total = Column(Numeric(10, 2), nullable=False)  # Total de la factura
    pdf_url = Column(Text, nullable=True)  # URL del PDF generado
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # Timestamp de creación

    # Relaciones
    client = relationship("Client", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    """
    Modelo de items individuales dentro de una factura.
    Cada item representa un producto específico con cantidad y precio en el momento de la venta.
    """
    __tablename__ = "invoice_items"
    
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(String(50), ForeignKey("invoices.invoice_id", ondelete="CASCADE"), nullable=False)
    # RESTRICT evita borrar productos que aparecen en facturas existentes
    sku = Column(String(50), ForeignKey("products.sku", ondelete="RESTRICT"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price_at_purchase = Column(Numeric(10, 2), nullable=False)  # Precio en el momento de la compra

    # Relaciones
    invoice = relationship("Invoice", back_populates="items")
    product = relationship("Product", back_populates="invoice_items")