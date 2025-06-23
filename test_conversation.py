#!/usr/bin/env python3
"""
Script de prueba para el bot de Telegram - Conversación Natural Completa
Simula una conversación real para verificar todas las funcionalidades
"""

import requests
import json
import time
import sys

# Configuración del endpoint
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/telegram/test"
CHAT_ID = 12345 # Usar un chat_id consistente para mantener el contexto

def send_message(text: str, chat_id: int = CHAT_ID) -> dict:
    """Envía un mensaje de prueba al bot y retorna la respuesta"""
    payload = {
        "message": {
            "message_id": int(time.time()),
            "from": {"id": chat_id, "is_bot": False, "first_name": "Test", "username": "test_user"},
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
            "text": text
        }
    }
    try:
        response = requests.post(ENDPOINT, json=payload, timeout=45)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_step(step, description):
    print(f"\n{'='*15} PASO {step}: {description} {'='*15}")

def print_result(user_msg, response):
    print(f"👤 Usuario: {user_msg}")
    if not response["success"]:
        print(f"❌ Error: {response['error']}")
        return
    
    data = response["data"]
    response_type = data.get("type", "unknown")
    
    if response_type == "text_messages":
        messages = data.get("messages", [])
        for i, msg in enumerate(messages):
            # Limitar la previsualización para no saturar la salida
            preview = msg.replace('\n', ' ')[:250]
            print(f"🤖 Bot: {preview}...")
    else:
        print(f"🤖 Bot ({response_type}): {json.dumps(data, indent=2, ensure_ascii=False)}")


def main():
    print("🚀 Iniciando prueba de conversación para el carrito de compras...")
    
    # --- SETUP: Vaciar carrito y añadir productos ---
    print_step(0, "Setup - Limpiando el carrito")
    print_result("Vaciar carrito", send_message("/vaciar_carrito"))
    time.sleep(1)

    print_step(0, "Setup - Buscar y añadir 3 Guantes")
    print_result("Buscar guantes", send_message("Busco Guantes Multiusos Facom"))
    time.sleep(2)
    print_result("Añadir 3 guantes", send_message("Añade 3 de esos guantes"))
    time.sleep(2)

    print_step(0, "Setup - Buscar y añadir 3 Adhesivos")
    print_result("Buscar adhesivos", send_message("Busco Adhesivo para Madera Makita"))
    time.sleep(2)
    print_result("Añadir 3 adhesivos", send_message("añade 3 de esos adhesivos"))
    time.sleep(2)
    
    # --- PRUEBA 1: Verificar carrito inicial ---
    print_step(1, "Verificar estado inicial del carrito")
    msg = "enséñame el carro"
    resp = send_message(msg)
    print_result(msg, resp)

    # --- PRUEBA 2: Reducir cantidad de un producto ---
    print_step(2, "Reducir la cantidad de un producto")
    msg = "puede eliminar 1 un guante del carrito?"
    resp = send_message(msg)
    print_result(msg, resp)
    time.sleep(2)

    # --- PRUEBA 3: Verificar carrito tras reducir cantidad ---
    print_step(3, "Verificar que la cantidad de guantes se haya reducido")
    msg = "muéstrame el carrito"
    resp = send_message(msg)
    print_result(msg, resp)

    # --- PRUEBA 4: Eliminar otro producto por referencia natural (plural) ---
    print_step(4, "Eliminar producto por referencia natural en plural")
    msg = "elimina los adhesivos"
    resp = send_message(msg)
    print_result(msg, resp)
    time.sleep(2)

    # --- PRUEBA 5: Verificar carrito final ---
    print_step(5, "Verificar que los adhesivos se hayan eliminado")
    msg = "ver carrito"
    resp = send_message(msg)
    print_result(msg, resp)

    print("\n\n" + "="*50)
    print("✅ Prueba de conversación del carrito finalizada.")
    print("Por favor, revisa los resultados de cada paso.")


if __name__ == "__main__":
    # Verificar que el backend esté corriendo
    try:
        health_check = requests.get(f"{BASE_URL}/api/v1/telegram/health", timeout=5)
        if health_check.status_code != 200:
            print("❌ El backend no está respondiendo correctamente. Abortando prueba.")
            sys.exit(1)
        print("✅ Backend detectado correctamente.")
    except Exception as e:
        print(f"❌ No se puede conectar al backend: {e}")
        print("💡 Asegúrate de que el backend esté corriendo en localhost:8000")
        sys.exit(1)
    
    main() 