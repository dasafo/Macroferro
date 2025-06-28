# backend/app/schemas/telegram_schema.py
"""
Esquemas Pydantic para el manejo de la API de Telegram Bot.

Define las estructuras de datos para validar los webhooks entrantes de Telegram
y para construir las respuestas salientes.

Documentación de referencia: https://core.telegram.org/bots/api#available-types
"""

from pydantic import BaseModel, Field
from typing import Optional
class TelegramUser(BaseModel):
    """Representa un usuario de Telegram."""
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

class TelegramChat(BaseModel):
    """Representa un chat de Telegram (privado, grupo, etc.)."""
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class TelegramMessage(BaseModel):
    """
    Representa un mensaje en Telegram.

    El campo `from_` usa un alias porque `from` es una palabra reservada en Python.
    """
    message_id: int
    from_: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    
    class Config:
        # Pydantic 2.x usa `populate_by_name` en lugar de `allow_population_by_field_name`
        # para permitir el uso de alias durante la creación del modelo.
        # Sin embargo, con Field(alias=...), esto ya se gestiona por defecto.
        # Mantendremos la configuración de Pydantic 1.x para compatibilidad si es necesario.
        allow_population_by_field_name = True

class TelegramUpdate(BaseModel):
    """
    Representa una actualización completa recibida del webhook de Telegram.
    Puede contener un nuevo mensaje, una edición, un callback, etc.
    """
    update_id: int
    message: Optional[TelegramMessage] = None
    # Otros campos como 'edited_message', 'callback_query' pueden añadirse aquí.

class TelegramResponse(BaseModel):
    """
    Estructura una respuesta para ser enviada a través de la API de Telegram,
    típicamente para el método 'sendMessage'.
    """
    method: str = "sendMessage"
    chat_id: int
    text: str
    parse_mode: Optional[str] = "Markdown"
