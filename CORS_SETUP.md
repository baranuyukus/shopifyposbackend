# CORS Kurulum ve Sorun Giderme Rehberi

## 🎯 CORS Nedir?

CORS (Cross-Origin Resource Sharing), bir web sayfasının farklı bir domain'deki API'ye istek yapmasına izin veren bir güvenlik mekanizmasıdır.

**Örnek:**
- Frontend: `http://localhost:3000` (React/Next.js)
- Backend: `http://localhost:8080` (FastAPI)

Bu iki farklı port olduğu için tarayıcı güvenlik nedeniyle istekleri bloklar. CORS bu sorunu çözer.

---

## ✅ Çözüm Uygulandı

Backend'e CORS middleware eklendi. Artık frontend'den gelen istekler kabul ediliyor.

### Eklenen Kod (`main.py`)

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # React/Next.js development
        "http://127.0.0.1:3000",      # Alternative localhost
        "http://localhost:5173",      # Vite development
        "http://127.0.0.1:5173",      # Alternative Vite
    ],
    allow_credentials=True,
    allow_methods=["*"],              # Tüm HTTP metodları
    allow_headers=["*"],              # Tüm header'lar
)
```

---

## 🧪 Test Etme

### 1. OPTIONS İsteği (Preflight)

```bash
curl -X OPTIONS http://localhost:8080/orders/create-cart \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v
```

**Beklenen Yanıt:**
```
< HTTP/1.1 200 OK
< access-control-allow-origin: http://localhost:3000
< access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
< access-control-allow-headers: Content-Type
< access-control-allow-credentials: true
```

### 2. Gerçek POST İsteği

```bash
curl -X POST http://localhost:8080/orders/create-cart \
  -H "Origin: http://localhost:3000" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [{"barcode": "88867624", "quantity": 1}],
    "payment_method": "cash",
    "email": "test@example.com"
  }' \
  -v
```

**Beklenen Yanıt:**
```
< HTTP/1.1 200 OK
< access-control-allow-origin: http://localhost:3000
< access-control-allow-credentials: true

{
  "status": "success",
  "message": "Order created...",
  ...
}
```

### 3. Frontend'den Test

**JavaScript/React:**
```javascript
fetch('http://localhost:8080/orders/create-cart', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    items: [{ barcode: '88867624', quantity: 1 }],
    payment_method: 'cash',
    email: 'test@example.com'
  })
})
  .then(response => response.json())
  .then(data => console.log('✅ Başarılı:', data))
  .catch(error => console.error('❌ Hata:', error));
```

---

## 🔧 Farklı Frontend Port'ları İçin

### Vite (Port 5173)
Zaten ekli: `http://localhost:5173`

### Create React App (Port 3000)
Zaten ekli: `http://localhost:3000`

### Next.js (Port 3000)
Zaten ekli: `http://localhost:3000`

### Angular (Port 4200)
Ekleyin:
```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:4200",  # ← Angular
    ...
]
```

### Vue.js (Port 8081)
Ekleyin:
```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:8081",  # ← Vue.js
    ...
]
```

---

## 🚀 Production Ayarları

### 1. Domain Ekleyin

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",           # Development
        "https://yourdomain.com",          # Production frontend
        "https://www.yourdomain.com",      # www subdomain
        "https://pos.yourdomain.com",      # POS subdomain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Ortam Değişkeni Kullanın

`.env` dosyasına ekleyin:
```bash
FRONTEND_URL=https://yourdomain.com
```

`main.py` dosyasında:
```python
import os
from dotenv import load_dotenv

load_dotenv()

FRONTEND_URLS = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Güvenlik İçin Spesifik Metodlar

Production'da tüm metodlara izin vermek yerine sadece gerekenleri belirtin:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Sadece bunlar
    allow_headers=["Content-Type", "Authorization"],  # Sadece bunlar
)
```

---

## 🐛 Sorun Giderme

### Sorun 1: Hala CORS Hatası Alıyorum

**Kontrol Edin:**
1. Backend yeniden başlatıldı mı?
   ```bash
   pkill -f "python.*main.py"
   python3 main.py
   ```

2. Frontend URL'i doğru mu?
   ```python
   # Frontend'inizin çalıştığı port ile eşleşmeli
   allow_origins=["http://localhost:3000"]  # ← Bu doğru mu?
   ```

3. Browser cache temizlendi mi?
   - Chrome: `Ctrl+Shift+Delete` → Clear cache
   - Veya Incognito/Private mode kullanın

### Sorun 2: OPTIONS İsteği 405 Method Not Allowed

**Çözüm:** CORS middleware eklenmemiş demektir.

```bash
# main.py dosyasında kontrol edin:
grep -n "CORSMiddleware" main.py

# Çıktı olmalı:
# 6:from fastapi.middleware.cors import CORSMiddleware
# 93:app.add_middleware(
# 94:    CORSMiddleware,
```

### Sorun 3: Credentials Hatası

