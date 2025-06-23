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

def test_step(step_number, description, message, expected_success=True):
    """Helper para ejecutar un paso de test"""
    print(f"\n🧪 Test {step_number}: {description}")
    print(f"   📝 Mensaje: '{message}'")
    
    success, response = send_message(message)
    
    if success:
        response_type = response.get('type', 'unknown')
        print(f"   ✅ Respuesta exitosa: {response_type}")
        
        if response_type == 'text_messages' and 'messages' in response:
            # Mostrar solo el primer mensaje para un resumen rápido
            first_msg = response['messages'][0] if response['messages'] else ""
            preview = first_msg[:150] + "..." if len(first_msg) > 150 else first_msg
            print(f"   📄 Contenido: {preview}")
            
            # Detectar si es un error o éxito
            if any(word in first_msg.lower() for word in ['error', 'no pude', 'no encontré', '❌']):
                print(f"   ⚠️  El bot reportó un problema")
                return False
            elif any(word in first_msg.lower() for word in ['añadido', 'agregado', 'carrito', '✅']):
                print(f"   🎯 Producto agregado exitosamente!")
                return True
        elif response_type == 'product_with_image':
            print(f"   🖼️  Producto mostrado con imagen")
            return True
        
        return expected_success
    else:
        print(f"   ❌ Error: {response}")
        return False

def main():
    print("🚀 Prueba Integral del Bot de Telegram - Referencias Contextuales")
    print("=" * 70)
    
    success_count = 0
    total_tests = 6
    
    # Test 1: Búsqueda de producto específico
    if test_step(1, "Búsqueda de tornillos específicos", 
                 "Busco Tornillos UNC para Plástico Facom"):
        success_count += 1
    
    time.sleep(2)
    
    # Test 2: Referencia contextual directa
    if test_step(2, "Agregar con referencia contextual directa", 
                 "Agrega esos tornillos UNC al carrito"):
        success_count += 1
    
    time.sleep(2)
    
    # Test 3: Búsqueda amplia de herramientas (carga contexto)
    if test_step(3, "Búsqueda amplia de herramientas", 
                 "Busco herramientas para construcción"):
        success_count += 1
    
    time.sleep(2)
    
    # Test 4: Referencia ambigua - debería elegir el más caro/profesional
    if test_step(4, "Referencia ambigua - elegir el modelo profesional", 
                 "Agrega el taladro Hilti al carrito"):
        success_count += 1
    
    time.sleep(2)
    
    # Test 5: Referencia específica con término técnico
    if test_step(5, "Referencia específica con término 'percutor'", 
                 "Agrega el taladro percutor al carrito"):
        success_count += 1
    
    time.sleep(2)
    
    # Test 6: Ver carrito final
    if test_step(6, "Verificar contenido del carrito", 
                 "Muéstrame mi carrito"):
        success_count += 1
    
    # Resumen final
    print(f"\n" + "=" * 70)
    print(f"📊 RESULTADOS FINALES")
    print(f"   ✅ Exitosos: {success_count}/{total_tests}")
    print(f"   ❌ Fallidos: {total_tests - success_count}/{total_tests}")
    print(f"   📈 Tasa de éxito: {(success_count/total_tests)*100:.1f}%")
    
    if success_count == total_tests:
        print(f"   🎉 ¡TODOS LOS TESTS PASARON! El bot maneja correctamente las referencias contextuales.")
    elif success_count >= total_tests * 0.8:
        print(f"   👍 Muy bien! La mayoría de funcionalidades trabajan correctamente.")
    else:
        print(f"   ⚠️  Necesita mejoras en el manejo de referencias contextuales.")

if __name__ == "__main__":
    main() 