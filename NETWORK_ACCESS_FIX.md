# Network Erişimi (192.168.x.x) Sorunu Çözümü

## ❌ Sorun

Frontend `http://192.168.1.134:3000` adresinden çalışıyor ama backend'e erişemiyor.

**Hata:**
```
Access to XMLHttpRequest at 'http://localhost:8080/orders/create-cart' 
from origin 'http://192.168.1.134:3000' has been blocked by CORS policy
```

---

## ✅ Çözüm (2 Adım)

### 1. Backend CORS Ayarları (✅ Tamamlandı)

`main.py` dosyasına network IP eklendi:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.1.134:3000",  # ← Network IP eklendi
        "http://192.168.1.134:5173",  # ← Vite için
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Frontend API URL Ayarları (❗ Yapılması Gereken)

Frontend'inizde API URL'ini network IP'nize göre ayarlayın.

---

## 🔧 Frontend Düzeltmeleri

### Seçenek 1: Ortam Değişkeni (Önerilen)

**`.env.local` dosyası oluşturun:**

```bash
# Frontend dizininizde
NEXT_PUBLIC_API_URL=http://192.168.1.134:8080
```

**Kodunuzda kullanın:**

```typescript
// api.ts veya config.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export const api = axios.create({
  baseURL: API_URL,
});
```

### Seçenek 2: Dinamik IP Algılama

```typescript
// utils/getApiUrl.ts
export const getApiUrl = () => {
  // Browser'da çalışıyorsa
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // Eğer network IP ile erişiliyorsa
    if (hostname.startsWith('192.168.') || hostname.startsWith('10.')) {
      return `http://${hostname}:8080`;
    }
  }
  
  // Varsayılan olarak localhost
  return 'http://localhost:8080';
};

// Kullanım
import { getApiUrl } from './utils/getApiUrl';

const API_URL = getApiUrl();
```

### Seçenek 3: Manuel Değiştirme

**Mevcut kodunuzda:**

```typescript
// ❌ Eski
const API_URL = 'http://localhost:8080';

// ✅ Yeni
const API_URL = 'http://192.168.1.134:8080';
```

---

## 🚀 Backend'i Network'de Erişilebilir Yapma

Backend şu anda sadece `localhost:8080`'de çalışıyor. Network'den erişilebilir yapmak için:

### Yöntem 1: Uvicorn Host Ayarı (Zaten Yapılmış)

`main.py` dosyasının sonunda:

```python
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
```

`host="0.0.0.0"` sayesinde tüm network interface'lerinden erişilebilir.

### Yöntem 2: Manuel Başlatma

```bash
cd /Users/baranuyukus/Desktop/kasa
source env/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🧪 Test Etme

### 1. Backend Network Erişimini Test Edin

**Başka bir cihazdan (telefon, tablet):**

```
http://192.168.1.134:8080/
```

**Beklenen Yanıt:**
```json
{
  "status": "healthy",
  "message": "Shopify POS & Inventory Backend is running",
  "version": "1.0.0"
}
```

### 2. CORS'u Test Edin

```bash
curl -X OPTIONS http://192.168.1.134:8080/orders/create-cart \
  -H "Origin: http://192.168.1.134:3000" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

**Beklenen:**
```
< HTTP/1.1 200 OK
< access-control-allow-origin: http://192.168.1.134:3000
```

### 3. Frontend'den Test Edin

Browser console'da:

```javascript
fetch('http://192.168.1.134:8080/', {
  method: 'GET',
})
  .then(res => res.json())
  .then(data => console.log('✅ Backend erişilebilir:', data))
  .catch(err => console.error('❌ Hata:', err));
```

---

## 🔍 IP Adresinizi Bulma

### macOS/Linux:

```bash
# Wi-Fi IP
ipconfig getifaddr en0