**Hata:**
```
Access to fetch at 'http://localhost:8080/...' from origin 'http://localhost:3000' 
has been blocked by CORS policy: The value of the 'Access-Control-Allow-Credentials' 
header in the response is '' which must be 'true' when the request's credentials 
mode is 'include'.
```

**Çözüm:**
```python
allow_credentials=True,  # ← Bu satır olmalı
```

### Sorun 4: Wildcard Origin Hatası

**Hata:**
```
The CORS protocol does not allow specifying a wildcard (any) origin and credentials 
at the same time.
```

**Yanlış:**
```python
allow_origins=["*"],          # ← Wildcard
allow_credentials=True,       # ← Credentials ile çakışıyor!
```

**Doğru:**
```python
allow_origins=[
    "http://localhost:3000",  # ← Spesifik origin
    "https://yourdomain.com"
],
allow_credentials=True,
```

### Sorun 5: Preflight Cache Sorunu

Tarayıcı preflight yanıtını önbelleğe alır. Değişiklik yaptıysanız cache'i temizleyin:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,  # ← 10 dakika (varsayılan)
)
```

Development'ta daha kısa süre kullanın:
```python
max_age=0,  # ← Cache yok
```

---

## 📊 CORS Header'ları Açıklaması

### Request Headers (Frontend → Backend)

| Header | Açıklama | Örnek |
|--------|----------|-------|
| `Origin` | İsteğin geldiği domain | `http://localhost:3000` |
| `Access-Control-Request-Method` | Kullanılacak HTTP metodu | `POST` |
| `Access-Control-Request-Headers` | Kullanılacak header'lar | `Content-Type` |

### Response Headers (Backend → Frontend)

| Header | Açıklama | Örnek |
|--------|----------|-------|
| `Access-Control-Allow-Origin` | İzin verilen origin | `http://localhost:3000` |
| `Access-Control-Allow-Methods` | İzin verilen metodlar | `GET, POST, PUT, DELETE` |
| `Access-Control-Allow-Headers` | İzin verilen header'lar | `Content-Type, Authorization` |
| `Access-Control-Allow-Credentials` | Cookie/auth izni | `true` |
| `Access-Control-Max-Age` | Preflight cache süresi | `600` (saniye) |

---

## 🔍 Browser Developer Tools'da Kontrol

### 1. Network Tab'ı Açın
- Chrome: `F12` → Network tab
- Firefox: `F12` → Network tab

### 2. OPTIONS İsteğini Bulun
- İlk istek OPTIONS olmalı (preflight)
- Status: 200 OK
- Method: OPTIONS

### 3. Response Headers'ı Kontrol Edin
```
access-control-allow-origin: http://localhost:3000
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
access-control-allow-headers: Content-Type
access-control-allow-credentials: true
```

### 4. POST İsteğini Kontrol Edin
- İkinci istek POST olmalı (gerçek istek)
- Status: 200 OK
- Response: JSON data

---

## 📝 Kontrol Listesi

Backend'de CORS düzgün çalışıyor mu?

- [x] `fastapi.middleware.cors` import edildi
- [x] `CORSMiddleware` eklendi
- [x] `allow_origins` frontend URL'ini içeriyor
- [x] `allow_credentials=True` ayarlandı
- [x] `allow_methods=["*"]` ayarlandı
- [x] `allow_headers=["*"]` ayarlandı
- [x] Backend yeniden başlatıldı
- [ ] Frontend'den test yapıldı
- [ ] OPTIONS isteği 200 OK dönüyor
- [ ] POST isteği başarılı

---

## 🎓 Best Practices

### Development
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],      # Tüm metodlar
    allow_headers=["*"],      # Tüm header'lar
    max_age=0,                # Cache yok
)
```

### Production
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://www.yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Sadece gerekli metodlar
    allow_headers=["Content-Type", "Authorization"], # Sadece gerekli header'lar
    max_age=3600,             # 1 saat cache
)
```

---

## 🔗 Faydalı Linkler

- [FastAPI CORS Dokümantasyonu](https://fastapi.tiangolo.com/tutorial/cors/)
- [MDN CORS Rehberi](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [CORS Test Tool](https://www.test-cors.org/)

---

## 📞 Destek

Sorun devam ederse:

1. **Backend loglarını kontrol edin:**
   ```bash
   tail -f server.log
   ```

2. **Browser console'u kontrol edin:**
   - F12 → Console tab
   - CORS hatası var mı?

3. **Network tab'ı kontrol edin:**
   - OPTIONS isteği başarılı mı?
   - Response header'lar doğru mu?

4. **CORS test edin:**
   ```bash
   curl -X OPTIONS http://localhost:8080/orders/create-cart \
     -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -v
   ```

---

**Son Güncelleme:** 15 Kasım 2024  
**Status:** ✅ CORS Aktif ve Çalışıyor  
**Desteklenen Frontend'ler:** React, Next.js, Vite, Vue.js, Angular

