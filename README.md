# Shopify POS & Inventory Backend

FastAPI tabanlı Shopify POS ve envanter yönetim sistemi. Ürün, müşteri ve sipariş verilerini yerel SQLite veritabanında önbelleğe alır ve Shopify ile senkronize eder.

## 🚀 Özellikler

- ✅ **Ürün Yönetimi**: Shopify ürünlerini yerel DB'de önbelleğe alma ve barkod ile arama
- ✅ **Müşteri Yönetimi**: Müşteri oluşturma, arama ve senkronizasyon
- ✅ **Sipariş Yönetimi**: POS siparişleri oluşturma (nakit/POS)
- ✅ **Karışık Sepet**: Barkodlu + custom ürünler aynı sipariş içinde
- ✅ **İndirim Sistemi**: Sipariş bazlı indirim uygulama
- ✅ **Webhook Desteği**: Shopify'dan gerçek zamanlı güncellemeler
- ✅ **Günlük Raporlar**: Satış istatistikleri ve raporlama

## 📋 Gereksinimler

- Python 3.13+
- Shopify mağazası ve Admin API erişimi
- Virtual environment (önerilir)

## 🛠️ Kurulum

### 1. Projeyi Klonlayın

```bash
cd /Users/baranuyukus/Desktop/kasa
```

### 2. Virtual Environment Oluşturun

```bash
python3 -m venv env
source env/bin/activate
```

### 3. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Ayarlayın

`.env` dosyası oluşturun:

```bash
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_admin_api_access_token
DATABASE_URL=sqlite:///./local.db
SHOPIFY_WEBHOOK_SECRET=your_webhook_secret  # Opsiyonel
```

### 5. Sunucuyu Başlatın

```bash
python3 main.py
```

Sunucu `http://localhost:8080` adresinde çalışacak.

## 📚 Dokümantasyon

- **API Dokümantasyonu**: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Webhook Kurulum Rehberi**: [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md)
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## 🎯 Hızlı Başlangıç

### 1. İlk Senkronizasyon

```bash
# Ürünleri senkronize et
curl -X POST http://localhost:8080/sync-products

# Müşterileri senkronize et
curl -X POST http://localhost:8080/customers/sync
```

### 2. Barkod ile Ürün Arama

```bash
curl http://localhost:8080/products/barcode/88834856
```

### 3. Sipariş Oluşturma

**Mevcut müşteri ile:**
```bash
curl -X POST http://localhost:8080/orders/create-cart \
  -H "Content-Type: application/json" \
  -d '{
    "items": [{"barcode": "88834856", "quantity": 2}],
    "payment_method": "cash",
    "email": "customer@example.com",
    "discount": 100
  }'
```

**Yeni müşteri ile:**
```bash
curl -X POST http://localhost:8080/orders/create-cart \
  -H "Content-Type: application/json" \
  -d '{
    "items": [{"barcode": "88834856", "quantity": 1}],
    "payment_method": "pos",
    "new_customer": {
      "first_name": "Ali",
      "last_name": "Veli",
      "email": "ali@example.com",
      "phone": "+905551234567"
    }
  }'
```

## 🔗 API Endpoint'leri

### Ürünler
- `POST /sync-products` - Shopify'dan ürünleri senkronize et
- `GET /products` - Tüm ürünleri listele
- `GET /products/{id}` - Ürün detayı
- `GET /products/barcode/{barcode}` - Barkod ile ara

### Müşteriler
- `POST /customers/sync` - Shopify'dan müşterileri senkronize et
- `GET /customers/search` - Email/telefon ile ara
- `POST /customers/create` - Yeni müşteri oluştur
- `GET /customers` - Tüm müşterileri listele
- `GET /customers/{id}` - Müşteri detayı

### Siparişler
- `POST /orders/create-cart` - Sepet ile sipariş oluştur
- `POST /orders/manual-create` - Manuel sipariş oluştur
- `GET /orders` - Tüm siparişleri listele
- `GET /orders/{id}` - Sipariş detayı
- `GET /orders/stats/today` - Günlük satış istatistikleri

### Webhook'lar
- `POST /webhooks/{topic}` - Shopify webhook alıcı
- `GET /webhooks/logs` - Webhook logları
- `GET /webhooks/stats` - Webhook istatistikleri

## 📊 Veritabanı Modelleri

### Product (Ürün)
```python
- id: Yerel ID
- shopify_id: Shopify variant ID
- title: Ürün adı
- barcode: Barkod
- price: Fiyat
- inventory_quantity: Stok miktarı
```

### Customer (Müşteri)
```python
- id: Yerel ID
- shopify_id: Shopify customer ID
- first_name, last_name: Ad, Soyad
- email: Email
- phone: Telefon
- address, city, country: Adres bilgileri
```

