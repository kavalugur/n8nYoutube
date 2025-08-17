# 🎬 YouTube Çoklu Dil Video Projesi

Bu proje, Google Drive'daki videoları otomatik olarak çoklu dile çevirip, ses sentezi yaparak YouTube'a yükleyen kapsamlı bir sistemdir.

## 🚀 Özellikler

- **Otomatik Çeviri**: Türkçe metinleri İngilizce ve Almanca'ya çevirir
- **Ses Sentezi**: Her dil için doğal ses dosyaları oluşturur
- **Altyazı Senkronizasyonu**: Profesyonel kalitede altyazılar
- **Video Montajı**: FFmpeg ile yüksek kaliteli video işleme
- **YouTube Entegrasyonu**: Otomatik yükleme ve playlist oluşturma
- **Drive Entegrasyonu**: Google Drive'dan otomatik dosya indirme

## 📁 Proje Yapısı

```
YTtrae/
├── data/
│   ├── input_videos/     # Giriş videoları
│   ├── text/            # Metin dosyaları
│   ├── audio/           # Oluşturulan ses dosyaları
│   ├── subtitles/       # Altyazı dosyaları
│   ├── final_videos/    # Son videolar
│   └── logs/           # Log dosyaları
├── src/
│   ├── translation/     # Çeviri modülü
│   ├── audio_synthesis/ # Ses sentezi
│   ├── video_processing/# Video işleme
│   └── youtube_upload/  # YouTube yükleme
├── config/             # Konfigürasyon dosyaları
├── main.py            # Ana uygulama
├── requirements.txt   # Python bağımlılıkları
└── .env              # Çevre değişkenleri
```

## 🛠️ Kurulum

### 1. Bağımlılıkları Yükle

```bash
pip install -r requirements.txt
```

### 2. FFmpeg Kurulumu

Windows için:
```bash
# Chocolatey ile
choco install ffmpeg

# Veya manuel olarak https://ffmpeg.org/download.html
```

### 3. Çevre Değişkenlerini Ayarla

`.env` dosyasındaki API anahtarlarını kontrol edin.

## 🎯 Kullanım

### Temel Kullanım

```bash
python main.py
```

### Adım Adım İşlem

1. **Drive'dan İndirme**: Video ve text dosyaları otomatik indirilir
2. **Çeviri**: Metin 3 dile çevrilir (TR, EN, DE)
3. **Ses Sentezi**: Her dil için doğal ses oluşturulur
4. **Altyazı**: Senkronize altyazılar hazırlanır
5. **Video Montajı**: Ses ve altyazı ile birleştirilir
6. **YouTube Yükleme**: Otomatik yükleme ve playlist oluşturma

## 🔧 Konfigürasyon

### Video Kalitesi
```env
VIDEO_QUALITY=720p  # 480p, 720p, 1080p
AUDIO_BITRATE=128k
```

### Desteklenen Diller
```env
SUPPORTED_LANGUAGES=tr,en,de
DEFAULT_LANGUAGE=tr
```

## 📊 API Kullanımı

### Google APIs
- **Drive API**: Dosya indirme
- **Translate API**: Çeviri işlemleri
- **YouTube API**: Video yükleme

### Ücretsiz Limitler
- Google Translate: Günlük 500,000 karakter
- YouTube API: Günlük 10,000 quota
- gTTS: Sınırsız (ücretsiz)

## 🎨 Özelleştirme

### Yeni Dil Ekleme

1. `.env` dosyasında `SUPPORTED_LANGUAGES` güncelle
2. `translator.py`'de dil kodunu ekle
3. `tts_generator.py`'de ses ayarlarını ekle

### Video Kalitesi Ayarlama

`video_editor.py` dosyasında `_get_video_settings()` fonksiyonunu düzenle.

## 🚨 Sorun Giderme

### Yaygın Hatalar

1. **FFmpeg Bulunamadı**
   ```bash
   # PATH'e FFmpeg ekleyin
   ```

2. **API Quota Aşımı**
   ```
   # .env dosyasında farklı API anahtarı kullanın
   ```

3. **Video Codec Hatası**
   ```bash
   # Video formatını kontrol edin (MP4 önerilen)
   ```

## 📈 Performans

- **Çeviri**: ~2-3 saniye/dil
- **Ses Sentezi**: ~5-10 saniye/dil
- **Video İşleme**: ~30-60 saniye (video uzunluğuna bağlı)
- **YouTube Yükleme**: ~2-5 dakika (dosya boyutuna bağlı)

## 🔒 Güvenlik

- API anahtarları `.env` dosyasında saklanır
- Token dosyaları `config/` klasöründe
- Hassas bilgiler log'lanmaz

## 📝 Lisans

MIT License - Detaylar için LICENSE dosyasına bakın.

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun
3. Değişikliklerinizi commit edin
4. Pull request gönderin

## 📞 Destek

Sorularınız için issue açabilir veya dokümentasyonu inceleyebilirsiniz.

---

**Not**: Bu proje eğitim amaçlıdır. Ticari kullanım için API limitlerini kontrol edin.