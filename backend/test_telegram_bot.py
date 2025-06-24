#!/usr/bin/env python3
"""
Script de Test en Lenguaje Natural para Telegram Bot de Macroferro

Este script simula conversaciones reales con el bot usando solo lenguaje natural:
- Búsquedas de productos reales que existen en la base de datos
- Conversaciones naturales sin comandos técnicos
- Gestión de carrito mediante lenguaje cotidiano
- Proceso de compra conversacional

Ejecutar desde la carpeta backend con: python3 test_telegram_bot.py
"""

import asyncio
import json
import sys
import os
from typing import Dict, Any, List
from datetime import datetime

# Configuración del test
TEST_CHAT_ID = 12345678  # ID de chat ficticio para tests
DELAY_BETWEEN_TESTS = 3.0  # Segundos entre cada test (más tiempo para conversaciones naturales)
PRINT_RESPONSES = True  # Si mostrar las respuestas completas

class TelegramBotTester:
    """Clase para testing automatizado del bot de Telegram usando lenguaje natural"""
    
    def __init__(self):
        self.test_number = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.service = None
        self.db = None
        
    async def initialize(self):
        """Inicializa los servicios necesarios"""
        try:
            from app.services.telegram_service import TelegramBotService
            from app.db.database import SessionLocal
            from app.core.config import settings
            
            self.service = TelegramBotService()
            self.db = SessionLocal()
            
            print("✅ Servicios inicializados correctamente")
            print(f"🔧 OpenAI API Key configurada: {'Sí' if settings.OPENAI_API_KEY else 'No'}")
            print(f"🤖 Telegram Token configurado: {'Sí' if settings.telegram_bot_token else 'No'}")
            return True
            
        except Exception as e:
            print(f"❌ Error al inicializar servicios: {e}")
            import traceback
            print(traceback.format_exc())
            return False
        
    def print_header(self, title: str):
        """Imprime un header bonito para cada sección de tests"""
        print("\n" + "="*80)
        print(f"🧪 {title}")
        print("="*80)
        
    def print_test_start(self, test_name: str, message: str):
        """Imprime el inicio de un test"""
        self.test_number += 1
        print(f"\n🔵 Test #{self.test_number}: {test_name}")
        print(f"📤 Usuario dice: '{message}'")
        print("-" * 60)
        
    def print_response(self, response: Dict[str, Any]):
        """Imprime la respuesta del bot de forma formateada"""
        if not PRINT_RESPONSES:
            return
            
        response_type = response.get("type", "unknown")
        messages = response.get("messages", [])
        
        print(f"📥 Tipo de respuesta: {response_type}")
        
        if messages:
            for i, msg in enumerate(messages, 1):
                if len(messages) > 1:
                    print(f"🤖 Bot responde (parte {i}):")
                else:
                    print("🤖 Bot responde:")
                
                # Formatear el mensaje para mejor legibilidad
                formatted_msg = str(msg).replace('*', '').replace('_', '').replace('`', '')
                
                # Limitar longitud para evitar spam en la consola
                if len(formatted_msg) > 400:
                    formatted_msg = formatted_msg[:400] + "..."
                    
                lines = formatted_msg.split('\n')
                for line in lines[:10]:  # Mostrar más líneas para conversaciones naturales
                    if line.strip():
                        print(f"   {line}")
                if len(lines) > 10:
                    print("   ...")
                if i < len(messages):
                    print()
        
    def mark_test_result(self, success: bool, notes: str = ""):
        """Marca el resultado de un test"""
        if success:
            self.passed_tests += 1
            print(f"✅ Conversación exitosa {notes}")
        else:
            self.failed_tests += 1
            print(f"❌ Conversación falló {notes}")
            
    async def simulate_message(self, message_text: str) -> Dict[str, Any]:
        """Simula el envío de un mensaje al bot con el formato correcto de Telegram"""
        # Formato correcto que espera Telegram (update completo)
        update_data = {
            "update_id": self.test_number,
            "message": {
                "message_id": self.test_number,
                "from": {
                    "id": TEST_CHAT_ID,
                    "is_bot": False,
                    "first_name": "Carlos",
                    "username": "carlos_constructor",
                    "language_code": "es"
                },
                "chat": {
                    "id": TEST_CHAT_ID,
                    "first_name": "Carlos",
                    "username": "carlos_constructor",
                    "type": "private"
                },
                "date": int(datetime.now().timestamp()),
                "text": message_text
            }
        }
        
        try:
            response = await self.service.process_message(self.db, update_data)
            return response or {"type": "no_response", "messages": []}
        except Exception as e:
            return {
                "type": "error",
                "messages": [f"Error: {str(e)}"]
            }
    
    async def test_natural_conversation_start(self):
        """Test de inicio de conversación natural"""
        self.print_header("INICIO DE CONVERSACIÓN NATURAL")
        
        # Saludo natural
        self.print_test_start("Saludo inicial", "Hola, ¿cómo están?")
        response = await self.simulate_message("Hola, ¿cómo están?")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe responder al saludo naturalmente")
        
        await asyncio.sleep(2)
        
        # Consulta general sobre servicios
        self.print_test_start("Consulta de servicios", "¿Me pueden ayudar con productos para construcción?")
        response = await self.simulate_message("¿Me pueden ayudar con productos para construcción?")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe ofrecer ayuda con productos")
        
    async def test_real_product_searches(self):
        """Test de búsquedas de productos reales"""
        self.print_header("BÚSQUEDA DE PRODUCTOS REALES")
        
        # Búsqueda de martillos (sabemos que existen por el test anterior)
        self.print_test_start("Búsqueda de martillos", "Necesito martillos para una obra")
        response = await self.simulate_message("Necesito martillos para una obra")
        self.print_response(response)
        success = response.get("type") != "error" and "martillo" in str(response).lower()
        self.mark_test_result(success, "- Debe encontrar martillos reales")
        
        await asyncio.sleep(3)
        
        # Búsqueda de adhesivos (sabemos que existen)
        self.print_test_start("Búsqueda de pegamentos", "Busco pegamento fuerte para metal")
        response = await self.simulate_message("Busco pegamento fuerte para metal")
        self.print_response(response)
        success = response.get("type") != "error" and ("adhesivo" in str(response).lower() or "pegamento" in str(response).lower())
        self.mark_test_result(success, "- Debe encontrar adhesivos reales")
        
        await asyncio.sleep(3)
        
        # Búsqueda de guantes (sabemos que existen)
        self.print_test_start("Búsqueda de protección", "¿Tienen guantes de trabajo?")
        response = await self.simulate_message("¿Tienen guantes de trabajo?")
        self.print_response(response)
        success = response.get("type") != "error" and "guantes" in str(response).lower()
        self.mark_test_result(success, "- Debe encontrar guantes reales")
        
    async def test_natural_cart_interaction(self):
        """Test de interacción natural con el carrito"""
        self.print_header("GESTIÓN NATURAL DEL CARRITO")
        
        # Primero buscar productos para tener contexto
        self.print_test_start("Consulta inicial", "Quiero ver qué martillos tienen disponibles")
        response = await self.simulate_message("Quiero ver qué martillos tienen disponibles")
        self.print_response(response)
        
        await asyncio.sleep(4)
        
        # Agregar producto usando lenguaje natural
        self.print_test_start("Agregar al carrito", "Me interesa el martillo Stanley, ponme 2 en mi pedido")
        response = await self.simulate_message("Me interesa el martillo Stanley, ponme 2 en mi pedido")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe agregar productos naturalmente")
        
        await asyncio.sleep(3)
        
        # Ver qué hay en el carrito
        self.print_test_start("Consultar pedido", "¿Qué tengo en mi pedido hasta ahora?")
        response = await self.simulate_message("¿Qué tengo en mi pedido hasta ahora?")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe mostrar el estado del pedido")
        
    async def test_product_by_number_reference(self):
        """Test de referencias por número de manera natural"""
        self.print_header("REFERENCIAS POR NÚMERO NATURALES")
        
        # Buscar adhesivos para tener una lista
        self.print_test_start("Ver opciones", "Muéstrame opciones de pegamento industrial")
        response = await self.simulate_message("Muéstrame opciones de pegamento industrial")
        self.print_response(response)
        
        await asyncio.sleep(4)
        
        # Seleccionar por número de manera natural
        self.print_test_start("Selección por número", "Me gusta la opción número 2, ponme 3 unidades")
        response = await self.simulate_message("Me gusta la opción número 2, ponme 3 unidades")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe entender referencias por número")
        
        await asyncio.sleep(3)
        
        # Otra referencia por número
        self.print_test_start("Otra selección", "También quiero del número 1, pero solo 1 unidad")
        response = await self.simulate_message("También quiero del número 1, pero solo 1 unidad")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe manejar múltiples referencias")
        
    async def test_natural_checkout_flow(self):
        """Test del proceso de compra natural"""
        self.print_header("PROCESO DE COMPRA NATURAL")
        
        # Consultar estado del pedido
        self.print_test_start("Revisar pedido", "¿Cuánto me sale todo lo que tengo?")
        response = await self.simulate_message("¿Cuánto me sale todo lo que tengo?")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe mostrar el total del pedido")
        
        await asyncio.sleep(3)
        
        # Iniciar proceso de compra naturalmente
        self.print_test_start("Solicitar compra", "Está bien, quiero comprar todo esto")
        response = await self.simulate_message("Está bien, quiero comprar todo esto")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe iniciar proceso de compra")
        
        await asyncio.sleep(3)
        
        # Consultar sobre envío
        self.print_test_start("Pregunta sobre envío", "¿Hacen envíos a domicilio?")
        response = await self.simulate_message("¿Hacen envíos a domicilio?")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe responder sobre envíos")
        
    async def test_customer_service_conversation(self):
        """Test de conversación de atención al cliente"""
        self.print_header("ATENCIÓN AL CLIENTE NATURAL")
        
        # Consulta sobre marcas
        self.print_test_start("Consulta de marcas", "¿Qué marcas de herramientas eléctricas manejan?")
        response = await self.simulate_message("¿Qué marcas de herramientas eléctricas manejan?")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe informar sobre marcas")
        
        await asyncio.sleep(3)
        
        # Consulta técnica
        self.print_test_start("Consulta técnica", "¿El martillo Bosch sirve para concreto?")
        response = await self.simulate_message("¿El martillo Bosch sirve para concreto?")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe dar información técnica")
        
        await asyncio.sleep(3)
        
        # Comparación de productos
        self.print_test_start("Comparación", "¿Cuál es la diferencia entre el adhesivo Hilti y el Makita?")
        response = await self.simulate_message("¿Cuál es la diferencia entre el adhesivo Hilti y el Makita?")
        self.print_response(response)
        success = response.get("type") != "error" and len(response.get("messages", [])) > 0
        self.mark_test_result(success, "- Debe comparar productos")
        
    async def test_realistic_conversation_flow(self):
        """Test de una conversación completa y realista"""
        self.print_header("CONVERSACIÓN COMPLETA REALISTA")
        
        # Escenario: Constructor buscando materiales para una obra
        conversation_steps = [
            ("Presentación", "Hola, soy constructor y necesito materiales para una obra pequeña"),
            ("Especificación", "Necesito herramientas básicas y algunos adhesivos fuertes"),
            ("Consulta específica", "¿Tienen martillos que sirvan para demolición menor?"),
            ("Interés en compra", "Me convence, ¿cuánto cuesta el Hilti?"),
            ("Decisión", "Está bien, lo voy a llevar junto con pegamento"),
            ("Finalización", "Perfecto, ¿cómo hago para que me lo envíen?")
        ]
        
        for step_name, message in conversation_steps:
            self.print_test_start(f"Conversación real: {step_name}", message)
            response = await self.simulate_message(message)
            self.print_response(response)
            success = response.get("type") != "error" and len(response.get("messages", [])) > 0
            self.mark_test_result(success, f"- {step_name} debe tener respuesta natural")
            await asyncio.sleep(3)
            
    def print_summary(self):
        """Imprime el resumen final de todos los tests"""
        total_tests = self.passed_tests + self.failed_tests
        success_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "="*80)
        print("📊 RESUMEN DE CONVERSACIONES NATURALES")
        print("="*80)
        print(f"✅ Conversaciones exitosas: {self.passed_tests}")
        print(f"❌ Conversaciones fallidas: {self.failed_tests}")
        print(f"📈 Total de conversaciones: {total_tests}")
        print(f"🎯 Tasa de éxito: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 ¡EXCELENTE! El bot mantiene conversaciones naturales muy bien.")
        elif success_rate >= 60:
            print("👍 BIEN! El bot conversa bien, pero puede mejorar en algunos aspectos.")
        else:
            print("⚠️  ATENCIÓN! El bot necesita mejorar en conversaciones naturales.")
            
        print("="*80)
        
    async def run_all_tests(self):
        """Ejecuta todos los tests de conversación natural"""
        print("🚀 INICIANDO TESTS DE CONVERSACIÓN NATURAL DEL TELEGRAM BOT")
        print(f"👤 Usuario simulado: Carlos (Constructor)")
        print(f"⏱️  Tiempo entre mensajes: {DELAY_BETWEEN_TESTS}s")
        print(f"💬 Usando solo lenguaje natural (sin comandos)")
        
        # Inicializar servicios
        if not await self.initialize():
            print("❌ No se pudieron inicializar los servicios")
            return
            
        try:
            # Ejecutar todos los grupos de tests naturales
            await self.test_natural_conversation_start()
            await asyncio.sleep(DELAY_BETWEEN_TESTS)
            
            await self.test_real_product_searches()
            await asyncio.sleep(DELAY_BETWEEN_TESTS)
            
            await self.test_natural_cart_interaction()
            await asyncio.sleep(DELAY_BETWEEN_TESTS)
            
            await self.test_product_by_number_reference()
            await asyncio.sleep(DELAY_BETWEEN_TESTS)
            
            await self.test_natural_checkout_flow()
            await asyncio.sleep(DELAY_BETWEEN_TESTS)
            
            await self.test_customer_service_conversation()
            await asyncio.sleep(DELAY_BETWEEN_TESTS)
            
            await self.test_realistic_conversation_flow()
            
        except Exception as e:
            print(f"\n❌ ERROR CRÍTICO durante las conversaciones: {e}")
            import traceback
            print(traceback.format_exc())
            self.failed_tests += 1
            
        finally:
            self.print_summary()
            if self.db:
                self.db.close()

async def main():
    """Función principal del script de test"""
    print("🧪 SCRIPT DE TEST DE CONVERSACIONES NATURALES")
    print("🗣️  Simula conversaciones reales con el bot de Macroferro")
    print("🔧 Usa productos que realmente existen en la base de datos\n")
    
    # Ejecutar tests
    tester = TelegramBotTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    # Configurar logging para tests
    import logging
    logging.basicConfig(level=logging.WARNING)  # Reducir ruido en tests
    
    # Ejecutar tests
    asyncio.run(main()) 