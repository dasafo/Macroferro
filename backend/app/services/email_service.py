from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from typing import List, Dict, Any
import logging
from pathlib import Path
from weasyprint import HTML
from datetime import datetime
import os
import tempfile

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Configuración del Servicio de Correo ---
# Usamos los settings que ya cargamos desde el .env
conf = ConnectionConfig(
    MAIL_USERNAME=settings.SMTP_USER,
    MAIL_PASSWORD=settings.SMTP_PASSWORD,
    MAIL_FROM=settings.SENDER_EMAIL,
    MAIL_PORT=settings.SMTP_PORT,
    MAIL_SERVER=settings.SMTP_HOST,
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

fm = FastMail(conf)

# --- Generación de Factura PDF ---

def _generate_invoice_html(order_data: Dict[str, Any]) -> str:
    """Genera el contenido HTML de una factura a partir de los datos del pedido."""
    
    items_html = ""
    for item in order_data.get("items", []):
        subtotal = item['price'] * item['quantity']
        items_html += f"""
            <tr>
                <td>{item['product_sku']}</td>
                <td>{item.get('name', 'Producto')}</td>
                <td class="quantity">{item['quantity']}</td>
                <td class="price">${item['price']:,.2f}</td>
                <td class="price">${subtotal:,.2f}</td>
            </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Factura #{order_data.get('id', 'N/A')}</title>
        <style>
            body {{ font-family: 'Helvetica Neue', 'Helvetica', Helvetica, Arial, sans-serif; color: #555; }}
            .invoice-box {{ max-width: 800px; margin: auto; padding: 30px; border: 1px solid #eee; box-shadow: 0 0 10px rgba(0, 0, 0, 0.15); font-size: 16px; line-height: 24px; }}
            .invoice-box table {{ width: 100%; line-height: inherit; text-align: left; border-collapse: collapse; }}
            .invoice-box table td {{ padding: 5px; vertical-align: top; }}
            .invoice-box table tr.top table td {{ padding-bottom: 20px; }}
            .invoice-box table tr.top table td.title {{ font-size: 45px; line-height: 45px; color: #333; }}
            .invoice-box table tr.information table td {{ padding-bottom: 40px; }}
            .invoice-box table tr.heading td {{ background: #eee; border-bottom: 1px solid #ddd; font-weight: bold; text-align: left;}}
            .invoice-box table tr.details td {{ padding-bottom: 20px; }}
            .invoice-box table tr.item td {{ border-bottom: 1px solid #eee; text-align: left; }}
            .invoice-box table tr.item.last td {{ border-bottom: none; }}
            .invoice-box table tr.total td:nth-child(4) {{ border-top: 2px solid #eee; font-weight: bold; text-align: right; }}
            .price, .quantity {{ text-align: right !important; }}
        </style>
    </head>
    <body>
        <div class="invoice-box">
            <table>
                <tr class="top">
                    <td colspan="5">
                        <table>
                            <tr>
                                <td class="title">
                                    Macroferro
                                </td>
                                <td>
                                    Factura #: {order_data.get('id', 'N/A')}<br>
                                    Creada: {datetime.now().strftime('%d/%m/%Y')}<br>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr class="information">
                    <td colspan="5">
                        <table>
                            <tr>
                                <td>
                                    Macroferro S.A.<br>
                                    Calle Falsa 123<br>
                                    Ciudad, Provincia
                                </td>
                                <td>
                                    {order_data.get('customer_name', '')}<br>
                                    {order_data.get('customer_email', '')}<br>
                                    {order_data.get('shipping_address', '')}
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr class="heading">
                    <td>SKU</td>
                    <td>Producto</td>
                    <td class="quantity">Cantidad</td>
                    <td class="price">Precio Unit.</td>
                    <td class="price">Subtotal</td>
                </tr>
                {items_html}
                <tr class="total">
                    <td colspan="3"></td>
                    <td colspan="2" style="text-align:right;">
                       <strong>Total: ${order_data.get('total_amount', 0.0):,.2f}</strong>
                    </td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """
    return html_content

def create_invoice_pdf(order_data: Dict[str, Any]) -> bytes:
    """Crea un archivo PDF en memoria a partir de los datos de un pedido."""
    html_string = _generate_invoice_html(order_data)
    # WeasyPrint necesita un objeto HTML para procesar
    html = HTML(string=html_string)
    # Escribir el PDF a un buffer de bytes en lugar de a un archivo físico
    pdf_bytes = html.write_pdf()
    return pdf_bytes

# --- Servicio de Envío de Correo ---

async def send_invoice_email(
    email_to: EmailStr,
    order_data: Dict[str, Any]
) -> None:
    """
    Genera una factura PDF y la envía por correo electrónico.
    """
    if not all([settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_PASSWORD]):
        logger.warning("Configuración SMTP no encontrada. Saltando envío de correo.")
        return

    logger.info(f"Preparando factura por correo para el pedido {order_data.get('id')} a {email_to}")
    
    temp_pdf_path = None
    try:
        # 1. Generar el PDF en memoria
        pdf_content = create_invoice_pdf(order_data)
        
        # 2. Guardar el PDF en un archivo temporal para poder adjuntarlo por su ruta
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(pdf_content)
            temp_pdf_path = temp_pdf.name
        
        # 3. Preparar el mensaje
        subject = f"Confirmación de tu pedido en Macroferro - Factura #{order_data.get('id')}"
        
        email_body = f"""
        <p>¡Hola, {order_data.get('customer_name', 'cliente')}!</p>
        <p>Gracias por tu compra en Macroferro. Adjuntamos la factura de tu pedido <strong>#{order_data.get('id')}</strong>.</p>
        <p>Estamos preparando tu pedido para el envío. Te notificaremos de nuevo cuando haya sido despachado.</p>
        <p>Gracias por confiar en nosotros.</p>
        <br>
        <p>El equipo de Macroferro</p>
        """
        
        message = MessageSchema(
            subject=subject,
            recipients=[email_to],
            body=email_body,
            subtype=MessageType.html,
            attachments=[{
                "file": temp_pdf_path,  # Usamos la ruta del archivo temporal
                "filename": f"Factura-Macroferro-{order_data.get('id', 'pedido')}.pdf",
                "mime_type": "application",
                "mime_subtype": "pdf"
            }]
        )
        
        # 4. Enviar el correo
        await fm.send_message(message)
        logger.info(f"Correo de factura enviado exitosamente a {email_to}")

    except Exception as e:
        logger.error(f"Error al enviar correo de factura a {email_to}: {e}", exc_info=True)
        # Aquí se podría añadir lógica de reintentos si fuera necesario
    finally:
        # 5. Limpiar: eliminar el archivo temporal después de usarlo
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            logger.info(f"Archivo temporal de factura eliminado: {temp_pdf_path}") 