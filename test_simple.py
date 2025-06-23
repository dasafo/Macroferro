import requests
import json
import time

def send_message(message_text):
    """Función auxiliar para enviar mensajes al bot"""
    url = "http://localhost:8000/api/v1/telegram/test"
    
    payload = {
        "message": {
            "message_id": 1,
            "from": {
                "id": 12345,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 12345,
                "type": "private"
            },
            "date": int(time.time()),
            "text": message_text
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}", "response": response.text}
    except Exception as e:
        return False, {"error": str(e)}

def main():
    # Test: Búsqueda de herramientas
    print("🔍 Buscando herramientas para construcción...")
    success, response = send_message("Busco herramientas para construcción")
    
    if success:
        print(f"\n📋 Respuesta completa:")
        print(json.dumps(response, indent=2, ensure_ascii=False))
        
        # Analizar contenido específico
        if 'messages' in response:
            print(f"\n📝 Análisis de contenido:")
            for i, msg in enumerate(response['messages']):
                print(f"\nMensaje {i+1}:")
                print(f"Longitud: {len(msg)} caracteres")
                print(f"Contenido: {msg[:400]}...")  # Primeros 400 caracteres
                
                # Buscar menciones de marcas específicas
                brands_to_check = ['hilti', 'dewalt', 'makita', 'bosch', 'milwaukee']
                for brand in brands_to_check:
                    if brand.lower() in msg.lower():
                        print(f"  ✅ Marca encontrada: {brand.upper()}")
    else:
        print(f"❌ Error: {response}")

if __name__ == "__main__":
    main() 