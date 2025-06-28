# 🤖 Demostración de Flujo de Interacción

Este documento muestra ejemplos detallados de cómo un usuario interactuaría con el **Asistente IA para E-commerce B2B**. Los escenarios demuestran la capacidad del bot para entender lenguaje natural, gestionar el contexto de la conversación y automatizar el proceso de venta completo.

---

## 🚀 Escenario 1: Nuevo Cliente - Consulta, Modificación de Carrito y Compra

**Objetivo:** Un cliente nuevo que no conoce el catálogo explora, añade productos, modifica su carrito y finaliza la compra por primera vez.

| Paso | Actor | Acción / Mensaje | Lógica Interna del Bot |
| :--: | :---: | :--- | :--- |
| 1 | 👤 Cliente | "Hola, busco algo para unir tuberías de metal, que no sea soldadura" | **[Análisis de Intención]** La IA identifica `intención: product_search` y `keywords: ["unir", "tuberías", "metal", "no soldadura"]`. |
| 2 | 🤖 Bot | "¡Claro! Para unir tuberías de metal sin soldar, te recomiendo:<br><br>1. **Conectores de Compresión de Latón** (SKU00810)<br>2. **Bridas de Acero Inoxidable** (SKU00815)<br>3. **Adhesivo Epóxico para Metales** (SKU00795)<br><br>¿Quieres saber más de alguno?" | **[Búsqueda Semántica]** Busca en la base de datos de vectores productos cuya descripción coincide con la intención del usuario. |
| 3 | 👤 Cliente | "dame detalles del primero y del adhesivo" | **[Resolución de Referencias]** La IA entiende "el primero" (posición 1) y "el adhesivo" (palabra clave). Prepara la información de ambos. |
| 4 | 🤖 Bot | "Aquí tienes:<br><br>🔩 **Conectores de Compresión de Latón (SKU00810)**<br>Ideales para uniones rápidas y seguras. Soportan alta presión.<br>_Precio: $25.00 c/u_<br><br>🧪 **Adhesivo Epóxico para Metales (SKU00795)**<br>Fuerza industrial, resistente a químicos y temperatura.<br>_Precio: $40.00 por tubo_<br><br>¿Cuál te interesa añadir?" | **[Presentación de Producto]** Formatea los datos clave de los productos solicitados. |
| 5 | 👤 Cliente | "agrega 10 conectores y 2 adhesivos" | **[Extracción de Entidades]** La IA identifica `acción: add_to_cart`, `items: [{"producto": "conectores", "cantidad": 10}, {"producto": "adhesivos", "cantidad": 2}]`. |
| 6 | 🤖 Bot | "✅ ¡Añadido!<br><br>🛒 **Tu Carrito:**<br> • 10 x Conectores de Compresión... - $250.00<br> • 2 x Adhesivo Epóxico... - $80.00<br><br>💰 **Total: $330.00**<br><br>¿Necesitas algo más?" | **[Gestión de Carrito]** Actualiza el carrito en la base de datos (Redis) y recalcula el total. |
| 7 | 👤 Cliente | "mejor que sean 15 conectores. Y quita el adhesivo, me equivoqué." | **[Modificación de Carrito]** La IA detecta dos acciones: `acción: update_quantity` para "conectores" y `acción: remove_item` para "adhesivo". |
| 8 | 🤖 Bot | "Entendido. He actualizado tu carrito:<br><br>🛒 **Tu Carrito:**<br> • 15 x Conectores de Compresión... - $375.00<br><br>💰 **Total: $375.00**<br><br>¿Listo para finalizar la compra?" | **[Gestión de Carrito]** Modifica las cantidades y elimina productos según las instrucciones. |
| 9 | 👤 Cliente | "sí, finalizar compra" | **[Inicio de Checkout]** El bot activa el flujo de finalización de compra. |
| 10 | 🤖 Bot | "Perfecto. Como es tu primera compra, necesito unos datos:<br><br>📧 **¿Cuál es tu email?**" | **[Flujo Guiado]** Pide la información necesaria paso a paso. |
| 11 | 👤 Cliente | "contacto@constructora-xyz.com" | El bot valida el formato del email. |
| 12 | 🤖 Bot | "Gracias. 🏢 **¿Nombre de tu empresa para la factura?**" | Continúa con el siguiente paso del flujo. |
| 13 | 👤 Cliente | "Constructora XYZ" | ...el proceso continúa hasta recolectar todos los datos. |
| 14 | 🤖 Bot | "🎉 **¡Pedido Confirmado!**<br><br>Hemos enviado la factura a tu email. Tu pedido **#ORD001235** está siendo preparado.<br><br>Gracias por confiar en Macroferro." | **[Automatización]** Genera el PDF, lo sube a Google Drive, guarda la orden en PostgreSQL y envía el email. |

