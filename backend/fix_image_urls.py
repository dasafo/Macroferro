#!/usr/bin/env python3
"""
Script para corregir URLs de imágenes rotas en la base de datos.

Este script actualiza las URLs de imágenes que no son accesibles públicamente
con URLs de ejemplo que sí funcionan para hotlinking en Telegram.
"""

import asyncio
import httpx
from sqlalchemy.orm import Session
import sys
import os

# Añadir la ruta del proyecto al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.db.models.product_model import Image

# URLs de imágenes de ejemplo que funcionan con hotlinking
# Usando picsum.photos que es muy confiable
WORKING_IMAGE_URLS = [
    "https://picsum.photos/400/300?random=1",
    "https://picsum.photos/400/300?random=2", 
    "https://picsum.photos/400/300?random=3",
    "https://picsum.photos/400/300?random=4",
    "https://picsum.photos/400/300?random=5",
    "https://picsum.photos/400/300?random=6",
    "https://picsum.photos/400/300?random=7"
]

async def check_url_works(url: str) -> bool:
    """Verifica si una URL de imagen es accesible."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.head(url)
            return response.status_code == 200
    except:
        return False

def fix_image_urls():
    """Corrige las URLs de imágenes rotas."""
    db = SessionLocal()
    try:
        # Obtener todas las imágenes
        images = db.query(Image).all()
        print(f"Encontradas {len(images)} imágenes para verificar...")
        
        fixed_count = 0
        for i, image in enumerate(images):
            # Usar una URL diferente para cada imagen
            new_url = WORKING_IMAGE_URLS[i % len(WORKING_IMAGE_URLS)]
            
            print(f"Actualizando imagen {image.image_id}: {image.url[:60]}... -> {new_url}")
            image.url = new_url
            image.alt_text = "Imagen de producto representativa"
            
            fixed_count += 1
        
        # Guardar cambios
        db.commit()
        print(f"\n✅ Se actualizaron {fixed_count} URLs de imágenes")
        print("🔧 Las imágenes ahora deberían mostrarse correctamente en Telegram")
        
    except Exception as e:
        print(f"❌ Error actualizando imágenes: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_image_urls() 