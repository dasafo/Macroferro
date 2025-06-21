#!/usr/bin/env python3
"""
🧪 TEST DE FUNCIONALIDAD TÉCNICA - BOT MACROFERRO

Este script simula diferentes tipos de consultas técnicas que un usuario
podría hacer al bot de Macroferro para validar las nuevas capacidades.
"""

import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Añadir el directorio raíz al path para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.telegram_service import TelegramBotService
from app.db.database import SessionLocal
from app.core.config import settings

class TechnicalQuestionsTest:
    def __init__(self):
        self.telegram_service = TelegramBotService()
        # Usar chat_id de prueba
        self.test_chat_id = 12345

    def print_header(self, title: str, emoji: str = "🔍"):
        """Imprime un encabezado formateado para las secciones de prueba"""
        print(f"\n{emoji} {title.upper()}")
        print("=" * 60)

    def print_question(self, question: str):
        """Imprime una pregunta de prueba formateada"""
        print(f"❓ Pregunta: '{question}'")
        print("-" * 60)

    async def test_question(self, db: Session, question: str):
        """Prueba una pregunta específica y muestra la respuesta"""
        try:
            response = await self.telegram_service.process_message(
                db=db, 
                message_text=question, 
                chat_id=self.test_chat_id
            )
            print(f"🤖 Respuesta del bot:")
            print(response)
            print("\n" + "=" * 80 + "\n")
            
        except Exception as e:
            print(f"❌ Error procesando pregunta: {e}")
            print("\n" + "=" * 80 + "\n")

    async def run_basic_tests(self):
        """Ejecuta pruebas básicas de funcionalidad"""
        # Usar SessionLocal para obtener una sesión síncrona
        db = SessionLocal()
        
        try:
            print("=" * 80)
            print("🤖 PRUEBA BÁSICA DE FUNCIONALIDAD - BOT MACROFERRO")
            print("=" * 80)
            print("📋 Probando capacidades mejoradas del bot:")
            print("   • Respuestas generales")
            print("   • Búsqueda básica de productos")
            print("   • Preguntas técnicas simples")
            print("=" * 80)

            # Pruebas básicas
            basic_tests = [
                "Hola, ¿cómo están?",
                "¿Qué productos manejan?",
                "Busco tubos de PVC",
                "¿Tienen válvulas de bola?",
                "¿Qué diámetro tiene el tubo de PVC?"
            ]

            for question in basic_tests:
                self.print_question(question)
                await self.test_question(db, question)
                
                # Pausa pequeña entre preguntas para evitar sobrecarga
                await asyncio.sleep(1)

        finally:
            db.close()

    async def run_technical_tests(self):
        """Ejecuta pruebas técnicas específicas"""
        db = SessionLocal()
        
        try:
            self.print_header("PREGUNTAS TÉCNICAS ESPECÍFICAS", "🔧")
            
            technical_tests = [
                "¿Cuál es la presión máxima del tubo de PVC de 110mm?",
                "¿De qué material está hecha la válvula de bola de 2 pulgadas?",
                "¿Qué certificaciones tiene el taladro percutor de 800W?",
                "¿Es compatible con agua potable el tubo PVC?"
            ]

            for question in technical_tests:
                self.print_question(question)
                await self.test_question(db, question)
                await asyncio.sleep(1)
                
        finally:
            db.close()

    async def run_all_tests(self):
        """Ejecuta todas las pruebas"""
        await self.run_basic_tests()
        await self.run_technical_tests()
        
        print("✅ PRUEBAS COMPLETADAS")
        print("📊 Revisa los resultados para validar:")
        print("   • Clasificación correcta de intenciones")
        print("   • Búsqueda relevante de productos")
        print("   • Análisis preciso de especificaciones")
        print("   • Calidad de respuestas generadas")

async def main():
    """Función principal para ejecutar las pruebas"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test del bot de Macroferro')
    parser.add_argument('--basic', action='store_true', help='Ejecutar solo pruebas básicas')
    parser.add_argument('--technical', action='store_true', help='Ejecutar solo pruebas técnicas')
    parser.add_argument('--interactive', action='store_true', help='Modo interactivo')
    
    args = parser.parse_args()
    
    tester = TechnicalQuestionsTest()
    
    try:
        if args.basic:
            await tester.run_basic_tests()
        elif args.technical:
            await tester.run_technical_tests()
        elif args.interactive:
            # Modo interactivo simple
            db = SessionLocal()
            try:
                print("🤖 Bot de Macroferro - Modo Interactivo")
                print("Escribe 'exit' para salir\n")
                
                while True:
                    question = input("❓ Tu pregunta: ").strip()
                    if question.lower() in ['exit', 'salir', 'quit']:
                        print("👋 ¡Hasta luego!")
                        break
                    
                    if question:
                        print("-" * 40)
                        await tester.test_question(db, question)
            finally:
                db.close()
        else:
            await tester.run_all_tests()
            
    except KeyboardInterrupt:
        print("\n👋 Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 