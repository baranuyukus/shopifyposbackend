# Shopify POS & Inventory API - Detaylı Dokümantasyon

**Version:** 1.0.0  
**Base URL:** `http://localhost:8080`  
**Swagger UI:** `http://localhost:8080/docs`

Bu API, Shopify mağazanız için yerel bir POS (Point of Sale) ve envanter yönetim sistemi sağlar. Tüm ürün, müşteri ve sipariş verilerini yerel SQLite veritabanında önbelleğe alır ve Shopify REST Admin API ile senkronize eder.

---

## 📑 İçindekiler

1. [Genel Bilgiler](#genel-bilgiler)
2. [Health Check](#health-check)
3. [Product Endpoints](#product-endpoints)
4. [Customer Endpoints](#customer-endpoints)
5. [Order Endpoints](#order-endpoints)
6. [Webhook Endpoints](#webhook-endpoints)
7. [Veri Modelleri](#veri-modelleri)
8. [Hata Kodları](#hata-kodları)
9. [Kullanım Örnekleri](#kullanım-örnekleri)

---

## Genel Bilgiler

### Kimlik Doğrulama
Bu API şu anda kimlik doğrulama gerektirmez (yerel kullanım için). Production ortamında API key veya OAuth eklenmelidir.

### Veri Formatı
- **Request Body:** JSON
- **Response:** JSON
- **Encoding:** UTF-8
- **Tarih Formatı:** ISO 8601 (YYYY-MM-DDTHH:MM:SS)

### Rate Limiting
Yerel API'de rate limit yoktur, ancak Shopify API'sine yapılan istekler Shopify'ın rate limit'lerine tabidir (2 requests/second).

---

## Health Check

### GET /
Sistem sağlık kontrolü endpoint'i.

**Response:**
```json
{
  "status": "healthy",
  "message": "Shopify POS & Inventory Backend is running",
  "version": "1.0.0"
}
```

**Status Codes:**
- `200 OK` - Sistem çalışıyor

---

## Product Endpoints

### 1. POST /sync-products
Shopify'daki tüm ürünleri yerel veritabanına senkronize eder.

**Açıklama:**
- Shopify'dan tüm ürünleri ve varyantlarını çeker
- Mevcut ürünleri günceller (upsert)
- Yeni ürünleri ekler
- Barkodu olmayan ürünleri atlar
- Duplicate shopify_id'leri filtreler

**Request:**
```http
POST /sync-products
```

**Response:**
```json
{
  "status": "success",
  "message": "Products synced successfully",
  "total_synced": 2603,
  "skipped_no_barcode": 150,
  "skipped_duplicate": 5
}
```

**Status Codes:**
- `200 OK` - Senkronizasyon başarılı
- `500 Internal Server Error` - Shopify API hatası veya veritabanı hatası

**Notlar:**
- İşlem uzun sürebilir (binlerce ürün için 1-2 dakika)
- Pagination otomatik olarak yapılır
- Shopify API version: 2024-10

---

### 2. GET /products
Yerel veritabanındaki tüm ürünleri listeler (pagination ile).

**Query Parameters:**
- `skip` (integer, optional): Atlanacak kayıt sayısı (default: 0)
- `limit` (integer, optional): Döndürülecek maksimum kayıt sayısı (default: 100)

**Request:**
```http
GET /products?skip=0&limit=50
```

**Response:**
```json
{
  "status": "success",
  "total": 2603,
  "skip": 0,
  "limit": 50,
  "products": [
    {
      "id": 1,
      "shopify_id": 49717824323880,
      "shopify_product_id": 9538140963112,
      "title": "Bape white crewneck",
      "sku": "72151606823880",
      "barcode": "24323880",
      "price": 2500.0,
      "inventory_quantity": 5,
      "variant_title": "L",
      "image_url": "https://cdn.shopify.com/...",
      "created_at": "2024-11-15T10:30:00",
      "updated_at": "2024-11-15T12:45:00"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Başarılı

---

### 3. GET /products/{product_id}
Belirli bir ürünü ID'sine göre getirir.

**Path Parameters:**
- `product_id` (integer, required): Yerel veritabanı ürün ID'si

**Request:**
```http
GET /products/1
```

**Response:**
```json
{
  "status": "success",
  "product": {
    "id": 1,
    "shopify_id": 49717824323880,
    "title": "Bape white crewneck",
    "barcode": "24323880",
    "price": 2500.0,
    "inventory_quantity": 5
  }
}
```

**Status Codes:**
- `200 OK` - Ürün bulundu
- `404 Not Found` - Ürün bulunamadı

---

### 4. GET /products/barcode/{barcode}
Barkod ile ürün arama (aynı barkoda sahip tüm varyantları döndürür).

**Path Parameters:**
- `barcode` (string, required): Ürün barkodu

**Request:**
```http
GET /products/barcode/24323880
```

**Response:**
```json
{
  "status": "success",
  "barcode": "24323880",
  "count": 3,
  "products": [
    {
      "id": 1,
      "title": "Bape white crewneck",
      "variant_title": "S",
      "price": 2500.0,
      "inventory_quantity": 5
    },
    {
      "id": 2,
      "title": "Bape white crewneck",
      "variant_title": "M",
      "price": 2500.0,
      "inventory_quantity": 3
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Ürün(ler) bulundu
- `404 Not Found` - Barkod bulunamadı

**Notlar:**
- Aynı barkoda sahip birden fazla varyant olabilir
- Stokta olan varyantlar önce gelir

---

## Customer Endpoints

### 1. POST /customers/sync
Shopify'daki tüm müşterileri yerel veritabanına senkronize eder.

**Request:**
```http
POST /customers/sync
```

**Response:**
```json
{
  "status": "success",
  "message": "Customers synced successfully",
  "total_synced": 3327,
  "skipped_duplicate": 2
}
```

**Status Codes:**
- `200 OK` - Senkronizasyon başarılı
- `500 Internal Server Error` - Hata

---

### 2. GET /customers/search
Email veya telefon numarası ile müşteri arama.

**Query Parameters:**
- `email` (string, optional): Müşteri email adresi
- `phone` (string, optional): Müşteri telefon numarası

**En az bir parametre gereklidir.**

**Request:**
```http
GET /customers/search?email=customer@example.com
```

**Response:**
```json
{
  "status": "success",
  "source": "local",
  "customers": [
    {
      "id": 1,
      "shopify_id": 9770006446376,
      "first_name": "Ahmet",
      "last_name": "Yılmaz",
      "email": "customer@example.com",
      "phone": "+905551234567",
      "address": "Atatürk Cad. No:123",
      "city": "Istanbul",
      "country": "Turkey",
      "created_at": "2024-11-15T10:00:00"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Müşteri bulundu
- `400 Bad Request` - Email veya phone parametresi eksik
- `404 Not Found` - Müşteri bulunamadı

**Notlar:**
- Önce yerel veritabanında arar
- Bulamazsa Shopify API'de arar
- Shopify'da bulursa yerel DB'ye kaydeder

---

### 3. POST /customers/create
Yeni müşteri oluşturur (Shopify ve yerel DB'ye).

**Request Body:**
```json
{
  "first_name": "Mehmet",
  "last_name": "Demir",
  "email": "mehmet@example.com",
  "phone": "+905551234567",
  "address": {
    "address1": "Cumhuriyet Bulvarı No:456",
    "address2": "Kat 3, Daire 8",
    "city": "Ankara",
    "province": "Ankara",
    "country": "Turkey",
    "zip": "06100"
  }
}
```

**Required Fields:**
- `first_name` (string)
- `last_name` (string)
- `email` (string, email format)

**Optional Fields:**
- `phone` (string)
- `address` (object)
  - `address1` (string)
  - `address2` (string)
  - `city` (string)
  - `province` (string)
  - `country` (string, default: "Turkey")
  - `zip` (string)

**Response:**
```json
{
  "status": "created",
  "customer": {
    "id": 100,
    "shopify_id": 9899339841832,
    "first_name": "Mehmet",
    "last_name": "Demir",
    "email": "mehmet@example.com",
    "phone": "+905551234567",
    "address": "Cumhuriyet Bulvarı No:456 Kat 3, Daire 8",
    "city": "Ankara",
    "country": "Turkey",
    "created_at": "2024-11-15T11:33:45"
  }
}
```

**Status Codes:**
- `200 OK` - Müşteri oluşturuldu
- `400 Bad Request` - Geçersiz veri
- `500 Internal Server Error` - Shopify API hatası

---

### 4. GET /customers
Tüm müşterileri listeler (pagination ile).

**Query Parameters:**
- `skip` (integer, optional): Atlanacak kayıt sayısı (default: 0)
- `limit` (integer, optional): Döndürülecek maksimum kayıt sayısı (default: 100)

**Request:**
```http
GET /customers?skip=0&limit=50
```

**Response:**
```json
{
  "status": "success",
  "total": 3327,
  "skip": 0,
  "limit": 50,
  "customers": [...]
}
```

**Status Codes:**
- `200 OK` - Başarılı

---

### 5. GET /customers/{customer_id}
Belirli bir müşteriyi ID'sine göre getirir.

**Path Parameters:**
- `customer_id` (integer, required): Yerel veritabanı müşteri ID'si

**Request:**
```http
GET /customers/1
```

**Response:**
```json
{
  "status": "success",
  "customer": {
    "id": 1,
    "shopify_id": 9770006446376,
    "first_name": "Ahmet",
    "last_name": "Yılmaz",
    "email": "ahmet@example.com"
  }
}
```

**Status Codes:**
- `200 OK` - Müşteri bulundu
- `404 Not Found` - Müşteri bulunamadı

---

## Order Endpoints

### 1. POST /orders/create-cart
Sepet sistemi ile sipariş oluşturur. Hem barkodlu ürünler hem de custom ürünler desteklenir.

**İki kullanım şekli vardır:**

#### SEÇENEK 1: Mevcut Müşteri ile Sipariş

**Request Body:**
```json
{
  "items": [
    {
      "barcode": "88834856",
      "quantity": 2
    },
    {
      "type": "custom",
      "title": "Özel Tişört",
      "size": "XL",
      "price": 150.0,
      "quantity": 1
    }
  ],
  "payment_method": "cash",
  "email": "mevcut@musteri.com",
  "discount": 100,
  "discount_reason": "Mağaza indirimi"
}
```

#### SEÇENEK 2: Yeni Müşteri Oluşturarak Sipariş

**Request Body:**
```json
{
  "items": [
    {
      "barcode": "88834856",
      "quantity": 1
    }
  ],
  "payment_method": "pos",
  "new_customer": {
    "first_name": "Ali",
    "last_name": "Veli",
    "email": "ali@example.com",
    "phone": "+905551234567",
    "address": {
      "address1": "Atatürk Cad. No:123",
      "city": "Istanbul",
      "country": "Turkey"
    }
  },
  "discount": 50
}
```

**Required Fields:**
- `items` (array): Sipariş kalemleri listesi
- `payment_method` (string): "cash" veya "pos"
- `email` (string) VEYA `new_customer` (object): Birini sağlamalısınız

**Optional Fields:**
- `discount` (float): İndirim tutarı (default: 0)
- `discount_reason` (string): İndirim nedeni

**Item Types:**

**Barkodlu Ürün:**
```json
{
  "barcode": "88834856",
  "quantity": 2
}
```

**Custom/Manuel Ürün:**
```json
{
  "type": "custom",
  "title": "Ürün Adı",
  "size": "L",
  "price": 250.0,
  "quantity": 1
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Order created with 3 items (cash)",
  "shopify_order_id": 6887668187432,
  "shopify_order_number": 3731,
  "original_amount": 3848.0,
  "final_amount": 3748.0,
  "items_count": 3,
  "orders": [
    {
      "id": 150,
      "shopify_order_id": 6887668187432,
      "customer_id": 50,
      "product_id": 100,
      "barcode": "88834856",
      "title": "032C Sweatshirt",
      "quantity": 2,
      "price": 1799.0,
      "payment_method": "cash",
      "status": "completed",
      "created_at": "2024-11-15T14:30:00"
    }
  ],
  "discount_applied": 100.0,
  "discount_reason": "Mağaza indirimi"
}
```

**Status Codes:**
- `200 OK` - Sipariş oluşturuldu
- `400 Bad Request` - Geçersiz veri
- `404 Not Found` - Müşteri veya ürün bulunamadı
- `500 Internal Server Error` - Shopify API hatası

**Notlar:**
- Aynı sipariş içinde hem barkodlu hem custom ürün olabilir
- İndirim toplam tutardan düşülür
- Shopify'a "in-store" tag'i ile kaydedilir
- Her item ayrı bir local order kaydı olarak saklanır

---

### 2. POST /orders/manual-create
Envanterde olmayan manuel ürünler için sipariş oluşturur.

**Request Body:**
```json
{
  "title": "Özel Tasarım Tişört",
  "size": "XL",
  "price": 350.0,
  "quantity": 2,
  "payment_method": "cash",
  "email": "customer@example.com",
  "discount": 50
}
```

**Required Fields:**
- `title` (string): Ürün adı
- `price` (float): Birim fiyat
- `payment_method` (string): "cash" veya "pos"

**Optional Fields:**
- `size` (string): Beden/boyut
- `quantity` (integer, default: 1)
- `email` (string): Müşteri email
- `discount` (float, default: 0)

**Response:**
```json
{
  "status": "success",
  "message": "Manual order created successfully",
  "shopify_order_id": 6887668416808,
  "shopify_order_number": 3732,
  "original_amount": 700.0,
  "final_amount": 650.0,
  "order": {
    "id": 151,
    "shopify_order_id": 6887668416808,
    "title": "Özel Tasarım Tişört - XL",
    "quantity": 2,
    "price": 350.0,
    "payment_method": "cash",
    "status": "completed"
  }
}
```

**Status Codes:**
- `200 OK` - Sipariş oluşturuldu
- `400 Bad Request` - Geçersiz veri
- `500 Internal Server Error` - Hata

**Notlar:**
- Shopify'a "manual" tag'i ile kaydedilir
- Envanter takibi yapılmaz

---

### 3. GET /orders
Tüm siparişleri listeler (pagination ile).

**Query Parameters:**
- `skip` (integer, optional): Atlanacak kayıt sayısı (default: 0)
- `limit` (integer, optional): Döndürülecek maksimum kayıt sayısı (default: 100)

**Request:**
```http
GET /orders?skip=0&limit=50
```

**Response:**
```json
{
  "status": "success",
  "total": 450,
  "skip": 0,
  "limit": 50,
  "orders": [...]
}
```

**Status Codes:**
- `200 OK` - Başarılı

---

### 4. GET /orders/{order_id}
Belirli bir siparişi ID'sine göre getirir.

**Path Parameters:**
- `order_id` (integer, required): Yerel veritabanı sipariş ID'si

**Request:**
```http
GET /orders/150
```

**Response:**
```json
{
  "status": "success",
  "order": {
    "id": 150,
    "shopify_order_id": 6887668187432,
    "customer_id": 50,
    "product_id": 100,
    "title": "032C Sweatshirt",
    "quantity": 2,
    "price": 1799.0,
    "payment_method": "cash",
    "status": "completed"
  }
}
```

**Status Codes:**
- `200 OK` - Sipariş bulundu
- `404 Not Found` - Sipariş bulunamadı

---

### 5. GET /orders/stats/today
Günlük satış istatistiklerini getirir.

**Request:**
```http
GET /orders/stats/today
```

**Response:**
```json
{
  "status": "success",
  "date": "2024-11-15",
  "total_orders": 25,
  "total_sales": 45000.0,
  "cash_sales": 30000.0,
  "pos_sales": 15000.0,
  "payment_breakdown": {
    "cash": {
      "count": 18,
      "amount": 30000.0
    },
    "pos": {
      "count": 7,
      "amount": 15000.0
    }
  }
}
```

**Status Codes:**
- `200 OK` - Başarılı

**Notlar:**
- Sadece bugünün siparişlerini içerir
- Gece yarısından itibaren hesaplanır

---

## Webhook Endpoints

### 1. POST /webhooks/{topic}
Shopify'dan gelen webhook'ları işler.

**Path Parameters:**
- `topic` (string, required): Webhook konusu (örn: "products/create")

**Desteklenen Konular:**
- `products/create` - Yeni ürün oluşturuldu
- `products/update` - Ürün güncellendi
- `products/delete` - Ürün silindi
- `inventory_levels/update` - Stok güncellendi
- `customers/create` - Yeni müşteri oluşturuldu
- `customers/update` - Müşteri güncellendi
- `orders/create` - Yeni sipariş oluşturuldu
- `orders/paid` - Sipariş ödendi
- `orders/cancelled` - Sipariş iptal edildi

**Request Headers:**
- `Content-Type: application/json`
- `X-Shopify-Hmac-SHA256` (optional): HMAC imzası

**Request Body:**
Shopify webhook payload (JSON)

**Response:**
```json
{
  "status": "ok",
  "topic": "products/create",
  "resource_id": 9538140963112,
  "message": "Webhook processed successfully"
}
```

**Status Codes:**
- `200 OK` - Webhook işlendi
- `400 Bad Request` - Geçersiz JSON
- `401 Unauthorized` - HMAC doğrulama başarısız (etkinse)
- `500 Internal Server Error` - İşleme hatası

**Notlar:**
- Tüm webhook'lar `webhook_events` tablosuna loglanır
- HMAC doğrulama varsayılan olarak kapalı (development için)
- Production'da HMAC'i etkinleştirin

---

### 2. GET /webhooks/logs
Webhook event loglarını görüntüler.

**Query Parameters:**
- `limit` (integer, optional): Döndürülecek log sayısı (default: 50)
- `topic` (string, optional): Konuya göre filtrele
- `status` (string, optional): Duruma göre filtrele ("processed", "failed", "skipped")

**Request:**
```http
GET /webhooks/logs?limit=20&status=failed
```

**Response:**
```json
{
  "status": "success",
  "count": 3,
  "logs": [
    {
      "id": 150,
      "topic": "products/update",
      "shopify_id": 9538140963112,
      "status": "processed",
      "error_message": null,
      "created_at": "2024-11-15T14:30:00"
    },
    {
      "id": 149,
      "topic": "orders/create",
      "shopify_id": 6887668187432,
      "status": "failed",
      "error_message": "Database connection error",
      "created_at": "2024-11-15T14:25:00"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Başarılı

---

### 3. GET /webhooks/stats
Webhook istatistiklerini getirir.

**Request:**
```http
GET /webhooks/stats
```

**Response:**
```json
{
  "status": "success",
  "total_webhooks": 1250,
  "by_status": {
    "processed": 1200,
    "failed": 45,
    "skipped": 5
  },
  "by_topic": {
    "products/create": 300,
    "products/update": 450,
    "inventory_levels/update": 200,
    "orders/create": 150,
    "customers/create": 100,
    "customers/update": 50
  }
}
```

**Status Codes:**
- `200 OK` - Başarılı

---

## Veri Modelleri

### Product Model
```json
{
  "id": 1,
  "shopify_id": 49717824323880,
  "shopify_product_id": 9538140963112,
  "title": "Bape white crewneck",
  "sku": "72151606823880",
  "barcode": "24323880",
  "price": 2500.0,
  "inventory_quantity": 5,
  "variant_title": "L",
  "image_url": "https://cdn.shopify.com/...",
  "created_at": "2024-11-15T10:30:00",
  "updated_at": "2024-11-15T12:45:00"
}
```

**Alan Açıklamaları:**
- `id`: Yerel veritabanı ID'si (primary key)
- `shopify_id`: Shopify variant ID'si (unique)
- `shopify_product_id`: Shopify product ID'si
- `title`: Ürün adı
- `sku`: Stok kodu
- `barcode`: Barkod (aynı barkoda sahip birden fazla varyant olabilir)
- `price`: Fiyat (TL)
- `inventory_quantity`: Stok miktarı
- `variant_title`: Varyant adı (S, M, L, vb.)
- `image_url`: Ürün görseli URL'i

---

### Customer Model
```json
{
  "id": 1,
  "shopify_id": 9770006446376,
  "first_name": "Ahmet",
  "last_name": "Yılmaz",
  "email": "ahmet@example.com",
  "phone": "+905551234567",
  "address": "Atatürk Cad. No:123 Daire 5",
  "city": "Istanbul",
  "country": "Turkey",
  "created_at": "2024-11-15T10:00:00",
  "updated_at": "2024-11-15T12:00:00"
}
```

**Alan Açıklamaları:**
- `id`: Yerel veritabanı ID'si (primary key)
- `shopify_id`: Shopify customer ID'si (unique)
- `first_name`: Ad
- `last_name`: Soyad
- `email`: Email adresi
- `phone`: Telefon numarası
- `address`: Adres (address1 + address2 birleştirilmiş)
- `city`: Şehir
- `country`: Ülke

---

### Order Model
```json
{
  "id": 150,
  "shopify_order_id": 6887668187432,
  "customer_id": 50,
  "product_id": 100,
  "barcode": "88834856",
  "title": "032C Sweatshirt",
  "quantity": 2,
  "price": 1799.0,
  "payment_method": "cash",
  "status": "completed",
  "created_at": "2024-11-15T14:30:00"
}
```

**Alan Açıklamaları:**
- `id`: Yerel veritabanı ID'si (primary key)
- `shopify_order_id`: Shopify order ID'si (aynı siparişin birden fazla item'ı olabilir)
- `customer_id`: Müşteri ID'si (foreign key)
- `product_id`: Ürün ID'si (foreign key, custom ürünlerde null)
- `barcode`: Ürün barkodu
- `title`: Ürün/sipariş adı
- `quantity`: Adet
- `price`: Birim fiyat
- `payment_method`: Ödeme yöntemi ("cash" veya "pos")
- `status`: Sipariş durumu ("completed", "paid", "cancelled")

---

### WebhookEvent Model
```json
{
  "id": 150,
  "topic": "products/update",
  "shopify_id": 9538140963112,
  "status": "processed",
  "error_message": null,
  "created_at": "2024-11-15T14:30:00"
}
```

**Alan Açıklamaları:**
- `id`: Log ID'si (primary key)
- `topic`: Webhook konusu
- `shopify_id`: İlgili kaynağın Shopify ID'si
- `status`: İşlem durumu ("processed", "failed", "skipped")
- `error_message`: Hata mesajı (varsa)
- `created_at`: Log oluşturulma zamanı

---

## Hata Kodları

### HTTP Status Codes

| Kod | Açıklama | Ne Zaman Kullanılır |
|-----|----------|---------------------|
| 200 | OK | İstek başarıyla tamamlandı |
| 400 | Bad Request | Geçersiz request body veya parametreler |
| 404 | Not Found | Kaynak bulunamadı |
| 422 | Unprocessable Entity | Shopify API validasyon hatası |
| 500 | Internal Server Error | Sunucu hatası, veritabanı hatası, Shopify API hatası |

### Hata Response Formatı

```json
{
  "detail": "Customer with email 'test@example.com' not found"
}
```

### Yaygın Hatalar

**1. Müşteri Bulunamadı**
```json
{
  "detail": "Customer with email 'test@example.com' not found. Use 'new_customer' to create a new one."
}
```

**2. Ürün Bulunamadı**
```json
{
  "detail": "No products found with barcode: 123456"
}
```

**3. Geçersiz Ödeme Yöntemi**
```json
{
  "detail": "Invalid payment method. Must be 'cash' or 'pos'."
}
```

**4. İndirim Tutarı Çok Yüksek**
```json
{
  "detail": "Discount amount (2000) cannot be greater than or equal to total (1500)"
}
```

**5. Shopify API Hatası**
```json
{
  "detail": "Failed to sync products: 422 Client Error: unknown for url: https://..."
}
```

---

## Kullanım Örnekleri

### Örnek 1: Barkod ile Ürün Arama ve Sipariş Oluşturma

```bash
# 1. Barkod ile ürün ara
curl -X GET "http://localhost:8080/products/barcode/88834856"

# 2. Müşteri ara
curl -X GET "http://localhost:8080/customers/search?email=customer@example.com"

# 3. Sipariş oluştur
curl -X POST "http://localhost:8080/orders/create-cart" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"barcode": "88834856", "quantity": 2}
    ],
    "payment_method": "cash",
    "email": "customer@example.com",
    "discount": 100
  }'
```

---

### Örnek 2: Yeni Müşteri ile Karışık Sepet Siparişi

```bash
curl -X POST "http://localhost:8080/orders/create-cart" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"barcode": "88834856", "quantity": 1},
      {"barcode": "21464872", "quantity": 2},
      {
        "type": "custom",
        "title": "Özel Tasarım Tişört",
        "size": "XL",
        "price": 350.0,
        "quantity": 1
      }
    ],
    "payment_method": "pos",
    "new_customer": {
      "first_name": "Ali",
      "last_name": "Veli",
      "email": "ali@example.com",
      "phone": "+905551234567",
      "address": {
        "address1": "Atatürk Cad. No:123",
        "city": "Istanbul",
        "country": "Turkey"
      }
    },
    "discount": 200
  }'
```

---

### Örnek 3: Manuel Ürün Siparişi

```bash
curl -X POST "http://localhost:8080/orders/manual-create" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Özel Tasarım Hoodie",
    "size": "L",
    "price": 450.0,
    "quantity": 2,
    "payment_method": "cash",
    "email": "customer@example.com",
    "discount": 50
  }'
```

---

### Örnek 4: Günlük Satış Raporu

```bash
# Bugünün satış istatistiklerini al
curl -X GET "http://localhost:8080/orders/stats/today"

# Tüm siparişleri listele
curl -X GET "http://localhost:8080/orders?limit=100"
```

---

### Örnek 5: Webhook Loglarını İnceleme

```bash
# Başarısız webhook'ları görüntüle
curl -X GET "http://localhost:8080/webhooks/logs?status=failed&limit=20"

# Webhook istatistiklerini al
curl -X GET "http://localhost:8080/webhooks/stats"

# Belirli bir konuya ait webhook'ları görüntüle
curl -X GET "http://localhost:8080/webhooks/logs?topic=products/update&limit=50"
```

---

### Örnek 6: Python ile API Kullanımı

```python
import requests

BASE_URL = "http://localhost:8080"

# Ürün arama
def search_product(barcode):
    response = requests.get(f"{BASE_URL}/products/barcode/{barcode}")
    return response.json()

# Sipariş oluşturma
def create_order(items, email, payment_method="cash", discount=0):
    payload = {
        "items": items,
        "email": email,
        "payment_method": payment_method,
        "discount": discount
    }
    response = requests.post(f"{BASE_URL}/orders/create-cart", json=payload)
    return response.json()

# Kullanım
product = search_product("88834856")
print(f"Ürün: {product['products'][0]['title']}")

order = create_order(
    items=[{"barcode": "88834856", "quantity": 2}],
    email="customer@example.com",
    payment_method="cash",
    discount=100
)
print(f"Sipariş ID: {order['shopify_order_id']}")
```

---

### Örnek 7: JavaScript/Node.js ile API Kullanımı

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:8080';

// Müşteri arama
async function searchCustomer(email) {
  const response = await axios.get(`${BASE_URL}/customers/search`, {
    params: { email }
  });
  return response.data;
}

// Yeni müşteri ile sipariş oluşturma
async function createOrderWithNewCustomer(items, customerData, paymentMethod = 'cash') {
  const payload = {
    items,
    payment_method: paymentMethod,
    new_customer: customerData
  };
  
  const response = await axios.post(`${BASE_URL}/orders/create-cart`, payload);
  return response.data;
}

// Kullanım
(async () => {
  try {
    const order = await createOrderWithNewCustomer(
      [
        { barcode: '88834856', quantity: 1 },
        { type: 'custom', title: 'Özel Ürün', price: 250, quantity: 1 }
      ],
      {
        first_name: 'Mehmet',
        last_name: 'Yılmaz',
        email: 'mehmet@example.com',
        phone: '+905551234567'
      },
      'pos'
    );
    
    console.log('Sipariş oluşturuldu:', order.shopify_order_id);
  } catch (error) {
    console.error('Hata:', error.response.data);
  }
})();
```

---

## Best Practices

### 1. Senkronizasyon
- İlk kurulumda `/sync-products` ve `/customers/sync` endpoint'lerini çalıştırın
- Webhook'ları kurduktan sonra manuel sync'e gerek kalmaz
- Webhook sorunlarında günde 1 kez sync yapabilirsiniz

### 2. Hata Yönetimi
- Tüm API çağrılarında try-catch kullanın
- 422 hatalarında Shopify error details'i kontrol edin
- 500 hatalarında retry logic uygulayın

### 3. Performance
- Pagination kullanın (limit parametresi)
- Gereksiz sync çağrılarından kaçının
- Webhook'ları kullanarak gerçek zamanlı güncelleyin

### 4. Güvenlik
- Production'da HMAC webhook doğrulamasını etkinleştirin
- API'ye kimlik doğrulama ekleyin
- HTTPS kullanın
- Rate limiting ekleyin

### 5. Veritabanı
- Düzenli backup alın
- SQLite dosyasını güvenli bir yerde saklayın
- Büyük ölçekte PostgreSQL'e geçiş düşünün

---

## Destek ve Katkı

### Sorun Bildirme
Hata bulursanız veya öneriniz varsa lütfen bildirin.

### Versiyon Geçmişi
- **v1.0.0** (2024-11-15): İlk sürüm
  - Ürün, müşteri, sipariş yönetimi
  - Webhook desteği
  - Karışık sepet sistemi
  - İndirim özelliği

---

## Lisans
Bu proje MIT lisansı altında lisanslanmıştır.

---

**Son Güncelleme:** 15 Kasım 2024  
**API Version:** 1.0.0  
**Shopify API Version:** 2024-10

