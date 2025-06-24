from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.core.config import Settings
from app.schemas.product_schema import ProductResponse
from app.schemas.order_schema import Order, OrderCreate
from app.services.cart_service import CartService
from app.crud import order_crud, product_crud
from app.schemas.cart_schema import CartItemCreate, Cart

router = APIRouter()

def get_cart_service(settings: Settings = Depends(deps.get_settings)):
    return CartService(settings)

@router.post("/{chat_id}/items", status_code=201, response_model=Cart)
async def add_item_to_cart(
    chat_id: str,
    item: CartItemCreate,
    db: Session = Depends(deps.get_db),
    cart_service: CartService = Depends(get_cart_service)
):
    """
    Añade un producto al carrito de un usuario.
    """
    product_db = product_crud.get_product_by_sku(db, sku=item.product_sku)
    if not product_db:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Convertir el modelo de la BD (SQLAlchemy) a un esquema Pydantic
    product_schema = ProductResponse.model_validate(product_db)

    try:
        await cart_service.add_product_to_cart(chat_id, product_schema, item.quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    cart_contents = await cart_service.get_cart_contents(chat_id)
    total_price = await cart_service.get_cart_total_price(chat_id)

    return Cart(items=cart_contents, total_price=total_price)

@router.get("/{chat_id}", response_model=Cart)
async def get_cart(
    chat_id: str,
    cart_service: CartService = Depends(get_cart_service)
):
    """
    Obtiene el contenido del carrito de un usuario.
    """
    cart_contents = await cart_service.get_cart_contents(chat_id)
    if not cart_contents:
        return Cart(items={}, total_price=0.0)
        
    total_price = await cart_service.get_cart_total_price(chat_id)
    return Cart(items=cart_contents, total_price=total_price)

@router.delete("/{chat_id}/items/{product_sku}", status_code=204)
async def remove_item_from_cart(
    chat_id: str,
    product_sku: str,
    cart_service: CartService = Depends(get_cart_service)
):
    """
    Elimina un producto del carrito de un usuario.
    """
    await cart_service.remove_product_from_cart(chat_id, product_sku)
    return

@router.post("/{chat_id}/checkout", response_model=Order)
async def checkout(
    chat_id: str,
    order_in: OrderCreate,
    db: Session = Depends(deps.get_db),
    cart_service: CartService = Depends(get_cart_service)
):
    """
    Procesa el pago, convierte el carrito en un pedido y lo vacía.
    """
    cart_contents = await cart_service.get_cart_contents(chat_id)
    if not cart_contents:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    total_price = await cart_service.get_cart_total_price(chat_id)
    
    # Aquí se podría integrar una pasarela de pago
    
    order = order_crud.create_order(db=db, order=order_in, total_amount=total_price)
    
    await cart_service.clear_cart(chat_id)
    
    return order 