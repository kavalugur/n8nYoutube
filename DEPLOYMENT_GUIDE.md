# Projeyi Google Cloud'a Taşıma Planı

Bu rehber, video birleştirme mikroservisini yerel ortamdan Google Cloud Platform'a (GCP) taşımak için adım adım talimatlar içerir.

## 1. Adım: Google Cloud Servisi ve Sanal Makine Seçimi

Projenin video işleme gibi yoğun görevleri için en uygun çözüm **Google Compute Engine (GCE)** sanal makinesidir.

### Önerilen Sanal Makine (VM) Yapılandırması:

*   **İşletim Sistemi:** **Ubuntu 22.04 LTS** (Stabil, güvenli ve Docker desteği mükemmel).
*   **Makine Tipi (Maliyet/Performans):**
    *   **Başlangıç:** `e2-medium` (2 vCPU, 4 GB RAM).
    *   **Yoğun Kullanım:** `e2-standard-2` (2 vCPU, 8 GB RAM).
*   **Depolama:** **30 GB Standart Kalıcı Disk**.
*   **Firewall:** **"HTTP trafiğine izin ver"** ve **"HTTPS trafiğine izin ver"** seçeneklerini etkinleştirin.

## 2. Adım: Sunucuyu Hazırlama ve Gerekli Yazılımları Kurma

1.  **Google Cloud Projesi Oluşturun:** Google Cloud Console'da yeni bir proje oluşturun ve faturalandırmayı etkinleştirin.
2.  **Sanal Makine (VM) Oluşturun:** Compute Engine bölümünden yukarıdaki özelliklere sahip bir VM oluşturun.
3.  **Statik IP Adresi Ayarlayın:** VM için harici bir statik IP adresi rezerve edin. Bu, IP adresinin değişmesini engeller.
4.  **Sunucuya SSH ile Bağlanın:** Google Cloud konsolu veya `gcloud` CLI ile sunucunuza bağlanın.
5.  **Sistemi Güncelleyin:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
6.  **Docker ve Docker Compose Kurulumu:**
    ```bash
    sudo apt install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    ```
7.  **Port 8000 için Firewall Kuralı Oluşturun:**
    Uygulamanızın dışarıdan erişilebilir olması için 8000 portuna izin veren bir güvenlik duvarı kuralı oluşturun. Bu komutu Google Cloud Shell üzerinden veya `gcloud` CLI'nin kurulu olduğu kendi terminalinizden çalıştırabilirsiniz.
    ```bash
    gcloud compute firewall-rules create allow-port-8000 --direction=INGRESS --priority=1000 --network=default --action=ALLOW --rules=tcp:8000 --source-ranges=0.0.0.0/0
    ```

8.  **Git Kurulumu:**
    ```bash
    sudo apt install -y git
    ```

## 3. Adım: Projeyi Sunucuya Yükleme ve Çalıştırma

Bu adım, projenizin kodunu GitHub'dan alıp Google Cloud sunucunuzda Docker ile nasıl çalıştıracağınızı detaylandırır.

### Adım 3.1: Projeyi GitHub'a Yükleme (Yerel Bilgisayarınızda)

Öncelikle, projenizin en güncel halini (yaptığımız tüm IP adresi güncellemeleri dahil) kendi bilgisayarınızdan GitHub'a gönderin.

```bash
# 1. Değişiklikleri ekleyin
git add .

# 2. Değişiklikleri bir mesajla kaydedin
git commit -m "Google Cloud dağıtımı için yapılandırma güncellendi"

# 3. GitHub'a gönderin
git push origin main
```

### Adım 3.2: Projeyi Sunucuya Klonlama (Google Cloud SSH Terminalinde)

Artık projeniz GitHub'da olduğuna göre, Google Cloud sunucunuza SSH ile bağlanın ve aşağıdaki komutlarla projeyi sunucuya çekin.

1.  **Projeyi Klonlayın:**
    ```bash
    git clone https://github.com/kavalugur/n8nYoutube.git
    cd n8nYoutube
    ```
