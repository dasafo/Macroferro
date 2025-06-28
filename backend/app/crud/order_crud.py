# backend/app/crud/order_crud.py
"""
Este archivo contiene las operaciones CRUD para el modelo Order.

Operaciones CRUD para el modelo Order.

Este módulo proporciona funciones para crear y gestionar pedidos, incluyendo la generación de IDs de pedido, actualización de estados y gestión de detalles de pedido.
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy import func, case, select
from sqlalchemy.types import Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.order_model import Order, OrderItem
from app.schemas.order_schema import OrderCreate, OrderStatus, OrderItemCreate
from app.crud import stock_crud

async def get_next_order_id(db: AsyncSession) -> str:
    """
    Calcula el siguiente ID de pedido secuencial con el formato ORDXXXXX de forma asíncrona.
    """
    numeric_part_str = func.substr(Order.order_id, 4)
    cleaned_numeric_part = func.regexp_replace(numeric_part_str, '[^0-9]', '', 'g')
    numeric_id = func.coalesce(func.cast(func.nullif(cleaned_numeric_part, ''), Integer), 0)

    max_id_query = select(func.max(numeric_id))
    max_id_result = await db.execute(max_id_query)
    last_id_num = max_id_result.scalar() or 0
        
    next_id_num = last_id_num + 1
    
    return f"ORD{next_id_num:05d}"

async def create_order(db: AsyncSession, order: OrderCreate) -> Order:
    """
    Crea un nuevo pedido en la base de datos de forma asíncrona.
    """
    new_order_id = await get_next_order_id(db)
    
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
        
        await stock_crud.deduct_stock(db, sku=item_data.product_sku, quantity=item_data.quantity)

    await db.commit()
    await db.refresh(db_order)
    return db_order

async def get_order(db: AsyncSession, order_id: str) -> Optional[Order]:
    """
    Obtiene un pedido por su ID de negocio de forma asíncrona.
    """
    result = await db.execute(select(Order).filter(Order.order_id == order_id))
    return result.scalars().first()

async def get_orders_by_chat_id(db: AsyncSession, chat_id: str, skip: int = 0, limit: int = 10) -> List[Order]:
    """
    Obtiene el historial de pedidos de un usuario de Telegram de forma asíncrona.
    """
    query = select(Order).filter(Order.chat_id == chat_id).order_by(Order.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def update_order_status(db: AsyncSession, order_id: str, status: OrderStatus) -> Optional[Order]:
    """
    Actualiza el estado de un pedido de forma asíncrona.
    """
    db_order = await get_order(db, order_id)
    if db_order:
        db_order.status = status
        await db.commit()
        await db.refresh(db_order)
    return db_order

async def update_order_pdf_url(db: AsyncSession, order_id: str, pdf_url: str) -> Order:
    """
    Actualiza la URL del PDF para un pedido específico de forma asíncrona.
    """
    db_order = await get_order(db, order_id)
    if db_order:
        db_order.pdf_url = pdf_url
        await db.commit()
        await db.refresh(db_order)
    return db_order 