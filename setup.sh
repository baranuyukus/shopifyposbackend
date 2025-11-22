#!/bin/bash

echo "🚀 Shopify POS Backend Kurulum Scripti"
echo "======================================="

# .env dosyası oluştur
if [ ! -f .env ]; then
    echo "📝 .env dosyası oluşturuluyor..."
    cat > .env << 'EOF'
# Shopify API Credentials
# Bu değerleri kendi Shopify bilgilerinizle değiştirin
SHOPIFY_API_KEY=your_api_key_here
SHOPIFY_API_SECRET=your_api_secret_here
SHOPIFY_ACCESS_TOKEN=your_access_token_here
SHOPIFY_SHOP_URL=your-shop.myshopify.com

# Database
DATABASE_URL=sqlite:///./local.db
EOF
    echo "✅ .env dosyası oluşturuldu"
else
    echo "ℹ️  .env dosyası zaten mevcut"
fi

# Virtual environment kontrol
if [ ! -d "env" ]; then
    echo "🔧 Virtual environment oluşturuluyor..."
    python3 -m venv env
    echo "✅ Virtual environment oluşturuldu"
else
    echo "ℹ️  Virtual environment zaten mevcut"
fi

# Virtual environment'ı aktifleştir
echo "🔌 Virtual environment aktifleştiriliyor..."
source env/bin/activate

# Bağımlılıkları yükle
echo "📦 Bağımlılıklar yükleniyor..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Kurulum tamamlandı!"
echo ""
echo "🎯 Sunucuyu başlatmak için:"
echo "   source env/bin/activate"
echo "   uvicorn main:app --reload"
echo ""
echo "📖 API Dokümantasyonu:"
echo "   http://127.0.0.1:8000/docs"
echo ""

