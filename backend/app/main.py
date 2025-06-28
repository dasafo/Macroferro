# backend/app/main.py
"""
Punto de entrada principal de la aplicación FastAPI.

Este módulo configura y inicializa la aplicación FastAPI completa,
incluyendo la configuración de rutas, middleware, documentación automática,
y eventos del ciclo de vida de la aplicación.

Características principales:
- Configuración centralizada de la aplicación
- Registro de routers de la API con prefijos
- Documentación automática (OpenAPI/Swagger)
- Eventos del ciclo de vida de la aplicación (startup/shutdown)
"""

from fastapi import FastAPI
from app.core.config import settings  # Configuración centralizada de la aplicación
from app.api.v1.api_router import api_router_v1  # Router principal de la API v1

# ========================================
# CONFIGURACIÓN DE LA APLICACIÓN FASTAPI
# ========================================

# Crear instancia principal de FastAPI con configuración desde settings
# Esta configuración permite que la app sea altamente configurable via variables de entorno
app = FastAPI(
    title=settings.PROJECT_NAME,  # Nombre del proyecto desde configuración
    openapi_url=f"{settings.API_V1_STR}/openapi.json",  # URL del schema OpenAPI personalizada
    version=settings.PROJECT_VERSION,  # Versión del proyecto desde configuración
    description="API para el sistema de gestión de Macroferro"  # Descripción para documentación
)

# ========================================
# REGISTRO DE ROUTERS DE LA API
# ========================================

# Incluir el router principal de la API v1 con prefijo configurado
# El prefijo se obtiene de settings (típicamente "/api/v1")
# Esto permite tener múltiples versiones de la API sin conflictos
app.include_router(api_router_v1, prefix=settings.API_V1_STR)


# ========================================
# ENDPOINTS RAÍZ Y VERIFICACIÓN DE ESTADO
# ========================================

# Endpoint raíz simple para verificar que la API está funcionando
# Este endpoint es útil para health checks y verificación básica del servicio
@app.get("/", tags=["Root"])
async def read_root():
    """
    Endpoint raíz para verificación básica del estado de la API.
    
    Proporciona información básica sobre la aplicación y confirma
    que el servicio está operativo y respondiendo a peticiones.
    
    **Propósito:**
    - Health check básico para monitoreo
    - Verificación de conectividad con la API
    - Información de bienvenida con nombre y versión
    - Endpoint de referencia para pruebas de conectividad
    
    **Casos de uso:**
    - Verificación de despliegue exitoso
    - Monitoreo de disponibilidad del servicio
    - Pruebas básicas de conectividad
    - Validación de configuración correcta
    
    **Respuesta:**
    Objeto JSON con mensaje de bienvenida que incluye
    el nombre del proyecto y la versión actual.
    
    Returns:
        dict: Mensaje de bienvenida con información del proyecto
        
    Example:
        GET /
        Response: {"message": "Bienvenido a Macroferro API v1.0.0"}
    """
    return {"message": f"Bienvenido a {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}"}

# ========================================
# EVENTOS DEL CICLO DE VIDA DE LA APLICACIÓN
# ========================================

# Los event handlers permiten ejecutar código en momentos específicos
# del ciclo de vida de la aplicación (inicio y cierre)

# EVENTO DE STARTUP - Ejecutado al iniciar la aplicación
# Aquí se pueden inicializar recursos, conexiones, servicios externos, etc.
@app.on_event("startup")
async def startup_event():
    """
    Evento ejecutado al iniciar la aplicación.
    
    Inicializa automáticamente el webhook de Telegram con la URL configurada
    en las variables de entorno para evitar configuración manual.
    
    Tareas de inicialización:
    - Configuración automática del webhook de Telegram
    - Verificación de conexión con la API de Telegram
    - Validación de la URL del webhook configurada
    """
    try:
        # Configurar automáticamente el webhook de Telegram
        from app.services.telegram_service import TelegramBotService
        
        # Solo configurar webhook si está definida la URL en las variables de entorno
        if settings.telegram_webhook_url:
            telegram_service = TelegramBotService()
            webhook_result = await telegram_service.set_webhook(
                webhook_url=settings.telegram_webhook_url,
                secret_token=settings.telegram_webhook_secret
            )
            
            if webhook_result.get("ok", False):
                print(f"✅ Webhook de Telegram configurado: {settings.telegram_webhook_url}")
            else:
                print(f"⚠️  Error al configurar webhook: {webhook_result}")
        else:
            print("ℹ️  TELEGRAM_WEBHOOK_URL no configurada, webhook no establecido")
            
    except Exception as e:
        print(f"❌ Error durante la inicialización del webhook: {e}")
        # No detener la aplicación si falla la configuración del webhook
