import requests
import json
import time
import sys

# Configuración del endpoint
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/telegram/test"
CHAT_ID = 98765 # Usar un chat_id consistente y diferente para no mezclar contextos

def send_message(text: str, chat_id: int = CHAT_ID) -> dict:
    """Envía un mensaje de prueba al bot y retorna la respuesta"""
    payload = {
        "message": {
            "message_id": int(time.time()),
            "from": {"id": chat_id, "is_bot": False, "first_name": "Final Test", "username": "final_test_user"},
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
        return False
    
    data = response["data"]
    response_type = data.get("type", "unknown")
    
    if response_type == "text_messages":
        messages = data.get("messages", [])
        if messages:
            preview = messages[0].replace('\n', ' ')[:250]
            print(f"🤖 Bot: {preview}...")
            # Comprobar si es una respuesta de error o de éxito
            if "añadido" in messages[0].lower() or "✅" in messages[0]:
                return True
            if "error" in messages[0].lower() or "no pude" in messages[0].lower():
                return False
    else:
        print(f"🤖 Bot (Respuesta de tipo: {response_type})")
    return True

def main():
    print("🚀 Iniciando prueba final de conversación...")
    
    success_count = 0
    total_steps = 3

    # --- SETUP: Vaciar carrito ---
    print_step(0, "Setup - Limpiando el carrito")
    send_message("/vaciar_carrito")
    time.sleep(1)

    # --- PRUEBA 1: Buscar adhesivos para establecer contexto ---
    print_step(1, "Buscar adhesivos para establecer contexto")
    msg1 = "busco adhesivos"
    if print_result(msg1, send_message(msg1)):
        # Este paso es de setup, no cuenta como éxito/fracaso del test principal
        pass
    time.sleep(2)

    # --- PRUEBA 2: Añadir producto específico por nombre ---
    print_step(2, "Añadir producto específico ('Facom') por nombre")
    msg2 = "si añade 3 adhesivos de montaje Facom al carro"
    if print_result(msg2, send_message(msg2)):
        success_count += 1
    time.sleep(2)

    # --- PRUEBA 3: Añadir otro producto con cantidad al principio ---
    print_step(3, "Añadir otro producto con cantidad al principio ('Hilti')")
    msg3 = "6 de Adhesivo Profesional Hilti"
    if print_result(msg3, send_message(msg3)):
        success_count += 1
    time.sleep(2)

    # --- PRUEBA 4: Verificar el contenido final del carrito ---
    print_step(4, "Verificar el contenido final del carrito")
    msg4 = "ver carrito"
    final_response = send_message(msg4)
    print_result(msg4, final_response)
    # Verificación final
    final_test_passed = False
    if final_response["success"]:
        cart_text = " ".join(final_response["data"].get("messages", []))
        if "Facom" in cart_text and "Hilti" in cart_text and "Total:" in cart_text:
            print("✅ Verificación: Ambos productos están en el carrito.")
            final_test_passed = True
            success_count += 1
        else:
            print("❌ Verificación: Faltan productos en el carrito final.")

    print("\n\n" + "="*50)
    print("📊 RESULTADOS FINALES DE LA PRUEBA")
    print(f"   Pasos exitosos: {success_count}/{total_steps}")
    if success_count == total_steps:
        print("   🎉 ¡Prueba superada! Todos los problemas han sido resueltos.")
    else:
        print("   ⚠️ La prueba ha fallado. Aún quedan problemas por resolver.")


if __name__ == "__main__":
    try:
        health_check = requests.get(f"{BASE_URL}/api/v1/telegram/health", timeout=5)
        if health_check.status_code != 200:
            sys.exit("❌ El backend no está respondiendo. Abortando prueba.")
        print("✅ Backend detectado correctamente.")
    except Exception as e:
        sys.exit(f"❌ No se puede conectar al backend: {e}")
    
    main()
