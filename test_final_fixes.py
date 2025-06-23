import requests
import json
import time
import sys

# Configuración
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/telegram/test"
CHAT_ID = 55555 # Usar un chat_id nuevo y consistente

def send_message(text: str, chat_id: int = CHAT_ID) -> dict:
    """Envía un mensaje de prueba al bot y retorna la respuesta"""
    payload = {
        "message": {
            "message_id": int(time.time()),
            "from": {"id": chat_id, "is_bot": False, "first_name": "Final Fix Test", "username": "final_fix_user"},
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
        preview = messages[0].replace('\n', ' ')[:300]
        print(f"🤖 Bot: {preview}...")
    else:
        print(f"🤖 Bot (Respuesta sin mensaje de texto)")
    return True

def check_cart(expected_quantity: int, expected_sku: str) -> bool:
    """Verifica si el carrito contiene la cantidad esperada para un SKU específico."""
    print_step(f"VERIFICANDO Carrito: Esperando {expected_quantity} de {expected_sku}")
    resp = send_message("ver carrito")
    print_result("ver carrito", resp)
    if not resp["success"]:
        print("❌ Fallo: No se pudo obtener el estado del carrito.")
        return False
        
    cart_text = " ".join(resp["data"].get("messages", []))
    expected_string = f"{expected_quantity} x"
    
    if expected_sku in cart_text and expected_string in cart_text:
        print(f"✅ Éxito: El carrito contiene {expected_quantity} unidades de {expected_sku}.")
        return True
    else:
        print(f"❌ Fallo: El estado del carrito es incorrecto.")
        return False

def main():
    print("🚀 Iniciando prueba final de corrección de contexto en el carrito...")
    
    # --- SETUP: Vaciar carrito ---
    print_step("SETUP: Limpiando el carrito")
    send_message("/vaciar_carrito")
    time.sleep(1)
    
    # --- PRUEBA 1: Añadir producto específico ---
    print_step("TEST 1: Añadir 23 Tornillos Métricos Makita")
    msg1 = "añade 23 tornillos Métricos Makita"
    resp1 = send_message(msg1)
    print_result(msg1, resp1)
    time.sleep(2)
    check_cart(expected_quantity=23, expected_sku="SKU00049")
    
    # --- PRUEBA 2: Quitar 2 unidades del producto ---
    print_step("TEST 2: Quitar '2 tornillos del carro'")
    msg2 = "quita mejor 2 tornillos del carro"
    resp2 = send_message(msg2)
    print_result(msg2, resp2)
    time.sleep(2)
    check_cart(expected_quantity=21, expected_sku="SKU00049")

if __name__ == "__main__":
    try:
        health_check = requests.get(f"{BASE_URL}/api/v1/telegram/health", timeout=5)
        if health_check.status_code != 200:
            sys.exit("❌ El backend no está respondiendo. Abortando prueba.")
        print("✅ Backend detectado correctamente.")
    except Exception as e:
        sys.exit(f"❌ No se puede conectar al backend: {e}")
    
    main() 