---

## 🎯 Escenario 2: Cliente Recurrente - Compra Rápida y Consulta Técnica

**Objetivo:** Un cliente que ya ha comprado antes necesita un producto específico rápidamente y tiene una duda técnica.

| Paso | Actor | Acción / Mensaje | Lógica Interna del Bot |
| :--: | :---: | :--- | :--- |
| 1 | 👤 Cliente | "Hola, necesito más tornillos de titanio grado 5" | **[Análisis + Contexto]** La IA identifica `intención: product_search` con `keywords: ["tornillos", "titanio", "grado 5"]`. El bot reconoce el ID del chat y carga el historial del cliente. |
| 2 | 🤖 Bot | "¡Hola de nuevo! Claro, buscando **Tornillos de Titanio Grado 5 (SKU00442)**.<br><br>He visto que la última vez pediste 200 unidades. ¿Quieres la misma cantidad?" | **[Personalización]** El bot consulta el historial de pedidos del cliente en la base de datos y ofrece una sugerencia proactiva. |
| 3 | 👤 Cliente | "sí, perfecto. añádelos" | **[Acción Rápida]** El cliente confirma la sugerencia. |
| 4 | 🤖 Bot | "✅ ¡Añadido!<br><br>🛒 **Tu Carrito:**<br> • 200 x Tornillos de Titanio... - $400.00<br><br>💰 **Total: $400.00**<br><br>¿Algo más?" | **[Gestión de Carrito]** Añade directamente la cantidad sugerida. |
| 5 | 👤 Cliente | "una pregunta, ¿esos tornillos aguantan bien en ambientes salinos?" | **[Pregunta Técnica + Contextual]** La IA detecta `intención: technical_question` y entiende que "esos tornillos" se refiere al último producto añadido al carrito. |
| 6 | 🤖 Bot | "Excelente pregunta. Buscando en la ficha técnica...<br><br>Sí, los **Tornillos de Titanio Grado 5** tienen una excelente resistencia a la corrosión, incluso en ambientes marinos o salinos, debido a la capa de óxido de titanio que se forma en su superficie.<br><br>Son ideales para esa aplicación. ¿Procedemos con la compra?" | **[Consulta de Conocimiento]** El bot no solo busca en la descripción, sino que puede tener una base de datos de conocimiento (o usar la IA con contexto de la ficha técnica) para dar una respuesta detallada. |
| 7 | 👤 Cliente | "proceder" | **[Inicio de Checkout]** |
| 8 | 🤖 Bot | "Confirmemos los datos de **Constructora XYZ**:<br><br>📧 Email: contacto@constructora-xyz.com<br>📞 Teléfono: 555-123-4567<br>📍 Dirección: Av. Siempre Viva 123<br><br>¿Es todo correcto?" | **[Recuperación de Datos]** El bot obtiene los datos guardados del cliente desde la base de datos. |
| 9 | 👤 Cliente | "correcto" | El cliente confirma con una sola palabra. |
| 10 | 🤖 Bot | "🎉 **¡Pedido Confirmado!**<br><br>Factura enviada. Tu pedido **#ORD001236** ya está en proceso.<br><br>¡Un placer ayudarte de nuevo!" | **[Automatización Completa]** El proceso es mucho más rápido para un cliente recurrente. |

---

### Capacidades Demostradas:
- **🧠 Comprensión del Lenguaje Natural:** Interpreta peticiones vagas y complejas.
- **🗣️ Gestión de Contexto:** Recuerda productos mostrados y conversaciones anteriores.
- **🛒 Modificación Flexible del Carrito:** Permite añadir, quitar y actualizar unidades de forma conversacional.
- ** personalize a los clientes recurrentes.
- **🤖 Automatización End-to-End:** Desde la consulta inicial hasta la facturación sin intervención humana.
- **❓ Resolución de Dudas Técnicas:** Actúa como un verdadero asistente de ventas experto. 