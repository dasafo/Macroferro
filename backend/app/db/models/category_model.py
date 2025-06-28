# backend/app/db/models/category_model.py
"""
Se encarga de definir los modelos de categoría para la aplicación.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base

class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)

    children = relationship("Category", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("Category", remote_side=[category_id], back_populates="children")
    products = relationship("Product", back_populates="category")

    __table_args__ = (
        UniqueConstraint('name', 'parent_id', name='uq_category_name_parent'),
    ) 