2.  **`docker-compose.yml` Dosyasını Güncelleyin:**
    `PUBLIC_BASE_URL` ortam değişkenini sunucunuzun statik IP adresi ile güncelleyin. `nano` veya `vim` gibi bir metin düzenleyici kullanabilirsiniz.
    ```bash
    nano docker-compose.yml
    ```
    Dosyadaki ilgili satırı şu şekilde değiştirin:
    ```yaml
    environment:
      - PUBLIC_BASE_URL=http://<STATIK_IP_ADRESINIZ>:8000
    ```
3.  **Uygulamayı Docker ile Başlatın:**
    Proje klasörünün içindeyken, aşağıdaki komutu çalıştırın. Bu komut, projenizi sihirli bir şekilde çalışır hale getirecektir.
    ```bash
    sudo docker-compose up -d --build
    ```
    **Bu Komut Ne Yapar?**
    *   `sudo`: Komutu yönetici yetkileriyle çalıştırır (Docker için gereklidir).
    *   `docker-compose up`: `docker-compose.yml` dosyasını okur ve içindeki servisleri başlatır.
    *   `--build`: Başlatmadan önce, `Dockerfile`'ı kullanarak projenizin "imajını" (yani paketini) oluşturur. Bu, tüm bağımlılıkların (FFmpeg, Python kütüphaneleri vb.) kurulduğu adımdır.
    *   `-d` (Detached): Konteyneri arka planda çalıştırır. Bu sayede SSH bağlantısını kapatsanız bile uygulamanız çalışmaya devam eder.
4.  **Kontrol Edin:**
    Servisin loglarını kontrol edin:
    ```bash
    sudo docker-compose logs -f
    ```
    Tarayıcınızdan `http://<STATIK_IP_ADRESINIZ>:8000/health` adresine giderek servisin sağlık durumunu kontrol edin.

## 4. Adım: Süreklilik ve Profesyonel Erişim (İleri Seviye)

*   **Sürekli Çalışma:** `docker-compose.yml` dosyasındaki `restart: unless-stopped` ayarı, sunucu yeniden başlasa bile servisinizin otomatik olarak çalışmasını sağlar.
*   **Alan Adı (Domain) ve SSL:**
    1.  Bir alan adı alıp DNS ayarlarından sunucunuzun statik IP adresine yönlendirin.
    2.  **Nginx**'i bir reverse proxy olarak kurarak alan adınıza gelen istekleri Docker'daki servisinize (port 8000) yönlendirin.
    3.  **Let's Encrypt** ile ücretsiz SSL sertifikası kurarak bağlantınızı `https` ile güvenli hale getirin.

Bu adımları takip ederek projenizi başarıyla Google Cloud'a taşıyabilirsiniz.

---

## 5. Adım: Onaylanmış Sanal Makine Yapılandırması

Aşağıda, proje için test edilmiş ve onaylanmış sanal makine yapılandırması bulunmaktadır. Bu yapılandırma, maliyet ve performans açısından en iyi dengeyi sunar.

*   **Makine Tipi:** `e2-standard-2` (2 vCPU, 8 GB RAM)
    *   **Gerekçe:** FFmpeg ve Whisper gibi yoğun işlem gücü ve bellek gerektiren görevler için yeterli kaynak sağlar.
*   **İşletim Sistemi:** `Ubuntu 22.04 LTS Minimal`
    *   **Gerekçe:** Gereksiz paketler olmadan temiz, güvenli ve kaynakları verimli kullanan bir sistem sunar.
*   **Disk:** `30 GB Standart Kalıcı Disk`
    *   **Gerekçe:** İşletim sistemi, Docker ve geçici video dosyaları için yeterli başlangıç alanıdır.

**Önemli Not:** Bu yapılandırma esnektir. Sanal makine oluşturulduktan sonra bile **Statik IP adresi** atayabilir, makinenin CPU/RAM özelliklerini ve disk boyutunu ihtiyacınıza göre kolayca değiştirebilirsiniz.
