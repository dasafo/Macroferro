# backend/app/db/database.py

"""
Configuración principal de la base de datos para la aplicación.

Este módulo establece la conexión con PostgreSQL usando SQLAlchemy y define
los componentes básicos que serán utilizados por toda la aplicación:
- Motor de base de datos (engine)
- Fábrica de sesiones (SessionLocal)  
- Clase base para modelos (Base)

La función get_db() se ha movido a app/api/deps.py para seguir las mejores
prácticas de FastAPI y mantener las dependencias separadas de la configuración.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings # Importamos nuestra configuración

# URL de conexión a PostgreSQL. La obtenemos directamente desde las variables de entorno
# a través de nuestra clase de configuración.
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Motor de SQLAlchemy: maneja el pool de conexiones y la comunicación con PostgreSQL
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Fábrica de sesiones de base de datos
# Cada sesión representa una "conversación" con la base de datos
# autocommit=False: Las transacciones deben confirmarse explícitamente con commit()
# autoflush=False: Los cambios no se envían automáticamente sin commit()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base declarativa para todos los modelos ORM
# Todos los modelos en models.py heredarán de esta clase
# Proporciona funcionalidad común como metadatos de tabla y mapeo ORM
Base = declarative_base()
