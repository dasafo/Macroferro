"""
Esquemas Pydantic para el modelo Telegram Bot.

Este módulo define los esquemas para manejar las interacciones con el bot de Telegram, incluyendo:
- Validación de datos de entrada desde webhooks de Telegram
- Manejo de estructuras de datos complejas (usuarios, chats, mensajes)
- Validación y parseado de actualizaciones de Telegram
- Estructuras de respuesta para envío de mensajes

Los esquemas representan la estructura exacta de los objetos JSON que envía Telegram
en sus webhooks, permitiendo validación automática y type safety en el procesamiento
de mensajes del bot.

Documentación oficial de Telegram Bot API:
https://core.telegram.org/bots/api#available-types
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

# ========================================
# ESQUEMAS DE ENTIDADES DE TELEGRAM
# ========================================

class TelegramUser(BaseModel):
    """
    Esquema para representar un usuario de Telegram.
    
    Corresponde al tipo 'User' de la API de Telegram Bot.
    Se utiliza para identificar quién envía mensajes al bot y
    proporcionar información de contexto para personalizar respuestas.
    
    Campos obligatorios según la API de Telegram:
    - id: Identificador único del usuario
    - is_bot: Indica si es un bot (siempre False para usuarios reales)
    - first_name: Nombre del usuario (siempre presente)
    
    Campos opcionales comunes:
    - last_name: Apellido del usuario
    - username: @username del usuario (puede no estar configurado)
    - language_code: Código de idioma (ej: 'es', 'en')
    
    Ejemplo de uso:
    {
        "id": 123456789,
        "is_bot": false,
        "first_name": "Juan",
        "last_name": "Pérez",
        "username": "juanperez",
        "language_code": "es"
    }
    """
    id: int = Field(..., description="Identificador único del usuario de Telegram")
    is_bot: bool = Field(..., description="True si este usuario es un bot")
    first_name: str = Field(..., description="Nombre del usuario")
    last_name: Optional[str] = Field(None, description="Apellido del usuario (opcional)")
    username: Optional[str] = Field(None, description="Username del usuario sin @ (opcional)")
    language_code: Optional[str] = Field(None, description="Código de idioma IETF del usuario (opcional)")


class TelegramChat(BaseModel):
    """
    Esquema para representar un chat de Telegram.
    
    Corresponde al tipo 'Chat' de la API de Telegram Bot.
    Puede representar diferentes tipos de chats:
    - "private": Chat individual con un usuario
    - "group": Grupo normal
    - "supergroup": Supergrupo
    - "channel": Canal
    
    Para bots de empresa (como Macroferro), típicamente manejamos chats privados
    donde los clientes consultan productos directamente al bot.
    
    Campos importantes:
    - id: Identificador único del chat (puede ser negativo para grupos)
    - type: Tipo de chat ("private", "group", "supergroup", "channel")
    
    Para chats privados, los campos adicionales coinciden con los del usuario:
    - first_name, last_name, username
    
    Para grupos y canales:
    - title: Nombre del grupo/canal
    
    Ejemplo de chat privado:
    {
        "id": 123456789,
        "type": "private",
        "first_name": "Juan",
        "last_name": "Pérez",
        "username": "juanperez"
    }
    """
    id: int = Field(..., description="Identificador único del chat")
    type: str = Field(..., description="Tipo de chat: private, group, supergroup o channel")
    title: Optional[str] = Field(None, description="Título del chat (para grupos y canales)")
    username: Optional[str] = Field(None, description="Username del chat (opcional)")
    first_name: Optional[str] = Field(None, description="Nombre (solo para chats privados)")
    last_name: Optional[str] = Field(None, description="Apellido (solo para chats privados)")


class TelegramMessage(BaseModel):
    """
    Esquema para representar un mensaje de Telegram.
    
    Corresponde al tipo 'Message' de la API de Telegram Bot.
    Es la estructura central para procesar todos los mensajes que llegan al bot.
    
    Campos principales:
    - message_id: ID único del mensaje (para referencias y respuestas)
    - from_: Usuario que envió el mensaje (usamos alias por palabra reservada)
    - chat: Chat donde se envió el mensaje
    - date: Timestamp Unix del mensaje
    - text: Contenido del mensaje (lo que procesará la IA)
    
    Notas importantes:
    - from_ usa alias "from" porque "from" es palabra reservada en Python
    - text es opcional porque los mensajes pueden ser fotos, stickers, etc.
    - date es timestamp Unix (segundos desde 1970)
    
    Para el bot de Macroferro, principalmente procesamos:
    1. Mensajes de texto con consultas de productos
    2. Comandos como /start, /help
    3. Respuestas a preguntas del bot
    
    Ejemplo de mensaje típico:
    {
        "message_id": 1234,
        "from": {
            "id": 123456789,
            "is_bot": false,
            "first_name": "Juan"
        },
        "chat": {
            "id": 123456789,
            "type": "private",
            "first_name": "Juan"
        },
        "date": 1699123456,
        "text": "Busco tubos de PVC de 110mm"
    }
    """
    message_id: int = Field(..., description="Identificador único del mensaje")
    from_: Optional[TelegramUser] = Field(None, description="Usuario que envió el mensaje")
    chat: TelegramChat = Field(..., description="Chat donde se envió el mensaje")
    date: int = Field(..., description="Timestamp Unix del envío del mensaje")
    text: Optional[str] = Field(None, description="Contenido de texto del mensaje")
    
    class Config:
        """
        Configuración de Pydantic para este esquema.
        
        Permite usar alias para campos con nombres que son palabras reservadas.
        "from_" se mapea a "from" en el JSON que llega de Telegram.
        
        Esto es necesario porque "from" es una palabra reservada en Python
        pero es el nombre oficial del campo en la API de Telegram.
        """
        fields = {"from_": "from"}


# ========================================
# ESQUEMAS DE ENTRADA (WEBHOOKS)
# ========================================

class TelegramUpdate(BaseModel):
    """
    Esquema para representar una actualización completa de Telegram.
    
    Corresponde al tipo 'Update' de la API de Telegram Bot.
    Es la estructura raíz que recibimos en el webhook cuando alguien
    interactúa con nuestro bot.
    
    Una actualización puede contener diferentes tipos de eventos:
    - message: Nuevo mensaje enviado al bot
    - edited_message: Mensaje editado
    - channel_post: Post en canal
    - callback_query: Respuesta a botón inline
    - etc.
    
    Para Macroferro, principalmente manejamos:
    - message: Consultas de productos, comandos, conversación
    
    Campos principales:
    - update_id: ID único incremental de la actualización
    - message: Objeto Message si es un mensaje nuevo (opcional)
    
    Ejemplo de actualización con mensaje:
    {
        "update_id": 123456789,
        "message": {
            "message_id": 1234,
            "from": { ... },
            "chat": { ... },
            "date": 1699123456,
            "text": "¿Tienen martillos?"
        }
    }
    
    Flujo de procesamiento:
    1. Telegram envía Update al webhook
    2. Validamos con este esquema
    3. Extraemos el mensaje si existe
    4. Procesamos con IA y enviamos respuesta
    """
    update_id: int = Field(..., description="Identificador único incremental de la actualización")
    message: Optional[TelegramMessage] = Field(None, description="Nuevo mensaje entrante (opcional)")


# ========================================
# ESQUEMAS DE SALIDA (RESPUESTAS)
# ========================================

class TelegramResponse(BaseModel):
    """
    Esquema para estructurar las respuestas que enviamos a Telegram.
    
    Representa los parámetros necesarios para el método 'sendMessage'
    de la API de Telegram Bot. Este esquema nos ayuda a construir
    respuestas consistentes y validadas antes de enviarlas.
    
    Campos principales:
    - method: Método de la API (típicamente "sendMessage")
    - chat_id: ID del chat donde enviar la respuesta
    - text: Contenido del mensaje de respuesta
    - parse_mode: Formato del texto ("Markdown", "HTML", None)
    
    Casos de uso en Macroferro:
    1. Respuestas con información de productos
    2. Mensajes de error o aclaración
    3. Confirmaciones de acciones
    4. Menús de opciones
    
    parse_mode="Markdown" permite formateo:
    - *texto en negrita*
    - _texto en cursiva_
    - `código`
    - [enlaces](https://example.com)
    
    Ejemplo de respuesta típica:
    {
        "method": "sendMessage",
        "chat_id": 123456789,
        "text": "*Productos encontrados:*\n\n📦 Tubo PVC 110mm - $25.000\n📦 Codo PVC 110mm - $8.000",
        "parse_mode": "Markdown"
    }
    
    Flujo de uso:
    1. Procesamos consulta del usuario
    2. Generamos respuesta con IA
    3. Creamos TelegramResponse
    4. Validamos estructura
    5. Enviamos a Telegram API
    """
    method: str = Field(default="sendMessage", description="Método de la API de Telegram a usar")
    chat_id: int = Field(..., description="ID del chat donde enviar la respuesta")
    text: str = Field(..., description="Contenido del mensaje de respuesta")
    parse_mode: Optional[str] = Field(default="Markdown", description="Modo de parseo del texto (Markdown, HTML, None)")

# ========================================
# NOTAS SOBRE INTEGRACIÓN
# ========================================

# Al usar estos esquemas en el endpoint del webhook:
# 1. FastAPI valida automáticamente el JSON entrante contra TelegramUpdate
# 2. Si la validación falla, retorna error 422 automáticamente
# 3. Si pasa, tenemos objetos Python tipados para trabajar
# 4. Para responder, creamos TelegramResponse y lo serializamos a JSON

# Ejemplos de uso en el endpoint:
# @router.post("/webhook")
# async def telegram_webhook(update: TelegramUpdate):
#     if update.message and update.message.text:
#         response = TelegramResponse(
#             chat_id=update.message.chat.id,
#             text="¡Hola! ¿En qué puedo ayudarte?"
#         )
#         return response
#     return {"status": "no_message"}

# ========================================
# EXTENSIONES FUTURAS
# ========================================

# Esquemas adicionales que podrían añadirse:
# - TelegramInlineKeyboard: Para botones interactivos
# - TelegramCallback: Para manejar respuestas de botones
# - TelegramPhoto: Para procesar imágenes de productos
# - TelegramLocation: Para búsquedas por ubicación
# - TelegramContact: Para datos de contacto de clientes 