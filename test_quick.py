#!/usr/bin/env python3
"""
Script de prueba rápida para referencias contextuales
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/telegram/test"

def send_message(text: str, chat_id: int = 123456789) -> dict:
    """Envía un mensaje de prueba al bot y retorna la respuesta"""
    payload = {
        "message": {
            "message_id": int(time.time()),
            "from": {
                "id": chat_id,
                "is_bot": False,
                "first_name": "David",
                "username": "david_test"
            },
            "chat": {
                "id": chat_id,
                "type": "private"
            },
            "date": int(time.time()),
            "text": text
        }
    }
    
    try:
        response = requests.post(ENDPOINT, json=payload, timeout=30)
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    print("🧪 Prueba rápida de referencias contextuales...")
    
    # 1. Buscar producto específico
    print("\n1️⃣ Buscando producto específico...")
    resp1 = send_message("Busco Tornillos UNC para Plástico Facom")
    print(f"✅ Respuesta: {resp1['data']['type'] if resp1['success'] else 'Error'}")
    
    time.sleep(2)
    
    # 2. Agregar con referencia contextual
    print("\n2️⃣ Intentando agregar con referencia contextual...")
    resp2 = send_message("Agrega esos tornillos UNC al carrito")
    print(f"📋 Respuesta: {json.dumps(resp2['data'], indent=2) if resp2['success'] else 'Error'}")
    
    time.sleep(2)
    
    # 3. Buscar herramientas
    print("\n3️⃣ Buscando herramientas...")
    resp3 = send_message("Busco herramientas para construcción")
    print(f"✅ Respuesta: {resp3['data']['type'] if resp3['success'] else 'Error'}")
    
    time.sleep(2)
    
    # 4. Agregar taladro específico
    print("\n4️⃣ Intentando agregar taladro específico...")
    resp4 = send_message("Agrega el taladro Hilti al carrito")
    print(f"📋 Respuesta: {json.dumps(resp4['data'], indent=2) if resp4['success'] else 'Error'}")

if __name__ == "__main__":
    main() 