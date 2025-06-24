from sqlalchemy.orm import Session
from typing import Optional
from app.db.models.client_model import Client
import uuid

def get_client_by_email(db: Session, email: str) -> Optional[Client]:
    """
    Busca un cliente por su dirección de correo electrónico.
    """
    return db.query(Client).filter(Client.email == email).first()

def create_client(db: Session, name: str, email: str, phone: str, address: str) -> Client:
    """
    Crea un nuevo cliente en la base de datos con un ID único.
    """
    # Generar un ID de cliente único y simple
    client_id = f"CUST-{uuid.uuid4().hex[:6].upper()}"
    
    db_client = Client(
        client_id=client_id,
        name=name,
        email=email,
        phone=phone,
        address=address
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client 