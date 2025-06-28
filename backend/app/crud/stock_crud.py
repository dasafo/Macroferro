# backend/app/crud/stock_crud.py
"""
Este archivo contiene las operaciones CRUD para el modelo Stock.

Operaciones CRUD para el modelo Stock.

Este módulo proporciona funciones para consultar y actualizar el stock de productos en diferentes almacenes.
"""

from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.db.models.stock_model import Stock, Warehouse

async def get_stock_by_sku(db: AsyncSession, sku: str) -> List[Stock]:
    """
    Obtiene el stock para un SKU específico en todos los almacenes de forma asíncrona.
    """
    query = select(Stock).filter(Stock.sku == sku).options(joinedload(Stock.warehouse))
    result = await db.execute(query)
    return result.scalars().all()

async def get_total_stock_by_sku(db: AsyncSession, sku: str) -> int:
    """
    Calcula el stock total para un SKU específico sumando las cantidades de todos los almacenes.
    """
    query = select(func.sum(Stock.quantity)).filter(Stock.sku == sku)
    total_stock = await db.scalar(query)
    
    return total_stock or 0

async def deduct_stock(db: AsyncSession, sku: str, quantity: int) -> None:
    """
    Deduce una cantidad de stock para un SKU específico de forma asíncrona y atómica.
    PRECONDICIÓN: Ya se ha verificado que hay stock suficiente.
    """
    stock_entries_query = (
        select(Stock)
        .filter(Stock.sku == sku, Stock.quantity > 0)
        .order_by(Stock.quantity.desc())
        .with_for_update()
    )
    
    result = await db.execute(stock_entries_query)
    stock_entries = result.scalars().all()

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
    
    # El commit se gestionará en la transacción de nivel superior que llama a esta función. 