from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Integer
from sqlalchemy.sql.functions import max as sql_max
from typing import Optional
from app.db.models.client_model import Client

def get_client_by_email(db: Session, email: str) -> Optional[Client]:
    """
    Busca un cliente por su dirección de correo electrónico.
    """
    return db.query(Client).filter(Client.email == email).first()

def create_client(db: Session, name: str, email: str, phone: str, address: str) -> Client:
    """
    Crea un nuevo cliente en la base de datos con un ID numérico secuencial.
    """
    # Usar una expresión regular para encontrar solo los IDs con formato CUST<números>
    # Esto evita errores con IDs que no siguen el patrón, como los generados por UUID.
    max_id_query = db.query(
        sql_max(
            cast(
                func.substr(Client.client_id, 5), 
                Integer
            )
        )
    ).filter(Client.client_id.op("~")('^CUST[0-9]+$'))
    
    max_id = max_id_query.scalar()
    
    # Si no hay clientes o ninguno sigue el patrón, empezar desde 1000
    next_id_num = (max_id + 1) if max_id is not None else 1000
    
    # Formatear el nuevo ID
    new_client_id = f"CUST{next_id_num}"
    
    db_client = Client(
        client_id=new_client_id,
        name=name,
        email=email,
        phone=phone,
        address=address
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client 