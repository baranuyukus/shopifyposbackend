# 🚀 Render Deployment Guide

Bu projeyi Render'da host etmek için gerekli adımlar:

## 📋 Gereksinimler

1. **Render Hesabı**: [render.com](https://render.com) üzerinde ücretsiz hesap oluşturun
2. **GitHub Repository**: Projenizi GitHub'a push edin
3. **Shopify Credentials**: Shopify API bilgileriniz hazır olmalı

## 🔧 Render'da Web Service Oluşturma

### 1. Yeni Web Service Oluştur

1. Render Dashboard'a giriş yapın
2. **"New +"** butonuna tıklayın
3. **"Web Service"** seçin
4. GitHub repository'nizi bağlayın

### 2. Build & Start Ayarları

- **Name**: `kasa-backend` (veya istediğiniz isim)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
  - Veya Procfile kullanıyorsanız otomatik algılanır

### 3. Environment Variables (Önemli!)

Render Dashboard'da **Environment** sekmesine gidin ve şu değişkenleri ekleyin:

#### Shopify API Bilgileri (Zorunlu)
```
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_access_token
SHOPIFY_API_KEY=your_api_key
SHOPIFY_API_SECRET=your_api_secret
```

#### Database (PostgreSQL - Önerilen)
Render'da ücretsiz PostgreSQL database oluşturun ve otomatik olarak `DATABASE_URL` environment variable'ı eklenir.

**Manuel ekleme gerekirse:**
```
DATABASE_URL=postgresql://user:password@host:port/database
```

#### CORS Ayarları (Opsiyonel)
Frontend URL'inizi ekleyin:
```
ALLOWED_ORIGINS=https://your-frontend-domain.com,https://www.your-frontend-domain.com
```

Eğer eklemezseniz, varsayılan olarak localhost origin'leri kullanılır.

### 4. PostgreSQL Database Oluşturma (Önerilen)

1. Render Dashboard'da **"New +"** → **"PostgreSQL"** seçin
2. Database adını girin (örn: `kasa-db`)
3. Plan: **Free** seçin (development için yeterli)
4. Oluşturduktan sonra, **"Connections"** sekmesinden `DATABASE_URL`'i kopyalayın
5. Web Service'inizde **"Environment"** sekmesine gidin
6. `DATABASE_URL` environment variable'ının otomatik eklendiğini kontrol edin

**Not**: Eğer otomatik eklenmediyse, manuel olarak ekleyin.

## 📁 Dosya Yapısı

Projenizde şu dosyalar olmalı:

```
kasa/
├── main.py              # FastAPI uygulaması
├── database.py          # Database konfigürasyonu (PostgreSQL desteği var)
├── models.py            # SQLAlchemy modelleri
├── shopify.py           # Shopify API entegrasyonu
├── webhooks.py          # Webhook handler'ları
├── utils/
│   └── pdf_generator.py  # PDF oluşturma
├── requirements.txt     # Python dependencies
├── Procfile            # Render startup command
├── runtime.txt         # Python version
└── .env                # Local development için (gitignore'da olmalı)
```

## 🔍 Kontrol Listesi

Deploy etmeden önce kontrol edin:

- [ ] `requirements.txt` dosyası mevcut ve güncel
- [ ] `Procfile` dosyası mevcut
- [ ] `runtime.txt` dosyası mevcut (Python version belirtilmiş)
- [ ] `database.py` PostgreSQL desteği var
- [ ] `main.py` PORT environment variable kullanıyor
- [ ] Tüm environment variables Render'da ayarlanmış
- [ ] GitHub repository'ye push edilmiş

## 🚀 Deploy Sonrası

1. **Health Check**: `https://your-app.onrender.com/` adresine gidin
   - `{"status": "healthy", ...}` yanıtı görmelisiniz

2. **API Docs**: `https://your-app.onrender.com/docs` adresine gidin
   - Swagger UI açılmalı

3. **Database Initialize**: İlk request'te database otomatik initialize edilir

## 🔧 Troubleshooting

### Database Connection Hatası
- PostgreSQL database'in oluşturulduğundan emin olun
- `DATABASE_URL` environment variable'ının doğru olduğunu kontrol edin
- Database'in Web Service ile aynı region'da olduğundan emin olun

### Port Hatası
- `Procfile` dosyasının doğru olduğundan emin olun
- `$PORT` environment variable'ının kullanıldığını kontrol edin

### CORS Hatası
- Frontend URL'inizi `ALLOWED_ORIGINS` environment variable'ına ekleyin
- Render URL'inizi de ekleyebilirsiniz: `https://your-app.onrender.com`

### Shopify API Hatası
- Tüm Shopify credentials'ların doğru olduğundan emin olun
- Shopify API version'unun güncel olduğunu kontrol edin

## 📝 Notlar

- **Free Plan**: Render free plan'da uygulama 15 dakika idle kalırsa sleep moduna geçer
- **Cold Start**: İlk request biraz yavaş olabilir (30-60 saniye)
- **Database**: PostgreSQL free plan'da 90 MB limit var
- **Logs**: Render Dashboard'da **"Logs"** sekmesinden logları görebilirsiniz

## 🔗 Webhook URL'leri

Render'a deploy ettikten sonra Shopify webhook URL'lerinizi güncelleyin:

```
https://your-app.onrender.com/webhooks/shopify
```

## 📞 Destek

Sorun yaşarsanız:
1. Render Dashboard → Logs sekmesini kontrol edin
2. Health check endpoint'ini test edin
3. Environment variables'ları kontrol edin

