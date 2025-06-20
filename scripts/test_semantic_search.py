#!/usr/bin/env python
# scripts/test_semantic_search.py

"""
Script de Prueba para Búsqueda Semántica en Qdrant

Propósito:
Este script permite probar la calidad de los embeddings y la lógica de búsqueda
semántica implementada en el proyecto. Toma una consulta de texto libre como
argumento, la convierte en un vector de embedding usando OpenAI y busca los
puntos más similares en la colección de Qdrant.

Uso:
Desde el host, ejecuta el siguiente comando en el Makefile:
make search-test query="tu frase de búsqueda aquí"

Ejemplos de búsqueda:
- "herramienta para cortar tubos de cobre"
- "necesito algo para fijar un cuadro pesado en una pared de ladrillo"
- "material para soldar componentes electrónicos"
- "disco para cortar metal con amoladora"
"""

import os
import sys
import asyncio
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
import argparse
import logging

# Añadir el directorio del proyecto al PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app.core.config import Settings

# --- Configuración ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
settings = Settings()

# --- Constantes ---
COLLECTION_NAME = "macroferro_products"
EMBEDDING_MODEL = "text-embedding-3-small"

async def perform_search(query_text: str, top_k: int = 5):
    """
    Realiza una búsqueda semántica en Qdrant.
    """
    if not query_text:
        logging.error("La consulta de búsqueda no puede estar vacía.")
        return

    logging.info(f"🚀 Realizando búsqueda para: '{query_text}'")

    # --- Clientes ---
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    qdrant_client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT_GRPC, api_key=settings.QDRANT_API_KEY)

    try:
        # 1. Generar embedding para la consulta del usuario
        logging.info("🧠 Generando embedding para la consulta...")
        embedding_response = await openai_client.embeddings.create(
            input=[query_text],
            model=EMBEDDING_MODEL
        )
        query_vector = embedding_response.data[0].embedding
        logging.info("✅ Embedding generado.")

        # 2. Buscar en Qdrant
        logging.info(f"🔍 Buscando los {top_k} productos más relevantes en Qdrant...")
        search_result = await qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            with_payload=True,  # Para obtener los datos del producto
        )
        logging.info("✅ Búsqueda completada.")

        # 3. Mostrar resultados
        print("\n" + "="*50)
        print("🏆 RESULTADOS DE LA BÚSQUEDA 🏆")
        print("="*50 + "\n")

        if not search_result:
            print("No se encontraron resultados para tu búsqueda.")
            return

        for i, hit in enumerate(search_result):
            payload = hit.payload
            print(f"--- Resultado #{i+1} ---")
            print(f"  SKU:      {payload.get('sku')}")
            print(f"  Nombre:   {payload.get('name')}")
            print(f"  Marca:    {payload.get('brand', 'N/A')}")
            print(f"  Categoría:{payload.get('category', 'N/A')}")
            print(f"  Score:    {hit.score:.4f} (Similitud)")
            print(f"  Desc. IA: {payload.get('llm_description', 'N/A')[:150]}...")
            print("\n")

    except Exception as e:
        logging.critical(f"Ha ocurrido un error durante la búsqueda: {e}", exc_info=True)
    finally:
        await qdrant_client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Realiza una búsqueda semántica en la base de datos de productos.")
    parser.add_argument("query", type=str, help="La frase de búsqueda en lenguaje natural.")
    parser.add_argument("--top", type=int, default=5, help="Número de resultados a devolver.")
    
    args = parser.parse_args()
    
    asyncio.run(perform_search(args.query, args.top)) 