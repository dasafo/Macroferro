from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base

class Warehouse(Base):
    __tablename__ = "warehouses"

    warehouse_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    address = Column(String, nullable=True)

    stock_items = relationship("Stock", back_populates="warehouse")

class Stock(Base):
    __tablename__ = "stock"

    stock_id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("products.sku", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)

    product = relationship("Product", back_populates="stock_levels")
    warehouse = relationship("Warehouse", back_populates="stock_items")

    __table_args__ = (
        UniqueConstraint('sku', 'warehouse_id', name='uq_stock_sku_warehouse'),
    )

# Es necesario añadir la relación inversa en el modelo Product
# Esto lo haré en el siguiente paso. 