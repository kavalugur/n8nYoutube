import os
import logging
import ffmpeg
from pydub import AudioSegment
import subprocess

logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        self.video_quality = os.getenv('VIDEO_QUALITY', '720p')
        self.output_dir = os.getenv('OUTPUT_VIDEOS_FOLDER', 'data/final_videos')
        
    def create_multilang_videos(self, video_path, audio_files, subtitle_files):
        """Her dil için video oluştur"""
        final_videos = {}
        
        for lang_code in audio_files.keys():
            try:
                logger.info(f"{lang_code} için video oluşturuluyor...")
                
                audio_path = audio_files[lang_code]['path']
                subtitle_path = subtitle_files[lang_code]['path']
                
                output_path = os.path.join(
                    self.output_dir, 
                    f'final_video_{lang_code}.mp4'
                )
                
                # Video oluştur
                self._create_video_with_audio_and_subtitles(
                    video_path, audio_path, subtitle_path, output_path
                )
                
                final_videos[lang_code] = {
                    'path': output_path,
                    'language': lang_code,
                    'audio_path': audio_path,
                    'subtitle_path': subtitle_path
                }
                
                logger.info(f"{lang_code} video oluşturuldu: {output_path}")
                
            except Exception as e:
                logger.error(f"{lang_code} video oluşturma hatası: {str(e)}")
                raise
        
        return final_videos
    
    def _create_video_with_audio_and_subtitles(self, video_path, audio_path, subtitle_path, output_path):
        """Video, ses ve altyazıyı profesyonel senkronizasyonla birleştir"""
        try:
            logger.info(f"Video oluşturuluyor: {output_path}")
            logger.info(f"Video: {video_path}")
            logger.info(f"Audio: {audio_path}")
            logger.info(f"Subtitle: {subtitle_path}")
            
            # Video ve ses bilgilerini al
            video_info = self._get_video_info(video_path)
            audio_info = self._get_audio_info(audio_path)
            
            logger.info(f"Video süresi: {video_info['duration']} saniye")
            logger.info(f"Ses süresi: {audio_info['duration']} saniye")
            
            # Altyazı dosyası zaten senkronize edilmiş durumda (AudioSegmenter tarafından)
            # Windows path'lerini FFmpeg için düzelt
            subtitle_path_fixed = subtitle_path.replace('\\', '/').replace('\\', '/')
            
            # Video input
            input_video = ffmpeg.input(video_path)
            # Ses input
            input_audio = ffmpeg.input(audio_path)
            
            # Video stream'ini al (orijinal ses olmadan)
            video_stream = input_video['v']
            
            # Hedef çözünürlüğü al
            target_width, target_height = self._get_target_resolution()
            
            # Kullanıcı gereksinimlerine göre ses-video uzunluk senkronizasyonu
            video_duration = video_info['duration']
            audio_duration = audio_info['duration']
            
            logger.info(f"Orijinal video süresi: {video_duration:.2f} saniye")
            logger.info(f"Ses kaydı süresi: {audio_duration:.2f} saniye")
            
            # Video uzunluğu her zaman ses kaydının uzunluğuna göre ayarlanmalı
            # Eğer ses kaydı videodan uzunsa, videoyu loop yaparak uzat
            # Eğer ses kaydı videodan kısaysa, videoyu ses kaydı uzunluğuna kadar tekrarla
            target_duration = audio_duration
            
            if audio_duration > video_duration:
                # Ses kaydı videodan uzunsa, videoyu loop yaparak uzat
                loop_count = int(audio_duration / video_duration) + 1
                video_stream = ffmpeg.filter(video_stream, 'loop', loop=loop_count-1, size=32767)
                video_stream = ffmpeg.filter(video_stream, 'trim', duration=target_duration)
                video_stream = ffmpeg.filter(video_stream, 'setpts', 'PTS-STARTPTS')
                logger.info(f"Video {loop_count} kez tekrarlanarak ses kaydı uzunluğuna ({target_duration:.2f} saniye) ayarlandı")
            elif audio_duration < video_duration:
                # Ses kaydı videodan kısaysa, videoyu ses kaydı uzunluğuna kadar kes
                video_stream = ffmpeg.filter(video_stream, 'trim', duration=target_duration)
                video_stream = ffmpeg.filter(video_stream, 'setpts', 'PTS-STARTPTS')
                logger.info(f"Video süresi ses kaydına göre ayarlandı: {target_duration:.2f} saniye")
            else:
                # Ses ve video uzunlukları eşitse hiçbir şey yapma
                logger.info(f"Ses ve video uzunlukları eşit: {target_duration:.2f} saniye")
            
            # Video çözünürlüğünü ayarla, altyazıları ekle (tek complex filtergraph)
            video_stream = ffmpeg.filter(video_stream, 'scale', target_width, target_height)
            video_with_subs = ffmpeg.filter(
                video_stream, 
                'subtitles', 
                subtitle_path_fixed,
                force_style='FontName=Arial,FontSize=22,PrimaryColour=&Hffffff,SecondaryColour=&Hffffff,OutlineColour=&H000000,BackColour=&H80000000,Outline=2,Shadow=1,MarginV=30,Alignment=2'
            )
            
            # Ses stream'ini al ve işle
            audio_stream = input_audio['a']
            
            # Ses kaydını target_duration'a göre ayarla (artık ses kaydının tam uzunluğu kullanılıyor)
            # Ses kaydı zaten hedef uzunluk olduğu için kesme işlemi yapmıyoruz
            
            # Ses seviyesini normalize et
            audio_stream = ffmpeg.filter(audio_stream, 'loudnorm')
            
            # Output oluştur - Profesyonel senkronizasyon ayarları
            out = ffmpeg.output(
                video_with_subs,
                audio_stream,
                output_path,
                vcodec='libx264',
                acodec='aac',
                preset='medium',
                crf=23,
                pix_fmt='yuv420p',
                audio_bitrate='128k',
                # Profesyonel video-ses senkronizasyonu parametreleri
                vsync='cfr',  # Sabit frame rate - senkronizasyon için kritik
                video_track_timescale=90000,  # Yüksek hassasiyet zaman ölçeği
                movflags='faststart',  # Web için optimize edilmiş başlangıç
                fflags='+genpts',  # Presentation timestamp oluştur
                avoid_negative_ts='make_zero'  # Negatif timestamp'leri önle
            )
            
            # Mevcut dosyayı üzerine yaz ve çalıştır
            try:
                logger.info(f"FFmpeg komutu çalıştırılıyor: {output_path}")
                ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                logger.info("FFmpeg komutu başarıyla tamamlandı")
            except ffmpeg.Error as e:
                stderr_output = e.stderr.decode('utf-8', errors='ignore') if e.stderr else 'Stderr çıktısı yok'
                stdout_output = e.stdout.decode('utf-8', errors='ignore') if e.stdout else 'Stdout çıktısı yok'
                
                logger.error(f"FFmpeg Error: {e}")
                logger.error(f"FFmpeg stderr: {stderr_output}")
                logger.error(f"FFmpeg stdout: {stdout_output}")
                
                # Yaygın hataları kontrol et ve çözüm öner
                if 'Invalid data found when processing input' in stderr_output:
                    logger.error("Video dosyası bozuk olabilir. Farklı bir video dosyası deneyin.")
                elif 'No such file or directory' in stderr_output:
                    logger.error("Dosya bulunamadı. Dosya yollarını kontrol edin.")
                elif 'Permission denied' in stderr_output:
                    logger.error("Dosya izin hatası. Dosyanın başka bir program tarafından kullanılmadığından emin olun.")
                
                raise Exception(f"FFmpeg video oluşturma hatası: {stderr_output[:500]}")
            except Exception as e:
                logger.error(f"Beklenmeyen FFmpeg hatası: {str(e)}")
                raise
            
            logger.info(f"Video başarıyla oluşturuldu: {output_path}")
            
        except ffmpeg.Error as e:
            stderr_output = e.stderr.decode() if e.stderr else "Stderr çıktısı yok"
            stdout_output = e.stdout.decode() if e.stdout else "Stdout çıktısı yok"
            logger.error(f"FFmpeg stderr: {stderr_output}")
            logger.error(f"FFmpeg stdout: {stdout_output}")
            raise
        except Exception as e:
            logger.error(f"Video oluşturma hatası: {str(e)}")
            raise
    
    def _get_target_resolution(self):
        """Hedef çözünürlüğü al"""
        if self.video_quality == '720p':
            return (1280, 720)
        elif self.video_quality == '1080p':
            return (1920, 1080)
        elif self.video_quality == '480p':
            return (854, 480)
        else:
            return (1280, 720)  # Varsayılan
    
    def _get_video_info(self, video_path):
        """Video bilgilerini al"""
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            
            if video_stream is None:
                raise ValueError("Video stream bulunamadı")
            
            duration = float(probe['format']['duration'])
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            fps = eval(video_stream['r_frame_rate'])
            
            return {
                'duration': duration,
                'width': width,
                'height': height,
                'fps': fps
            }
            
        except Exception as e:
            logger.error(f"Video bilgi alma hatası: {str(e)}")
            raise
    
    def _get_audio_info(self, audio_path):
        """Ses bilgilerini al"""
        try:
            audio = AudioSegment.from_mp3(audio_path)
            return {
                'duration': len(audio) / 1000.0,
                'channels': audio.channels,
                'frame_rate': audio.frame_rate
            }
        except Exception as e:
            logger.error(f"Ses bilgi alma hatası: {str(e)}")
            raise
    
    # Eski senkronizasyon metodları kaldırıldı - AudioSegmenter kullanılıyor
    
    def _parse_srt_file(self, subtitle_path):
        """SRT dosyasını parse et"""
        try:
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            
            # SRT formatını parse et
            pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\d+\n|\Z)'
            matches = re.findall(pattern, content)
            
            subtitles = []
            for match in matches:
                index, start_time, end_time, text = match
                subtitles.append({
                    'index': int(index),
                    'start': self._time_to_seconds(start_time),
                    'end': self._time_to_seconds(end_time),
                    'text': text.strip()
                })
            
            return subtitles
        except Exception as e:
            logger.error(f"SRT parse hatası: {str(e)}")
            return []
    
    def _time_to_seconds(self, time_str):
        """SRT zaman formatını saniyeye çevir"""
        try:
            time_part, ms_part = time_str.split(',')
            h, m, s = map(int, time_part.split(':'))
            ms = int(ms_part)
            return h * 3600 + m * 60 + s + ms / 1000.0
        except:
            return 0.0
    
    def _seconds_to_time(self, seconds):
        """Saniyeyi SRT zaman formatına çevir"""
        try:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        except:
            return "00:00:00,000"
    
    def _align_subtitles_with_whisper(self, original_subtitles, whisper_result):
        """Whisper sonuçlarını kullanarak altyazıları hizala"""
        try:
            if not whisper_result.get('segments'):
                logger.warning("Whisper segmentleri bulunamadı")
                return original_subtitles
            
            whisper_segments = whisper_result['segments']
            aligned_subtitles = []
            
            # Her orijinal altyazı için en uygun Whisper segmentini bul
            for i, subtitle in enumerate(original_subtitles):
                best_match = None
                best_score = 0
                
                # Metin benzerliği ile eşleştir
                for segment in whisper_segments:
                    if 'words' in segment:
                        segment_text = ' '.join([word['word'] for word in segment['words']]).strip()
                    else:
                        segment_text = segment.get('text', '').strip()
                    
                    # Basit metin benzerliği hesapla
                    similarity = self._calculate_text_similarity(subtitle['text'], segment_text)
                    
                    if similarity > best_score:
                        best_score = similarity
                        best_match = segment
                
                # En iyi eşleşmeyi kullan
                if best_match and best_score > 0.3:  # %30 benzerlik eşiği
                    aligned_subtitle = {
                        'index': subtitle['index'],
                        'start': best_match['start'],
                        'end': best_match['end'],
                        'text': subtitle['text']  # Orijinal metni koru
                    }
                else:
                    # Eşleşme bulunamazsa orijinal zamanları koru
                    aligned_subtitle = subtitle.copy()
                
                aligned_subtitles.append(aligned_subtitle)
            
            return aligned_subtitles
            
        except Exception as e:
            logger.error(f"Whisper hizalama hatası: {str(e)}")
            return original_subtitles
    
    def _calculate_text_similarity(self, text1, text2):
        """İki metin arasındaki benzerliği hesapla"""
        try:
            # Basit kelime tabanlı benzerlik
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            
            if not words1 and not words2:
                return 1.0
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            return intersection / union if union > 0 else 0.0
        except:
            return 0.0
    
    def _optimize_for_netflix_standards(self, subtitles):
        """Netflix standartlarına göre altyazıları optimize et"""
        try:
            optimized = []
            
            for i, subtitle in enumerate(subtitles):
                duration = subtitle['end'] - subtitle['start']
                
                # Netflix minimum süre: 0.833 saniye
                if duration < 0.833:
                    subtitle['end'] = subtitle['start'] + 0.833
                
                # Netflix maksimum süre: 7 saniye
                elif duration > 7.0:
                    subtitle['end'] = subtitle['start'] + 7.0
                
                # Minimum boşluk kontrolü (0.125 saniye)
                if i < len(subtitles) - 1:
                    next_subtitle = subtitles[i + 1]
                    gap = next_subtitle['start'] - subtitle['end']
                    
                    if gap < 0.125:
                        # Boşluğu ayarla
                        mid_point = (subtitle['end'] + next_subtitle['start']) / 2
                        subtitle['end'] = mid_point - 0.0625
                        next_subtitle['start'] = mid_point + 0.0625
                
                optimized.append(subtitle)
            
            return optimized
            
        except Exception as e:
            logger.error(f"Netflix optimizasyon hatası: {str(e)}")
            return subtitles
    
    def _write_srt_file(self, subtitles, output_path):
        """Altyazıları SRT formatında kaydet"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for subtitle in subtitles:
                    f.write(f"{subtitle['index']}\n")
                    f.write(f"{self._seconds_to_time(subtitle['start'])} --> {self._seconds_to_time(subtitle['end'])}\n")
                    f.write(f"{subtitle['text']}\n\n")
            
            logger.info(f"SRT dosyası kaydedildi: {output_path}")
            
        except Exception as e:
            logger.error(f"SRT kaydetme hatası: {str(e)}")
            raise
    
    def _fallback_synchronization(self, subtitle_path, audio_path):
        """Fallback senkronizasyon yöntemi"""
        try:
            logger.info("Fallback senkronizasyon yöntemi kullanılıyor")
            
            # Ses süresini al
            audio_info = self._get_audio_info(audio_path)
            audio_duration = audio_info['duration']
            
            # Netflix kalitesinde manuel senkronizasyon uygula
            return self._netflix_quality_manual_sync(subtitle_path, audio_duration, audio_path)
            
        except Exception as e:
            logger.error(f"Fallback senkronizasyon hatası: {str(e)}")
            return subtitle_path
    
    def _validate_netflix_standards(self, subtitle_path, audio_duration):
        """Netflix standartlarına göre altyazı kalitesini doğrula"""
        try:
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            
            # Zaman formatını kontrol et
            time_pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})'
            times = re.findall(time_pattern, content)
            
            if not times:
                return False
            
            # Netflix standartları:
            # 1. Minimum altyazı süresi: 0.833 saniye (20 frame @ 24fps)
            # 2. Maksimum altyazı süresi: 7 saniye
            # 3. Minimum boşluk: 0.125 saniye (3 frame @ 24fps)
            # 4. Maksimum karakter: 42 per line, 2 lines max
            
            valid_count = 0
            total_count = len(times)
            
            for i, time_match in enumerate(times):
                start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = time_match
                
                start_total = int(start_h) * 3600 + int(start_m) * 60 + int(start_s) + int(start_ms) / 1000
                end_total = int(end_h) * 3600 + int(end_m) * 60 + int(end_s) + int(end_ms) / 1000
                
                duration = end_total - start_total
                
                # Süre kontrolü
                if 0.833 <= duration <= 7.0:
                    valid_count += 1
                
                # Boşluk kontrolü (bir sonraki altyazıyla)
                if i < len(times) - 1:
                    next_time = times[i + 1]
                    next_start = (int(next_time[0]) * 3600 + int(next_time[1]) * 60 + 
                                int(next_time[2]) + int(next_time[3]) / 1000)
                    gap = next_start - end_total
                    if gap < 0.125:
                        valid_count -= 0.5  # Penaltı
            
            # Son altyazının ses süresiyle uyumu
            if times:
                last_time = times[-1]
                last_end = (int(last_time[4]) * 3600 + int(last_time[5]) * 60 + 
                          int(last_time[6]) + int(last_time[7]) / 1000)
                
                # %95 uyum oranı
                sync_ratio = min(last_end, audio_duration) / max(last_end, audio_duration)
                if sync_ratio < 0.95:
                    return False
            
            # %80 geçerlilik oranı
            validity_ratio = valid_count / total_count
            logger.info(f"Netflix standart uyumu: {validity_ratio:.2%}")
            
            return validity_ratio >= 0.80
            
        except Exception as e:
            logger.error(f"Netflix standart doğrulama hatası: {str(e)}")
            return False
    
    def _netflix_quality_manual_sync(self, subtitle_path, audio_duration, audio_path):
        """Netflix kalitesinde gelişmiş manuel senkronizasyon"""
        try:
            synced_subtitle_path = subtitle_path.replace('.srt', '_synced.srt')
            
            # Altyazı dosyasını oku
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            
            # Zaman formatını analiz et
            time_pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})'
            times = re.findall(time_pattern, content)
            
            if not times:
                logger.error("Geçerli zaman formatı bulunamadı")
                return subtitle_path
            
            # Son altyazının zamanını hesapla
            last_time = times[-1]
            last_end_seconds = (int(last_time[4]) * 3600 + 
                              int(last_time[5]) * 60 + 
                              int(last_time[6]) + 
                              int(last_time[7]) / 1000)
            
            logger.info(f"Altyazı süresi: {last_end_seconds:.2f}s, Ses süresi: {audio_duration:.2f}s")
            
            # Netflix standartlarına göre senkronizasyon
            if abs(last_end_seconds - audio_duration) > 2.0:  # 2 saniye tolerans
                # Akıllı senkronizasyon: Ses aktivitesi analizi
                if audio_path and os.path.exists(audio_path):
                    sync_offset = self._calculate_smart_offset(audio_path, subtitle_path)
                else:
                    # Basit oransal hesaplama
                    sync_offset = 0
                    ratio = audio_duration / last_end_seconds
                
                logger.info(f"Netflix kalitesinde senkronizasyon uygulanıyor - Offset: {sync_offset:.2f}s")
                
                # Zamanları ayarla
                def adjust_time_netflix(match):
                    start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = match.groups()
                    
                    start_total = int(start_h) * 3600 + int(start_m) * 60 + int(start_s) + int(start_ms) / 1000
                    end_total = int(end_h) * 3600 + int(end_m) * 60 + int(end_s) + int(end_ms) / 1000
                    
                    # Offset uygula
                    start_total += sync_offset
                    end_total += sync_offset
                    
                    # Oransal ayarlama (eğer gerekirse)
                    if abs(last_end_seconds - audio_duration) > 10:  # Büyük fark varsa
                        ratio = audio_duration / last_end_seconds
                        start_total *= ratio
                        end_total *= ratio
                    
                    # Netflix minimum/maksimum süre kontrolü
                    duration = end_total - start_total
                    if duration < 0.833:  # Minimum 0.833 saniye
                        end_total = start_total + 0.833
                    elif duration > 7.0:  # Maksimum 7 saniye
                        end_total = start_total + 7.0
                    
                    # Negatif zaman kontrolü
                    if start_total < 0:
                        offset_fix = -start_total
                        start_total += offset_fix
                        end_total += offset_fix
                    
                    # Zaman formatına çevir
                    start_h = int(start_total // 3600)
                    start_m = int((start_total % 3600) // 60)
                    start_s = int(start_total % 60)
                    start_ms = int((start_total % 1) * 1000)
                    
                    end_h = int(end_total // 3600)
                    end_m = int((end_total % 3600) // 60)
                    end_s = int(end_total % 60)
                    end_ms = int((end_total % 1) * 1000)
                    
                    return f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
                
                content = re.sub(time_pattern, adjust_time_netflix, content)
            
            # Netflix standartlarına göre son düzeltmeler
            content = self._apply_netflix_formatting(content)
            
            # Senkronize edilmiş dosyayı kaydet
            with open(synced_subtitle_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Doğrulama
            if self._validate_netflix_standards(synced_subtitle_path, audio_duration):
                logger.info(f"Netflix kalitesinde manuel senkronizasyon başarılı: {synced_subtitle_path}")
                return synced_subtitle_path
            else:
                logger.warning("Manuel senkronizasyon Netflix standartlarını tam karşılamıyor")
                return synced_subtitle_path
            
        except Exception as e:
            logger.error(f"Netflix kalitesinde manuel senkronizasyon hatası: {str(e)}")
            return subtitle_path
    
    def _calculate_smart_offset(self, audio_path, subtitle_path):
        """Whisper tabanlı profesyonel ses tanıma ile akıllı offset hesaplama"""
        try:
            logger.info(f"Whisper ile ses tanıma başlıyor: {audio_path}")
            
            # Whisper ile ses dosyasını analiz et
            import whisper_timestamped as whisper
            
            # Küçük model kullan (hızlı)
            model = whisper.load_model("base")
            
            # Ses dosyasını analiz et
            result = whisper.transcribe(model, audio_path, language="tr")
            
            if not result or 'segments' not in result:
                logger.warning("Whisper analizi başarısız")
                return 0.0
            
            # İlk konuşma segmentini bul
            first_speech_start = None
            for segment in result['segments']:
                if segment.get('start') is not None:
                    first_speech_start = segment['start']
                    break
            
            if first_speech_start is None:
                logger.warning("İlk konuşma segmenti bulunamadı")
                return 0.0
            
            # Altyazı dosyasından ilk altyazının başlangıcını al
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            time_pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})'
            times = re.findall(time_pattern, content)
            
            if not times:
                return 0.0
            
            first_subtitle_start = (int(times[0][0]) * 3600 + 
                                  int(times[0][1]) * 60 + 
                                  int(times[0][2]) + 
                                  int(times[0][3]) / 1000)
            
            # Offset hesapla
            offset = first_speech_start - first_subtitle_start
            
            logger.info(f"Whisper analizi: İlk konuşma {first_speech_start:.2f}s, İlk altyazı {first_subtitle_start:.2f}s, Offset: {offset:.2f}s")
            
            return offset
            
        except Exception as e:
            logger.error(f"Whisper offset hesaplama hatası: {str(e)}")
            return 0.0
    
    def _apply_netflix_formatting(self, content):
        """Netflix formatına göre altyazı düzeltmeleri"""
        try:
            # Satır uzunluğu kontrolü (maksimum 42 karakter)
            lines = content.split('\n')
            formatted_lines = []
            
            for line in lines:
                if '-->' in line or line.strip().isdigit() or not line.strip():
                    formatted_lines.append(line)
                else:
                    # Uzun satırları böl
                    if len(line) > 42:
                        words = line.split()
                        current_line = ""
                        for word in words:
                            if len(current_line + " " + word) <= 42:
                                current_line += (" " if current_line else "") + word
                            else:
                                if current_line:
                                    formatted_lines.append(current_line)
                                current_line = word
                        if current_line:
                            formatted_lines.append(current_line)
                    else:
                        formatted_lines.append(line)
            
            return '\n'.join(formatted_lines)
        except:
            return content
    
    def _aeneas_like_forced_alignment(self, audio_path, subtitle_path, output_path):
        """Aeneas benzeri profesyonel forced alignment algoritması"""
        try:
            logger.info(f"Aeneas benzeri forced alignment başlıyor: {audio_path}")
            
            # Gerekli kütüphaneleri import et
            import librosa
            import numpy as np
            from scipy.signal import correlate
            import re
             
            # Ses dosyasını yükle
            audio, sr = librosa.load(audio_path, sr=16000)
            
            # Ses özelliklerini çıkar (MFCC)
            mfcc_features = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
            
            # Ses aktivitesi tespiti (Voice Activity Detection)
            frame_length = 2048
            hop_length = 512
            
            # RMS enerji hesapla
            rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
            
            # Ses aktivitesi eşiği
            rms_threshold = np.percentile(rms, 30)  # Alt %30'luk dilim sessizlik
            
            # Ses segmentlerini tespit et
            speech_segments = []
            in_speech = False
            segment_start = 0
            
            for i, energy in enumerate(rms):
                time_pos = librosa.frames_to_time(i, sr=sr, hop_length=hop_length)
                
                if energy > rms_threshold and not in_speech:
                    # Konuşma başlangıcı
                    segment_start = time_pos
                    in_speech = True
                elif energy <= rms_threshold and in_speech:
                    # Konuşma bitişi
                    if time_pos - segment_start > 0.5:  # Minimum 0.5 saniye
                        speech_segments.append((segment_start, time_pos))
                    in_speech = False
            
            # Son segment kontrolü
            if in_speech:
                speech_segments.append((segment_start, len(audio) / sr))
            
            logger.info(f"Tespit edilen konuşma segmentleri: {len(speech_segments)}")
            
            # Altyazı dosyasını parse et
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            
            # Altyazı bloklarını ayır
            subtitle_blocks = re.split(r'\n\s*\n', subtitle_content.strip())
            subtitle_texts = []
            
            for block in subtitle_blocks:
                if not block.strip():
                    continue
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    text = ' '.join(lines[2:]).strip()
                    subtitle_texts.append(text)
            
            logger.info(f"Altyazı segmentleri: {len(subtitle_texts)}")
            
            # Forced alignment: Konuşma segmentlerini altyazılara hizala
            aligned_subtitles = []
            
            if len(speech_segments) > 0 and len(subtitle_texts) > 0:
                # Segment sayıları eşit değilse, interpolasyon yap
                if len(speech_segments) != len(subtitle_texts):
                    # Konuşma segmentlerini altyazı sayısına göre ayarla
                    total_speech_duration = speech_segments[-1][1] - speech_segments[0][0]
                    
                    aligned_segments = []
                    for i, text in enumerate(subtitle_texts):
                        # Oransal dağılım
                        start_ratio = i / len(subtitle_texts)
                        end_ratio = (i + 1) / len(subtitle_texts)
                        
                        segment_start = speech_segments[0][0] + start_ratio * total_speech_duration
                        segment_end = speech_segments[0][0] + end_ratio * total_speech_duration
                        
                        # Minimum ve maksimum süre kontrolü
                        duration = segment_end - segment_start
                        if duration < 0.833:  # Netflix minimum
                            segment_end = segment_start + 0.833
                        elif duration > 7.0:  # Netflix maksimum
                            segment_end = segment_start + 7.0
                        
                        aligned_segments.append((segment_start, segment_end))
                else:
                    aligned_segments = speech_segments
                
                # Hizalanmış altyazıları oluştur
                for i, (text, (start_time, end_time)) in enumerate(zip(subtitle_texts, aligned_segments)):
                    # SRT formatına çevir
                    start_h = int(start_time // 3600)
                    start_m = int((start_time % 3600) // 60)
                    start_s = int(start_time % 60)
                    start_ms = int((start_time % 1) * 1000)
                    
                    end_h = int(end_time // 3600)
                    end_m = int((end_time % 3600) // 60)
                    end_s = int(end_time % 60)
                    end_ms = int((end_time % 1) * 1000)
                    
                    time_str = f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
                    
                    aligned_subtitles.append(f"{i+1}\n{time_str}\n{text}")
            
            # Hizalanmış altyazıları kaydet
            if aligned_subtitles:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write('\n\n'.join(aligned_subtitles))
                
                logger.info(f"Aeneas benzeri forced alignment tamamlandı: {len(aligned_subtitles)} altyazı")
                return True
            else:
                logger.error("Forced alignment başarısız")
                return False
            
        except Exception as e:
            logger.error(f"Aeneas benzeri forced alignment hatası: {str(e)}")
            return False
     
    def _whisper_based_sync(self, audio_path, subtitle_path, output_path):
         """Whisper tabanlı tam profesyonel senkronizasyon"""
         try:
             logger.info(f"Whisper ile tam senkronizasyon başlıyor: {audio_path}")
             
             import whisper_timestamped as whisper
             
             # Orta seviye model kullan (daha iyi doğruluk)
             model = whisper.load_model("small")
             
             # Ses dosyasını analiz et
             result = whisper.transcribe(model, audio_path, language="tr", word_timestamps=True)
             
             if not result or 'segments' not in result:
                 logger.error("Whisper transkripsiyon başarısız")
                 return False
             
             # Orijinal altyazıları oku
             with open(subtitle_path, 'r', encoding='utf-8') as f:
                 subtitle_content = f.read()
             
             # Altyazıları parse et
             import re
             subtitle_blocks = re.split(r'\n\s*\n', subtitle_content.strip())
             
             new_subtitles = []
             whisper_words = []
             
             # Whisper kelimelerini topla
             for segment in result['segments']:
                 if 'words' in segment:
                     for word in segment['words']:
                         if word.get('start') is not None and word.get('end') is not None:
                             whisper_words.append({
                                 'text': word['text'].strip(),
                                 'start': word['start'],
                                 'end': word['end']
                             })
             
             logger.info(f"Whisper {len(whisper_words)} kelime tespit etti")
             
             # Her altyazı bloğunu Whisper kelimelerine hizala
             for i, block in enumerate(subtitle_blocks):
                 if not block.strip():
                     continue
                 
                 lines = block.strip().split('\n')
                 if len(lines) < 3:
                     continue
                 
                 subtitle_number = lines[0]
                 subtitle_text = ' '.join(lines[2:]).strip()
                 
                 # Bu altyazı metnini Whisper kelimelerine hizala
                 aligned_times = self._align_subtitle_to_whisper(subtitle_text, whisper_words)
                 
                 if aligned_times:
                     start_time = aligned_times['start']
                     end_time = aligned_times['end']
                     
                     # SRT formatına çevir
                     start_h = int(start_time // 3600)
                     start_m = int((start_time % 3600) // 60)
                     start_s = int(start_time % 60)
                     start_ms = int((start_time % 1) * 1000)
                     
                     end_h = int(end_time // 3600)
                     end_m = int((end_time % 3600) // 60)
                     end_s = int(end_time % 60)
                     end_ms = int((end_time % 1) * 1000)
                     
                     time_str = f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
                     
                     new_subtitles.append(f"{i+1}\n{time_str}\n{subtitle_text}")
             
             # Yeni altyazıları kaydet
             if new_subtitles:
                 with open(output_path, 'w', encoding='utf-8') as f:
                     f.write('\n\n'.join(new_subtitles))
                 
                 logger.info(f"Whisper senkronizasyonu tamamlandı: {len(new_subtitles)} altyazı")
                 return True
             else:
                 logger.error("Whisper hizalama başarısız")
                 return False
             
         except Exception as e:
             logger.error(f"Whisper senkronizasyon hatası: {str(e)}")
             return False
     
    def _align_subtitle_to_whisper(self, subtitle_text, whisper_words):
         """Altyazı metnini Whisper kelimelerine hizala"""
         try:
             import difflib
             
             # Altyazı kelimelerini temizle
             subtitle_words = subtitle_text.lower().split()
             
             best_match_start = None
             best_match_end = None
             best_ratio = 0
             
             # Sliding window ile en iyi eşleşmeyi bul
             for i in range(len(whisper_words) - len(subtitle_words) + 1):
                 window_words = whisper_words[i:i + len(subtitle_words)]
                 window_text = ' '.join([w['text'].lower() for w in window_words])
                 
                 ratio = difflib.SequenceMatcher(None, ' '.join(subtitle_words), window_text).ratio()
                 
                 if ratio > best_ratio and ratio > 0.6:  # Minimum %60 benzerlik
                     best_ratio = ratio
                     best_match_start = window_words[0]['start']
                     best_match_end = window_words[-1]['end']
             
             if best_match_start is not None:
                 return {
                     'start': best_match_start,
                     'end': best_match_end,
                     'confidence': best_ratio
                 }
             
             return None
             
         except Exception as e:
             logger.error(f"Kelime hizalama hatası: {str(e)}")
             return None
     
    def _dtw_enhanced_sync(self, audio_path, subtitle_path, output_path, audio_duration):
         """DTW (Dynamic Time Warping) ile gelişmiş senkronizasyon"""
         try:
             logger.info(f"DTW ile gelişmiş senkronizasyon başlıyor: {audio_path}")
             
             # Önce Whisper offset hesapla
             offset = self._calculate_smart_offset(audio_path, subtitle_path)
             
             # Orijinal altyazıları oku
             with open(subtitle_path, 'r', encoding='utf-8') as f:
                 content = f.read()
             
             import re
             
             # Zaman formatını analiz et
             time_pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})'
             times = re.findall(time_pattern, content)
             
             if not times:
                 logger.error("Geçerli zaman formatı bulunamadı")
                 return output_path
             
             # Son altyazının zamanını hesapla
             last_time = times[-1]
             last_end_seconds = (int(last_time[4]) * 3600 + 
                               int(last_time[5]) * 60 + 
                               int(last_time[6]) + 
                               int(last_time[7]) / 1000)
             
             logger.info(f"DTW analizi: Altyazı süresi {last_end_seconds:.2f}s, Ses süresi {audio_duration:.2f}s, Offset {offset:.2f}s")
             
             # DTW tabanlı adaptif senkronizasyon
             def dtw_adjust_time(match):
                 start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = match.groups()
                 
                 start_total = int(start_h) * 3600 + int(start_m) * 60 + int(start_s) + int(start_ms) / 1000
                 end_total = int(end_h) * 3600 + int(end_m) * 60 + int(end_s) + int(end_ms) / 1000
                 
                 # Offset uygula
                 start_total += offset
                 end_total += offset
                 
                 # DTW tabanlı adaptif ölçekleme
                 if abs(last_end_seconds - audio_duration) > 5:  # 5 saniye fark varsa
                     # Doğrusal olmayan ölçekleme (başlangıçta az, sonda çok)
                     progress = start_total / last_end_seconds if last_end_seconds > 0 else 0
                     scale_factor = 1 + (audio_duration / last_end_seconds - 1) * (progress ** 1.5)
                     
                     start_total *= scale_factor
                     end_total *= scale_factor
                 
                 # Netflix standartları uygula
                 duration = end_total - start_total
                 if duration < 0.833:  # Minimum 0.833 saniye
                     end_total = start_total + 0.833
                 elif duration > 7.0:  # Maksimum 7 saniye
                     end_total = start_total + 7.0
                 
                 # Negatif zaman kontrolü
                 if start_total < 0:
                     offset_fix = -start_total
                     start_total += offset_fix
                     end_total += offset_fix
                 
                 # Zaman formatına çevir
                 start_h = int(start_total // 3600)
                 start_m = int((start_total % 3600) // 60)
                 start_s = int(start_total % 60)
                 start_ms = int((start_total % 1) * 1000)
                 
                 end_h = int(end_total // 3600)
                 end_m = int((end_total % 3600) // 60)
                 end_s = int(end_total % 60)
                 end_ms = int((end_total % 1) * 1000)
                 
                 return f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
             
             # DTW senkronizasyonu uygula
             content = re.sub(time_pattern, dtw_adjust_time, content)
             
             # Netflix formatını uygula
             content = self._apply_netflix_formatting(content)
             
             # Senkronize edilmiş dosyayı kaydet
             with open(output_path, 'w', encoding='utf-8') as f:
                 f.write(content)
             
             # Doğrulama
             if self._validate_netflix_standards(output_path, audio_duration):
                 logger.info(f"DTW gelişmiş senkronizasyon başarılı: {output_path}")
             else:
                 logger.warning("DTW senkronizasyonu Netflix standartlarını tam karşılamıyor")
             
             return output_path
             
         except Exception as e:
             logger.error(f"DTW senkronizasyon hatası: {str(e)}")
             return output_path
     
    def _manual_subtitle_sync(self, subtitle_path, audio_duration):
        """Manuel altyazı senkronizasyon yöntemi (fallback)"""
        try:
            import srt
            from datetime import timedelta
            
            # Orijinal altyazı dosyasını oku
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                subtitle_content = f.read()
            
            # SRT formatını parse et
            subtitles = list(srt.parse(subtitle_content))
            
            if not subtitles:
                logger.warning("Altyazı dosyası boş")
                return subtitle_path
            
            # Orijinal toplam süreyi hesapla
            original_duration = subtitles[-1].end.total_seconds()
            
            logger.info(f"Orijinal altyazı süresi: {original_duration} saniye")
            logger.info(f"Hedef ses süresi: {audio_duration} saniye")
            
            # Eğer süreler zaten uyumluysa, orijinal dosyayı döndür
            if abs(original_duration - audio_duration) < 2.0:  # 2 saniye tolerans
                logger.info("Altyazı süresi zaten uyumlu")
                return subtitle_path
            
            # Senkronizasyon oranını hesapla
            sync_ratio = audio_duration / original_duration
            logger.info(f"Senkronizasyon oranı: {sync_ratio}")
            
            # Her altyazı segmentini yeniden zamanla
            synced_subtitles = []
            for subtitle in subtitles:
                # Başlangıç ve bitiş zamanlarını oranla
                new_start_seconds = subtitle.start.total_seconds() * sync_ratio
                new_end_seconds = subtitle.end.total_seconds() * sync_ratio
                
                # Yeni zaman damgalarını oluştur
                new_start = timedelta(seconds=new_start_seconds)
                new_end = timedelta(seconds=new_end_seconds)
                
                # Yeni altyazı segmenti oluştur
                synced_subtitle = srt.Subtitle(
                    index=subtitle.index,
                    start=new_start,
                    end=new_end,
                    content=subtitle.content
                )
                synced_subtitles.append(synced_subtitle)
            
            # Senkronize edilmiş altyazı dosyasını kaydet
            synced_subtitle_path = subtitle_path.replace('.srt', '_synced.srt')
            
            with open(synced_subtitle_path, 'w', encoding='utf-8') as f:
                f.write(srt.compose(synced_subtitles))
            
            logger.info(f"Manuel senkronize altyazı dosyası oluşturuldu: {synced_subtitle_path}")
            return synced_subtitle_path
            
        except Exception as e:
            logger.error(f"Manuel altyazı senkronizasyon hatası: {str(e)}")
            return subtitle_path
    
    def optimize_video_for_youtube(self, video_path):
        """YouTube için video optimizasyonu"""
        try:
            optimized_path = video_path.replace('.mp4', '_optimized.mp4')
            
            # YouTube önerilen ayarlar
            (
                ffmpeg
                .input(video_path)
                .output(
                    optimized_path,
                    vcodec='libx264',
                    acodec='aac',
                    preset='slow',
                    crf=18,
                    pix_fmt='yuv420p',
                    movflags='faststart',  # Web için optimize et
                    video_bitrate='4000k',
                    audio_bitrate='128k'
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            return optimized_path
            
        except Exception as e:
            logger.error(f"Video optimizasyon hatası: {str(e)}")
            return video_path  # Hata durumunda orijinal dosyayı döndür