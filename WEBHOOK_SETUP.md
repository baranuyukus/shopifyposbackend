# Shopify Webhook Kurulum Rehberi

Bu rehber, Shopify mağazanızdan FastAPI backend'inize gerçek zamanlı webhook'ları nasıl kuracağınızı gösterir.

## 🎯 Webhook'lar Nedir?

Webhook'lar, Shopify'da bir olay gerçekleştiğinde (ürün oluşturma, sipariş verme vb.) Shopify'ın backend'inize otomatik olarak bildirim göndermesini sağlar. Bu sayede:

- ✅ Manuel `/sync` çağrılarına gerek kalmaz
- ✅ Veriler gerçek zamanlı olarak güncellenir
- ✅ Stok değişiklikleri anında yansır
- ✅ Yeni müşteriler ve siparişler otomatik kaydedilir

## 📡 Desteklenen Webhook Konuları

Backend'imiz şu webhook'ları destekler:

### Ürün Webhook'ları
- `products/create` - Yeni ürün oluşturulduğunda
- `products/update` - Ürün güncellendiğinde
- `products/delete` - Ürün silindiğinde

### Stok Webhook'ları
- `inventory_levels/update` - Stok miktarı değiştiğinde

### Müşteri Webhook'ları
- `customers/create` - Yeni müşteri oluşturulduğunda
- `customers/update` - Müşteri bilgileri güncellendiğinde

### Sipariş Webhook'ları
- `orders/create` - Yeni sipariş oluşturulduğunda
- `orders/paid` - Sipariş ödendiğinde
- `orders/cancelled` - Sipariş iptal edildiğinde

## 🛠️ Shopify Admin'de Webhook Kurulumu

### Adım 1: Shopify Admin'e Giriş Yapın

1. Shopify Admin paneline gidin: `https://[your-store].myshopify.com/admin`
2. Sol menüden **Settings** (Ayarlar) → **Notifications** (Bildirimler) seçin
3. Sayfayı aşağı kaydırın ve **Webhooks** bölümünü bulun

### Adım 2: Webhook Oluşturma

Her webhook için aşağıdaki adımları tekrarlayın:

1. **"Create webhook"** butonuna tıklayın
2. Aşağıdaki bilgileri girin:

#### Ürün Oluşturma Webhook'u
```
Event: Product creation
Format: JSON
URL: https://[your-domain]/webhooks/products/create
API version: 2024-10
```

#### Ürün Güncelleme Webhook'u
```
Event: Product update
Format: JSON
URL: https://[your-domain]/webhooks/products/update
API version: 2024-10
```

#### Ürün Silme Webhook'u
```
Event: Product deletion
Format: JSON
URL: https://[your-domain]/webhooks/products/delete
API version: 2024-10
```

#### Stok Güncelleme Webhook'u
```
Event: Inventory level update
Format: JSON
URL: https://[your-domain]/webhooks/inventory_levels/update
API version: 2024-10
```

#### Müşteri Oluşturma Webhook'u
```
Event: Customer creation
Format: JSON
URL: https://[your-domain]/webhooks/customers/create
API version: 2024-10
```

#### Müşteri Güncelleme Webhook'u
```
Event: Customer update
Format: JSON
URL: https://[your-domain]/webhooks/customers/update
API version: 2024-10
```

#### Sipariş Oluşturma Webhook'u
```
Event: Order creation
Format: JSON
URL: https://[your-domain]/webhooks/orders/create
API version: 2024-10
```

#### Sipariş Ödeme Webhook'u
```
Event: Order payment
Format: JSON
URL: https://[your-domain]/webhooks/orders/paid
API version: 2024-10
```

#### Sipariş İptal Webhook'u
```
Event: Order cancellation
Format: JSON
URL: https://[your-domain]/webhooks/orders/cancelled
API version: 2024-10
```

### Adım 3: Her Webhook için "Save" butonuna tıklayın

## 🔒 Güvenlik (HMAC Doğrulama)

Üretim ortamında webhook'ların gerçekten Shopify'dan geldiğini doğrulamak için HMAC imzası kullanılmalıdır.

### HMAC Doğrulamayı Etkinleştirme

1. `.env` dosyanıza webhook secret'ı ekleyin:
```bash
SHOPIFY_WEBHOOK_SECRET=your_webhook_secret_here
```

2. `main.py` dosyasında HMAC doğrulama kodunun yorumunu kaldırın:

```python
# Bu satırların yorumunu kaldırın (main.py, satır ~1328-1333):
webhook_secret = os.getenv("SHOPIFY_WEBHOOK_SECRET")
if webhook_secret:
    hmac_header = request.headers.get("X-Shopify-Hmac-SHA256")
    if not hmac_header or not verify_shopify_webhook(raw_body, hmac_header, webhook_secret):
        print(f"❌ Invalid HMAC signature for webhook: {topic}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
```

### Webhook Secret'ı Bulma

Shopify Admin'de her webhook'un yanında bir "Show" butonu vardır. Bu butona tıklayarak webhook secret'ı görebilirsiniz.

## 🧪 Test Etme

### 1. Yerel Test (Development)

