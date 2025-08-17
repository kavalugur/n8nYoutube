import os
import logging
from gtts import gTTS
from pydub import AudioSegment
from pydub.silence import split_on_silence
from pydub.utils import which
import srt
from datetime import timedelta
import re
from .audio_segmenter import AudioSegmenter

logger = logging.getLogger(__name__)

# FFmpeg yolunu manuel olarak ayarla
ffmpeg_path = r"C:\Users\ugurkaval\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1.1-full_build\bin"
if os.path.exists(ffmpeg_path):
    # Ortam değişkenini ayarla
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")
    # Pydub için manuel yol ayarla
    AudioSegment.converter = os.path.join(ffmpeg_path, "ffmpeg.exe")
    AudioSegment.ffmpeg = os.path.join(ffmpeg_path, "ffmpeg.exe")
    AudioSegment.ffprobe = os.path.join(ffmpeg_path, "ffprobe.exe")

class TTSGenerator:
    def __init__(self):
        self.audio_bitrate = os.getenv('AUDIO_BITRATE', '128k')
        self.audio_dir = 'data/audio'
        self.subtitle_dir = 'data/subtitles'
        
        # Gerekli dizinleri oluştur
        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.subtitle_dir, exist_ok=True)
        
        self.segmenter = AudioSegmenter(output_dir=self.audio_dir)
        
    def generate_segmented_audio_files(self, translations):
        """Her dil için cümle bazlı segmentli ses dosyaları oluştur - ElevenLabs optimize edilmiş"""
        audio_files = {}
        
        # ElevenLabs kullanım durumunu kontrol et
        if self.segmenter.use_elevenlabs:
            logger.info("[TTS] ElevenLabs TTS ile ses dosyaları oluşturuluyor...")
        else:
            logger.info("[TTS] Google TTS ile ses dosyaları oluşturuluyor...")
        
        for lang_code, translation_data in translations.items():
            try:
                logger.info(f"{lang_code.upper()} için cümle bazlı segmentli ses dosyası oluşturuluyor...")
                
                text = translation_data['text']
                
                # Metni cümlelere böl
                sentences = self._split_into_sentences(text)
                logger.info(f"{lang_code.upper()} - {len(sentences)} cümle tespit edildi")
                
                # AudioSegmenter ile cümle bazlı ses oluştur
                segmentation_result = self.segmenter.create_segmented_audio_with_timing(
                    sentences=sentences,
                    language=lang_code,
                    output_filename_base='audio'
                )
                
                audio_files[lang_code] = {
                    'path': segmentation_result['audio_path'],
                    'json_path': segmentation_result['json_path'],
                    'duration': segmentation_result['total_duration'],
                    'segments': segmentation_result['segments'],
                    'language': lang_code,
                    'total_segments': len(segmentation_result['segments']),
                    'tts_engine': 'ElevenLabs' if self.segmenter.use_elevenlabs else 'Google TTS'
                }
                
                logger.info(f"[BASARILI] {lang_code.upper()} segmentli ses dosyası oluşturuldu: {segmentation_result['audio_path']}")
                logger.info(f"[JSON] {lang_code.upper()} zamanlama JSON'u: {segmentation_result['json_path']}")
                logger.info(f"[SURE] {lang_code.upper()} toplam süre: {segmentation_result['total_duration']:.2f} saniye")
                
            except Exception as e:
                logger.error(f"❌ {lang_code.upper()} segmentli ses oluşturma hatası: {str(e)}")
                raise
        
        # Özet bilgi
        total_duration = sum(audio['duration'] for audio in audio_files.values())
        logger.info(f"[TTS] Toplam {len(audio_files)} dil için ses dosyaları oluşturuldu")
        logger.info(f"[SURE] Toplam ses süresi: {total_duration:.2f} saniye")
        
        return audio_files
    
    def generate_perfect_synchronized_subtitles(self, audio_files):
        """JSON zamanlama verilerinden mükemmel senkronize altyazılar oluştur"""
        subtitle_files = {}
        
        for lang_code, audio_data in audio_files.items():
            try:
                logger.info(f"{lang_code} için mükemmel senkronize altyazı oluşturuluyor...")
                
                json_path = audio_data['json_path']
                
                # Altyazı dosyası oluştur
                subtitle_path = os.path.join(self.subtitle_dir, f'subtitle_{lang_code}.srt')
                self.segmenter.create_synchronized_subtitles_from_json(json_path, subtitle_path)
                
                # Mükemmel senkronizasyon kalitesini doğrula
                validation = self.segmenter.validate_perfect_synchronization(json_path)
                
                subtitle_files[lang_code] = {
                    'path': subtitle_path,
                    'json_path': json_path,
                    'language': lang_code,
                    'total_segments': audio_data['total_segments'],
                    'synchronization_quality': validation,
                    'is_perfectly_synchronized': validation.get('is_perfectly_synchronized', False),
                    'success_rate': validation.get('success_rate', 0)
                }
                
                if validation.get('is_perfectly_synchronized', False):
                    logger.info(f"{lang_code} altyazı %{validation.get('success_rate', 0):.1f} başarı oranıyla mükemmel senkronizasyonla oluşturuldu: {subtitle_path}")
                else:
                    logger.warning(f"{lang_code} altyazı oluşturuldu ancak senkronizasyon uyarısı var: {subtitle_path}")
                    logger.warning(f"Süre farkı: {validation.get('duration_difference', 'N/A')} saniye")
                
            except Exception as e:
                logger.error(f"{lang_code} altyazı oluşturma hatası: {str(e)}")
                raise
        
        return subtitle_files
    
    def get_timing_data(self, lang_code, audio_files):
        """Belirli bir dil için zamanlama verilerini al"""
        try:
            if lang_code in audio_files:
                json_path = audio_files[lang_code]['json_path']
                return self.segmenter.get_timing_data(json_path)
            return None
        except Exception as e:
            logger.error(f"{lang_code} zamanlama verisi alma hatası: {str(e)}")
            return None
    
    def get_all_timing_data(self, audio_files):
        """Tüm diller için zamanlama verilerini al"""
        timing_data = {}
        for lang_code in audio_files:
            timing_data[lang_code] = self.get_timing_data(lang_code, audio_files)
        return timing_data
    
    def create_complete_audio_package(self, translations):
        """Tüm diller için ses, altyazı ve zamanlama verilerini içeren tam paket oluştur"""
        try:
            logger.info("Tüm diller için tam ses paketi oluşturuluyor...")
            
            # Segmentli ses dosyaları oluştur
            audio_files = self.generate_segmented_audio_files(translations)
            
            # Mükemmel senkronize altyazılar oluştur
            subtitle_files = self.generate_perfect_synchronized_subtitles(audio_files)
            
            # Tüm zamanlama verilerini al
            timing_data = self.get_all_timing_data(audio_files)
            
            complete_package = {
                'audio_files': audio_files,
                'subtitle_files': subtitle_files,
                'timing_data': timing_data,
                'languages': list(translations.keys()),
                'total_languages': len(translations),
                'package_created_at': self._get_timestamp()
            }
            
            logger.info(f"Tam ses paketi başarıyla oluşturuldu: {len(translations)} dil")
            return complete_package
            
        except Exception as e:
            logger.error(f"Tam ses paketi oluşturma hatası: {str(e)}")
            raise
    
    def _get_timestamp(self):
        """Zaman damgası al"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _split_into_sentences(self, text):
        """Metni cümlelere böl"""
        import re
        
        # Cümle sonlarını belirten işaretler
        sentence_endings = r'[.!?]+'
        
        # Metni cümlelere böl
        sentences = re.split(sentence_endings, text)
        
        # Boş cümleleri kaldır ve temizle
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences