from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy import func, case
from sqlalchemy.types import Integer

from app.db.models.order_model import Order, OrderItem
from app.schemas.order_schema import OrderCreate, OrderStatus, OrderItemCreate

def get_next_order_id(db: Session) -> str:
    """
    Calcula el siguiente ID de pedido secuencial con el formato ORDXXXXX.
    Ejemplo: Si el último ID es ORD00042, el siguiente será ORD00043.
    """
    # Extraer la parte del string que debería ser numérica (después de 'ORD')
    numeric_part_str = func.substr(Order.order_id, 4)
    
    # Limpiar el string para que solo contenga dígitos usando una expresión regular.
    # Esto elimina cualquier carácter no numérico que pudiera haber.
    # La 'g' al final asegura que se reemplacen todas las ocurrencias.
    cleaned_numeric_part = func.regexp_replace(numeric_part_str, '[^0-9]', '', 'g')

    # Convertir el string limpio a un entero de forma segura.
    # 1. nullif(..., ''): Si el string está vacío, lo convierte en NULL.
    # 2. cast(..., Integer): Intenta convertir a entero. Si es NULL, el resultado es NULL.
    # 3. coalesce(..., 0): Si el resultado es NULL, lo convierte en 0.
    numeric_id = func.coalesce(func.cast(func.nullif(cleaned_numeric_part, ''), Integer), 0)

    # Buscar el número más alto entre todos los IDs de pedido
    max_id_result = db.query(func.max(numeric_id)).one_or_none()
    
    last_id_num = 0
    if max_id_result and max_id_result[0] is not None:
        last_id_num = max_id_result[0]
        
    next_id_num = last_id_num + 1
    
    # Formatear el nuevo ID con 5 dígitos y el prefijo "ORD"
    return f"ORD{next_id_num:05d}"

def create_order(db: Session, order: OrderCreate) -> Order:
    """
    Crea un nuevo pedido en la base de datos.
    """
    # Generar el nuevo ID de pedido secuencial
    new_order_id = get_next_order_id(db)
    
    db_order = Order(
        order_id=new_order_id,
        client_id=order.client_id,
        chat_id=order.chat_id,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        shipping_address=order.shipping_address,
        total_amount=order.total_amount,
        status=order.status
    )
    db.add(db_order)
    
    for item_data in order.items:
        db_item = OrderItem(
            order_id=new_order_id,
            product_sku=item_data.product_sku,
            quantity=item_data.quantity,
            price=item_data.price
        )
        db.add(db_item)
        
    db.commit()
    db.refresh(db_order)
    return db_order

def get_order(db: Session, order_id: str) -> Optional[Order]:
    """
    Obtiene un pedido por su ID de negocio (ej: ORD00123).
    """
    return db.query(Order).filter(Order.order_id == order_id).first()

def get_orders_by_chat_id(db: Session, chat_id: str, skip: int = 0, limit: int = 10) -> List[Order]:
    """
    Obtiene el historial de pedidos de un usuario de Telegram.
    """
    return db.query(Order).filter(Order.chat_id == chat_id).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

def update_order_status(db: Session, order_id: str, status: OrderStatus) -> Optional[Order]:
    """
    Actualiza el estado de un pedido.
    """
    db_order = get_order(db, order_id) # Usamos la función ya corregida
    if db_order:
        db_order.status = status
        db.commit()
        db.refresh(db_order)
    return db_order

def update_order_pdf_url(db: Session, order_id: str, pdf_url: str) -> Order:
    """
    Actualiza la URL del PDF para un pedido específico.
    """
    db_order = db.query(Order).filter(Order.order_id == order_id).one_or_none()
    if db_order:
        db_order.pdf_url = pdf_url
        db.commit()
        db.refresh(db_order)
    return db_order 