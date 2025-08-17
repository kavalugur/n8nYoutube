import os
import logging
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaFileUpload
import time

logger = logging.getLogger(__name__)

class YouTubeUploader:
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube'
        ]
        self.service = self._authenticate()
        self.playlists = {}
        
    def _authenticate(self):
        """YouTube API kimlik doğrulaması"""
        creds = None
        
        # Token dosyası varsa yükle
        if os.path.exists('config/youtube_token.json'):
            creds = Credentials.from_authorized_user_file('config/youtube_token.json', self.SCOPES)
        
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
            with open('config/youtube_token.json', 'w') as token:
                token.write(creds.to_json())
        
        return build('youtube', 'v3', credentials=creds)
    
    def upload_videos(self, final_videos, translations):
        """Videoları YouTube'a yükle"""
        upload_results = {}
        
        # Her dil için playlist oluştur
        self._create_playlists(translations)
        
        for lang_code, video_data in final_videos.items():
            try:
                logger.info(f"{lang_code} videosu YouTube'a yükleniyor...")
                
                video_path = video_data['path']
                translation_data = translations[lang_code]
                
                # Video metadata'sını hazırla
                metadata = self._prepare_video_metadata(translation_data)
                
                # Videoyu yükle
                video_id = self._upload_single_video(video_path, metadata)
                
                # Playlist'e ekle
                playlist_id = self.playlists[lang_code]
                self._add_video_to_playlist(video_id, playlist_id)
                
                upload_results[lang_code] = {
                    'video_id': video_id,
                    'playlist_id': playlist_id,
                    'video_url': f'https://www.youtube.com/watch?v={video_id}',
                    'playlist_url': f'https://www.youtube.com/playlist?list={playlist_id}',
                    'status': 'success'
                }
                
                logger.info(f"{lang_code} videosu başarıyla yüklendi: {video_id}")
                
                # Rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"{lang_code} video yükleme hatası: {str(e)}")
                upload_results[lang_code] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return upload_results
    
    def _create_playlists(self, translations):
        """Her dil için playlist oluştur"""
        for lang_code, translation_data in translations.items():
            try:
                language_name = translation_data['language_name']
                playlist_title = f"Videolar - {language_name}"
                playlist_description = f"{language_name} dilinde videolar"
                
                # Playlist oluştur
                playlist_response = self.service.playlists().insert(
                    part='snippet,status',
                    body={
                        'snippet': {
                            'title': playlist_title,
                            'description': playlist_description,
                            'defaultLanguage': lang_code
                        },
                        'status': {
                            'privacyStatus': 'public'
                        }
                    }
                ).execute()
                
                playlist_id = playlist_response['id']
                self.playlists[lang_code] = playlist_id
                
                logger.info(f"{lang_code} playlist oluşturuldu: {playlist_id}")
                
            except Exception as e:
                logger.error(f"{lang_code} playlist oluşturma hatası: {str(e)}")
                raise
    
    def _prepare_video_metadata(self, translation_data):
        """Video metadata'sını hazırla"""
        text = translation_data['text']
        lang_code = translation_data['language']
        language_name = translation_data['language_name']
        
        # Başlık oluştur (ilk 100 karakter)
        title_words = text.split()[:10]
        title = ' '.join(title_words)
        if len(title) > 100:
            title = title[:97] + "..."
        
        # Açıklama oluştur
        description_templates = {
            'tr': f"""Bu videoda: {text[:300]}...

[ICERIK] Bu İçerik Hakkında:
Bu video, kaliteli içerik sunmak amacıyla hazırlanmıştır.

[SOSYAL] Sosyal Medya:
#türkçe #video #içerik #eğitim

[ZAMAN] Video Süresi: Tam içerik
[SES] Ses Kalitesi: HD
[ALTYAZI] Altyazı: Mevcut

Beğenmeyi ve abone olmayı unutmayın!""",
            
            'en': f"""In this video: {text[:300]}...

[CONTENT] About This Content:
This video has been prepared to provide quality content.

[SOCIAL] Social Media:
#english #video #content #education

[TIME] Video Duration: Full content
[AUDIO] Audio Quality: HD
[SUBTITLES] Subtitles: Available

Don't forget to like and subscribe!""",
            
            'de': f"""In diesem Video: {text[:300]}...

[INHALT] Über diesen Inhalt:
Dieses Video wurde erstellt, um qualitativ hochwertige Inhalte zu bieten.

[SOZIAL] Soziale Medien:
#deutsch #video #inhalt #bildung

[ZEIT] Videodauer: Vollständiger Inhalt
[AUDIO] Audioqualität: HD
[UNTERTITEL] Untertitel: Verfügbar

Vergessen Sie nicht zu liken und zu abonnieren!"""
        }
        
        description = description_templates.get(lang_code, text[:500])
        
        # Tags oluştur
        tags = {
            'tr': ['türkçe', 'video', 'içerik', 'eğitim', 'kaliteli'],
            'en': ['english', 'video', 'content', 'education', 'quality'],
            'de': ['deutsch', 'video', 'inhalt', 'bildung', 'qualität']
        }
        
        return {
            'title': title,
            'description': description,
            'tags': tags.get(lang_code, ['video', 'content']),
            'language': lang_code,
            'category_id': '22'  # People & Blogs
        }
    
    def _upload_single_video(self, video_path, metadata):
        """Tek video yükle"""
        try:
            # Media upload objesi oluştur
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            # Video yükleme isteği
            insert_request = self.service.videos().insert(
                part='snippet,status',
                body={
                    'snippet': {
                        'title': metadata['title'],
                        'description': metadata['description'],
                        'tags': metadata['tags'],
                        'categoryId': metadata['category_id'],
                        'defaultLanguage': metadata['language']
                    },
                    'status': {
                        'privacyStatus': 'public',
                        'selfDeclaredMadeForKids': False
                    }
                },
                media_body=media
            )
            
            # Resumable upload
            response = None
            error = None
            retry = 0
            
            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    if status:
                        logger.info(f"Yükleme: {int(status.progress() * 100)}%")
                except Exception as e:
                    error = e
                    if retry < 3:
                        retry += 1
                        time.sleep(2 ** retry)
                        continue
                    else:
                        raise
            
            if 'id' in response:
                return response['id']
            else:
                raise Exception(f"Video yükleme başarısız: {response}")
                
        except Exception as e:
            logger.error(f"Video yükleme hatası: {str(e)}")
            raise
    
    def _add_video_to_playlist(self, video_id, playlist_id):
        """Videoyu playlist'e ekle"""
        try:
            self.service.playlistItems().insert(
                part='snippet',
                body={
                    'snippet': {
                        'playlistId': playlist_id,
                        'resourceId': {
                            'kind': 'youtube#video',
                            'videoId': video_id
                        }
                    }
                }
            ).execute()
            
            logger.info(f"Video playlist'e eklendi: {video_id} -> {playlist_id}")
            
        except Exception as e:
            logger.error(f"Playlist'e ekleme hatası: {str(e)}")
            # Bu hata kritik değil, devam et
            pass