@echo off
echo ========================================
echo Video Merge Mikroservisi Baslatiyor...
echo ========================================

echo.
echo 1. Docker servisini kontrol ediliyor...
docker --version >nul 2>&1
if errorlevel 1 (
    echo HATA: Docker bulunamadi! Lutfen Docker Desktop'i kurun.
    echo https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo ✓ Docker hazir

echo.
echo 2. Mikroservis baslatiliyor...
docker-compose up -d
if errorlevel 1 (
    echo HATA: Mikroservis baslatilamadi!
    pause
    exit /b 1
)

echo.
echo 3. Servis hazir olana kadar bekleniyor...
timeout /t 10 /nobreak >nul

echo.
echo 4. Health check yapiliyor...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo UYARI: Servis henuz hazir olmayabilir. Birkaç saniye daha bekleyin.
) else (
    echo ✓ Mikroservis basariyla calisiyor!
)

echo.
echo ========================================
echo Mikroservis Bilgileri:
echo ========================================
echo Lokal URL: http://localhost:8000
echo Health Check: http://localhost:8000/health
echo.
echo Sonraki adimlar:
echo 1. Bu servis artik Google Cloud uzerinde calisiyor.
echo 2. Statik IP adresi: http://34.63.103.31:8000
echo 3. n8n workflow'undaki URL'lerin bu adres oldugundan emin olun.
echo.
echo Servisi durdurmak icin: docker-compose down
echo Loglari gormek icin: docker-compose logs -f
echo.
pause
