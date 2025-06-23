import requests
import json
import time
import sys
import re

# Configuración
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/telegram/test"
CHAT_ID = 66666 # Usar un chat_id nuevo y consistente

def send_message(text: str, chat_id: int = CHAT_ID) -> dict:
    """Envía un mensaje de prueba al bot y retorna la respuesta."""
    payload = {
        "message": {
            "message_id": int(time.time()),
            "from": {"id": chat_id, "is_bot": False, "first_name": "Search Test", "username": "search_test_user"},
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
            preview = msg.replace('\n', ' ')[:150]
            print(f"🤖 Bot (Msg {i+1}): {preview}...")
    else:
        print(f"🤖 Bot (Respuesta sin mensaje de texto)")
    return True

def main():
    print("🚀 Iniciando prueba de formato de resultados de búsqueda...")
    
    # --- PRUEBA: Buscar "guantes" y verificar el formato ---
    print_step("TEST: Buscar 'guantes' y validar la respuesta")
    msg = "busco guantes"
    resp = send_message(msg)
    
    if not print_result(msg, resp):
        sys.exit("❌ La prueba falló porque la petición al bot no fue exitosa.")

    # Verificación del formato de la respuesta
    print_step("VERIFICACIÓN: La respuesta no debe contener 'Especificaciones'")
    
    full_response_text = " ".join(resp["data"].get("messages", []))
    
    # Comprobar que no aparezcan las palabras "Especificaciones", "rosca" o "material"
    # Usamos regex para no ser sensibles a mayúsculas/minúsculas
    forbidden_words = ["especificaciones", "rosca", "material"]
    error_found = False
    for word in forbidden_words:
        if re.search(word, full_response_text, re.IGNORECASE):
            print(f"❌ Fallo: La palabra prohibida '{word}' fue encontrada en la respuesta.")
            error_found = True
            
    # Comprobar que no haya productos duplicados (mismo nombre y precio)
    product_entries = re.findall(r"\*\d+\. (.*?)\*.*?💰 Precio: \*\$(.*?)\*", full_response_text)
    if len(product_entries) != len(set(product_entries)):
        print(f"❌ Fallo: Se encontraron productos duplicados en la lista.")
        error_found = True

    if not error_found:
        print("✅ Éxito: El formato de la respuesta es correcto. No se encontraron especificaciones irrelevantes ni duplicados obvios.")
    else:
        sys.exit("--- PRUEBA FALLIDA ---")


if __name__ == "__main__":
    try:
        health_check = requests.get(f"{BASE_URL}/api/v1/telegram/health", timeout=5)
        if health_check.status_code != 200:
            sys.exit("❌ El backend no está respondiendo. Abortando prueba.")
        print("✅ Backend detectado correctamente.")
    except Exception as e:
        sys.exit(f"❌ No se puede conectar al backend: {e}")
    
    main() 