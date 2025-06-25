import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Configuración de la API de Google Drive ---
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'google-credentials.json')

class GoogleDriveService:
    def __init__(self):
        self.creds = None
        self.service = None
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            try:
                self.creds = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )
                self.service = build('drive', 'v3', credentials=self.creds)
                logger.info("Servicio de Google Drive inicializado correctamente.")
            except Exception as e:
                logger.error(f"No se pudo inicializar el servicio de Google Drive: {e}", exc_info=True)
        else:
            logger.warning("No se encontró el archivo de credenciales de Google. El servicio de Drive no estará disponible.")

    def _find_folder_id(self, folder_name: str) -> Optional[str]:
        """Busca el ID de una carpeta por su nombre."""
        if not self.service:
            return None
        
        try:
            query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
            response = self.service.files().list(
                q=query, 
                spaces='drive', 
                fields='files(id, name)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            files = response.get('files', [])
            
            if files:
                folder_id = files[0].get('id')
                logger.info(f"Carpeta '{folder_name}' encontrada con ID: {folder_id}")
                return folder_id
            else:
                logger.warning(f"No se encontró la carpeta con el nombre: {folder_name}")
                return None
        except Exception as e:
            logger.error(f"Error buscando la carpeta '{folder_name}' en Google Drive: {e}", exc_info=True)
            return None

    def upload_pdf(self, pdf_content: bytes, pdf_filename: str, folder_name: str) -> Optional[str]:
        """Sube un contenido de PDF a una carpeta específica en Google Drive."""
        if not self.service:
            logger.error("El servicio de Google Drive no está disponible. No se puede subir el archivo.")
            return None

        folder_id = self._find_folder_id(folder_name)
        if not folder_id:
            logger.error(f"No se pudo subir el archivo porque la carpeta '{folder_name}' no fue encontrada.")
            return None

        try:
            file_metadata = {
                'name': pdf_filename,
                'parents': [folder_id]
            }
            
            media = MediaIoBaseUpload(io.BytesIO(pdf_content), mimetype='application/pdf', resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            file_id = file.get('id')
            file_link = file.get('webViewLink')
            logger.info(f"Archivo '{pdf_filename}' subido a Google Drive con ID: {file_id}. Enlace: {file_link}")
            return file_link
        except Exception as e:
            logger.error(f"Error al subir el archivo '{pdf_filename}' a Google Drive: {e}", exc_info=True)
            return None

# Instancia única del servicio para ser usada en la aplicación
google_drive_service = GoogleDriveService() 