Yerel ortamda test etmek için [ngrok](https://ngrok.com/) gibi bir tunnel servisi kullanın:

```bash
# ngrok'u başlatın
ngrok http 8080

# ngrok size bir public URL verecek, örneğin:
# https://abc123.ngrok.io
```

Shopify webhook URL'lerini ngrok URL'iniz ile güncelleyin:
```
https://abc123.ngrok.io/webhooks/products/create
```

### 2. Manuel Test

Shopify Admin'de bir ürün oluşturun veya güncelleyin. Backend loglarında webhook'un geldiğini görmelisiniz:

```
============================================================
📡 Received Shopify Webhook: products/create
============================================================
Payload keys: ['id', 'title', 'variants', ...]
  📦 Processing product: Test Product (ID: 123456)
  📦 Variants count: 2
    ➕ Creating new variant: Small (Barcode: 123)
    ➕ Creating new variant: Large (Barcode: 456)
  ✅ Product webhook processed successfully
✅ Webhook processed successfully: products/create
============================================================
```

### 3. Webhook Loglarını Kontrol Etme

API endpoint'leri ile webhook loglarını görüntüleyin:

```bash
# Son 50 webhook'u görüntüle
curl http://localhost:8080/webhooks/logs

# Sadece başarısız webhook'ları görüntüle
curl "http://localhost:8080/webhooks/logs?status=failed"

# Sadece ürün webhook'larını görüntüle
curl "http://localhost:8080/webhooks/logs?topic=products/create"

# Webhook istatistiklerini görüntüle
curl http://localhost:8080/webhooks/stats
```

## 📊 Webhook Endpoint'leri

Backend'iniz şu webhook endpoint'lerini sağlar:

### POST /webhooks/{topic}
Ana webhook alıcı endpoint'i. Shopify bu endpoint'e webhook'ları gönderir.

**Örnek Response:**
```json
{
  "status": "ok",
  "topic": "products/create",
  "resource_id": 123456,
  "message": "Webhook processed successfully"
}
```

### GET /webhooks/logs
Webhook event loglarını görüntüler.

**Query Parameters:**
- `limit` (int): Döndürülecek log sayısı (varsayılan: 50)
- `topic` (string): Konuya göre filtrele (örn: "products/create")
- `status` (string): Duruma göre filtrele ("processed", "failed", "skipped")

**Örnek Response:**
```json
{
  "status": "success",
  "count": 10,
  "logs": [
    {
      "id": 1,
      "topic": "products/create",
      "shopify_id": 123456,
      "status": "processed",
      "error_message": null,
      "created_at": "2024-11-15T10:30:00"
    }
  ]
}
```

### GET /webhooks/stats
Webhook istatistiklerini görüntüler.

**Örnek Response:**
```json
{
  "status": "success",
  "total_webhooks": 150,
  "by_status": {
    "processed": 145,
    "failed": 3,
    "skipped": 2
  },
  "by_topic": {
    "products/create": 50,
    "products/update": 80,
    "orders/create": 20
  }
}
```

## 🐛 Sorun Giderme

### Webhook Gelmiyor

1. **URL'yi kontrol edin**: Webhook URL'sinin doğru ve erişilebilir olduğundan emin olun
2. **Firewall kontrolü**: Backend'inizin public internet'ten erişilebilir olduğundan emin olun
3. **HTTPS gereksinimi**: Shopify sadece HTTPS URL'lerine webhook gönderir (ngrok otomatik HTTPS sağlar)
4. **Shopify webhook durumunu kontrol edin**: Admin panelde webhook'un yanında "Delivered" veya "Failed" durumunu görebilirsiniz

### Webhook Başarısız Oluyor

1. **Backend loglarını kontrol edin**: `server.log` veya console output'unda hata mesajlarını arayın
2. **Webhook loglarını kontrol edin**: `GET /webhooks/logs?status=failed` endpoint'ini kullanın
3. **Database bağlantısını kontrol edin**: SQLite dosyasının yazılabilir olduğundan emin olun
4. **API version uyumluluğunu kontrol edin**: Shopify webhook API version'ı ile backend'inizin uyumlu olduğundan emin olun

### HMAC Doğrulama Hatası

1. **Secret'ın doğru olduğundan emin olun**: `.env` dosyasındaki `SHOPIFY_WEBHOOK_SECRET` değerini kontrol edin
2. **Secret'ı Shopify'dan alın**: Her webhook için Shopify Admin'de gösterilen secret'ı kullanın
3. **Development'ta HMAC'i devre dışı bırakın**: Test ederken HMAC doğrulamayı yorumda bırakabilirsiniz

## 📝 Notlar

- **API Version**: Shopify'da webhook oluştururken en güncel stable version'ı kullanın (2024-10 veya daha yeni)
- **Format**: Her zaman JSON formatını seçin
- **Retry Logic**: Shopify, başarısız webhook'ları otomatik olarak yeniden dener (48 saat boyunca)
- **Rate Limiting**: Shopify webhook'ları rate limit'e tabi değildir, ancak backend'iniz yüksek trafiği kaldırabilmelidir
- **Database Backup**: Webhook'lar veritabanını otomatik günceller, düzenli backup almayı unutmayın

## ✅ Başarılı Kurulum Kontrolü

Webhook'larınızın doğru çalıştığını kontrol etmek için:

1. ✅ Shopify Admin'de bir test ürünü oluşturun
2. ✅ Backend loglarında webhook mesajını görün
3. ✅ `GET /products` endpoint'i ile ürünün local DB'ye eklendiğini doğrulayın
4. ✅ `GET /webhooks/stats` ile webhook istatistiklerini kontrol edin

Artık sisteminiz gerçek zamanlı senkronizasyon ile çalışıyor! 🎉

