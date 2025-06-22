# macroferro_project/scripts/index_qdrant_data.py

"""
Script de Indexación para Qdrant y OpenAI con Enriquecimiento LLM y Caché Redis

Propósito:
Este script se encarga de extraer datos de productos desde una base de datos 
PostgreSQL, generar descripciones semánticas enriquecidas para cada producto 
utilizando un LLM (GPT-3.5-Turbo), cachear estas descripciones en Redis para
evitar llamadas redundantes, generar embeddings con la API de OpenAI, y finalmente 
indexar estos embeddings en una colección de Qdrant.

Flujo de Operaciones:
1.  Configuración y Conexiones: Carga variables de entorno y establece 
    conexiones con PostgreSQL, Qdrant, Redis y OpenAI.
2.  Manejo de Estado: Lee un timestamp de un fichero local para saber desde
    cuándo buscar productos nuevos o modificados.
3.  Extracción de Datos: Obtiene solo los productos actualizados desde la
    última ejecución exitosa.
4.  Procesamiento Concurrente por Producto:
    a.  Caché (Redis): Para cada producto, comprueba si ya existe una 
        descripción semántica generada para su versión actual.
    b.  Enriquecimiento (LLM): Si no está en caché, llama a la API de OpenAI
        para generar un párrafo de marketing optimizado. Se reintenta con
        backoff exponencial en caso de errores de rate limit.
    c.  Guardado en Caché: Almacena la nueva descripción en Redis.
    d.  Fallback: Si el LLM falla por cualquier otra razón, se usa una 
        descripción simple (nombre + descripción).
    e.  Generación de Embedding: Usa el texto (enriquecido o de fallback)
        para generar un vector de embedding.
    f.  Preparación de Punto: Crea un objeto `PointStruct` para Qdrant.
5.  Indexación (Upsert): Sube todos los puntos generados a Qdrant en un único
    lote eficiente.
6.  Guardado de Estado: Si la indexación fue exitosa Y NO HUBO ERRORES, 
    guarda el timestamp actual para la próxima ejecución.

Requisitos Previos:
-   Un archivo `.env` configurado.
-   Contenedores de PostgreSQL, Qdrant y Redis en ejecución.
"""
import asyncio
import json
import uuid
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from qdrant_client import AsyncQdrantClient, models
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from openai import AsyncOpenAI, RateLimitError, APIError
from redis.asyncio import Redis

# Añadir el directorio del proyecto al PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app.core.config import Settings

# --- Configuración ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constantes ---
COLLECTION_NAME = "macroferro_products"
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini-2024-07-18"
EMBEDDING_DIM = 1536
STATE_FILE_PATH = "scripts/indexing_state.json"

# --- Clientes (inicializados en main) ---
settings = Settings()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=5, timeout=60.0)
redis_client: Optional[Redis] = None
qdrant_client: Optional[AsyncQdrantClient] = None

# --- Manejo de Estado ---
def get_last_run_timestamp() -> Optional[datetime]:
    """Lee el timestamp de la última ejecución exitosa."""
    if not os.path.exists(STATE_FILE_PATH):
        logging.info("No se encontró el fichero de estado. Se procesarán todos los productos.")
        return None
    try:
        with open(STATE_FILE_PATH, 'r') as f:
            data = json.load(f)
            ts_str = data.get("last_run_timestamp")
            if ts_str:
                return datetime.fromisoformat(ts_str)
    except (json.JSONDecodeError, FileNotFoundError):
        logging.warning("Fichero de estado corrupto o no encontrado. Se procesarán todos los productos.")
    return None

def save_last_run_timestamp():
    """Guarda el timestamp de la ejecución actual."""
    state = {"last_run_timestamp": datetime.now(timezone.utc).isoformat()}
    with open(STATE_FILE_PATH, 'w') as f:
        json.dump(state, f, indent=4)
    logging.info("Timestamp de la ejecución guardado correctamente.")

# --- Lógica Principal ---
async def get_db_connection() -> Session:
    """Establece y devuelve una conexión a la base de datos."""
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def get_products(db: Session, last_run: Optional[datetime]) -> List[Dict[str, Any]]:
    """Obtiene productos de la BD que han sido actualizados desde la última ejecución."""
    query_str = """
        SELECT 
            p.sku, 
            p.name AS name_cleaned, 
            p.description AS description_cleaned, 
            p.brand AS brand_name, 
            c.name AS category_name,
            p.updated_at,
            p.spec_json as attributes
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.category_id
    """
    params = {}
    if last_run:
        query_str += " WHERE p.updated_at > :last_run"
        params["last_run"] = last_run

    query = text(query_str)
    result = db.execute(query, params).mappings().all()
    logging.info(f"Se encontraron {len(result)} productos para procesar.")
    return result

