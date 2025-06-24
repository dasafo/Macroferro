from sqlalchemy import Column, String, Text
from app.db.database import Base

class Client(Base):
    __tablename__ = "clients"

    client_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255))
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50))
    address = Column(Text) 