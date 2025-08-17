import os
import logging
from deep_translator import GoogleTranslator
import deepl
import time
import re

logger = logging.getLogger(__name__)

class Translator:
    def __init__(self):
        # deep_translator kullanımı için translator objesi oluşturmaya gerek yok
        self.supported_languages = os.getenv('SUPPORTED_LANGUAGES', 'tr,en,de').split(',')
        
        # DeepL translator'ı başlat
        deepl_api_key = os.getenv('DEEPL_API_KEY')
        if deepl_api_key:
            self.deepl_translator = deepl.Translator(deepl_api_key)
            logger.info("DeepL translator başlatıldı")
        else:
            self.deepl_translator = None
            logger.warning("DeepL API key bulunamadı, Google Translate kullanılacak")
        
    def translate_text(self, text):
        """Metni desteklenen dillere çevir"""
        translations = {}
        
        # Orijinal Türkçe metni ekle
        translations['tr'] = {
            'text': text,
            'language': 'tr',
            'language_name': 'Türkçe'
        }
        
        # Diğer dillere çevir
        for lang_code in self.supported_languages:
            if lang_code == 'tr':  # Türkçe zaten var
                continue
                
            try:
                logger.info(f"Metin {lang_code} diline çevriliyor...")
                
                # DeepL kullanarak çevir
                if self.deepl_translator:
                    translated_text = self._translate_with_deepl(text, lang_code)
                else:
                    # Fallback: Google Translate kullan
                    chunks = self._split_text(text, max_length=4500)
                    translated_chunks = []
                    
                    for chunk in chunks:
                        # Rate limiting
                        time.sleep(0.5)
                        
                        translated = GoogleTranslator(source='tr', target=lang_code).translate(chunk)
                        translated_chunks.append(translated)
                    
                    translated_text = ' '.join(translated_chunks)
                
                # Post-processing: Çeviri kalitesini artır
                translated_text = self._improve_translation(translated_text, lang_code)
                
                translations[lang_code] = {
                    'text': translated_text,
                    'language': lang_code,
                    'language_name': self._get_language_name(lang_code)
                }
                
                logger.info(f"{lang_code} çevirisi tamamlandı")
                
            except Exception as e:
                logger.error(f"{lang_code} çeviri hatası: {str(e)}")
                # Hata durumunda orijinal metni kullan
                translations[lang_code] = {
                    'text': text,
                    'language': lang_code,
                    'language_name': self._get_language_name(lang_code)
                }
        
        return translations
    
    def _split_text(self, text, max_length=4500):
        """Metni parçalara böl"""
        if len(text) <= max_length:
            return [text]
        
        # Cümle sonlarında böl
        sentences = re.split(r'[.!?]+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk + sentence) <= max_length:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _improve_translation(self, text, lang_code):
        """Çeviri kalitesini artır"""
        # Dil özelinde düzeltmeler
        if lang_code == 'en':
            # İngilizce için yaygın düzeltmeler
            text = re.sub(r'\bi\b', 'I', text)  # 'i' -> 'I'
            text = re.sub(r'\bim\b', "I'm", text, flags=re.IGNORECASE)
            
        elif lang_code == 'de':
            # Almanca için büyük harf düzeltmeleri
            words = text.split()
            corrected_words = []
            for word in words:
                # Almanca'da isimler büyük harfle başlar
                if len(word) > 3 and word.islower():
                    # Basit isim tespiti (geliştirilmesi gerekebilir)
                    if any(ending in word for ending in ['ung', 'heit', 'keit', 'schaft']):
                        word = word.capitalize()
                corrected_words.append(word)
            text = ' '.join(corrected_words)
        
        # Genel düzeltmeler
        text = re.sub(r'\s+', ' ', text)  # Fazla boşlukları temizle
        text = text.strip()
        
        return text
    
    def _translate_with_deepl(self, text, target_lang):
        """DeepL ile metni çevir"""
        try:
            # DeepL dil kodlarını dönüştür
            deepl_lang_map = {
                'en': 'EN',
                'de': 'DE',
                'fr': 'FR',
                'es': 'ES',
                'it': 'IT',
                'pt': 'PT',
                'ru': 'RU',
                'ja': 'JA',
                'zh': 'ZH'
            }
            
            deepl_target = deepl_lang_map.get(target_lang, target_lang.upper())
            
            # DeepL ile çevir
            result = self.deepl_translator.translate_text(text, target_lang=deepl_target)
            translated_text = result.text
            
            logger.info(f"DeepL ile {target_lang} çevirisi tamamlandı")
            return translated_text
            
        except Exception as e:
            logger.error(f"DeepL çeviri hatası ({target_lang}): {str(e)}")
            # Hata durumunda Google Translate'e fallback
            return GoogleTranslator(source='tr', target=target_lang).translate(text)
    
    def _get_language_name(self, lang_code):
        """Dil kodundan dil adını al"""
        language_names = {
            'tr': 'Türkçe',
            'en': 'English',
            'de': 'Deutsch'
        }
        return language_names.get(lang_code, lang_code)
    
    def generate_video_metadata(self, text, lang_code):
        """Video için başlık ve açıklama oluştur"""
        try:
            # Metinden anahtar kelimeleri çıkar
            words = text.split()
            title_words = words[:8]  # İlk 8 kelime
            title = ' '.join(title_words)
            
            if len(title) > 100:
                title = title[:97] + "..."
            
            # Açıklama oluştur
            description_template = {
                'tr': f"Bu videoda: {text[:200]}...\n\n#türkçe #video #içerik",
                'en': f"In this video: {text[:200]}...\n\n#english #video #content",
                'de': f"In diesem Video: {text[:200]}...\n\n#deutsch #video #inhalt"
            }
            
            description = description_template.get(lang_code, text[:200])
            
            return {
                'title': title,
                'description': description
            }
            
        except Exception as e:
            logger.error(f"Metadata oluşturma hatası: {str(e)}")
            return {
                'title': f"Video - {self._get_language_name(lang_code)}",
                'description': text[:200] if len(text) > 200 else text
            }