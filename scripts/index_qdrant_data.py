# macroferro_project/scripts/index_qdrant_data.py

"""
Script de Indexación para Qdrant y OpenAI

Propósito:
Este script se encarga de extraer datos de productos desde una base de datos 
PostgreSQL, generar embeddings semánticos para cada producto utilizando la API 
de OpenAI, y finalmente indexar estos embeddings en una colección de Qdrant. 
El objetivo es preparar los datos para realizar búsquedas semánticas eficientes.

Flujo de Operaciones:
1.  Configuración Inicial: Carga variables de entorno (claves de API, URLs de BD).
2.  Conexión a Bases de Datos: Establece conexión con PostgreSQL y Qdrant.
3.  Extracción de Datos: Obtiene todos los productos de la tabla `products` en PostgreSQL.
4.  Preparación de Texto: Combina campos relevantes de cada producto (nombre, 
    descripción, marca, categoría, especificaciones) en un único texto cohesivo.
5.  Generación de Embeddings: Envía el texto de cada producto a la API de OpenAI 
    para obtener un vector de embedding que capture su significado semántico.
6.  Gestión de Colección en Qdrant: Se asegura de que la colección en Qdrant 
    exista y esté configurada correctamente. Por defecto, la recrea para 
    garantizar una indexación limpia.
7.  Indexación (Upsert): Sube los embeddings y metadatos asociados a Qdrant 
    en lotes, usando el SKU del producto como identificador único.

Requisitos Previos:
-   Un archivo `.env` en la raíz del proyecto con las siguientes variables:
    - `DATABASE_URL`: Cadena de conexión a PostgreSQL.
    - `OPENAI_API_KEY`: Clave de la API de OpenAI.
    - `QDRANT_HOST`, `QDRANT_PORT_REST`, `QDRANT_PORT_GRPC`: Host y puertos de Qdrant.
    - `QDRANT_API_KEY` (opcional si Qdrant no requiere autenticación).
-   Los contenedores de PostgreSQL y Qdrant deben estar en ejecución.
-   La base de datos PostgreSQL debe tener la tabla `products` poblada.
"""

import asyncio
import os
import sys
import json
import uuid # Importar la librería para generar UUIDs
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from openai import AsyncOpenAI # Cambiado a AsyncOpenAI para operaciones concurrentes
from qdrant_client import QdrantClient, models as qdrant_models

# Añadir el directorio del proyecto al PYTHONPATH para poder importar módulos de la app
# Esto es necesario si ejecutas el script directamente y no como un módulo dentro de la app
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

from app.core.config import settings # Importar configuración de la app
# Necesitaremos los modelos de producto para obtener los datos
# from app.db.models import Product # Si quisieras usar SQLAlchemy ORM completo

# --- Configuración ---
QDRANT_HOST = settings.QDRANT_HOST
QDRANT_PORT_REST = settings.QDRANT_PORT_REST
QDRANT_PORT_GRPC = settings.QDRANT_PORT_GRPC
QDRANT_COLLECTION_NAME = "macroferro_products"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small" # Modelo de embedding recomendado y más nuevo/eficiente
EMBEDDING_DIM = 1536 # Para text-embedding-3-small. Verifica la dimensión para el modelo que uses
                    # text-embedding-ada-002 tiene 1536

# --- Fichero de Estado para Sincronización ---
# Este fichero guardará la fecha de la última ejecución exitosa para procesar solo los cambios.
STATE_FILE_PATH = os.path.join(project_root, "scripts", "indexing_state.json")

