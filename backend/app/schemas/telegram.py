from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

class TelegramChat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class TelegramMessage(BaseModel):
    message_id: int
    from_: Optional[TelegramUser] = None
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    
    class Config:
        # Permitir nombres de campo con alias
        fields = {"from_": "from"}

class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None

class TelegramResponse(BaseModel):
    method: str = "sendMessage"
    chat_id: int
    text: str
    parse_mode: Optional[str] = "Markdown" 