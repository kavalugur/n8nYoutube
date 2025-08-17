#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Merge Mikroservisi Test Script'i
Bu script mikroservisinizin doğru çalışıp çalışmadığını test eder.
"""

import requests
import json
import time
import sys

# Test konfigürasyonu
MICROSERVICE_URL = "http://34.63.103.31:8000"  # Google Cloud statik IP adresiniz

# Test için örnek Google Drive dosya URL'leri
# Bu URL'leri kendi dosyalarınızla değiştirin
TEST_VIDEO_URL = "https://drive.google.com/uc?export=download&id=16gIOjbvLyZTc3rHIIeL-0RmtDMQor4e7"
TEST_AUDIO_URL = "https://drive.google.com/uc?export=download&id=YOUR_AUDIO_FILE_ID"

def test_health():
    """Mikroservisin sağlık durumunu kontrol et"""
    print("🔍 Health check testi...")
    try:
        response = requests.get(f"{MICROSERVICE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Mikroservis çalışıyor: {data['status']}")
            print(f"   Zaman: {data['timestamp']}")
            return True
        else:
            print(f"❌ Health check başarısız: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Bağlantı hatası: {e}")
        return False

def test_process_video():
    """Video işleme testi"""
    print("\n🎬 Video işleme testi...")
    
    # Test verisi
    test_data = {
        "video_url": TEST_VIDEO_URL,
        "audio_url": TEST_AUDIO_URL,
        "soft_subtitles": True,
        "burn_subtitles": False,
        "audio_offset_ms": 0,
        "subtitle_language": "tr",
        "volume": 1.0
    }
    
    print(f"📤 İstek gönderiliyor...")
    print(f"   Video URL: {test_data['video_url'][:50]}...")
    print(f"   Audio URL: {test_data['audio_url'][:50]}...")
    
    try:
        response = requests.post(
            f"{MICROSERVICE_URL}/process",
            json=test_data,
            timeout=900  # 15 dakika timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Video işleme başarılı!")
            print(f"   Process ID: {result['process_id']}")
            print(f"   Download URL: {result['download_url']}")
            if result.get('srt_url'):
                print(f"   SRT URL: {result['srt_url']}")
            print(f"   Dil: {result['subtitle_language']}")
            return result
        else:
            print(f"❌ Video işleme başarısız: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Hata: {error_data.get('error', 'Bilinmeyen hata')}")
            except:
                print(f"   Ham yanıt: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ İstek zaman aşımına uğradı (15 dakika)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ İstek hatası: {e}")
        return None

def test_download(download_url):
    """İndirme URL'ini test et"""
    print(f"\n📥 İndirme testi...")
    print(f"   URL: {download_url}")
    
    try:
        # Sadece HEAD request ile dosya varlığını kontrol et
        response = requests.head(download_url, timeout=30)
        if response.status_code == 200:
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                print(f"✅ Dosya hazır, boyut: {size_mb:.2f} MB")
            else:
                print("✅ Dosya hazır")
            return True
        else:
            print(f"❌ Dosya indirme başarısız: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ İndirme testi hatası: {e}")
        return False

def main():
    """Ana test fonksiyonu"""
    print("🚀 Video Merge Mikroservisi Test Başlıyor...")
    print(f"📍 Mikroservis URL: {MICROSERVICE_URL}")
    print("=" * 60)
    
    # 1. Health check
    if not test_health():
        print("\n❌ Mikroservis çalışmıyor. Lütfen servisi başlatın.")
        print("\n💡 Başlatma komutları:")
        print("   Docker: docker-compose up -d")
        print("   Python: python video_merge_service.py")
        sys.exit(1)
    
    # 2. Video işleme testi
    if TEST_AUDIO_URL == "https://drive.google.com/uc?export=download&id=YOUR_AUDIO_FILE_ID":
        print("\n⚠️  Test için gerçek audio URL'i gerekli!")
        print("   TEST_AUDIO_URL değişkenini güncelleyin.")
        return
    
    result = test_process_video()
    if not result:
        print("\n❌ Video işleme testi başarısız.")
        return
    
    # 3. İndirme testi
    if result.get('download_url'):
        test_download(result['download_url'])
    
    # 4. SRT testi
    if result.get('srt_url'):
        print("\n📝 SRT dosyası testi...")
        test_download(result['srt_url'])
    
    print("\n" + "=" * 60)
    print("🎉 Tüm testler tamamlandı!")
    print("\n📋 Sonraki adımlar:")
    print("1. ngrok ile mikroservisi yayınlayın")
    print("2. n8n workflow'unda ngrok URL'ini güncelleyin")
    print("3. Workflow'u test edin")
    print("4. VPS'e taşıyın")

if __name__ == "__main__":
    main()
