import os
import logging
import whisper
import google.generativeai as genai
import deepl
from moviepy.editor import VideoFileClip
from dotenv import load_dotenv
from src.drive_manager import DriveManager
from src.translation.translator import Translator
from src.audio_synthesis.tts_generator import TTSGenerator
from src.video_processing.video_editor import VideoEditor
from src.youtube_upload.uploader import YouTubeUploader

# Load environment variables
load_dotenv()

# Log klasörünü oluştur
os.makedirs('data/logs', exist_ok=True)

# Setup logging with UTF-8 encoding for Windows
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOG_FILE', 'data/logs/app.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Windows terminal için encoding ayarı
import sys
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

logger = logging.getLogger(__name__)

class YouTubeMultiLangProject:
    def __init__(self):
        """Projeyi başlat ve gerekli servisleri yapılandır"""
        logger.info("YouTube Multi-Language Project baslatiliyor...")
        
        try:
            # Whisper modelini yükle
            logger.info("Whisper modeli yukleniyor...")
            self.whisper_model = whisper.load_model("base")
            logger.info("Whisper modeli basariyla yuklendi")
        except Exception as e:
            logger.error(f"Whisper model yukleme hatasi: {str(e)}")
            raise
        
        try:
            # Gemini AI'yi yapılandır
            gemini_api_key = os.getenv('GEMINI_API_KEY')
            if not gemini_api_key:
                raise ValueError("GEMINI_API_KEY ortam degiskeni bulunamadi")
            genai.configure(api_key=gemini_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            logger.info("Gemini AI basariyla yapilandirildi")
        except Exception as e:
            logger.error(f"Gemini AI yapillandirma hatasi: {str(e)}")
            raise
        
        try:
            # DeepL çeviriciyi yapılandır
            deepl_api_key = os.getenv('DEEPL_API_KEY')
            if not deepl_api_key:
                raise ValueError("DEEPL_API_KEY ortam degiskeni bulunamadi")
            self.deepl_translator = deepl.Translator(deepl_api_key)
            logger.info("DeepL cevirici basariyla yapilandirildi")
        except Exception as e:
            logger.error(f"DeepL yapillandirma hatasi: {str(e)}")
            raise
        
        try:
            # Diğer servisleri başlat
            self.drive_manager = DriveManager()
            self.translator = Translator()
            self.tts_generator = TTSGenerator()
            self.video_editor = VideoEditor()
            self.youtube_uploader = YouTubeUploader()
            logger.info("Tum servisler basariyla baslatildi")
        except Exception as e:
            logger.error(f"Servis baslatma hatasi: {str(e)}")
            raise
        
        # Klasör yapısını oluştur
        self._create_folder_structure()
        
    def run_complete_pipeline(self):
        """Ana proje pipeline'ını çalıştırır"""
        try:
            logger.info("YouTube Coklu Dil Projesi Baslatiliyor...")
            
            # 1. Drive'dan dosyaları indir (video ve resimler)
            logger.info("1. Adim: Drive'dan dosyalar indiriliyor...")
            video_path = self.drive_manager.download_video_and_images()
            if not video_path:
                logger.error("Video indirilemedi")
                return None
            
            if not os.path.exists(video_path):
                logger.error(f"Video dosyasi bulunamadi: {video_path}")
                return None
            
            # 2. Videodan ses boşluklarını kaldır
            logger.info("2. Adim: Video ses bosluklari kesiliyor...")
            processed_video_path = self._remove_silence_from_video(video_path)
            
            # 3. Speech to text ile transkript elde et
            logger.info("3. Adim: Videodan transkript olusturuluyor...")
            transcript = self._extract_transcript(processed_video_path)
            if not transcript or len(transcript.strip()) == 0:
                logger.error("Transkript olusturulamadi veya bos")
                return None
            
            # 4. AI ile metni düzenle
            logger.info("4. Adim: Metin AI ile duzenleniyor...")
            enhanced_text_tr = self._enhance_text_with_ai(transcript)
            
            # 5. Türkçe metni kaydet
            logger.info("5. Adim: Turkce metin kaydediliyor...")
            self._save_text_file(enhanced_text_tr, 'tr', 'video_ai_tr.txt')
            
            # 6. DeepL ile çeviri yap
            logger.info("6. Adim: Metin DeepL ile cevriliyor...")
            enhanced_text_en = self._translate_with_deepl(enhanced_text_tr, 'EN-US')
            enhanced_text_de = self._translate_with_deepl(enhanced_text_tr, 'DE')
            
            # Çeviri kontrolü
            if not enhanced_text_en or len(enhanced_text_en.strip()) == 0:
                logger.warning("EN cevirisi bos, orijinal metin kullaniliyor")
                enhanced_text_en = enhanced_text_tr
            
            if not enhanced_text_de or len(enhanced_text_de.strip()) == 0:
                logger.warning("DE cevirisi bos, orijinal metin kullaniliyor")
                enhanced_text_de = enhanced_text_tr
            
            # 7. Çevrilmiş metinleri kaydet
            logger.info("7. Adim: Cevrilmis metinler kaydediliyor...")
            self._save_text_file(enhanced_text_en, 'en', 'video_ai_en.txt')
            self._save_text_file(enhanced_text_de, 'de', 'video_ai_de.txt')
            
            # 8. Çeviri sözlüğü oluştur
            translations = {
                'tr': {'text': enhanced_text_tr, 'language': 'tr', 'language_name': 'Türkçe'},
                'en': {'text': enhanced_text_en, 'language': 'en', 'language_name': 'English'},
                'de': {'text': enhanced_text_de, 'language': 'de', 'language_name': 'Deutsch'}
            }
            
            # 9. Tam ses paketi oluştur (ses + altyazı + zamanlama)
            logger.info("8. Adim: Segmentli ses dosyalari ve mukemmel senkronize altyazilar olusturuluyor...")
            try:
                complete_package = self.tts_generator.create_complete_audio_package(translations)
                
                audio_files = complete_package['audio_files']
                subtitle_files = complete_package['subtitle_files']
                timing_data = complete_package['timing_data']
            except Exception as e:
                logger.error(f"Ses paketi olusturma hatasi: {str(e)}")
                return None
            
            # 10. Videoları montajla
            logger.info("9. Adim: Videolar montajlaniyor...")
            try:
                final_videos = self.video_editor.create_multilang_videos(
                    processed_video_path, audio_files, subtitle_files
                )
                
                # Oluşturulan videoları kontrol et
                for lang, video_data in final_videos.items():
                    video_file = video_data.get('path', '')
                    if video_file and os.path.exists(video_file):
                        file_size = os.path.getsize(video_file) / (1024 * 1024)  # MB cinsinden
                        logger.info(f"{lang.upper()} video oluşturuldu: {video_file} ({file_size:.2f} MB)")
                    else:
                        logger.error(f"{lang.upper()} video dosyası oluşturulamadı: {video_file}")
                        
            except Exception as e:
                logger.error(f"Video montaj hatasi: {str(e)}")
                logger.error(f"Hata detayi: {type(e).__name__}")
                # Hata olsa bile devam et, çünkü videolar oluşmuş olabilir
                final_videos = {}
                # Çıktı dizinindeki videoları kontrol et
                video_output_dir = 'data/video'
                if os.path.exists(video_output_dir):
                    for file in os.listdir(video_output_dir):
                        if file.endswith('.mp4'):
                            video_path_check = os.path.join(video_output_dir, file)
                            # Dosya adından dili çıkarmaya çalış
                            if '_tr.' in file or '_turkish' in file.lower():
                                final_videos['tr'] = {'path': video_path_check}
                            elif '_en.' in file or '_english' in file.lower():
                                final_videos['en'] = {'path': video_path_check}
                            elif '_de.' in file or '_german' in file.lower():
                                final_videos['de'] = {'path': video_path_check}
                            logger.info(f"Mevcut video bulundu: {video_path_check}")
                
                if not final_videos:
                    logger.error("Hiçbir video dosyası bulunamadı. İşlem durduruluyor.")
                    return None
                else:
                    logger.info(f"Hata olmasına rağmen {len(final_videos)} video dosyası bulundu, devam ediliyor.")
            
            # 11. YouTube'a yükle
            logger.info("10. Adim: YouTube'a yukleniyor...")
            upload_results = {}
            for lang in translations.keys():
                try:
                    if lang in final_videos:
                        logger.info(f"{lang.upper()} dili için YouTube yüklemesi başlatılıyor...")
                        upload_result = self.youtube_uploader.upload_videos(
                            {lang: final_videos[lang]}, {lang: translations[lang]}
                        )
                        if upload_result and lang in upload_result:
                            upload_results[lang] = upload_result[lang]
                            logger.info(f"{lang.upper()} YouTube yüklemesi başarılı: {upload_result[lang].get('video_url', 'URL yok')}")
                        else:
                            logger.warning(f"{lang.upper()} YouTube yüklemesi sonucu alınamadı")
                    else:
                        logger.warning(f"{lang.upper()} dili için video dosyası bulunamadı, YouTube yüklemesi atlanıyor")
                except Exception as e:
                    logger.error(f"{lang.upper()} YouTube yukleme hatasi: {str(e)}")
                    logger.error(f"Hata detayi: {type(e).__name__}")
                    # YouTube yükleme hatası kritik değil, diğer dillere devam et
                    continue
            
            # 12. Google Sheets'e logla
            logger.info("11. Adim: Google Sheets'e loglaniyor...")
            try:
                self._log_to_google_sheets(upload_results, translations, final_videos)
                logger.info("Google Sheets loglama başarılı")
            except Exception as e:
                logger.error(f"Google Sheets loglama hatasi: {str(e)}")
                logger.error(f"Hata detayi: {type(e).__name__}")
                # Bu hata kritik değil, devam et
                logger.info("Google Sheets loglama başarısız oldu ama işlem devam ediyor")
            
            # Sonuç özeti
            successful_uploads = len(upload_results)
            total_languages = len(translations)
            
            logger.info("Proje basariyla tamamlandi!")
            logger.info(f"Toplam dil: {total_languages}")
            logger.info(f"Basarili yuklemeler: {successful_uploads} ({list(upload_results.keys())})")
            logger.info(f"Basari orani: {(successful_uploads/total_languages)*100:.1f}%")
            
            if successful_uploads == 0:
                logger.warning("Hiçbir video YouTube'a yüklenemedi!")
            elif successful_uploads < total_languages:
                logger.warning(f"Bazı videolar yüklenemedi. Başarısız: {total_languages - successful_uploads}")
            
            return upload_results
            
        except Exception as e:
            logger.error(f"Proje hatasi: {str(e)}")
            raise
    
    def _create_folder_structure(self):
        """Gerekli klasör yapısını oluştur"""
        folders = [
            'data/text/tr',
            'data/text/en', 
            'data/text/de',
            'data/images',
            'data/audio',
            'data/video',
            'data/logs'
        ]
        
        for folder in folders:
            try:
                os.makedirs(folder, exist_ok=True)
                logger.info(f"Klasör oluşturuldu: {folder}")
            except Exception as e:
                logger.error(f"Klasör oluşturma hatasi ({folder}): {str(e)}")
                raise
    
    def _remove_silence_from_video(self, video_path):
        """Videodan ses boşluklarını kaldır"""
        try:
            logger.info("Video ses bosluklari kesiliyor...")
            
            # Video yükle
            video = VideoFileClip(video_path)
            
            # Ses boşluklarını tespit et ve kaldır
            # Basit implementasyon - geliştirilmesi gerekebilir
            audio = video.audio
            
            # Ses seviyesi düşük olan kısımları tespit et
            # Bu kısım daha gelişmiş algoritma gerektirebilir
            processed_video_path = video_path.replace('.mp4', '_processed.mp4')
            
            # Şimdilik orijinal videoyu döndür - ses kesme algoritması eklenebilir
            video.close()
            return video_path
            
        except Exception as e:
            logger.error(f"Video ses kesme hatasi: {str(e)}")
            return video_path
    
    def _extract_transcript(self, video_path):
        """Whisper ile videodan transkript çıkar"""
        try:
            logger.info("Whisper ile transkript olusturuluyor...")
            
            # Whisper ile transkript oluştur
            result = self.whisper_model.transcribe(video_path, language='tr')
            transcript = result['text']
            
            logger.info(f"Transkript olusturuldu: {len(transcript)} karakter")
            return transcript
            
        except Exception as e:
            logger.error(f"Transkript olusturma hatasi: {str(e)}")
            raise
    
    def _enhance_text_with_ai(self, text):
        """Gemini AI ile metni düzenle"""
        try:
            logger.info("Metin Gemini AI ile duzenleniyor...")
            
            prompt = f"""
            İçeriği doğal ve kültürel uyuma uygun şekilde yeniden yaz. 
            Metni YouTube videosu için optimize et. Metni daha akıcı, anlaşılır ve ilgi çekici hale getir.
            Gramer hatalarını düzelt, cümle yapılarını iyileştir ve içeriği daha profesyonel hale getir.
            Orijinal anlamı koruyarak metni geliştir.
            
            ÖNEMLİ TTS KURALLARI:
            - Sadece düz metin kullan. Hiçbir markdown formatı (**, ##, *, _, #, `, ~) kullanma.
            - Parantez kullanma, bunun yerine virgül veya tire kullan.
            - Büyük harflerle yazılmış kelimeler kullanma (BÜYÜK HARF yerine normal yazım).
            - Avoid using special characters like hashtags, asterisks, underscores, backticks, tildes, brackets, and curly braces
            - Ses sentezi için doğal ve akıcı cümleler kur.
            - Kısaltmalar yerine tam kelimeler kullan.
            - Sayıları yazı ile yaz (3 yerine üç).
            
            Metin:
            {text}
            
            Düzenlenmiş metin:
            """
            
            response = self.gemini_model.generate_content(prompt)
            enhanced_text = response.text.strip()
            
            # Markdown formatlarını temizle
            enhanced_text = self._clean_text_for_tts(enhanced_text)
            
            logger.info(f"Metin AI ile duzenlendi: {len(enhanced_text)} karakter")
            return enhanced_text
            
        except Exception as e:
            logger.error(f"AI metin duzenleme hatasi: {str(e)}")
            # Hata durumunda orijinal metni döndür
            return text
    
    def _translate_with_deepl(self, text, target_language):
        """DeepL ile metni çevir"""
        try:
            logger.info(f"DeepL ile {target_language} diline cevriliyor...")
            
            result = self.deepl_translator.translate_text(text, target_lang=target_language)
            translated_text = result.text
            
            logger.info(f"{target_language} cevirisi tamamlandi: {len(translated_text)} karakter")
            return translated_text
            
        except Exception as e:
            logger.error(f"DeepL ceviri hatasi ({target_language}): {str(e)}")
            # Hata durumunda orijinal metni döndür
            return text
    
    def _clean_text_for_tts(self, text):
        """TTS için metni temizle - markdown formatlarını ve TTS için uygun olmayan karakterleri kaldır"""
        import re
        
        # Markdown formatlarını temizle
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **bold** -> bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # *italic* -> italic
        text = re.sub(r'_(.*?)_', r'\1', text)        # _underline_ -> underline
        text = re.sub(r'#{1,6}\s*', '', text)         # ## başlık -> başlık
        text = re.sub(r'`(.*?)`', r'\1', text)        # `code` -> code
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # [link](url) -> link
        
        # TTS için uygun olmayan karakterleri temizle
        text = re.sub(r'[#*_`~\[\]{}]', '', text)     # Özel karakterleri kaldır
        text = re.sub(r'\(([^)]+)\)', r'\1', text)      # Parantezleri kaldır ama içeriği koru
        
        # Büyük harfle yazılmış kelimeleri normal hale getir (2+ büyük harf yan yana)
        def normalize_caps(match):
            word = match.group(0)
            if len(word) > 1:  # 2+ karakter büyük harfse
                return word.capitalize()  # İlk harfi büyük, diğerleri küçük
            return word
        
        text = re.sub(r'\b[A-ZÜĞŞÇÖI]{2,}\b', normalize_caps, text)
        
        # Çoklu boşlukları tek boşluğa çevir
        text = re.sub(r'\s+', ' ', text)
        
        # Başlangıç ve sondaki boşlukları temizle
        text = text.strip()
        
        return text
    
    def _save_text_file(self, text, language, filename):
        """Metni dosyaya kaydet"""
        try:
            file_path = os.path.join('data', 'text', language, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            logger.info(f"{language.upper()} metni kaydedildi: {file_path}")
            
        except Exception as e:
            logger.error(f"Metin kaydetme hatasi ({language}): {str(e)}")
    
    def _log_to_google_sheets(self, upload_results, translations, final_videos):
        """YouTube yükleme sonuçlarını Google Sheets'e logla"""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            import datetime
            
            # Service account credentials
            credentials = Credentials.from_service_account_file(
                'atomic-affinity-466211-m1-846745504e96.json',
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            # Google Sheets client
            gc = gspread.authorize(credentials)
            
            # Spreadsheet açma (ID'yi .env'den al)
            spreadsheet_id = os.getenv('GOOGLE_SHEETS_ID', '1YourSpreadsheetID')
            try:
                sheet = gc.open_by_key(spreadsheet_id).sheet1
            except:
                # Eğer spreadsheet yoksa yeni oluştur
                spreadsheet = gc.create('YouTube Video Upload Logs')
                sheet = spreadsheet.sheet1
                # Header ekle
                sheet.append_row([
                    'Tarih', 'Saat', 'Dil', 'Video ID', 'Video URL', 
                    'Playlist ID', 'Playlist URL', 'Durum', 'Hata Mesajı',
                    'Video Dosyası', 'Ses Dosyası', 'Altyazı Dosyası'
                ])
                logger.info(f"Yeni spreadsheet oluşturuldu: {spreadsheet.url}")
            
            # Her dil için log ekle
            now = datetime.datetime.now()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H:%M:%S')
            
            for lang_code in translations.keys():
                if lang_code in upload_results:
                    result = upload_results[lang_code]
                    video_data = final_videos.get(lang_code, {})
                    
                    row_data = [
                        date_str,
                        time_str,
                        translations[lang_code]['language_name'],
                        result.get('video_id', ''),
                        result.get('video_url', ''),
                        result.get('playlist_id', ''),
                        result.get('playlist_url', ''),
                        result.get('status', 'unknown'),
                        result.get('error', ''),
                        video_data.get('path', ''),
                        video_data.get('audio_path', ''),
                        video_data.get('subtitle_path', '')
                    ]
                    
                    sheet.append_row(row_data)
                    logger.info(f"{lang_code} için Google Sheets'e log eklendi")
                else:
                    # Başarısız yükleme için log
                    row_data = [
                        date_str,
                        time_str,
                        translations[lang_code]['language_name'],
                        '',
                        '',
                        '',
                        '',
                        'failed',
                        'Upload failed',
                        final_videos.get(lang_code, {}).get('path', ''),
                        final_videos.get(lang_code, {}).get('audio_path', ''),
                        final_videos.get(lang_code, {}).get('subtitle_path', '')
                    ]
                    
                    sheet.append_row(row_data)
                    logger.info(f"{lang_code} için başarısız yükleme Google Sheets'e loglandı")
            
            logger.info("Google Sheets loglama tamamlandı")
            
        except ImportError:
            logger.warning("gspread kütüphanesi bulunamadı. Google Sheets loglama atlanıyor.")
            logger.info("Kurulum için: pip install gspread")
        except Exception as e:
            logger.error(f"Google Sheets loglama hatası: {str(e)}")
            raise

if __name__ == "__main__":
    try:
        logger.info("Uygulama baslatiliyor...")
        project = YouTubeMultiLangProject()
        result = project.run_complete_pipeline()
        
        if result:
            logger.info("Uygulama basariyla tamamlandi!")
        else:
            logger.error("Uygulama basarisiz oldu")
            
    except KeyboardInterrupt:
        logger.info("Uygulama kullanici tarafindan durduruldu")
    except Exception as e:
        logger.error(f"Uygulama hatasi: {str(e)}")
        raise