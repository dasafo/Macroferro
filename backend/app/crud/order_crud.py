from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.order_model import Order, OrderItem
from app.schemas.order import OrderCreate, OrderStatus

def create_order(db: Session, order: OrderCreate, total_amount: float) -> Order:
    """
    Crea un nuevo pedido en la base de datos.
    """
    db_order = Order(
        chat_id=order.chat_id,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        shipping_address=order.shipping_address,
        total_amount=total_amount,
        status=order.status
    )
    db.add(db_order)
    db.flush()  # Para obtener el ID del pedido para los items

    for item_data in order.items:
        db_item = OrderItem(
            order_id=db_order.id,
            product_sku=item_data.product_sku,
            quantity=item_data.quantity,
            price=item_data.price
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_order)
    return db_order

def get_order(db: Session, order_id: int) -> Optional[Order]:
    """
    Obtiene un pedido por su ID.
    """
    return db.query(Order).filter(Order.id == order_id).first()

def get_orders_by_chat_id(db: Session, chat_id: str, skip: int = 0, limit: int = 10) -> List[Order]:
    """
    Obtiene el historial de pedidos de un usuario de Telegram.
    """
    return db.query(Order).filter(Order.chat_id == chat_id).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

def update_order_status(db: Session, order_id: int, status: OrderStatus) -> Optional[Order]:
    """
    Actualiza el estado de un pedido.
    """
    db_order = get_order(db, order_id)
    if db_order:
        db_order.status = status
        db.commit()
        db.refresh(db_order)
    return db_order 