# Video Montaj Mikroservisi Kurulum ve Entegrasyon Rehberi

## 📋 Genel Bakış

Bu proje, mevcut n8n workflow'unuza video montaj özelliği ekler. Mikroservis:
- Video dosyasının orijinal sesini kaldırır
- Yeni TTS ses dosyasını entegre eder
- Otomatik altyazı (SRT) oluşturur
- 3 dilde (TR/EN/DE) final videolar üretir

## 🛠️ Gereksinimler

### Sistem Gereksinimleri
- Windows 10/11
- Docker Desktop
- Python 3.10+ (opsiyonel, Docker kullanıyorsanız gerekli değil)
- FFmpeg (Docker kullanıyorsanız otomatik yüklenir)
- ngrok hesabı (ücretsiz)

### Kurulum Adımları

#### 1. Docker Desktop Kurulumu
```bash
# Docker Desktop'ı indirin ve kurun:
# https://www.docker.com/products/docker-desktop/
```

#### 2. ngrok Kurulumu
```bash
# ngrok'u indirin: https://ngrok.com/download
# Hesap oluşturun ve auth token alın
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

#### 3. Mikroservisi Başlatma

**Docker ile (Önerilen):**
```bash
# Proje dizinine gidin
cd c:\Users\ugurkaval\Desktop\n8nYoutube6

# Docker container'ı başlatın
docker-compose up -d

# Servisi kontrol edin
curl http://localhost:8000/health
```

**Python ile (Alternatif):**
```bash
# Bağımlılıkları yükleyin
pip install -r requirements.txt

# FFmpeg kurulumunu kontrol edin
ffmpeg -version

# Whisper kurulumunu kontrol edin
whisper --help

# Servisi başlatın
python video_merge_service.py
```

#### 4. ngrok Tüneli Açma
```bash
# Yeni terminal açın ve ngrok'u başlatın
ngrok http 8000

# Çıktıda gösterilen HTTPS URL'ini not alın:
# Örnek: https://abc123.ngrok-free.app
```

#### 5. Mikroservis Test Etme
```bash
# Health check
curl https://YOUR_NGROK_URL.ngrok-free.app/health

# Test request (örnek)
curl -X POST https://YOUR_NGROK_URL.ngrok-free.app/process \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://drive.google.com/uc?export=download&id=VIDEO_FILE_ID",
    "audio_url": "https://drive.google.com/uc?export=download&id=AUDIO_FILE_ID",
    "soft_subtitles": true,
    "subtitle_language": "tr"
  }'
