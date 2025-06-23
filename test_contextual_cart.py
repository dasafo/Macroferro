import requests
import json
import time
import sys

# Configuración
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/telegram/test"
CHAT_ID = 44444 # Usar un chat_id consistente y nuevo

def send_message(text: str, chat_id: int = CHAT_ID) -> dict:
    """Envía un mensaje de prueba al bot y retorna la respuesta"""
    payload = {
        "message": {
            "message_id": int(time.time()),
            "from": {"id": chat_id, "is_bot": False, "first_name": "Context Test", "username": "context_test_user"},
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
            "text": text
        }
    }
    try:
        response = requests.post(ENDPOINT, json=payload, timeout=45)
        # No usamos raise_for_status() para poder manejar errores 400
        return {"success": response.ok, "status_code": response.status_code, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def print_step(description):
    print(f"\n{'='*15} {description} {'='*15}")

def print_result(user_msg, response):
    print(f"👤 Usuario: {user_msg}")
    if not response["success"]:
        detail = response.get("data", {}).get("detail", response.get("error", "Error desconocido"))
        print(f"❌ Error (esperado o inesperado): {detail}")
        return False
    
    data = response["data"]
    messages = data.get("messages", [])
    if messages:
        preview = messages[0].replace('\n', ' ')[:250]
        print(f"🤖 Bot: {preview}...")
    else:
        print(f"🤖 Bot (Respuesta sin mensaje de texto)")
    return True

def main():
    print("🚀 Iniciando prueba de contexto del carrito y validación...")
    
    # --- SETUP: Vaciar carrito y añadir productos ---
    print_step("SETUP: Limpiando y poblando el carrito")
    send_message("/vaciar_carrito")
    time.sleep(1)
    send_message("añade 2 Guantes de Protección Einhell")
    time.sleep(2)
    print_result("Verificando setup", send_message("ver carrito"))
    
    # --- PRUEBA 1: Añadir MÁS de un producto existente ---
    print_step("TEST 1: Añadir 'más' de un producto existente")
    msg1 = "añade 5 guantes mas al carro"
    resp1 = send_message(msg1)
    print_result(msg1, resp1)
    time.sleep(2)
    
    # Verificación del Test 1
    print_step("VERIFICACIÓN 1: El total de guantes debe ser 7")
    resp_verif_1 = send_message("ver carrito")
    print_result("ver carrito", resp_verif_1)
    if resp_verif_1["success"]:
        cart_text = " ".join(resp_verif_1["data"].get("messages", []))
        if "7 x" in cart_text and "Einhell" in cart_text:
            print("✅ Éxito: La cantidad de guantes se actualizó a 7.")
        else:
            print("❌ Fallo: La cantidad no se actualizó correctamente o se añadió un producto nuevo.")

    # --- PRUEBA 2: Intentar eliminar más unidades de las que hay ---
    print_step("TEST 2: Intentar eliminar más unidades de las existentes")
    msg2 = "elimina 10 guantes"
    resp2 = send_message(msg2)
    print_result(msg2, resp2)
    
    # La lógica del bot ahora devuelve 200 OK con un mensaje de error, no un status 400.
    # Adaptamos la prueba para verificar el contenido del mensaje.
    error_message_found = False
    if resp2["success"] and resp2["data"].get("messages"):
        if "No puedes eliminar más unidades" in resp2["data"]["messages"][0]:
            error_message_found = True

    if error_message_found:
        print("✅ Éxito: El bot ha devuelto el mensaje de error esperado.")
    else:
        print("❌ Fallo: El bot no devolvió el mensaje de error esperado.")

    # --- Verificación Final ---
    print_step("VERIFICACIÓN FINAL: El carrito no debe haber cambiado")
    resp_verif_2 = send_message("ver carrito")
    print_result("ver carrito", resp_verif_2)
    if resp_verif_2["success"]:
        cart_text = " ".join(resp_verif_2["data"].get("messages", []))
        if "7 x" in cart_text and "Einhell" in cart_text:
            print("✅ Éxito: El carrito se mantiene con 7 guantes.")
        else:
            print("❌ Fallo: El carrito fue modificado incorrectamente.")


if __name__ == "__main__":
    try:
        health_check = requests.get(f"{BASE_URL}/api/v1/telegram/health", timeout=5)
        if health_check.status_code != 200:
            sys.exit("❌ El backend no está respondiendo. Abortando prueba.")
        print("✅ Backend detectado correctamente.")
    except Exception as e:
        sys.exit(f"❌ No se puede conectar al backend: {e}")
    
    main()
