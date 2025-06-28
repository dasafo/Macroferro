# backend/app/db/models/product.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base

class Product(Base):
    __tablename__ = "products"

    sku = Column(String(50), primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    brand = Column(String(100), nullable=True, index=True)
    spec_json = Column(JSONB, nullable=True)

    category = relationship("Category", back_populates="products")
    _images_association = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    
    images = relationship(
        "Image",
        secondary="product_images",
        back_populates="products",
        viewonly=True,
        sync_backref=False
    )
    
    stock_levels = relationship("Stock", back_populates="product", cascade="all, delete-orphan")

    def to_dict(self):
        """Convierte el objeto Product en un diccionario."""
        return {
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "price": float(self.price) if self.price is not None else 0.0,
            "brand": self.brand,
            "category_name": self.category.name if self.category else None,
            "spec_json": self.spec_json or {},
            "images": [img.url for img in self.images]
        }


class Image(Base):
    __tablename__ = "images"

    image_id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, unique=True, nullable=False, index=True)
    alt_text = Column(String(255), nullable=True)
    
    products = relationship(
        "Product",
        secondary="product_images",
        back_populates="images",
        viewonly=True,
        sync_backref=False
    )
    products_association = relationship("ProductImage", back_populates="image", cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"

    sku = Column(String(50), ForeignKey("products.sku", ondelete="CASCADE"), primary_key=True)
    image_id = Column(Integer, ForeignKey("images.image_id", ondelete="CASCADE"), primary_key=True)

    product = relationship("Product", back_populates="_images_association")
    image = relationship("Image", back_populates="products_association") 