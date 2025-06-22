# Hoja de Ruta: Implementación del Carrito de Compra y Pedidos

## Visión General de la Arquitectura Propuesta

*   **Carrito de Compra (Sesión Temporal):** Usaremos **Redis** para gestionar los carritos de compra activos. Redis es perfecto para esto: es increíblemente rápido y está diseñado para datos temporales. Cada usuario de Telegram (`chat_id`) tendrá su propio carrito almacenado en Redis.
*   **Pedidos (Persistente):** Una vez que el cliente confirma la compra, el contenido del carrito se moverá de Redis a la base de datos **PostgreSQL**, creando un registro de `Order` y `OrderItem` permanente.
*   **Servicios Modulares:** Crearemos nuevos servicios (`CartService`, `OrderService`, `PDFService`, `EmailService`) para mantener el código limpio, organizado y fácil de mantener, siguiendo el patrón que ya establecimos.
*   **Generación de PDF:** Integraremos una librería para crear facturas en PDF sobre la marcha.
*   **Notificaciones:** Usaremos el `TelegramBotService` existente para enviar la factura por Telegram y un nuevo `EmailService` para enviarla por correo, aprovechando la configuración SMTP que ya tienes en tu `.env`.

---

## Fases del Proyecto

### Fase 1: El Fundamento - Modelos de Datos y Lógica del Carrito

En esta fase, sentaremos las bases de todo el sistema. No habrá nada visible para el usuario final, pero es el trabajo más crítico.

1.  **Actualizar la Base de Datos (PostgreSQL):**
    *   Crear nuevos modelos en SQLAlchemy: `Order` y `OrderItem`.
    *   **Archivos a crear/modificar:**
        *   `backend/app/db/models/order.py` (nuevo)
        *   `backend/app/schemas/order.py` (nuevo)
        *   `backend/app/crud/order_crud.py` (nuevo)

2.  **Crear el Servicio del Carrito (`CartService`):**
    *   Contendrá toda la lógica para interactuar con **Redis**.
    *   Funciones: `add_to_cart`, `remove_from_cart`, `get_cart`, `clear_cart`.
    *   **Archivos a crear:**
        *   `backend/app/services/cart_service.py` (nuevo)

3.  **Añadir Nuevas Dependencias:**
    *   Agregar `reportlab` (para PDF) y `fastapi-mail` (para correos) a `requirements.txt`.
    *   **Archivos a modificar:**
        *   `backend/requirements.txt`

### Fase 2: Interacción con el Usuario - Comandos del Bot

Haremos que el bot entienda cómo manejar el carrito.

1.  **Actualizar el Análisis de Intenciones (IA):**
    *   Modificar el prompt en `TelegramBotService` para reconocer intenciones como `add_to_cart`, `view_cart`, `remove_from_cart`, `checkout`.

2.  **Implementar los Manejadores de Intenciones:**
    *   Dentro de `TelegramBotService`, crear funciones (`_handle_add_to_cart`, etc.) que llamen al `CartService`.
    *   El bot dará feedback inmediato al usuario.
    *   **Archivos a modificar:**
        *   `backend/app/services/telegram_service.py`

### Fase 3: El Checkout - De Carrito a Pedido Formal

Convertiremos un carrito temporal en un pedido permanente.

1.  **Crear el Servicio de Pedidos (`OrderService`):**
    *   Orquestará el proceso de checkout con la función `create_order_from_cart(chat_id, customer_data)`.
    *   Moverá los datos de Redis a PostgreSQL.
    *   **Archivos a crear:**
        *   `backend/app/services/order_service.py` (nuevo)

2.  **Manejar la Lógica de Checkout en el Bot:**
    *   Al detectar la intención `checkout`, el bot recopilará los datos del cliente.
    *   Llamará a `OrderService.create_order_from_cart`.
    *   **Archivos a modificar:**
        *   `backend/app/services/telegram_service.py`

### Fase 4: La Entrega - Generación y Envío de la Factura

El paso final: entregarle al cliente el comprobante de su compra.

1.  **Crear el Servicio de PDF (`PDFService`):**
    *   Tomará un objeto `Order` y generará una factura en PDF.
    *   **Archivos a crear:**
        *   `backend/app/services/pdf_service.py` (nuevo)

2.  **Crear el Servicio de Email (`EmailService`):**
    *   Usará la configuración SMTP para enviar un correo con la factura.
    *   **Archivos a crear:**
        *   `backend/app/services/email_service.py` (nuevo)

3.  **Integrar Todo en el Flujo de Pedido:**
    *   Al final de `OrderService.create_order_from_cart`, se llamará a `PDFService`, `TelegramBotService` y `EmailService` para generar y enviar la factura.
    *   **Archivos a modificar:**
        *   `backend/app/services/order_service.py`
