# backend/app/crud/client_crud.py
"""
Este archivo contiene las operaciones CRUD para el modelo Client.

Este módulo proporciona funciones para crear y buscar clientes en la base de datos.
"""

from sqlalchemy import func, cast, Integer, select
from sqlalchemy.sql.functions import max as sql_max
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.models.client_model import Client

async def get_client_by_email(db: AsyncSession, email: str) -> Optional[Client]:
    """
    Busca un cliente por su dirección de correo electrónico de forma asíncrona.
    """
    result = await db.execute(select(Client).filter(Client.email == email))
    return result.scalars().first()

async def create_client(db: AsyncSession, name: str, email: str, phone: Optional[str] = None, address: Optional[str] = None) -> Client:
    """
    Crea un nuevo cliente en la base de datos con un ID numérico secuencial de forma asíncrona.
    """
    max_id_query = select(
        sql_max(
            cast(
                func.substr(Client.client_id, 5), 
                Integer
            )
        )
    ).filter(Client.client_id.op("~")('^CUST[0-9]+$')) # Filtra los IDs que empiezan con CUST seguido de números
    
    max_id_result = await db.execute(max_id_query)
    max_id = max_id_result.scalar()
    
    next_id_num = (max_id + 1) if max_id is not None else 1000
    
    new_client_id = f"CUST{next_id_num}"
    
    db_client = Client(
        client_id=new_client_id,
        name=name,
        email=email,
        phone=phone,
        address=address
    )
    db.add(db_client)
    await db.commit()
    await db.refresh(db_client)
    return db_client 