# backend/app/main.py

"""
Punto de entrada principal de la aplicación FastAPI.

Este módulo configura y inicializa la aplicación FastAPI completa,
incluyendo la configuración de rutas, middleware, documentación automática,
y eventos del ciclo de vida de la aplicación.

Responsabilidades del módulo principal:
- Creación e inicialización de la instancia FastAPI
- Configuración de metadatos de la aplicación (título, versión, descripción)
- Registro de routers de la API con sus prefijos correspondientes
- Configuración de la documentación automática (OpenAPI/Swagger)
- Definición de endpoints raíz para verificación de estado
- Preparación para eventos de ciclo de vida (startup/shutdown)

Arquitectura de la aplicación:
- Application Factory: Configuración centralizada de la app
- Modular Routing: Separación de endpoints por versión y funcionalidad
- Configuration-Driven: Usa settings del módulo core.config
- API Versioning: Preparado para múltiples versiones de la API
- Auto-Documentation: Swagger UI y ReDoc automáticos

Patrones implementados:
- Factory Pattern: Creación configurada de la instancia FastAPI
- Router Registration: Inclusión modular de routers por dominio
- Environment Configuration: Configuración via variables de entorno
- Health Check: Endpoint simple para verificación de estado
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

# EXTENSIÓN FUTURA: Registro de routers adicionales
# app.include_router(api_router_v2, prefix="/api/v2")  # Para versión 2 de la API
# app.include_router(admin_router, prefix="/admin")     # Para endpoints administrativos
# app.include_router(auth_router, prefix="/auth")       # Para autenticación y autorización

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

# EVENTO DE SHUTDOWN - Ejecutado al cerrar la aplicación
# Aquí se pueden limpiar recursos, cerrar conexiones, guardar estados, etc.
# @app.on_event("shutdown")
# async def shutdown_event():
#     """
#     Evento ejecutado al cerrar la aplicación.
#     
#     Aquí se pueden realizar tareas de limpieza como:
#     - Cerrar conexiones a bases de datos
#     - Finalizar pools de conexiones
#     - Guardar estados temporales
#     - Limpiar archivos temporales
#     - Cerrar conexiones a servicios externos
#     - Finalizar procesos en background
#     
#     Ejemplos de limpieza:
#     - Cerrar conexiones Redis
#     - Finalizar workers de background tasks
#     - Guardar métricas finales
#     - Limpiar cache temporal
#     """
#     # Ejemplo: Cerrar conexiones Redis
#     # from app.core.cache import close_redis_connections
#     # await close_redis_connections()
#     
#     # Ejemplo: Finalizar background tasks
#     # from app.core.background import stop_background_workers
#     # await stop_background_workers()
#     
#     # Ejemplo: Guardar métricas finales
#     # from app.core.metrics import save_final_metrics
#     # await save_final_metrics()
#     
#     pass

# ========================================
# CONFIGURACIÓN ADICIONAL FUTURA
# ========================================

# MIDDLEWARE: Aquí se pueden agregar middlewares personalizados
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.ALLOWED_HOSTS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# EXCEPTION HANDLERS: Manejo global de excepciones
# @app.exception_handler(ValidationError)
# async def validation_exception_handler(request: Request, exc: ValidationError):
#     return JSONResponse(
#         status_code=422,
#         content={"detail": exc.errors(), "body": exc.body},
#     )

# STATIC FILES: Servir archivos estáticos si es necesario
# from fastapi.staticfiles import StaticFiles
# app.mount("/static", StaticFiles(directory="static"), name="static")

# TEMPLATES: Configuración de templates si se usan
# from fastapi.templating import Jinja2Templates
# templates = Jinja2Templates(directory="templates")