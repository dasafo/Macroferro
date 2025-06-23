from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from app.db.models.stock_model import Stock, Warehouse

def get_stock_by_sku(db: Session, sku: str) -> List[Stock]:
    """
    Obtiene el stock para un SKU específico en todos los almacenes.

    Args:
        db: La sesión de la base de datos.
        sku: El SKU del producto a consultar.

    Returns:
        Una lista de objetos Stock, cada uno con la información del almacén precargada.
    """
    return db.query(Stock).filter(Stock.sku == sku).options(joinedload(Stock.warehouse)).all()

def get_total_stock_by_sku(db: Session, sku: str) -> int:
    """
    Calcula el stock total para un SKU específico sumando las cantidades de todos los almacenes.

    Args:
        db: La sesión de la base de datos.
        sku: El SKU del producto a consultar.

    Returns:
        La cantidad total de stock para el SKU.
    """
    stocks = db.query(Stock.quantity).filter(Stock.sku == sku).all()
    return sum(stock.quantity for stock in stocks) 