from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models import order as order_model
from app.schemas import order as order_schema

def create_order(db: Session, order: order_schema.OrderCreate, chat_id: str, total_amount: float) -> order_model.Order:
    """
    Crea una nueva orden en la base de datos.
    """
    db_order = order_model.Order(
        chat_id=chat_id,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        shipping_address=order.shipping_address,
        total_amount=total_amount,
        status=order_model.OrderStatus.PENDING
    )
    db.add(db_order)
    db.flush() # Para obtener el ID de la orden antes del commit

    for item in order.items:
        db_item = order_model.OrderItem(
            order_id=db_order.id,
            product_sku=item.product_sku,
            quantity=item.quantity,
            price=item.price
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_order)
    return db_order

def get_order(db: Session, order_id: int) -> Optional[order_model.Order]:
    """
    Obtiene una orden por su ID.
    """
    return db.query(order_model.Order).filter(order_model.Order.id == order_id).first()

def get_orders_by_chat_id(db: Session, chat_id: str, skip: int = 0, limit: int = 10) -> List[order_model.Order]:
    """
    Obtiene una lista de órdenes para un chat_id específico (historial de pedidos).
    """
    return db.query(order_model.Order).filter(order_model.Order.chat_id == chat_id).order_by(order_model.Order.created_at.desc()).offset(skip).limit(limit).all()

def update_order_status(db: Session, order_id: int, status: order_model.OrderStatus) -> Optional[order_model.Order]:
    """
    Actualiza el estado de una orden.
    """
    db_order = get_order(db, order_id)
    if db_order:
        db_order.status = status
        db.commit()
        db.refresh(db_order)
    return db_order 