# Conexión a PostgreSQL (usando SQLAlchemy core para una consulta simple)
# Asegúrate de que DATABASE_URL esté correctamente configurada en tu .env y settings
engine = create_engine(str(settings.DATABASE_URL)) # SQLAlchemy 2.0 prefiere str()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_products_from_db(db_session, since_timestamp: Optional[str] = None):
    """
    Obtiene productos de la BD, opcionalmente solo los actualizados desde una fecha.
    
    Si se proporciona `since_timestamp`, la función solo devolverá los productos
    cuya columna `updated_at` sea más reciente que la fecha proporcionada.
    
    Args:
        db_session: Una sesión activa de SQLAlchemy.
        since_timestamp (str, optional): Timestamp en formato ISO 8601.
        
    Returns:
        Una lista de diccionarios, donde cada diccionario representa un producto.
        
    **Requisito**: La tabla 'products' debe tener una columna 'updated_at' que
    se actualice en cada modificación para que la sincronización funcione.
    """
    base_query = """
        SELECT 
            p.sku, 
            p.name, 
            p.description, 
            p.brand, 
            c.name as category_name,
            p.spec_json
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.category_id
    """
    
    if since_timestamp:
        # Añade la condición para obtener solo los productos modificados recientemente.
        query = text(base_query + " WHERE p.updated_at > :since_timestamp")
        result = db_session.execute(query, {"since_timestamp": since_timestamp})
        print(f"Obteniendo productos actualizados desde {since_timestamp}...")
    else:
        # Si no hay fecha, obtiene todos los productos (para la primera ejecución).
        query = text(base_query + ";")
        result = db_session.execute(query)
        print("Obteniendo todos los productos (primera ejecución o reinicio)...")

    products = [dict(row._mapping) for row in result]
    return products

def create_text_for_embedding(product_data: dict) -> str:
    """
    Crea un string de texto unificado a partir de los datos de un producto.
    
    Este texto combinado será el que se envíe a OpenAI para generar el embedding.
    La calidad y estructura de este texto son cruciales para la relevancia de las
    búsquedas semánticas. Unir campos clave con separadores ayuda al modelo a
    distinguir la semántica de cada parte.
    
    Args:
        product_data: Un diccionario con los datos de un producto.
        
    Returns:
        Un string único que representa al producto.
    """
    # Lista de los campos de texto más importantes del producto.
    parts = [
        f"Nombre: {product_data.get('name', '')}",
        f"Descripción: {product_data.get('description', '')}",
        f"Marca: {product_data.get('brand', '')}",
        f"Categoría: {product_data.get('category_name', '')}"
    ]
    
    # Procesa las especificaciones técnicas (spec_json) si existen.
    # Esto enriquece el embedding con detalles técnicos específicos.
    spec_json = product_data.get("spec_json")
    if isinstance(spec_json, dict):
        spec_parts = [f"{key}: {value}" for key, value in spec_json.items()]
        if spec_parts:
            parts.append(f"Especificaciones: {' | '.join(spec_parts)}")

    # `filter(None, parts)` elimina strings vacíos si algún campo es nulo.
    # ` " | ".join(...)` une todas las partes en un único string, fácil de procesar por el modelo.
    return " | ".join(filter(None, parts)).strip()

async def process_product_embedding(product: dict, openai_client: AsyncOpenAI) -> Optional[qdrant_models.PointStruct]:
    """
    Genera el embedding para un único producto y devuelve un PointStruct de Qdrant.
    
    Esta función encapsula la lógica para un solo producto, permitiendo su ejecución
    concurrente.
    
    Args:
        product: Diccionario con los datos del producto.
        openai_client: Cliente asíncrono de OpenAI.
        
    Returns:
        Un objeto PointStruct listo para ser insertado en Qdrant, o None si ocurre un error.
    """
    text_to_embed = create_text_for_embedding(product)
    if not text_to_embed:
        print(f"Advertencia: No se pudo generar texto para el SKU {product['sku']}. Se omite.")
        return None
    
    try:
        # Llamada asíncrona a la API de OpenAI
        response = await openai_client.embeddings.create(
            input=[text_to_embed],
            model=OPENAI_EMBEDDING_MODEL
        )
        embedding = response.data[0].embedding
        
        # Guardamos el SKU y otros datos importantes en el payload.
        payload = {
            "sku": product.get("sku"), # <-- Guardamos el SKU aquí
            "name": product.get("name"),
            "brand": product.get("brand"),
            "category_name": product.get("category_name"),
        }
        
        # Generamos un UUID para usarlo como ID del punto, como requiere Qdrant.
        # Usamos un UUID version 5, que es determinista a partir de un namespace y un nombre.
        # Esto garantiza que el mismo SKU siempre generará el mismo UUID.
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, product["sku"]))

        return qdrant_models.PointStruct(
            id=point_id, # Usamos el UUID generado como ID
            vector=embedding,
            payload=payload
        )
    except Exception as e:
        print(f"Error procesando el SKU {product['sku']}: {e}")
        return None