```

## 🔧 n8n Workflow Entegrasyonu

### Adım 1: Mevcut Workflow'u Yedekleyin
1. n8n Cloud'da mevcut workflow'unuzu açın
2. "Export" butonuna tıklayın
3. JSON dosyasını kaydedin

### Adım 2: Yeni Düğümler Ekleme

#### A) Google Drive Paylaşım Düğümleri
Mevcut upload düğümlerinden sonra şu düğümleri ekleyin:

1. **Share Video Public**
   - Type: Google Drive
   - Operation: Share
   - File ID: `={{ $node['Extract File ID'].json.fileId }}`
   - Share Type: Anyone with link
   - Role: Reader

2. **Share Audio TR Public**
   - Type: Google Drive
   - Operation: Share
   - File ID: `={{ $node['Upload Audio TR to Drive'].json.id }}`
   - Share Type: Anyone with link
   - Role: Reader

3. **Share Audio EN Public** (aynı şekilde)
4. **Share Audio DE Public** (aynı şekilde)

#### B) URL Builder Düğümü
**Build Public URLs**
- Type: Set
- Values:
  ```javascript
  video_url: https://drive.google.com/uc?export=download&id={{ $node['Extract File ID'].json.fileId }}
  audio_tr_url: https://drive.google.com/uc?export=download&id={{ $node['Upload Audio TR to Drive'].json.id }}
  audio_en_url: https://drive.google.com/uc?export=download&id={{ $node['Upload Audio EN to Drive'].json.id }}
  audio_de_url: https://drive.google.com/uc?export=download&id={{ $node['Upload Audio DE to Drive'].json.id }}
  microservice_url: https://YOUR_NGROK_URL.ngrok-free.app
  ```

#### C) Video Montaj Düğümleri

1. **Merge Video TR**
   - Type: HTTP Request
   - Method: POST
   - URL: `={{ $node['Build Public URLs'].json.microservice_url }}/process`
   - Body:
     ```json
     {
       "video_url": "={{ $node['Build Public URLs'].json.video_url }}",
       "audio_url": "={{ $node['Build Public URLs'].json.audio_tr_url }}",
       "soft_subtitles": true,
       "subtitle_language": "tr",
       "volume": 1.0
     }
     ```
   - Timeout: 900000ms

2. **Merge Video EN** (aynı şekilde, audio_en_url ve language: "en")
3. **Merge Video DE** (aynı şekilde, audio_de_url ve language: "de")

#### D) İndirme ve Yükleme Düğümleri

1. **Download Merged TR**
   - Type: HTTP Request
   - Method: GET
   - URL: `={{ $json.download_url }}`
   - Response Format: File

2. **Upload Final Video TR**
   - Type: Google Drive
   - Operation: Upload
   - Name: `={{ 'video_tr_' + new Date().getTime() + '.mp4' }}`
   - Folder: İstediğiniz klasör

3. Aynı şekilde EN ve DE için de ekleyin

### Adım 3: Bağlantıları Kurma

```
Upload Audio TR to Drive → Share Audio TR Public
Upload Audio EN to Drive → Share Audio EN Public  
Upload Audio DE to Drive → Share Audio DE Public
Share Audio DE Public → Build Public URLs
Build Public URLs → [Merge Video TR, Merge Video EN, Merge Video DE]
Merge Video TR → Download Merged TR → Upload Final Video TR
Merge Video EN → Download Merged EN → Upload Final Video EN
Merge Video DE → Download Merged DE → Upload Final Video DE
```

### Adım 4: Konfigürasyon Güncellemeleri

1. **workflow_extension.json** dosyasını açın
2. `microservice_url` değerini ngrok URL'iniz ile güncelleyin
3. Google Drive klasör ID'lerini kontrol edin
4. Credential ID'lerini mevcut workflow'unuzla eşleştirin

## 🧪 Test Etme

### Lokal Test
1. Mikroservisi başlatın
2. ngrok tünelini açın
3. n8n workflow'unda ngrok URL'ini güncelleyin
4. Workflow'u manuel olarak çalıştırın
5. Logları kontrol edin:
   ```bash
   docker-compose logs -f video-merge-service
   ```

### Hata Ayıklama

**Yaygın Sorunlar:**

1. **FFmpeg bulunamadı**
   ```bash
   # Docker container'ında kontrol edin
   docker exec -it n8nyoutube6_video-merge-service_1 ffmpeg -version
   ```

2. **Google Drive erişim hatası**
   - Dosyaların public olarak paylaşıldığından emin olun
   - URL formatını kontrol edin

3. **Timeout hataları**
   - n8n'de timeout değerini artırın (900000ms)
   - Video boyutunu kontrol edin

4. **ngrok bağlantı hatası**
   - ngrok'un çalıştığından emin olun
   - URL'in doğru olduğunu kontrol edin

## 🚀 VPS'e Taşıma

Lokal testler başarılı olduktan sonra:

1. **VPS Hazırlığı**
   ```bash
   # VPS'e Docker kurulumu
   sudo apt update
   sudo apt install docker.io docker-compose
   
   # Proje dosyalarını VPS'e kopyalayın
   scp -r . user@your-vps:/path/to/project
   ```

2. **VPS'de Çalıştırma**
   ```bash
   # VPS'de
   cd /path/to/project
   docker-compose up -d
   
   # Nginx reverse proxy kurulumu (opsiyonel)
   # SSL sertifikası ile HTTPS
   ```

3. **n8n Workflow Güncelleme**
   - ngrok URL'ini VPS IP/domain ile değiştirin
   - Güvenlik için API key ekleyin

## 📊 Performans Optimizasyonu

- **Video kalitesi**: FFmpeg CRF değerini ayarlayın (23 = iyi kalite)
- **İşlem hızı**: FFmpeg preset'ini değiştirin (fast/medium/slow)
- **Disk alanı**: Geçici dosyaları otomatik temizleyin
- **Bellek**: Docker container'ına bellek limiti ekleyin

## 🔒 Güvenlik

- API endpoint'lerine authentication ekleyin
- Rate limiting uygulayın
- Dosya boyutu limitlerini ayarlayın
- VPS'de firewall kuralları ekleyin

## 📝 Notlar

- Her video işlemi 5-15 dakika sürebilir
- Disk alanını düzenli kontrol edin
- Logları düzenli olarak temizleyin
- Backup stratejisi oluşturun

## 🆘 Destek

Sorun yaşarsanız:
1. Logları kontrol edin
2. Health endpoint'ini test edin
3. Google Drive izinlerini kontrol edin
4. FFmpeg ve Whisper kurulumlarını doğrulayın