### Order (Sipariş)
```python
- id: Yerel ID
- shopify_order_id: Shopify order ID
- customer_id: Müşteri ID
- product_id: Ürün ID
- quantity: Adet
- price: Fiyat
- payment_method: Ödeme yöntemi (cash/pos)
- status: Durum
```

### WebhookEvent (Webhook Log)
```python
- id: Log ID
- topic: Webhook konusu
- shopify_id: Kaynak ID
- status: İşlem durumu
- error_message: Hata mesajı
```

## 🔒 Güvenlik

### Development (Yerel)
- HMAC webhook doğrulaması kapalı
- Kimlik doğrulama yok
- HTTP kullanımı

### Production (Önerilen)
- HMAC webhook doğrulamasını etkinleştirin
- API key veya OAuth ekleyin
- HTTPS kullanın
- Rate limiting ekleyin
- Firewall kuralları ayarlayın

## 🧪 Test

### Manuel Test
```bash
# Health check
curl http://localhost:8080/

# Ürün arama
curl http://localhost:8080/products/barcode/88834856

# Günlük satışlar
curl http://localhost:8080/orders/stats/today
```

### Python ile Test
```python
import requests

BASE_URL = "http://localhost:8080"

# Ürün ara
response = requests.get(f"{BASE_URL}/products/barcode/88834856")
print(response.json())

# Sipariş oluştur
order_data = {
    "items": [{"barcode": "88834856", "quantity": 1}],
    "payment_method": "cash",
    "email": "test@example.com"
}
response = requests.post(f"{BASE_URL}/orders/create-cart", json=order_data)
print(response.json())
```

## 📁 Proje Yapısı

```
kasa/
├── main.py              # FastAPI uygulaması ve endpoint'ler
├── database.py          # SQLAlchemy veritabanı yapılandırması
├── models.py            # Veritabanı modelleri
├── shopify.py           # Shopify API client
├── webhooks.py          # Webhook handler fonksiyonları
├── requirements.txt     # Python bağımlılıkları
├── .env                 # Ortam değişkenleri (git'e eklenmez)
├── local.db             # SQLite veritabanı (otomatik oluşturulur)
├── README.md            # Bu dosya
├── API_DOCUMENTATION.md # Detaylı API dokümantasyonu
└── WEBHOOK_SETUP.md     # Webhook kurulum rehberi
```

## 🐛 Sorun Giderme

### Sunucu Başlamıyor
```bash
# Port kullanımda mı kontrol et
lsof -i :8080

# Veritabanı dosyası izinlerini kontrol et
ls -la local.db

# Bağımlılıkları yeniden yükle
pip install -r requirements.txt --force-reinstall
```

### Shopify API Hatası
```bash
# .env dosyasını kontrol et
cat .env

# Access token'ın geçerli olduğundan emin ol
# Shopify Admin → Settings → Apps and sales channels → Develop apps
```

### Webhook Gelmiyor
```bash
# Webhook URL'sini kontrol et (HTTPS gerekli)
# ngrok kullanarak test edin:
ngrok http 8080

# Webhook loglarını kontrol et
curl http://localhost:8080/webhooks/logs?limit=20
```

## 📈 Performans İpuçları

1. **Pagination Kullanın**: Büyük veri setlerinde `limit` parametresi kullanın
2. **Webhook'ları Etkinleştirin**: Manuel sync yerine webhook kullanın
3. **Index'leri Kullanın**: Veritabanı sorguları için index'ler tanımlı
4. **Önbellek**: Sık kullanılan veriler yerel DB'de önbelleğe alınır

## 🔄 Güncelleme

```bash
# Kodu güncelleyin
git pull

# Bağımlılıkları güncelleyin
pip install -r requirements.txt --upgrade

# Veritabanını yedekleyin
cp local.db local.db.backup

# Sunucuyu yeniden başlatın
python3 main.py
```

## 📝 Changelog

### v1.0.0 (2024-11-15)
- ✅ İlk sürüm
- ✅ Ürün, müşteri, sipariş yönetimi
- ✅ Webhook desteği
- ✅ Karışık sepet sistemi
- ✅ İndirim özelliği
- ✅ Günlük satış raporları

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push yapın (`git push origin feature/amazing-feature`)
5. Pull Request açın

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 📞 İletişim

Sorularınız için:
- 📧 Email: [your-email@example.com]
- 🌐 Website: [your-website.com]

## 🙏 Teşekkürler

- FastAPI framework
- Shopify REST Admin API
- SQLAlchemy ORM

---

**Geliştirici:** [Your Name]  
**Son Güncelleme:** 15 Kasım 2024  
**Version:** 1.0.0