# Veya tüm network interface'leri göster
ifconfig | grep "inet " | grep -v 127.0.0.1
```

### Windows:

```cmd
ipconfig
```

`IPv4 Address` satırını bulun (örn: `192.168.1.134`)

---

## 📱 Mobil Test İçin

### 1. Backend'i Network'de Çalıştırın

```bash
cd /Users/baranuyukus/Desktop/kasa
source env/bin/activate
python3 main.py
```

Backend şu adreslerde erişilebilir olmalı:
- `http://localhost:8080` (aynı bilgisayardan)
- `http://192.168.1.134:8080` (network'teki diğer cihazlardan)

### 2. Frontend'i Network'de Çalıştırın

```bash
# Next.js
npm run dev -- -H 0.0.0.0

# Veya package.json'da:
"scripts": {
  "dev": "next dev -H 0.0.0.0"
}
```

Frontend şu adreslerde erişilebilir olmalı:
- `http://localhost:3000` (aynı bilgisayardan)
- `http://192.168.1.134:3000` (network'teki diğer cihazlardan)

### 3. Mobil Cihazdan Erişin

Telefonunuzun browser'ında:
```
http://192.168.1.134:3000
```

---

## 🐛 Sorun Giderme

### Sorun 1: Backend'e Erişilemiyor

**Kontrol:**
```bash
# Backend çalışıyor mu?
curl http://localhost:8080/

# Network'den erişilebilir mi?
curl http://192.168.1.134:8080/
```

**Çözüm:**
- Backend'in `host="0.0.0.0"` ile çalıştığından emin olun
- Firewall'u kontrol edin (macOS: System Preferences → Security → Firewall)

### Sorun 2: CORS Hatası Devam Ediyor

**Kontrol:**
```bash
# Backend loglarını kontrol edin
tail -f /Users/baranuyukus/Desktop/kasa/server.log

# CORS ayarlarını kontrol edin
grep -A 10 "CORSMiddleware" /Users/baranuyukus/Desktop/kasa/main.py
```

**Çözüm:**
- Backend'i yeniden başlatın
- Browser cache'i temizleyin
- Incognito/Private mode deneyin

### Sorun 3: Frontend API URL'i Yanlış

**Kontrol:**
Browser console'da:
```javascript
console.log('API URL:', process.env.NEXT_PUBLIC_API_URL);
```

**Çözüm:**
- `.env.local` dosyasını oluşturun
- `NEXT_PUBLIC_API_URL=http://192.168.1.134:8080` ekleyin
- Frontend'i yeniden başlatın

### Sorun 4: IP Adresi Değişti

Wi-Fi'ye her bağlandığınızda IP değişebilir.

**Çözüm 1: Statik IP Kullanın**
Router ayarlarından MAC adresinize statik IP atayın.

**Çözüm 2: Dinamik URL**
Frontend'de dinamik IP algılama kullanın (yukarıda Seçenek 2).

---

## 📋 Kontrol Listesi

Backend:
- [x] CORS middleware'de network IP eklendi
- [x] Backend `host="0.0.0.0"` ile çalışıyor
- [x] Backend yeniden başlatıldı
- [ ] Backend network'den erişilebilir (`http://192.168.1.134:8080/`)

Frontend:
- [ ] API URL network IP'ye göre ayarlandı
- [ ] `.env.local` dosyası oluşturuldu
- [ ] Frontend yeniden başlatıldı
- [ ] Frontend network'den erişilebilir (`http://192.168.1.134:3000`)

Test:
- [ ] OPTIONS isteği başarılı
- [ ] POST isteği başarılı
- [ ] Mobil cihazdan test edildi

---

## 🎯 Hızlı Çözüm

### Backend (Zaten Yapıldı ✅)

```bash
cd /Users/baranuyukus/Desktop/kasa
source env/bin/activate
python3 main.py
```

### Frontend (Yapılması Gereken ❗)

**1. `.env.local` oluşturun:**
```bash
echo "NEXT_PUBLIC_API_URL=http://192.168.1.134:8080" > .env.local
```

**2. Frontend'i yeniden başlatın:**
```bash
npm run dev
```

**3. Test edin:**
```
http://192.168.1.134:3000
```

---

## 🔒 Güvenlik Notu

Network IP'nizi CORS'a eklemek development için güvenlidir. Production'da:

1. Sadece production domain'inizi ekleyin
2. Wildcard (`*`) kullanmayın
3. HTTPS kullanın
4. Rate limiting ekleyin

---

## 📞 Destek

Sorun devam ederse:

1. **Backend loglarını kontrol edin:**
   ```bash
   tail -f /Users/baranuyukus/Desktop/kasa/server.log
   ```

2. **Network bağlantısını kontrol edin:**
   ```bash
   ping 192.168.1.134
   ```

3. **Firewall'u kontrol edin:**
   - macOS: System Preferences → Security & Privacy → Firewall
   - Port 8080'in açık olduğundan emin olun

4. **Browser console'u kontrol edin:**
   - F12 → Console tab
   - Network tab → Failed requests

---

**Son Güncelleme:** 15 Kasım 2024  
**Backend Status:** ✅ Network'de Erişilebilir  
**CORS Status:** ✅ 192.168.1.134:3000 Destekleniyor  
**Frontend:** ❗ API URL'ini güncellemeniz gerekiyor