# --- Funciones para Manejar el Estado de Sincronización ---

def read_last_run_timestamp() -> Optional[str]:
    """Lee la fecha de la última ejecución del fichero de estado."""
    try:
        with open(STATE_FILE_PATH, "r") as f:
            state = json.load(f)
            return state.get("last_successful_run")
    except (FileNotFoundError, json.JSONDecodeError):
        # Si el fichero no existe o está corrupto, es como si fuera la primera vez.
        print("Fichero de estado no encontrado o inválido. Se procesarán todos los productos.")
        return None

def save_last_run_timestamp(timestamp: str):
    """Guarda la fecha de la ejecución actual en el fichero de estado."""
    with open(STATE_FILE_PATH, "w") as f:
        json.dump({"last_successful_run": timestamp}, f)
    print(f"Estado de sincronización guardado. Última ejecución: {timestamp}")

async def main():
    """Función principal que orquesta todo el proceso de indexación."""
    print("Iniciando proceso de indexación en Qdrant...")
    
    # Guardamos la hora de inicio para registrarla si todo sale bien.
    # Usamos timezone.utc para asegurar consistencia independientemente del servidor.
    start_time_iso = datetime.now(timezone.utc).isoformat()

    # --- 1. Inicializar Clientes de API ---
    try:
        # Cliente de OpenAI: se usará para generar los embeddings.
        # Requiere que la variable de entorno OPENAI_API_KEY esté configurada.
        openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        if not settings.OPENAI_API_KEY:
            raise ValueError("La variable de entorno OPENAI_API_KEY no está configurada.")
            
        # Cliente de Qdrant: se usará para interactuar con la base de datos de vectores.
        # Se conecta usando el host y el puerto gRPC para evitar ambigüedades.
        qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT_GRPC, api_key=settings.QDRANT_API_KEY)
        print(f"Conectado a Qdrant en {QDRANT_HOST}:{QDRANT_PORT_GRPC} (gRPC)")
    except Exception as e:
        print(f"Error fatal al inicializar los clientes: {e}")
        return

    # --- 2. Obtener Productos de PostgreSQL (solo los actualizados) ---
    last_run = read_last_run_timestamp()
    db_session = SessionLocal()
    try:
        # Pasamos la fecha de la última ejecución a la función de obtención de datos.
        products_data = get_products_from_db(db_session, since_timestamp=last_run)
        
        if not products_data:
            print("No se encontraron productos nuevos o actualizados para procesar. Finalizando script.")
            # Guardamos la hora actual para que la próxima ejecución empiece desde ahora.
            save_last_run_timestamp(start_time_iso)
            return
            
        print(f"Se encontraron {len(products_data)} productos para procesar.")
    except Exception as e:
        print(f"Error fatal al obtener productos de la base de datos: {e}")
        return
    finally:
        # Es crucial cerrar la sesión de la base de datos para liberar la conexión.
        db_session.close()

    # --- 3. Asegurar la Existencia de la Colección en Qdrant (sin recrearla) ---
    try:
        print(f"Verificando y preparando la colección '{QDRANT_COLLECTION_NAME}' en Qdrant...")
        collections_response = qdrant_client.get_collections()
        collection_names = [col.name for col in collections_response.collections]

        if QDRANT_COLLECTION_NAME not in collection_names:
            print(f"La colección '{QDRANT_COLLECTION_NAME}' no existe. Se procederá a crearla.")
            # Crea la colección solo si no existe.
            qdrant_client.create_collection(
                collection_name=QDRANT_COLLECTION_NAME,
                vectors_config=qdrant_models.VectorParams(size=EMBEDDING_DIM, distance=qdrant_models.Distance.COSINE)
            )
            print("Colección creada exitosamente.")
        else:
            print(f"La colección '{QDRANT_COLLECTION_NAME}' ya existe. Se procederá a actualizarla (upsert).")
            
    except Exception as e:
        print(f"Error fatal manejando la colección de Qdrant: {e}")
        return

    # --- 4. Generar Embeddings e Indexar en Qdrant (de forma concurrente) ---
    print("Iniciando generación de embeddings concurrentes...")
    
    # Crear una lista de tareas asíncronas, una para cada producto.
    # Cada tarea llamará a la API de OpenAI para obtener el embedding.
    tasks = [process_product_embedding(product, openai_client) for product in products_data]
    
    # Ejecutar todas las tareas en paralelo usando asyncio.gather.
    # Esto es mucho más rápido que hacerlo secuencialmente.
    # `return_exceptions=True` evita que una tarea fallida detenga todo el proceso.
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Procesar los resultados: separar los puntos válidos de los errores.
    points_to_upsert = []
    failed_skus = 0
    for i, res in enumerate(results):
        if isinstance(res, qdrant_models.PointStruct):
            points_to_upsert.append(res)
        else:
            # Si `res` no es un PointStruct, es un error (None o una excepción).
            failed_skus += 1
            sku = products_data[i].get('sku', 'desconocido')
            print(f"  Fallo al procesar SKU {sku}. Razón: {res}")
            
    print(f"Generación de embeddings completada. Puntos válidos: {len(points_to_upsert)}. Fallos: {failed_skus}.")

    # --- 5. Subir Puntos a Qdrant en Lotes (Batch Upsert) ---
    if points_to_upsert:
        print(f"Subiendo {len(points_to_upsert)} puntos a Qdrant en lotes...")
        try:
            # Subir los puntos en lotes es mucho más eficiente que subirlos de uno en uno.
            batch_size = 100 
            for i in range(0, len(points_to_upsert), batch_size):
                batch = points_to_upsert[i:i + batch_size]
                # `upsert` inserta nuevos puntos o actualiza los existentes si el ID ya está.
                # `wait=True` hace que la llamada sea bloqueante hasta que la operación se complete.
                qdrant_client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=batch, wait=True)
                print(f"  Lote de {len(batch)} puntos subido correctamente.")
            print("¡Indexación completada! Todos los puntos han sido subidos a Qdrant.")
        except Exception as e:
            print(f"Error fatal durante la subida de puntos a Qdrant: {e}")
            return # Si la subida falla, no actualizamos el timestamp para poder reintentar.
    else:
        print("No se generaron puntos válidos para subir. Verifique los datos de origen y los logs.")

    # Si todo el proceso ha sido exitoso, guardamos la fecha de esta ejecución.
    save_last_run_timestamp(start_time_iso)
    
    print("Proceso de indexación finalizado.")

# --- Manejo de Eliminaciones (Mejora Futura) ---
# Este script ahora maneja creaciones y actualizaciones. Para manejar eliminaciones,
# se podría implementar una estrategia de "soft delete" en la base de datos:
# 1. Añadir una columna `is_deleted` (boolean) a la tabla `products`.
# 2. En lugar de borrar un producto, se marcaría `is_deleted = true`.
# 3. Este script podría tener un paso adicional que:
#    a. Consulte los productos marcados como eliminados desde la última ejecución.
#    b. Use `qdrant_client.delete(collection_name=..., points_selector=...)`
#       para eliminarlos de Qdrant usando sus SKUs.

if __name__ == "__main__":
    # Este bloque se ejecuta solo cuando el script es llamado directamente.
    
    # Contexto sobre asincronía:
    # La librería `openai` v1.x.x realiza llamadas de red síncronas por defecto.
    # En un script de ejecución única como este, una ejecución síncrona es aceptable.
    # Si este proceso se integrara en una aplicación asíncrona (como FastAPI),
    # o si se procesaran cientos de miles de productos, sería recomendable usar
    # un cliente asíncrono (`AsyncOpenAI`) para no bloquear el bucle de eventos.
    
    # Usamos `asyncio.run()` para ejecutar la función `main` que hemos definido como `async`.
    # Aunque las llamadas a la API son síncronas, esto establece un buen patrón
    # si en el futuro se añaden operaciones asíncronas.
    asyncio.run(main())