import requests
import json
import time
import sys
import re

# Configuración
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/telegram/test"
CHAT_ID = 77777 # Usar un chat_id nuevo y consistente

def send_message(text: str, chat_id: int = CHAT_ID) -> dict:
    """Envía un mensaje de prueba al bot y retorna la respuesta."""
    payload = {
        "message": {
            "message_id": int(time.time()),
            "from": {"id": chat_id, "is_bot": False, "first_name": "Understanding Test", "username": "understanding_user"},
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
            "text": text
        }
    }
    try:
        response = requests.post(ENDPOINT, json=payload, timeout=45)
        return {"success": response.ok, "status_code": response.status_code, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_step(description):
    print(f"\n{'='*20} {description} {'='*20}")

def print_result(user_msg, response):
    print(f"👤 Usuario: {user_msg}")
    if not response["success"]:
        detail = response.get("data", {}).get("detail", response.get("error", "Error desconocido"))
        print(f"❌ Error: {detail}")
        return False
    
    data = response["data"]
    messages = data.get("messages", [])
    if messages:
        for i, msg in enumerate(messages):
            preview = msg.replace('\n', ' ')
            print(f"🤖 Bot (Msg {i+1}): {preview}")
    else:
        print(f"🤖 Bot (Respuesta sin mensaje de texto)")
    return True

def main():
    print("🚀 Iniciando prueba de comprensión de mensajes...")
    
    # --- PRUEBA 1: Saludo simple ---
    print_step("TEST 1: Enviar un saludo simple ('hola')")
    msg1 = "hola"
    resp1 = send_message(msg1)
    print_result(msg1, resp1)
    
    response_text1 = " ".join(resp1.get("data", {}).get("messages", []))
    if "no he entendido" in response_text1:
        print("❌ Fallo: El bot pidió aclaración para un saludo simple.")
        sys.exit("--- PRUEBA FALLIDA ---")
    else:
        print("✅ Éxito: El bot respondió correctamente al saludo.")

    time.sleep(2)

    # --- PRUEBA 2: Mensaje ambiguo ---
    print_step("TEST 2: Enviar un mensaje ambiguo ('tienes cosas de metal?')")
    msg2 = "tienes cosas de metal?"
    resp2 = send_message(msg2)
    print_result(msg2, resp2)

    response_text2 = " ".join(resp2.get("data", {}).get("messages", []))
    if "consulta es un poco general" in response_text2 and "más específico" in response_text2:
        print("✅ Éxito: El bot pidió educadamente una aclaración.")
    else:
        print("❌ Fallo: El bot no pidió aclaración para un mensaje ambiguo.")
        sys.exit("--- PRUEBA FALLIDA ---")
        
    print("\n🎉 Todas las pruebas de comprensión han pasado con éxito.")


if __name__ == "__main__":
    try:
        health_check = requests.get(f"{BASE_URL}/api/v1/telegram/health", timeout=5)
        if health_check.status_code != 200:
            sys.exit("❌ El backend no está respondiendo. Abortando prueba.")
        print("✅ Backend detectado correctamente.")
    except Exception as e:
        sys.exit(f"❌ No se puede conectar al backend: {e}")
    
    main() 