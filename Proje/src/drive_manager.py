import os
import io
import logging
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

class DriveManager:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        self.service = self._authenticate()
        self.drive_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        self.images_folder_id = os.getenv('GOOGLE_DRIVE_IMAGES_FOLDER_ID')
        
    def _authenticate(self):
        """Google Drive API kimlik doğrulaması"""
        creds = None
        
        # Token dosyası varsa yükle
        if os.path.exists('config/token.json'):
            creds = Credentials.from_authorized_user_file('config/token.json', self.SCOPES)
        
        # Geçerli kimlik bilgileri yoksa yeniden kimlik doğrula
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Credentials dosyası oluştur
                credentials_info = {
                    "installed": {
                        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
                        "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
                    }
                }
                
                flow = InstalledAppFlow.from_client_config(credentials_info, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Token'ı kaydet
            with open('config/token.json', 'w') as token:
                token.write(creds.to_json())
        
        return build('drive', 'v3', credentials=creds)
    
    def download_video_and_images(self):
        """Drive'dan video ve resimleri indir"""
        try:
            # Video dosyasını indir
            video_path = self._download_video_from_drive()
            
            # Resimleri indir
            self._download_images_from_drive()
            
            return video_path
            
        except Exception as e:
            logger.error(f"Drive dosya indirme hatası: {str(e)}")
            raise
    
    def _download_video_from_drive(self):
        """Drive'dan video dosyasını indir"""
        try:
            # Video klasöründeki dosyaları listele
            results = self.service.files().list(
                q=f"'{self.drive_folder_id}' in parents",
                fields="nextPageToken, files(id, name, mimeType)"
            ).execute()
            
            items = results.get('files', [])
            video_path = None
            
            logger.info(f"Video klasöründe bulunan dosyalar: {[item['name'] for item in items]}")
            
            for item in items:
                file_name = item['name'].lower()
                file_id = item['id']
                
                # Video dosyasını bul ve indir
                if any(ext in file_name for ext in ['.mp4', '.avi', '.mov', '.mkv']):
                    video_path = self._download_video(file_id, item['name'])
                    logger.info(f"Video indirildi: {video_path}")
                    break
            
            # Video dosyası Drive'da yoksa local dosyayı kullan
            if not video_path:
                local_video_path = os.path.join('data', 'input_videos', 'test_video.mp4')
                if os.path.exists(local_video_path):
                    video_path = local_video_path
                    logger.info(f"Local video dosyası kullanılıyor: {video_path}")
                else:
                    raise Exception("Video dosyası bulunamadı!")
            
            return video_path
            
        except Exception as e:
            logger.error(f"Video indirme hatası: {str(e)}")
            raise
    
    def _download_images_from_drive(self):
        """Drive'dan resimleri indir"""
        try:
            if not self.images_folder_id:
                logger.warning("Resim klasörü ID'si bulunamadı, resimler indirilmeyecek")
                return
            
            # Resim klasöründeki dosyaları listele
            results = self.service.files().list(
                q=f"'{self.images_folder_id}' in parents",
                fields="nextPageToken, files(id, name, mimeType)"
            ).execute()
            
            items = results.get('files', [])
            
            logger.info(f"Resim klasöründe bulunan dosyalar: {[item['name'] for item in items]}")
            
            for item in items:
                file_name = item['name'].lower()
                file_id = item['id']
                
                # Resim dosyalarını indir
                if any(ext in file_name for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                    self._download_image(file_id, item['name'])
                    logger.info(f"Resim indirildi: {item['name']}")
            
        except Exception as e:
            logger.error(f"Resim indirme hatası: {str(e)}")
    
    def download_files(self):
        """Eski metod - geriye dönük uyumluluk için"""
        try:
            # Klasördeki dosyaları listele
            results = self.service.files().list(
                q=f"'{self.drive_folder_id}' in parents",
                fields="nextPageToken, files(id, name, mimeType)"
            ).execute()
            
            items = results.get('files', [])
            video_path = None
            text_content = None
            
            # Debug: Bulunan dosyaları logla
            logger.info(f"Drive klasöründe bulunan dosyalar: {[item['name'] for item in items]}")
            
            for item in items:
                file_name = item['name'].lower()
                file_id = item['id']
                logger.info(f"İşlenen dosya: {item['name']} (lowercase: {file_name})")
                
                # Video dosyasını bul ve indir
                if any(ext in file_name for ext in ['.mp4', '.avi', '.mov', '.mkv']):
                    video_path = self._download_video(file_id, item['name'])
                    logger.info(f"Video indirildi: {video_path}")
                
                # Text dosyasını bul ve oku
                elif 'video.txt' in file_name:
                    text_content = self._download_text(file_id)
                    logger.info("Text dosyası okundu")
            
            # Video dosyası Drive'da yoksa local dosyayı kullan
            if not video_path:
                local_video_path = os.path.join('data', 'input_videos', 'test_video.mp4')
                if os.path.exists(local_video_path):
                    video_path = local_video_path
                    logger.info(f"Local video dosyası kullanılıyor: {video_path}")
                else:
                    raise Exception("Video dosyası bulunamadı!")
            
            if not text_content:
                raise Exception("video.txt dosyası bulunamadı!")
            
            return video_path, text_content
            
        except Exception as e:
            logger.error(f"Drive dosya indirme hatası: {str(e)}")
            raise
    
    def _download_video(self, file_id, file_name):
        """Video dosyasını indir"""
        request = self.service.files().get_media(fileId=file_id)
        video_path = os.path.join('data', 'input_videos', file_name)
        
        with io.FileIO(video_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(f"Video indirme: {int(status.progress() * 100)}%")
        
        return video_path
    
    def _download_image(self, file_id, file_name):
        """Resim dosyasını indir"""
        request = self.service.files().get_media(fileId=file_id)
        image_path = os.path.join('data', 'images', file_name)
        
        # images klasörünü oluştur
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        
        with io.FileIO(image_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(f"Resim indirme: {int(status.progress() * 100)}%")
        
        return image_path
    
    def _download_text(self, file_id):
        """Text dosyasını oku"""
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        fh.seek(0)
        return fh.read().decode('utf-8')