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
    # Test 1: Búsqueda específica de producto
    print("Test 1: Buscando Tornillos UNC específicos...")
    success, response = send_message("Busco Tornillos UNC para Plástico Facom")
    if success:
        print(f"Response type: {response.get('response_type')}")
    else:
        print(f"Error: {response}")
    
    time.sleep(2)
    
    # Test 2: Agregar producto específico con referencia contextual
    print("\nTest 2: Agregando esos tornillos UNC al carrito...")
    success, response = send_message("Agrega esos tornillos UNC al carrito")
    if success:
        print(f"Response: {response}")
    else:
        print(f"Error: {response}")
    
    time.sleep(2)
    
    # Test 3: Búsqueda de herramientas (con logging detallado)
    print("\nTest 3: Buscando herramientas para construcción...")
    success, response = send_message("Busco herramientas para construcción")
    if success:
        print(f"Response type: {response.get('response_type')}")
        # Mostrar parte del contenido para ver qué productos incluye
        if 'text_messages' in response:
            print(f"Total messages: {len(response['text_messages'])}")
            for i, msg in enumerate(response['text_messages'][:4]):  # Primeros 4 mensajes
                print(f"Message {i+1}: {msg[:300]}...")  # Primeros 300 caracteres
                # Buscar menciones de Hilti en el contenido
                if 'hilti' in msg.lower():
                    print(f"  *** HILTI ENCONTRADO en mensaje {i+1} ***")
    else:
        print(f"Error: {response}")
    
    time.sleep(2)
    
    # Test 4: Búsqueda específica de Hilti primero
    print("\nTest 4: Buscando específicamente productos Hilti...")
    success, response = send_message("Busco taladros Hilti")
    if success:
        print(f"Response type: {response.get('response_type')}")
        if 'text_messages' in response:
            print(f"Total messages: {len(response['text_messages'])}")
            for i, msg in enumerate(response['text_messages'][:4]):
                print(f"Message {i+1}: {msg[:300]}...")
    else:
        print(f"Error: {response}")
        
    time.sleep(2)
    
    # Test 5: Agregar taladro Hilti después de búsqueda específica
    print("\nTest 5: Agregando el taladro Hilti al carrito...")
    success, response = send_message("Agrega el taladro Hilti al carrito")
    if success:
        print(f"Response: {response}")
    else:
        print(f"Error: {response}")

if __name__ == "__main__":
    main() 