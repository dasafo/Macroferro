# Hoja de Ruta: Implementación del Carrito de Compra y Pedidos (Actualizada)

## Visión General de la Arquitectura

*   **Carrito de Compra (Sesión Temporal):** Se utiliza **Redis** para gestionar los carritos. Cada `chat_id` tiene un carrito temporal, gestionado por el `CartHandler`.
*   **Pedidos (Persistente):** Al confirmar la compra, el `CheckoutHandler` mueve los datos del carrito de Redis a **PostgreSQL**, creando un registro de `Order` y `OrderItem`.
*   **Servicios Modulares:** La lógica está encapsulada en `Handlers` especializados (`CartHandler`, `CheckoutHandler`) dentro del `telegram_service`, que actúa como orquestador.
*   **Notificaciones:** Se usa `TelegramBotService` para notificaciones directas. Un `EmailService` está en desarrollo para enviar facturas por correo.

---

## Fases del Proyecto

### ✅ Fase 1: El Fundamento - Modelos de Datos y Lógica del Carrito - **COMPLETADA**

1.  **Actualizar la Base de Datos (PostgreSQL):**
    *   Modelos `Order` y `OrderItem` creados.
    *   **Archivos modificados:**
        *   `backend/app/db/models/order.py`
        *   `backend/app/schemas/order.py`
        *   `backend/app/crud/order_crud.py`

2.  **Crear el Servicio del Carrito (Ahora `CartHandler`):**
    *   Lógica de Redis encapsulada en `CartHandler`.
    *   Funciones: `add_item_to_cart`, `remove_item_from_cart`, `view_cart`, `clear_cart`.
    *   **Archivo principal:**
        *   `backend/app/services/bot_components/cart_handler.py`

### ✅ Fase 2: Interacción con el Usuario - Comandos del Bot - **COMPLETADA**

1.  **Actualizar el Análisis de Intenciones (`AIAnalyzer`):**
    *   Se ha refinado el `system_prompt` en `AIAnalyzer` para reconocer `add_to_cart`, `view_cart`, `remove_from_cart`, `checkout` y variantes en lenguaje natural.

2.  **Implementar los Manejadores de Intenciones:**
    *   `TelegramBotService` delega las intenciones relacionadas con el carrito al `CartHandler`.
    *   El bot proporciona feedback inmediato tras cada operación.
    *   **Archivos modificados:**
        *   `backend/app/services/telegram_service.py`
        *   `backend/app/services/bot_components/ai_analyzer.py`

### ✅ Fase 3: El Checkout - De Carrito a Pedido Formal - **COMPLETADA**

1.  **Crear el Orquestador de Pedidos (`CheckoutHandler`):**
    *   El `CheckoutHandler` gestiona el proceso de pago, recopilando datos del cliente y creando el pedido.
    *   Su función principal es `create_order_from_cart`.
    *   Mueve los datos de Redis a PostgreSQL usando `order_crud`.
    *   **Archivo principal:**
        *   `backend/app/services/bot_components/checkout_handler.py`

2.  **Manejar la Lógica de Checkout en el Bot:**
    *   Al detectar la intención `checkout`, `TelegramBotService` inicia el `CheckoutHandler`.
    *   **Archivos modificados:**
        *   `backend/app/services/telegram_service.py`

### 🚧 Fase 4: La Entrega - Generación y Envío de la Factura - **EN PREPARACIÓN**

El paso final: entregarle al cliente el comprobante de su compra.

1.  **Crear el Servicio de PDF (`PDFService`):**
    *   **Tarea:** Tomará un objeto `Order` y generará una factura en PDF.
    *   **Archivos a crear:** `backend/app/services/pdf_service.py` (pendiente)

2.  **Crear el Servicio de Email (`EmailService`):**
    *   **Tarea:** Usará la configuración SMTP para enviar un correo con la factura.
    *   **Archivos a crear:** `backend/app/services/email_service.py` (pendiente, aunque el fichero existe está vacío)

3.  **Integrar Todo en el Flujo de Pedido:**
    *   **Tarea:** Al final del `CheckoutHandler`, se deberá llamar a los futuros `PDFService` y `EmailService`.
    *   **Archivos a modificar:** `backend/app/services/bot_components/checkout_handler.py` (pendiente)
