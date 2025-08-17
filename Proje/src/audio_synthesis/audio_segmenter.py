import os
import json
import logging
from pydub import AudioSegment
import srt
from datetime import timedelta
from gtts import gTTS
import tempfile
import re
from elevenlabs.client import ElevenLabs
from elevenlabs import play
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class AudioSegmenter:
    """Cümle bazlı ses segmentasyonu ve mükemmel altyazı senkronizasyonu sınıfı"""
    
    def __init__(self, output_dir="data/audio"):
        self.output_dir = output_dir
        self.segments_data = {}
        os.makedirs(output_dir, exist_ok=True)
        
        # ElevenLabs API ayarları
        self.use_elevenlabs = os.getenv('USE_ELEVENLABS_TTS', 'false').lower() == 'true'
        self.elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
        self.elevenlabs_voice_id = "GLHtjkeLJ9Rxcv9JhLmh"  # Doğa sesi Voice ID
        
        # Dil kodları eşleştirmesi (ElevenLabs için)
        self.language_mapping = {
            'tr': 'tr',  # Türkçe
            'en': 'en',  # İngilizce
            'de': 'de'   # Almanca
        }
        
        if self.use_elevenlabs and self.elevenlabs_api_key:
            self.elevenlabs_client = ElevenLabs(api_key=self.elevenlabs_api_key)
            logger.info("[TTS] ElevenLabs TTS aktif edildi")
            logger.info(f"[TTS] Kullanılan ses: {self.elevenlabs_voice_id}")
        else:
            self.elevenlabs_client = None
            logger.info("[TTS] Google TTS (gTTS) kullanılacak")
        
    def create_segmented_audio_with_timing(self, sentences, language='tr', output_filename_base='audio'):
        """Cümle bazlı ses dosyaları oluştur ve mükemmel zamanlamayı hesapla"""
        try:
            logger.info(f"Cümle bazlı ses segmentasyonu başlatılıyor - {len(sentences)} cümle")
            
            # Her cümle için ayrı ses dosyası oluştur ve gerçek sürelerini hesapla
            sentence_segments = self._create_individual_sentence_audio_files(sentences, language)
            
            # Ana ses dosyasını birleştir ve zamanlamaları hesapla
            main_audio_path, timing_data = self._combine_audio_files_with_timing(sentence_segments, output_filename_base, language)
            
            # JSON dosyasına kaydet
            json_path = self._save_timing_data_to_json(timing_data, output_filename_base, language)
            
            logger.info(f"Segmentasyon tamamlandı: {main_audio_path}")
            logger.info(f"Zamanlama verileri kaydedildi: {json_path}")
            
            return {
                'audio_path': main_audio_path,
                'json_path': json_path,
                'segments': timing_data['segments'],
                'total_duration': timing_data['total_duration']
            }
            
        except Exception as e:
            logger.error(f"Ses segmentasyon hatası: {str(e)}")
            raise
    
    def _create_individual_sentence_audio_files(self, sentences, language):
        """Her cümle için ayrı ses dosyası oluştur ve gerçek sürelerini hesapla"""
        sentence_segments = []
        temp_audio_files = []
        
        logger.info(f"Her cümle için ayrı ses dosyaları oluşturuluyor...")
        
        for i, sentence in enumerate(sentences):
            try:
                # Cümleyi temizle
                clean_sentence = sentence.strip()
                if not clean_sentence:
                    continue
                    
                logger.debug(f"Cümle {i+1}/{len(sentences)}: {clean_sentence[:50]}...")
                
                # TTS ile ses oluştur
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_audio_path = temp_file.name
                temp_file.close()
                
                if self.use_elevenlabs and self.elevenlabs_client:
                    try:
                        # ElevenLabs ile ses oluştur (yeni API)
                        audio_generator = self.elevenlabs_client.text_to_speech.convert(
                            text=clean_sentence,
                            voice_id=self.elevenlabs_voice_id,
                            model_id="eleven_multilingual_v2",
                            output_format="mp3_44100_128"
                        )
                        # Generator'dan bytes verisini topla ve dosyaya kaydet
                        with open(temp_audio_path, 'wb') as f:
                            for chunk in audio_generator:
                                if chunk:
                                    f.write(chunk)
                        logger.debug(f"ElevenLabs ile ses oluşturuldu: {clean_sentence[:30]}...")
                    except Exception as elevenlabs_error:
                        logger.warning(f"ElevenLabs hatası, gTTS'ye geçiliyor: {str(elevenlabs_error)}")
                        # ElevenLabs başarısız olursa gTTS kullan
                        tts = gTTS(text=clean_sentence, lang=language, slow=False)
                        tts.save(temp_audio_path)
                else:
                    # Google TTS kullan
                    tts = gTTS(text=clean_sentence, lang=language, slow=False)
                    tts.save(temp_audio_path)
                
                temp_audio_files.append(temp_audio_path)
                
                # Ses dosyasını yükle ve süresini hesapla
                sentence_audio = AudioSegment.from_mp3(temp_audio_path)
                duration_ms = len(sentence_audio)
                duration_seconds = duration_ms / 1000.0
                
                segment_data = {
                    'index': i + 1,
                    'text': clean_sentence,
                    'duration_seconds': round(duration_seconds, 3),
                    'duration_ms': duration_ms,
                    'audio_path': temp_audio_path,
                    'audio_segment': sentence_audio
                }
                
                sentence_segments.append(segment_data)
                logger.debug(f"Cümle {i+1} tamamlandı: {duration_seconds:.3f}s")
                
            except Exception as e:
                logger.error(f"Cümle {i+1} ses oluşturma hatası: {str(e)}")
                # Hata durumunda tahmini süre ile devam et
                estimated_duration = max(len(clean_sentence) * 0.08, 1.0)  # Min 1 saniye
                
                segment_data = {
                    'index': i + 1,
                    'text': clean_sentence,
                    'duration_seconds': round(estimated_duration, 3),
                    'duration_ms': int(estimated_duration * 1000),
                    'audio_path': None,
                    'audio_segment': None,
                    'error': str(e)
                }
                
                sentence_segments.append(segment_data)
        
        logger.info(f"Toplam {len(sentence_segments)} cümle ses dosyası oluşturuldu")
        return sentence_segments
    
    def _combine_audio_files_with_timing(self, sentence_segments, output_filename_base, language):
        """Cümle ses dosyalarını birleştir ve mükemmel zamanlamayı hesapla"""
        try:
            logger.info("Ses dosyaları birleştiriliyor ve zamanlama hesaplanıyor...")
            
            # Ana ses dosyasını oluştur
            combined_audio = AudioSegment.empty()
            timing_segments = []
            current_time = 0.0
            
            # Cümle arası sessizlik (300ms)
            silence_between_sentences = AudioSegment.silent(duration=300)
            
            for i, segment in enumerate(sentence_segments):
                if segment['audio_segment'] is None:
                    # Hata durumunda sessizlik ekle
                    error_silence = AudioSegment.silent(duration=segment['duration_ms'])
                    combined_audio += error_silence
                    
                    timing_segments.append({
                        'index': segment['index'],
                        'text': segment['text'],
                        'start_time': round(current_time, 3),
                        'end_time': round(current_time + segment['duration_seconds'], 3),
                        'duration': segment['duration_seconds'],
                        'status': 'error',
                        'error': segment.get('error', 'Unknown error')
                    })
                    
                    current_time += segment['duration_seconds']
                else:
                    # Gerçek ses dosyasını ekle
                    sentence_audio = segment['audio_segment']
                    actual_duration = len(sentence_audio) / 1000.0
                    
                    combined_audio += sentence_audio
                    
                    timing_segments.append({
                        'index': segment['index'],
                        'text': segment['text'],
                        'start_time': round(current_time, 3),
                        'end_time': round(current_time + actual_duration, 3),
                        'duration': round(actual_duration, 3),
                        'status': 'success'
                    })
                    
                    current_time += actual_duration
                
                # Cümle arası sessizlik ekle (son cümle hariç)
                if i < len(sentence_segments) - 1:
                    combined_audio += silence_between_sentences
                    current_time += 0.3  # 300ms sessizlik
            
            # Ana ses dosyasını kaydet
            output_audio_path = os.path.join(self.output_dir, f"{output_filename_base}_{language}.mp3")
            combined_audio.export(output_audio_path, format="mp3")
            
            # Zamanlama verilerini hazırla
            timing_data = {
                'language': language,
                'total_duration': round(current_time, 3),
                'total_segments': len(timing_segments),
                'audio_file': output_audio_path,
                'created_at': str(timedelta(seconds=0)),  # Şu anki zaman
                'segments': timing_segments
            }
            
            # Geçici dosyaları temizle
            self._cleanup_temp_files(sentence_segments)
            
            logger.info(f"Ana ses dosyası oluşturuldu: {output_audio_path}")
            logger.info(f"Toplam süre: {current_time:.3f} saniye")
            
            return output_audio_path, timing_data
            
        except Exception as e:
            logger.error(f"Ses birleştirme hatası: {str(e)}")
            raise
    
    def _save_timing_data_to_json(self, timing_data, output_filename_base, language):
        """Zamanlama verilerini JSON dosyasına kaydet"""
        try:
            json_filename = f"{output_filename_base}_{language}_timing.json"
            json_path = os.path.join(self.output_dir, json_filename)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(timing_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Zamanlama verileri JSON'a kaydedildi: {json_path}")
            return json_path
            
        except Exception as e:
            logger.error(f"JSON kaydetme hatası: {str(e)}")
            raise
    
    def _cleanup_temp_files(self, sentence_segments):
        """Geçici ses dosyalarını temizle"""
        try:
            for segment in sentence_segments:
                if segment.get('audio_path') and os.path.exists(segment['audio_path']):
                    os.unlink(segment['audio_path'])
            logger.debug("Geçici dosyalar temizlendi")
        except Exception as e:
            logger.warning(f"Geçici dosya temizleme hatası: {str(e)}")
    
    def create_synchronized_subtitles_from_json(self, json_path, output_path):
        """JSON zamanlama verilerinden mükemmel senkronize altyazı oluştur"""
        try:
            # JSON dosyasını oku
            with open(json_path, 'r', encoding='utf-8') as f:
                timing_data = json.load(f)
            
            subtitles = []
            
            for segment in timing_data['segments']:
                # Sadece başarılı segmentleri altyazıya ekle
                if segment.get('status') == 'success':
                    start_time = timedelta(seconds=segment['start_time'])
                    end_time = timedelta(seconds=segment['end_time'])
                    
                    subtitle = srt.Subtitle(
                        index=segment['index'],
                        start=start_time,
                        end=end_time,
                        content=segment['text']
                    )
                    
                    subtitles.append(subtitle)
            
            # SRT dosyasını kaydet
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subtitles))
            
            logger.info(f"Mükemmel senkronize altyazı dosyası oluşturuldu: {output_path}")
            logger.info(f"Toplam {len(subtitles)} altyazı segmenti oluşturuldu")
            return output_path
            
        except Exception as e:
            logger.error(f"Altyazı oluşturma hatası: {str(e)}")
            raise
    
    def create_synchronized_subtitles(self, segments, output_path):
        """Segmentlerden senkronize altyazı dosyası oluştur (eski metot - uyumluluk için)"""
        try:
            subtitles = []
            
            for segment in segments:
                start_time = timedelta(seconds=segment['start_time'])
                end_time = timedelta(seconds=segment['end_time'])
                
                subtitle = srt.Subtitle(
                    index=segment['index'],
                    start=start_time,
                    end=end_time,
                    content=segment['text']
                )
                
                subtitles.append(subtitle)
            
            # SRT dosyasını kaydet
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(subtitles))
            
            logger.info(f"Senkronize altyazı dosyası oluşturuldu: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Altyazı oluşturma hatası: {str(e)}")
            raise
    
    def validate_perfect_synchronization(self, json_path):
        """Mükemmel senkronizasyon kalitesini doğrula"""
        try:
            # JSON dosyasını oku
            with open(json_path, 'r', encoding='utf-8') as f:
                timing_data = json.load(f)
            
            # Ses dosyasını kontrol et
            audio_path = timing_data['audio_file']
            if not os.path.exists(audio_path):
                return {'is_synchronized': False, 'error': 'Ses dosyası bulunamadı'}
            
            audio = AudioSegment.from_mp3(audio_path)
            actual_audio_duration = len(audio) / 1000.0
            expected_duration = timing_data['total_duration']
            
            # Süre farkını hesapla
            duration_diff = abs(actual_audio_duration - expected_duration)
            
            # Başarılı segmentleri say
            successful_segments = [s for s in timing_data['segments'] if s.get('status') == 'success']
            error_segments = [s for s in timing_data['segments'] if s.get('status') == 'error']
            
            validation_result = {
                'is_perfectly_synchronized': duration_diff <= 0.5,  # 500ms tolerans
                'actual_audio_duration': round(actual_audio_duration, 3),
                'expected_duration': expected_duration,
                'duration_difference': round(duration_diff, 3),
                'total_segments': timing_data['total_segments'],
                'successful_segments': len(successful_segments),
                'error_segments': len(error_segments),
                'success_rate': round(len(successful_segments) / timing_data['total_segments'] * 100, 2),
                'language': timing_data['language'],
                'audio_file': audio_path,
                'json_file': json_path
            }
            
            logger.info(f"Mükemmel senkronizasyon doğrulaması: {validation_result}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Senkronizasyon doğrulama hatası: {str(e)}")
            return {'is_perfectly_synchronized': False, 'error': str(e)}
    
    def get_timing_data(self, json_path):
        """JSON dosyasından zamanlama verilerini al"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"JSON okuma hatası: {str(e)}")
            return None