async def get_llm_description(product: Dict[str, Any]) -> Tuple[str, bool]:
    """
    Obtiene la descripción de un producto, ya sea de caché o generada por LLM.
    Devuelve la descripción y un booleano indicando si hubo un error.
    """
    if not redis_client:
        return f"{product['name_cleaned']} {product['description_cleaned']}", True

    cache_key = f"product_description:{LLM_MODEL}:{product['sku']}"
    try:
        cached_description = await redis_client.get(cache_key)
        if cached_description:
            logging.info(f"Cache HIT para SKU: {product['sku']}")
            return cached_description.decode('utf-8'), False
    except Exception as e:
        logging.error(f"Error al leer de Redis para SKU {product['sku']}: {e}")

    logging.info(f"Cache MISS para SKU: {product['sku']}. Generando nueva descripción con LLM.")
    prompt = f"""
    Eres un experto en marketing para una ferretería industrial. Genera una descripción de producto atractiva y rica en semántica para el siguiente artículo.
    Enfócate en los casos de uso, beneficios y posibles aplicaciones profesionales. No incluyas el nombre del producto ni el SKU en la descripción.
    Sé conciso y directo, utilizando un máximo de 150 palabras.

    Producto:
    - Nombre: {product.get('name_cleaned', 'N/A')}
    - Descripción: {product.get('description_cleaned', 'N/A')}
    - Marca: {product.get('brand_name', 'N/A')}
    - Categoría: {product.get('category_name', 'N/A')}
    - Atributos: {', '.join([f'{k}: {v}' for k, v in (product.get('attributes') or {}).items()])}
    """
    try:
        response = await openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=250
        )
        description = response.choices[0].message.content.strip()
        try:
            await redis_client.set(cache_key, description, ex=3600 * 24 * 7)  # Cache por 1 semana
            logging.info(f"Descripción para SKU {product['sku']} guardada en caché.")
        except Exception as e:
            logging.error(f"Error al escribir en Redis para SKU {product['sku']}: {e}")
        return description, False
    except (RateLimitError, APIError) as e:
        logging.warning(f"Error de API (RateLimit/APIError) para SKU {product['sku']}: {e}. Se usará fallback.")
        return f"{product['name_cleaned']} {product['description_cleaned']}", True
    except Exception as e:
        logging.error(f"Error inesperado al generar descripción para SKU {product['sku']}: {e}. Se usará fallback.")
        return f"{product['name_cleaned']} {product['description_cleaned']}", True

async def process_product(product: Dict[str, Any]) -> Tuple[Optional[models.PointStruct], bool]:
    """
    Procesa un solo producto: obtiene descripción, genera embedding y crea el punto para Qdrant.
    Devuelve el punto y un booleano indicando si hubo error.
    """
    description, has_error = await get_llm_description(product)
    
    text_to_embed = f"Nombre: {product['name_cleaned']}\nDescripción: {description}\nMarca: {product.get('brand_name', 'N/A')}\nCategoría: {product.get('category_name', 'N/A')}"

    try:
        embedding_response = await openai_client.embeddings.create(
            input=[text_to_embed],
            model=EMBEDDING_MODEL
        )
        vector = embedding_response.data[0].embedding
    except Exception as e:
        logging.error(f"No se pudo generar embedding para SKU {product['sku']}: {e}")
        return None, True

    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(product['sku'])))
    payload = {
        "sku": product["sku"],
        "name": product["name_cleaned"],
        "brand": product.get("brand_name"),
        "category": product.get("category_name"),
        "updated_at": product["updated_at"].isoformat(),
        "source_description": product["description_cleaned"],
        "llm_description": description if not has_error else None,
    }
    point = models.PointStruct(id=point_id, vector=vector, payload=payload)
    return point, has_error

async def setup_qdrant_collection():
    """Asegura que la colección en Qdrant exista con la configuración correcta."""
    if not qdrant_client:
        return
    try:
        await qdrant_client.get_collection(collection_name=COLLECTION_NAME)
        logging.info(f"La colección '{COLLECTION_NAME}' ya existe.")
    except Exception:
        logging.info(f"La colección '{COLLECTION_NAME}' no existe, creándola.")
        await qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
        )
        logging.info(f"Colección '{COLLECTION_NAME}' creada.")

async def main():
    """Función principal del script de indexación."""
    global redis_client, qdrant_client
    
    logging.info("--- Iniciando script de indexación ---")
    
    db = None
    any_errors = False
    
    try:
        # --- Conexiones ---
        db = await get_db_connection()
        redis_client = Redis.from_url(f"redis://{settings.REDIS_HOST}", decode_responses=False)
        qdrant_client = AsyncQdrantClient(
            url=f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT_GRPC}"
        )
        
        await setup_qdrant_collection()
        
        # --- Obtener productos ---
        last_run = get_last_run_timestamp()
        products = get_products(db, last_run)
        
        if not products:
            logging.info("No hay productos nuevos o actualizados para procesar.")
            save_last_run_timestamp() # Guardamos timestamp para no re-escanear en vano
            return

        # --- Procesamiento y carga ---
        tasks = [process_product(p) for p in products]
        results = await asyncio.gather(*tasks)

        points_to_upload = []
        for point, error in results:
            if point:
                points_to_upload.append(point)
            if error:
                any_errors = True

        if points_to_upload:
            logging.info(f"Subiendo {len(points_to_upload)} puntos a Qdrant...")
            await qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                points=points_to_upload,
                wait=True
            )
            logging.info("Puntos subidos exitosamente a Qdrant.")
        else:
            logging.info("No hay puntos para subir a Qdrant.")
            
        # --- Guardado de estado ---
        if not any_errors:
            save_last_run_timestamp()
        else:
            logging.warning("Se encontraron errores durante el procesamiento. El timestamp no se guardará para reintentar los fallos en la próxima ejecución.")

    except Exception as e:
        logging.critical(f"Ha ocurrido un error crítico en el script: {e}", exc_info=True)
    finally:
        # --- Cierre de conexiones ---
        if db:
            db.close()
        if redis_client:
            await redis_client.aclose()
        if qdrant_client:
            await qdrant_client.close()
        logging.info("--- Script de indexación finalizado ---")

if __name__ == "__main__":
    asyncio.run(main())