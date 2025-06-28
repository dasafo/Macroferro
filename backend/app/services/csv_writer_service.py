# backend/app/services/csv_writer_service.py
"""
Este servicio se encarga de escribir datos en archivos CSV, especialmente para
la generación de facturas y registros de ventas. Utiliza un Lock para evitar
condiciones de carrera si dos pedidos se procesan simultáneamente.
"""

import csv
import os
import threading
import logging
from datetime import datetime
from typing import Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Configuración de Rutas y Bloqueo ---

# Construimos la ruta a los archivos CSV desde la raíz del proyecto
CSV_DATA_PATH = os.path.join(settings.BASE_DIR, 'init_db_scripts', 'csv_data')
INVOICES_FILE_PATH = os.path.join(CSV_DATA_PATH, 'invoices.csv')
INVOICE_ITEMS_FILE_PATH = os.path.join(CSV_DATA_PATH, 'invoice_items.csv')

# Un Lock para prevenir condiciones de carrera si dos pedidos se procesan simultáneamente.
# Esto asegura que solo un hilo pueda escribir en los archivos a la vez.
csv_lock = threading.Lock()

# --- Servicio de Escritura en CSV ---

def append_to_invoices_csvs(order_data: Dict[str, Any], pdf_url: str) -> None:
    """
    Añade los datos de una nueva factura a los archivos invoices.csv y invoice_items.csv.
    Esta operación es atómica gracias al uso de un Lock.
    """
    invoice_id = order_data.get('id')
    client_id = order_data.get('client_id')
    total_amount = order_data.get('total_amount')
    created_at_raw = order_data.get('created_at', datetime.now())
    items = order_data.get('items', [])

    if not all([invoice_id, client_id, total_amount, items]):
        logger.error(f"Faltan datos esenciales para escribir en CSV para la factura {invoice_id}. Datos recibidos: {order_data}")
        return

    logger.info(f"Iniciando escritura en CSV para la factura: {invoice_id}")
    
    with csv_lock:
        try:
            # Convertir la fecha si es un string en formato ISO
            if isinstance(created_at_raw, str):
                created_at = datetime.fromisoformat(created_at_raw)
            else:
                created_at = created_at_raw

            # 1. Escribir en invoices.csv
            invoice_row = [
                invoice_id,
                client_id,
                total_amount,
                pdf_url or "",  # Asegurarse de que no sea None
                created_at.strftime('%Y-%m-%d')
            ]
            
            with open(INVOICES_FILE_PATH, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(invoice_row)
            
            logger.info(f"Fila añadida a invoices.csv para la factura {invoice_id}")

            # 2. Escribir en invoice_items.csv
            with open(INVOICE_ITEMS_FILE_PATH, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for item in items:
                    item_row = [
                        invoice_id,
                        item.get('product_sku'),
                        item.get('quantity'),
                        item.get('price')
                    ]
                    writer.writerow(item_row)
            
            logger.info(f"{len(items)} filas añadidas a invoice_items.csv para la factura {invoice_id}")

        except Exception as e:
            logger.error(f"Error crítico al escribir en los archivos CSV para la factura {invoice_id}: {e}", exc_info=True)

# Instancia del "servicio" (en este caso, solo la función) para ser importada
csv_writer_service = append_to_invoices_csvs 