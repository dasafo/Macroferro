from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
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
    total_stock = db.query(func.sum(Stock.quantity)).filter(Stock.sku == sku).scalar()
    
    return total_stock or 0

def deduct_stock(db: Session, sku: str, quantity: int) -> None:
    """
    Deduce una cantidad de stock para un SKU específico.
    PRECONDICIÓN: Ya se ha verificado que hay stock suficiente.

    La estrategia es deducir primero de los almacenes con más stock
    para minimizar el riesgo de agotar un almacén pequeño.

    Args:
        db: La sesión de la base de datos.
        sku: El SKU del producto a deducir.
        quantity: La cantidad total a deducir.

    Raises:
        ValueError: Si no hay suficiente stock total para cubrir la cantidad.
    """
    stock_entries = db.query(Stock).filter(Stock.sku == sku, Stock.quantity > 0).order_by(Stock.quantity.desc()).with_for_update().all()
    
    remaining_quantity_to_deduct = quantity
    for entry in stock_entries:
        if remaining_quantity_to_deduct <= 0:
            break

        if entry.quantity >= remaining_quantity_to_deduct:
            entry.quantity -= remaining_quantity_to_deduct
            remaining_quantity_to_deduct = 0
        else:
            remaining_quantity_to_deduct -= entry.quantity
            entry.quantity = 0
    
    # La sesión de la base de datos (db) se encargará de hacer commit
    # de los cambios fuera de esta función. 