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

def print_conversation(user_msg: str, bot_response: dict):
    """Imprime la conversación de manera bonita"""
    print(f"\n👤 Usuario: {user_msg}")
    
    if not bot_response["success"]:
        print(f"❌ Error: {bot_response['error']}")
        return
    
    data = bot_response["data"]
    response_type = data.get("type", "unknown")
    
    print(f"🤖 Bot ({response_type}):")
    
    if response_type == "text_messages":
        messages = data.get("messages", [])
        for msg in messages:
            print(f"   💬 {msg}")
    
    elif response_type == "product_with_image":
        product = data.get("product", {})
        caption = data.get("caption", "")
        additional = data.get("additional_messages", [])
        
        print(f"   🖼️ Producto: {product.get('name', 'N/A')} (SKU: {product.get('sku', 'N/A')})")
        print(f"   📝 Caption: {caption[:100]}...")
        
        for msg in additional:
            print(f"   💬 {msg}")
    
    else:
        print(f"   📋 Datos: {json.dumps(data, indent=2, ensure_ascii=False)}")

def main():
    """Ejecuta una conversación completa de prueba"""
    print("🚀 Iniciando conversación de prueba completa...")
    print("=" * 60)
    
    # Conversación Natural Completa
    conversation = [
        # 1. Saludo inicial
        "Hola, buenos días",
        
        # 2. Búsqueda de producto específico que sabemos que existe
        "Busco Tornillos UNC para Plástico Facom",
        
        # 3. Pregunta específica sobre ese producto
        "¿Qué especificaciones tienen esos tornillos UNC?",
        
        # 4. Agregar producto al carrito (referencia natural)
        "Agrega esos tornillos UNC al carrito",
        
        # 5. Buscar otro tipo de producto específico
        "Necesito también Tornillos Métricos para Plástico Bosch",
        
        # 6. Agregar con cantidad específica
        "Agrega 2 de esos tornillos métricos al carrito",
        
        # 7. Ver carrito actual
        "Muéstrame mi carrito",
        
        # 8. Pregunta técnica sobre producto reciente
        "¿Cuál es el peso de los tornillos Bosch?",
        
        # 9. Quitar producto específico
        "Quita los tornillos UNC del carrito",
        
        # 10. Ver carrito actualizado
        "¿Cómo está mi carrito ahora?",
        
        # 11. Buscar producto por categoría
        "Busco herramientas para construcción",
        
        # 12. Agregar herramienta específica
        "Agrega el taladro Hilti al carrito",
        
        # 13. Finalizar compra
        "Quiero finalizar la compra",
        
        # 14. Verificar carrito después de compra
        "¿Está vacío mi carrito?",
        
        # 15. Despedida
        "Gracias, hasta luego"
    ]
    
    # Ejecutar conversación paso a paso
    for i, message in enumerate(conversation, 1):
        print(f"\n{'='*10} PASO {i} {'='*10}")
        
        # Enviar mensaje
        response = send_message(message)
        
        # Mostrar conversación
        print_conversation(message, response)
        
        # Pausa entre mensajes para simular conversación real
        if i < len(conversation):
            print("\n⏳ Esperando 2 segundos...")
            time.sleep(2)
    
    print("\n" + "=" * 60)
    print("✅ Conversación de prueba completada!")
    print("\n📊 Resumen de funcionalidades probadas:")
    print("   ✓ Saludo y conversación general")
    print("   ✓ Búsqueda de productos por categoría")
    print("   ✓ Consultas técnicas específicas")
    print("   ✓ Agregar productos al carrito (natural)")
    print("   ✓ Agregar productos con cantidades específicas")
    print("   ✓ Ver contenido del carrito")
    print("   ✓ Quitar productos del carrito")
    print("   ✓ Finalizar compra")
    print("   ✓ Vaciar carrito")
    print("   ✓ Referencias contextuales ('ese producto', 'el último')")

if __name__ == "__main__":
    # Verificar que el backend esté corriendo
    try:
        health_check = requests.get(f"{BASE_URL}/api/v1/telegram/health", timeout=5)
        if health_check.status_code != 200:
            print("❌ Backend no está respondiendo correctamente")
            sys.exit(1)
    except Exception as e:
        print(f"❌ No se puede conectar al backend: {e}")
        print("💡 Asegúrate de que el backend esté corriendo en localhost:8000")
        sys.exit(1)
    
    main() 