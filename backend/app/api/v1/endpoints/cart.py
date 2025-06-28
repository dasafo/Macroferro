# backend/app/api/v1/endpoints/cart.py
"""
Este archivo contiene los endpoints para el carrito de compras.

Se encarga de gestionar las operaciones de agregar productos, eliminar productos,
obtener el contenido del carrito y procesar el checkout.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging

from app.api import deps
from app.core.config import Settings
from app.schemas.product_schema import ProductResponse
from app.schemas.order_schema import Order, OrderCreate
from app.services.cart_service import CartService
from app.crud import order_crud, product_crud, stock_crud
from app.schemas.cart_schema import CartItemCreate, Cart

# Router para el carrito de compras
router = APIRouter()

def get_cart_service(settings: Settings = Depends(deps.get_settings)):
    """
    Dependencia para obtener el servicio de carrito.
    """
    return CartService(settings)

@router.post("/{chat_id}/items", status_code=201, response_model=Cart)
async def add_item_to_cart(
    chat_id: str,
    item: CartItemCreate,
    db: AsyncSession = Depends(deps.get_db),
    cart_service: CartService = Depends(get_cart_service)
):
    """
    Añade un producto al carrito de un usuario, verificando el stock disponible.
    """
    product_db = product_crud.get_product_by_sku(db, sku=item.product_sku)
    if not product_db:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # --- NUEVA VERIFICACIÓN DE STOCK ---
    total_stock = stock_crud.get_total_stock_by_sku(db, sku=item.product_sku)
    if total_stock < item.quantity:
        raise HTTPException(
            status_code=409, # Conflict
            detail=f"Stock insuficiente para {product_db.name}. Solicitado: {item.quantity}, Disponible: {total_stock}"
        )
    # --- FIN DE LA VERIFICACIÓN ---

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
    db: AsyncSession = Depends(deps.get_db),
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

@router.delete("/{chat_id}", status_code=204)
async def clear_cart(
    chat_id: str,
    cart_service: CartService = Depends(get_cart_service)
):
    """
    Vacía completamente el carrito de un usuario.
    """
    await cart_service.clear_cart(chat_id)
    return

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
    db: AsyncSession = Depends(deps.get_db),
    cart_service: CartService = Depends(get_cart_service)
):
    """
    Procesa el checkout:
    1. Verifica el stock de los productos en el carrito.
    2. Si hay stock, crea la orden en la base de datos.
    3. Deduce las cantidades del stock.
    4. Vacía el carrito.
    Todo esto se ejecuta en una única transacción.
    """
    cart_items = await cart_service.get_cart_contents(chat_id)
    if not cart_items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    # Aquí iría la información del cliente, que asumimos se obtiene de algún modo
    # (ej: del perfil de Telegram o un paso anterior no implementado)
    customer_data = {
        "customer_name": "Cliente de Telegram",
        "customer_email": "telegram.user@example.com",
        "shipping_address": "Dirección a definir"
    }

    try:
        # Iniciamos la transacción
        db.begin()

        # 1. VERIFICACIÓN DE STOCK
        for sku, item_data in cart_items.items():
            total_stock = stock_crud.get_total_stock_by_sku(db, sku)
            if total_stock < item_data['quantity']:
                raise HTTPException(
                    status_code=409, # 409 Conflict es apropiado aquí
                    detail=f"Stock insuficiente para {item_data['name']} (SKU: {sku}). Pedido: {item_data['quantity']}, Disponible: {total_stock}"
                )
        
        # 2. CREACIÓN DE LA ORDEN
        total_price = await cart_service.get_cart_total_price(chat_id)
        
        order_to_create = OrderCreate(
            order_id=order_crud.get_next_order_id(db),
            chat_id=chat_id,
            customer_name=customer_data["customer_name"],
            customer_email=customer_data["customer_email"],
            shipping_address=customer_data["shipping_address"],
            total_amount=total_price,
            items=[CartItemCreate(product_sku=sku, quantity=item['quantity'], price=item['price']) for sku, item in cart_items.items()]
        )
        
        order = order_crud.create_order(db=db, order=order_to_create)

        # 3. DEDUCCIÓN DE STOCK
        for sku, item_data in cart_items.items():
            stock_crud.deduct_stock(db, sku, item_data['quantity'])

        # Si todo ha ido bien, confirmamos la transacción
        db.commit()
        db.refresh(order)

    except HTTPException as http_exc:
        db.rollback() # Revertimos en caso de error de stock
        raise http_exc # Re-lanzamos la excepción HTTP
    except Exception as e:
        db.rollback() # Revertimos en caso de cualquier otro error
        raise HTTPException(status_code=500, detail=f"Ocurrió un error inesperado durante el checkout: {e}")

    # 4. VACIAR EL CARRITO (solo después de que la transacción sea exitosa)
    await cart_service.clear_cart(chat_id)
    
    # Aquí se podría encolar el envío del email de confirmación
    
    return order 