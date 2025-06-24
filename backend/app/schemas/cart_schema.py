from pydantic import BaseModel
from typing import Dict, Any

class CartItemCreate(BaseModel):
    product_sku: str
    quantity: int = 1

class Cart(BaseModel):
    items: Dict[str, Any]
    total_price: float 