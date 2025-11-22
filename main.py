"""
FastAPI main application
Shopify POS & Inventory Backend
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from pydantic import BaseModel, EmailStr
import uvicorn
import json
import hmac
import hashlib
import base64
import os

from database import get_db, init_db
from models import Product, Customer, Order, WebhookEvent
from shopify import shopify_api
from webhooks import (
    handle_product_webhook,
    handle_product_delete,
    handle_inventory_update,
    handle_customer_webhook,
    handle_order_webhook
)


# ==================== PYDANTIC MODELS ====================

class CustomerAddress(BaseModel):
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None  # İl/Eyalet
    country: Optional[str] = "Turkey"
    zip: Optional[str] = None

class CustomerCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[CustomerAddress] = None

class CartItemBarcode(BaseModel):
    barcode: str
    quantity: int = 1

class CartItemCustom(BaseModel):
    type: str = "custom"
    title: str
    size: Optional[str] = ""
    price: float
    quantity: int = 1

class NewCustomerInOrder(BaseModel):
    """Customer info for creating new customer during order"""
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[CustomerAddress] = None

class CartOrder(BaseModel):
    items: List[dict]  # Can be mix of barcode and custom items
    payment_method: str
    email: Optional[str] = None  # Existing customer email
    new_customer: Optional[NewCustomerInOrder] = None  # Or create new customer
    discount: Optional[float] = 0
    discount_reason: Optional[str] = "Store discount"

class ManualOrder(BaseModel):
    title: str
    size: Optional[str] = ""
    price: float
    quantity: int = 1
    payment_method: str = "cash"
    email: Optional[str] = None
    discount: Optional[float] = 0

# Initialize FastAPI app
app = FastAPI(
    title="Shopify POS & Inventory API",
    description="Local backend for POS and inventory system integrated with Shopify",
    version="1.0.0"
)

# ==================== CORS MIDDLEWARE ====================
# CORS (Cross-Origin Resource Sharing) ayarları
# Frontend'den gelen isteklere izin vermek için gerekli

# Get allowed origins from environment variable or use defaults
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # Comma-separated list from environment variable
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
else:
    # Default origins for development
    allowed_origins = [
        "http://localhost:3000",      # React/Next.js development
        "http://127.0.0.1:3000",      # Alternative localhost
        "http://localhost:5173",      # Vite development
        "http://127.0.0.1:5173",      # Alternative Vite
        "http://192.168.1.134:3000",  # Network IP (mobil test için)
        "http://192.168.1.134:5173",  # Network IP Vite
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,           # Cookie ve authentication header'larına izin ver
    allow_methods=["*"],              # Tüm HTTP metodlarına izin ver (GET, POST, PUT, DELETE, OPTIONS)
    allow_headers=["*"],              # Tüm header'lara izin ver
)


@app.on_event("startup")
async def startup_event():
    """
    Initialize database on startup
    """
    init_db()
    print("✅ Database initialized")
    print("🚀 FastAPI server is running")
    print("📖 API Documentation: http://127.0.0.1:8000/docs")


@app.get("/", tags=["Health"])
async def root():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "message": "Shopify POS & Inventory Backend is running",
        "version": "1.0.0"
    }


@app.post("/sync-products", tags=["Sync"])
async def sync_products(db: Session = Depends(get_db)):
    """
    Sync all products from Shopify to local database
    Uses upsert logic: updates existing products or inserts new ones
    """
    try:
        # Fetch all products from Shopify
        print("🔄 Fetching products from Shopify...")
        shopify_products = shopify_api.get_all_products()
        
        added_count = 0
        updated_count = 0
        skipped_no_barcode = 0
        processed_variant_ids = set()  # Track processed variants in THIS sync to avoid API duplicates
        
        for product in shopify_products:
            product_title = product.get("title", "Unknown Product")
            product_id = product.get("id")
            
            # Get product image
            image_url = None
            if product.get("images") and len(product["images"]) > 0:
                image_url = product["images"][0].get("src")
            
            # Process each variant
            for variant in product.get("variants", []):
                variant_id = variant.get("id")
                barcode = variant.get("barcode")
                
                # Skip variants without barcode or variant_id
                if not barcode or not variant_id:
                    skipped_no_barcode += 1
                    continue
                
                # Skip if we already processed this exact variant_id in this sync
                # (Shopify API sometimes returns duplicates due to pagination)
                if variant_id in processed_variant_ids:
                    continue
                
                processed_variant_ids.add(variant_id)
                
                # UPSERT LOGIC: Check if product already exists by shopify_id
                existing_product = db.query(Product).filter(
                    Product.shopify_id == variant_id
                ).first()
                
                if existing_product:
                    # UPDATE existing product
                    existing_product.title = product_title
                    existing_product.shopify_product_id = product_id
                    existing_product.sku = variant.get("sku")
                    existing_product.barcode = barcode
                    existing_product.price = float(variant.get("price") or 0)
                    existing_product.inventory_quantity = int(variant.get("inventory_quantity") or 0)
                    existing_product.variant_title = variant.get("title")
                    existing_product.image_url = image_url
                    updated_count += 1
                else:
                    # INSERT new product
                    new_product = Product(
                        shopify_id=variant_id,
                        shopify_product_id=product_id,
                        title=product_title,
                        sku=variant.get("sku"),
                        barcode=barcode,
                        price=float(variant.get("price") or 0),
                        inventory_quantity=int(variant.get("inventory_quantity") or 0),
                        variant_title=variant.get("title"),
                        image_url=image_url
                    )
                    db.add(new_product)
                    added_count += 1
        
        # Commit all changes once at the end
        db.commit()
        
        print(f"✅ Sync complete: {added_count} added, {updated_count} updated, {skipped_no_barcode} skipped (no barcode)")
        
        return {
            "status": "ok",
            "added": added_count,
            "updated": updated_count,
            "skipped_no_barcode": skipped_no_barcode,
            "total_products": len(shopify_products)
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error syncing products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync products: {str(e)}"
        )


@app.get("/product/{barcode}", tags=["Products"])
async def get_product_by_barcode(barcode: str, db: Session = Depends(get_db)):
    """
    Get all products with the given barcode from local database
    Returns all matching products (multiple variants can have same barcode)
    """
    products = db.query(Product).filter(Product.barcode == barcode).all()
    
    if not products:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No products found with barcode '{barcode}'"
        )
    
    return {
        "status": "success",
        "count": len(products),
        "products": [product.to_dict() for product in products]
    }


@app.get("/products", tags=["Products"])
async def get_all_products(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all products from local database with pagination
    """
    products = db.query(Product).offset(skip).limit(limit).all()
    total = db.query(Product).count()
    
    return {
        "status": "success",
        "total": total,
        "showing": len(products),
        "products": [product.to_dict() for product in products]
    }


@app.get("/products/search", tags=["Products"])
async def search_products(
    query: str,
    db: Session = Depends(get_db)
):
    """
    Search products by title, SKU, or barcode
    """
    products = db.query(Product).filter(
        (Product.title.ilike(f"%{query}%")) |
        (Product.sku.ilike(f"%{query}%")) |
        (Product.barcode.ilike(f"%{query}%"))
    ).all()
    
    return {
        "status": "success",
        "query": query,
        "results": len(products),
        "products": [product.to_dict() for product in products]
    }


@app.delete("/products/clear", tags=["Products"])
async def clear_products(db: Session = Depends(get_db)):
    """
    Clear all products from local database
    Use with caution - this will delete all cached products
    """
    try:
        count = db.query(Product).delete()
        db.commit()
        
        return {
            "status": "success",
            "message": f"Deleted {count} products from local database"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear products: {str(e)}"
        )


# ==================== CUSTOMER ENDPOINTS ====================

@app.post("/customers/sync", tags=["Customers"])
async def sync_customers(db: Session = Depends(get_db)):
    """
    Sync all customers from Shopify to local database
    Fetches all customers and stores them locally for fast lookup
    """
    try:
        print("🔄 Fetching customers from Shopify...")
        shopify_customers = shopify_api.get_all_customers()
        
        added_count = 0
        updated_count = 0
        processed_customer_ids = set()  # Track processed customers in THIS sync to avoid API duplicates
        
        for customer in shopify_customers:
            customer_id = customer.get("id")
            
            if not customer_id:
                continue
            
            # Skip if we already processed this customer in this sync
            # (Shopify API sometimes returns duplicates due to pagination)
            if customer_id in processed_customer_ids:
                continue
            
            processed_customer_ids.add(customer_id)
            
            # Extract address information
            address_str = None
            city = None
            country = None
            
            if customer.get("addresses") and len(customer["addresses"]) > 0:
                addr = customer["addresses"][0]
                address_parts = []
                if addr.get("address1"):
                    address_parts.append(addr["address1"])
                if addr.get("address2"):
                    address_parts.append(addr["address2"])
                address_str = " ".join(address_parts) if address_parts else None
                city = addr.get("city")
                country = addr.get("country")
            
            # Check if customer already exists
            existing_customer = db.query(Customer).filter(
                Customer.shopify_id == customer_id
            ).first()
            
            if existing_customer:
                # UPDATE existing customer
                existing_customer.first_name = customer.get("first_name")
                existing_customer.last_name = customer.get("last_name")
                existing_customer.email = customer.get("email")
                existing_customer.phone = customer.get("phone")
                existing_customer.address = address_str
                existing_customer.city = city
                existing_customer.country = country
                updated_count += 1
            else:
                # INSERT new customer
                new_customer = Customer(
                    shopify_id=customer_id,
                    first_name=customer.get("first_name"),
                    last_name=customer.get("last_name"),
                    email=customer.get("email"),
                    phone=customer.get("phone"),
                    address=address_str,
                    city=city,
                    country=country
                )
                db.add(new_customer)
                added_count += 1
        
        # Commit all changes
        db.commit()
        
        print(f"✅ Customer sync complete: {added_count} added, {updated_count} updated")
        
        return {
            "status": "ok",
            "added": added_count,
            "updated": updated_count,
            "total_customers": len(shopify_customers)
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error syncing customers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync customers: {str(e)}"
        )


@app.get("/customers/search", tags=["Customers"])
async def search_customer(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Search customer by email, phone, or name (first_name, last_name, or full name)
    Searches local database first for instant results
    Falls back to Shopify API if not found locally
    
    Query Parameters:
    - email: Email address (exact match)
    - phone: Phone number (exact match)
    - first_name: First name (partial match, case-insensitive)
    - last_name: Last name (partial match, case-insensitive)
    - name: Full name (searches both first_name and last_name, partial match)
    
    At least one parameter is required.
    """
    if not email and not phone and not first_name and not last_name and not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least one search parameter: email, phone, first_name, last_name, or name"
        )
    
    results = []
    source = "local"
    
    # Search in local database first
    query = db.query(Customer)
    
    # Email search (exact match)
    if email:
        customers = query.filter(Customer.email.ilike(f"%{email}%")).all()
        if customers:
            results.extend([c.to_dict() for c in customers])
        else:
            # Not found locally, search Shopify
            print(f"🔍 Customer not found locally, searching Shopify for email: {email}")
            shopify_results = shopify_api.search_customer_by_email(email)
            if shopify_results:
                source = "shopify"
                # Convert Shopify format to our format
                for c in shopify_results:
                    results.append({
                        "shopify_id": c.get("id"),
                        "first_name": c.get("first_name"),
                        "last_name": c.get("last_name"),
                        "email": c.get("email"),
                        "phone": c.get("phone"),
                        "address": c.get("addresses", [{}])[0].get("address1") if c.get("addresses") else None,
                        "city": c.get("addresses", [{}])[0].get("city") if c.get("addresses") else None,
                        "country": c.get("addresses", [{}])[0].get("country") if c.get("addresses") else None,
                    })
    
    # Phone search (exact match)
    if phone:
        # Remove spaces, dashes, and parentheses for better matching
        phone_clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace("+", "")
        customers = query.filter(
            func.replace(func.replace(func.replace(Customer.phone, " ", ""), "-", ""), "+", "").ilike(f"%{phone_clean}%")
        ).all()
        if customers:
            results.extend([c.to_dict() for c in customers if c.to_dict() not in results])
        else:
            # Not found locally, search Shopify
            print(f"🔍 Customer not found locally, searching Shopify for phone: {phone}")
            shopify_results = shopify_api.search_customer_by_phone(phone)
            if shopify_results:
                source = "shopify"
                for c in shopify_results:
                    customer_dict = {
                        "shopify_id": c.get("id"),
                        "first_name": c.get("first_name"),
                        "last_name": c.get("last_name"),
                        "email": c.get("email"),
                        "phone": c.get("phone"),
                        "address": c.get("addresses", [{}])[0].get("address1") if c.get("addresses") else None,
                        "city": c.get("addresses", [{}])[0].get("city") if c.get("addresses") else None,
                        "country": c.get("addresses", [{}])[0].get("country") if c.get("addresses") else None,
                    }
                    if customer_dict not in results:
                        results.append(customer_dict)
    
    # Name search (partial match)
    if name:
        # Search by full name (searches both first_name and last_name)
        customers = query.filter(
            or_(
                Customer.first_name.ilike(f"%{name}%"),
                Customer.last_name.ilike(f"%{name}%"),
                func.concat(Customer.first_name, " ", Customer.last_name).ilike(f"%{name}%")
            )
        ).all()
        if customers:
            results.extend([c.to_dict() for c in customers if c.to_dict() not in results])
        else:
            # Not found locally, search Shopify
            print(f"🔍 Customer not found locally, searching Shopify for name: {name}")
            shopify_results = shopify_api.search_customer_by_name(name=name)
            if shopify_results:
                source = "shopify"
                for c in shopify_results:
                    customer_dict = {
                        "shopify_id": c.get("id"),
                        "first_name": c.get("first_name"),
                        "last_name": c.get("last_name"),
                        "email": c.get("email"),
                        "phone": c.get("phone"),
                        "address": c.get("addresses", [{}])[0].get("address1") if c.get("addresses") else None,
                        "city": c.get("addresses", [{}])[0].get("city") if c.get("addresses") else None,
                        "country": c.get("addresses", [{}])[0].get("country") if c.get("addresses") else None,
                    }
                    if customer_dict not in results:
                        results.append(customer_dict)
    
    # First name search
    if first_name:
        customers = query.filter(Customer.first_name.ilike(f"%{first_name}%")).all()
        if customers:
            results.extend([c.to_dict() for c in customers if c.to_dict() not in results])
        else:
            # Not found locally, search Shopify
            print(f"🔍 Customer not found locally, searching Shopify for first_name: {first_name}")
            shopify_results = shopify_api.search_customer_by_name(first_name=first_name)
            if shopify_results:
                source = "shopify"
                for c in shopify_results:
                    customer_dict = {
                        "shopify_id": c.get("id"),
                        "first_name": c.get("first_name"),
                        "last_name": c.get("last_name"),
                        "email": c.get("email"),
                        "phone": c.get("phone"),
                        "address": c.get("addresses", [{}])[0].get("address1") if c.get("addresses") else None,
                        "city": c.get("addresses", [{}])[0].get("city") if c.get("addresses") else None,
                        "country": c.get("addresses", [{}])[0].get("country") if c.get("addresses") else None,
                    }
                    if customer_dict not in results:
                        results.append(customer_dict)
    
    # Last name search
    if last_name:
        customers = query.filter(Customer.last_name.ilike(f"%{last_name}%")).all()
        if customers:
            results.extend([c.to_dict() for c in customers if c.to_dict() not in results])
        else:
            # Not found locally, search Shopify
            print(f"🔍 Customer not found locally, searching Shopify for last_name: {last_name}")
            shopify_results = shopify_api.search_customer_by_name(last_name=last_name)
            if shopify_results:
                source = "shopify"
                for c in shopify_results:
                    customer_dict = {
                        "shopify_id": c.get("id"),
                        "first_name": c.get("first_name"),
                        "last_name": c.get("last_name"),
                        "email": c.get("email"),
                        "phone": c.get("phone"),
                        "address": c.get("addresses", [{}])[0].get("address1") if c.get("addresses") else None,
                        "city": c.get("addresses", [{}])[0].get("city") if c.get("addresses") else None,
                        "country": c.get("addresses", [{}])[0].get("country") if c.get("addresses") else None,
                    }
                    if customer_dict not in results:
                        results.append(customer_dict)
    
    # Remove duplicates based on shopify_id or email
    seen = set()
    unique_results = []
    for r in results:
        identifier = r.get("shopify_id") or r.get("email")
        if identifier and identifier not in seen:
            seen.add(identifier)
            unique_results.append(r)
    
    if not unique_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No customers found matching the search criteria"
        )
    
    # If only one result and searching by email or phone (exact match), return single customer format for backward compatibility
    if len(unique_results) == 1 and (email or phone):
        return {
            "status": "success",
            "source": source,
            "customer": unique_results[0]
        }
    
    # Return multiple results
    return {
        "status": "success",
        "source": source,
        "count": len(unique_results),
        "customers": unique_results
    }


@app.post("/customers/create", tags=["Customers"])
async def create_customer(customer_data: CustomerCreate, db: Session = Depends(get_db)):
    """
    Create new customer in Shopify and save locally
    Required fields: first_name, last_name, email
    Optional: phone, address, city, country
    """
    try:
        print(f"📝 Creating customer in Shopify: {customer_data.email}")
        
        # Prepare customer data for Shopify
        customer_payload = {
            "first_name": customer_data.first_name,
            "last_name": customer_data.last_name,
            "email": customer_data.email,
            "phone": customer_data.phone
        }
        
        # Add address if provided
        if customer_data.address:
            customer_payload["addresses"] = [{
                "address1": customer_data.address.address1,
                "address2": customer_data.address.address2,
                "city": customer_data.address.city,
                "province": customer_data.address.province,
                "country": customer_data.address.country,
                "zip": customer_data.address.zip
            }]
        
        # Create customer in Shopify
        shopify_customer = shopify_api.create_customer(customer_payload)
        
        if not shopify_customer:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create customer in Shopify"
            )
        
        # Extract address information from Shopify response
        address_str = None
        city = None
        country = None
        
        if shopify_customer.get("addresses") and len(shopify_customer["addresses"]) > 0:
            addr = shopify_customer["addresses"][0]
            address_parts = []
            if addr.get("address1"):
                address_parts.append(addr["address1"])
            if addr.get("address2"):
                address_parts.append(addr["address2"])
            address_str = " ".join(address_parts) if address_parts else None
            city = addr.get("city")
            country = addr.get("country")
        
        # Save to local database
        new_customer = Customer(
            shopify_id=shopify_customer["id"],
            first_name=shopify_customer.get("first_name"),
            last_name=shopify_customer.get("last_name"),
            email=shopify_customer.get("email"),
            phone=shopify_customer.get("phone"),
            address=address_str,
            city=city,
            country=country
        )
        
        db.add(new_customer)
        db.commit()
        db.refresh(new_customer)
        
        print(f"✅ Customer created: {new_customer.email}")
        
        return {
            "status": "created",
            "customer": new_customer.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Customer creation failed: {str(e)}"
        )


@app.get("/customers", tags=["Customers"])
async def get_all_customers_local(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all customers from local database with pagination
    """
    customers = db.query(Customer).offset(skip).limit(limit).all()
    total = db.query(Customer).count()
    
    return {
        "status": "success",
        "total": total,
        "showing": len(customers),
        "customers": [customer.to_dict() for customer in customers]
    }


@app.get("/customers/{customer_id}", tags=["Customers"])
async def get_customer_by_id(customer_id: int, db: Session = Depends(get_db)):
    """
    Get customer by local database ID
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found"
        )
    
    return {
        "status": "success",
        "customer": customer.to_dict()
    }


# ==================== ORDER ENDPOINTS ====================

@app.post("/orders/create-cart", tags=["Orders"])
async def create_order_from_cart(
    request_data: CartOrder,
    db: Session = Depends(get_db)
):
    """
    Create a new Shopify order from POS cart system
    Supports mixed cart: barcode products + custom/manual products
    
    OPTION 1 - Use existing customer by email:
    {
        "items": [
            {"barcode": "88834856", "quantity": 2},
            {"type": "custom", "title": "Custom T-Shirt", "size": "XL", "price": 150.0, "quantity": 1}
        ],
        "payment_method": "cash",
        "email": "existing@customer.com",
        "discount": 100
    }
    
    OPTION 2 - Create new customer during order:
    {
        "items": [
            {"barcode": "88834856", "quantity": 2}
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
        "discount": 0
    }
    
    Note: Provide either 'email' (existing customer) OR 'new_customer' (create new), not both.
    """
    try:
        # Validate request data
        items = request_data.items
        payment_method = request_data.payment_method
        email = request_data.email
        new_customer_data = request_data.new_customer
        discount_amount = request_data.discount
        discount_reason = request_data.discount_reason
        
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Items list cannot be empty"
            )
        
        if not payment_method or payment_method not in ["cash", "pos"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment method. Must be 'cash' or 'pos'."
            )
        
        # Check if either email or new_customer is provided
        if not email and not new_customer_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'email' (for existing customer) or 'new_customer' (to create new) must be provided"
            )
        
        if email and new_customer_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either 'email' OR 'new_customer', not both"
            )
        
        customer = None
        
        # OPTION 1: Create new customer
        if new_customer_data:
            print(f"👤 Creating new customer: {new_customer_data.email}")
            
            # Check if customer already exists
            existing = db.query(Customer).filter(Customer.email == new_customer_data.email).first()
            if existing:
                print(f"⚠️  Customer already exists with email: {new_customer_data.email}")
                customer = existing
            else:
                # Prepare customer data for Shopify
                customer_payload = {
                    "first_name": new_customer_data.first_name,
                    "last_name": new_customer_data.last_name,
                    "email": new_customer_data.email,
                    "phone": new_customer_data.phone
                }
                
                # Add address if provided
                if new_customer_data.address:
                    customer_payload["addresses"] = [{
                        "address1": new_customer_data.address.address1,
                        "address2": new_customer_data.address.address2,
                        "city": new_customer_data.address.city,
                        "province": new_customer_data.address.province,
                        "country": new_customer_data.address.country,
                        "zip": new_customer_data.address.zip
                    }]
                
                # Create customer in Shopify
                shopify_customer = shopify_api.create_customer(customer_payload)
                
                if not shopify_customer:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create customer in Shopify"
                    )
                
                # Extract address information from Shopify response
                address_str = None
                city = None
                country = None
                
                if shopify_customer.get("addresses") and len(shopify_customer["addresses"]) > 0:
                    addr = shopify_customer["addresses"][0]
                    address_parts = []
                    if addr.get("address1"):
                        address_parts.append(addr["address1"])
                    if addr.get("address2"):
                        address_parts.append(addr["address2"])
                    address_str = " ".join(address_parts) if address_parts else None
                    city = addr.get("city")
                    country = addr.get("country")
                
                # Save to local database
                customer = Customer(
                    shopify_id=shopify_customer["id"],
                    first_name=shopify_customer.get("first_name"),
                    last_name=shopify_customer.get("last_name"),
                    email=shopify_customer.get("email"),
                    phone=shopify_customer.get("phone"),
                    address=address_str,
                    city=city,
                    country=country
                )
                
                db.add(customer)
                db.commit()
                db.refresh(customer)
                print(f"✅ New customer created and saved: {customer.email}")
        
        # OPTION 2: Use existing customer by email
        else:
            # Find customer locally
            customer = db.query(Customer).filter(Customer.email == email).first()
            
            if not customer:
                print(f"🔍 Customer not found locally, searching Shopify: {email}")
                shopify_customers = shopify_api.search_customer_by_email(email)
                
                if shopify_customers:
                    c = shopify_customers[0]
                    address_str = None
                    city = None
                    country = None
                    
                    if c.get("addresses") and len(c["addresses"]) > 0:
                        addr = c["addresses"][0]
                        address_parts = []
                        if addr.get("address1"):
                            address_parts.append(addr["address1"])
                        if addr.get("address2"):
                            address_parts.append(addr["address2"])
                        address_str = " ".join(address_parts) if address_parts else None
                        city = addr.get("city")
                        country = addr.get("country")
                    
                    customer = Customer(
                        shopify_id=c["id"],
                        first_name=c.get("first_name"),
                        last_name=c.get("last_name"),
                        email=c.get("email"),
                        phone=c.get("phone"),
                        address=address_str,
                        city=city,
                        country=country
                    )
                    db.add(customer)
                    db.commit()
                    db.refresh(customer)
                    print(f"✅ Customer saved to local DB: {customer.email}")
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Customer with email '{email}' not found. Use 'new_customer' to create a new one."
                    )
        
        # Process cart items and build line_items for Shopify
        line_items = []
        local_orders = []
        total_amount = 0
        
        for item in items:
            item_type = item.get("type", "barcode")  # Default to barcode type
            quantity = item.get("quantity", 1)
            
            if item_type == "custom":
                # CUSTOM/MANUAL PRODUCT
                custom_title = item.get("title")
                custom_size = item.get("size", "")
                custom_price = float(item.get("price", 0))
                
                if not custom_title or custom_price <= 0:
                    print(f"⚠️ Invalid custom product, skipping...")
                    continue
                
                full_title = f"{custom_title} - {custom_size}" if custom_size else custom_title
                
                # Add to Shopify line_items
                line_items.append({
                    "title": full_title,
                    "quantity": quantity,
                    "price": str(custom_price)
                })
                
                # Prepare local order record for custom product
                local_orders.append({
                    "type": "custom",
                    "title": full_title,
                    "quantity": quantity,
                    "price": custom_price,
                    "barcode": None,
                    "product": None
                })
                
                total_amount += custom_price * quantity
                
                print(f"  ✏️ Custom: {full_title} x{quantity} = {custom_price * quantity}")
                
            else:
                # BARCODE PRODUCT
                barcode = item.get("barcode")
                
                if not barcode:
                    continue
                
                # Find products by barcode
                products = db.query(Product).filter(Product.barcode == barcode).all()
                
                if not products:
                    print(f"⚠️ Product with barcode {barcode} not found, skipping...")
                    continue
                
                # Select product with stock if available
                product = None
                for p in products:
                    if p.inventory_quantity > 0:
                        product = p
                        break
                
                if not product:
                    product = products[0]
                
                # Add to Shopify line_items
                line_items.append({
                    "title": product.title,
                    "quantity": quantity,
                    "price": str(product.price),
                    "variant_id": product.shopify_id,
                })
                
                # Prepare local order record
                local_orders.append({
                    "type": "barcode",
                    "product": product,
                    "quantity": quantity,
                    "barcode": barcode,
                    "title": product.title,
                    "price": product.price
                })
                
                total_amount += product.price * quantity
                
                print(f"  📦 {product.title} x{quantity} = {product.price * quantity}")
        
        if not line_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid products found in cart"
            )
        
        # Apply discount if provided
        original_total = total_amount
        if discount_amount > 0:
            if discount_amount >= total_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Discount amount ({discount_amount}) cannot be greater than or equal to total ({total_amount})"
                )
            total_amount = total_amount - discount_amount
            print(f"💰 Discount applied: -{discount_amount} (Original: {original_total} → Final: {total_amount})")
        
        print(f"🛒 Creating order with {len(line_items)} items, total: {total_amount}")
        
        # Create order in Shopify with all line items
        order_payload = {
            "order": {
                "line_items": line_items,
                "tags": f"in-store, {payment_method}",
                "financial_status": "paid",
                "email": customer.email,
                "customer": {"id": customer.shopify_id} if customer.shopify_id else None,
                "transactions": [{
                    "kind": "sale",
                    "status": "success",
                    "amount": str(total_amount),
                    "gateway": "cash" if payment_method == "cash" else "pos"
                }]
            }
        }
        
        # Add discount as a line item if discount was applied
        if discount_amount > 0:
            order_payload["order"]["note"] = f"Discount applied: {discount_amount} TL - Reason: {discount_reason}"
            # Add discount as negative line item
            order_payload["order"]["line_items"].append({
                "title": f"Discount - {discount_reason}",
                "quantity": 1,
                "price": str(-discount_amount),
            })
        
        print(f"📦 Creating order in Shopify...")
        response = shopify_api._make_request("POST", "orders.json", data=order_payload)
        shopify_order = response.get("order")
        
        if not shopify_order:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order in Shopify"
            )
        
        print(f"✅ Order created in Shopify: #{shopify_order.get('order_number')}")
        
        # Save each item as separate local order record
        created_orders = []
        for order_data in local_orders:
            if order_data.get("type") == "custom":
                # Custom product order
                new_order = Order(
                    shopify_order_id=shopify_order.get("id"),
                    customer_id=customer.id,
                    product_id=None,  # No product ID for custom items
                    barcode=None,  # No barcode for custom items
                    title=order_data["title"],
                    quantity=order_data["quantity"],
                    price=order_data["price"],
                    payment_method=payment_method,
                    status="completed"
                )
            else:
                # Barcode product order
                new_order = Order(
                    shopify_order_id=shopify_order.get("id"),
                    customer_id=customer.id,
                    product_id=order_data["product"].id,
                    barcode=order_data["barcode"],
                    title=order_data["title"],
                    quantity=order_data["quantity"],
                    price=order_data["price"],
                    payment_method=payment_method,
                    status="completed"
                )
            
            db.add(new_order)
            created_orders.append(new_order.to_dict())
        
        db.commit()
        
        print(f"✅ {len(created_orders)} orders saved to local DB")
        
        # Generate PDF receipt
        try:
            from utils.pdf_generator import generate_order_pdf
            
            # Prepare data for PDF
            pdf_data = {
                "shopify_order_number": shopify_order.get("order_number"),
                "shopify_order_id": shopify_order.get("id"),
                "customer_name": f"{customer.first_name} {customer.last_name}",
                "email": customer.email,
                "payment_method": payment_method,
                "discount_applied": discount_amount,
                "original_amount": original_total,
                "final_amount": total_amount,
                "items": [
                    {
                        "title": order.get("title"),
                        "quantity": order.get("quantity"),
                        "price": order.get("price")
                    }
                    for order in created_orders
                ]
            }
            
            pdf_path = generate_order_pdf(pdf_data)
            print(f"🧾 Receipt generated: {pdf_path}")
            
        except Exception as pdf_error:
            print(f"⚠️  PDF generation failed (order still created): {pdf_error}")
            # Don't fail the order if PDF generation fails
        
        response_data = {
            "status": "success",
            "message": f"Order created with {len(line_items)} items ({payment_method})",
            "shopify_order_id": shopify_order.get("id"),
            "shopify_order_number": shopify_order.get("order_number"),
            "original_amount": original_total,
            "final_amount": total_amount,
            "items_count": len(line_items),
            "orders": created_orders
        }
        
        if discount_amount > 0:
            response_data["discount_applied"] = discount_amount
            response_data["discount_reason"] = discount_reason
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating order: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Order creation failed: {str(e)}"
        )


@app.post("/orders/create", tags=["Orders"])
async def create_order_endpoint(
    barcode: str,
    payment_method: str,
    email: str,
    quantity: int = 1,
    db: Session = Depends(get_db)
):
    """
    Create a new Shopify order from POS system
    - Finds product(s) by barcode (may return multiple variants)
    - Finds customer by email
    - Creates order on Shopify with tags and payment info
    - Saves order locally
    
    Parameters:
    - barcode: Product barcode
    - payment_method: "cash" or "pos"
    - email: Customer email
    - quantity: Quantity to order (default: 1)
    """
    try:
        # Validate payment method
        if payment_method not in ["cash", "pos"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment method. Must be 'cash' or 'pos'."
            )
        
        # Find products by barcode (may be multiple variants with same barcode)
        products = db.query(Product).filter(Product.barcode == barcode).all()
        
        if not products:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with barcode '{barcode}' not found"
            )
        
        # If multiple products with same barcode, use the first one with stock
        product = None
        for p in products:
            if p.inventory_quantity > 0:
                product = p
                break
        
        # If no product with stock, just use the first one
        if not product:
            product = products[0]
        
        print(f"🛒 Processing order: {product.title} (barcode: {barcode})")
        
        # Find customer by email
        customer = db.query(Customer).filter(Customer.email == email).first()
        
        if not customer:
            # Search Shopify if not found locally
            print(f"🔍 Customer not found locally, searching Shopify: {email}")
            shopify_customers = shopify_api.search_customer_by_email(email)
            
            if shopify_customers:
                c = shopify_customers[0]
                # Save customer to local DB
                address_str = None
                city = None
                country = None
                
                if c.get("addresses") and len(c["addresses"]) > 0:
                    addr = c["addresses"][0]
                    address_parts = []
                    if addr.get("address1"):
                        address_parts.append(addr["address1"])
                    if addr.get("address2"):
                        address_parts.append(addr["address2"])
                    address_str = " ".join(address_parts) if address_parts else None
                    city = addr.get("city")
                    country = addr.get("country")
                
                customer = Customer(
                    shopify_id=c["id"],
                    first_name=c.get("first_name"),
                    last_name=c.get("last_name"),
                    email=c.get("email"),
                    phone=c.get("phone"),
                    address=address_str,
                    city=city,
                    country=country
                )
                db.add(customer)
                db.commit()
                db.refresh(customer)
                print(f"✅ Customer saved to local DB: {customer.email}")
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer with email '{email}' not found in local DB or Shopify"
                )
        
        # Create order in Shopify
        shopify_order = shopify_api.create_order(
            product.to_dict(),
            customer.to_dict(),
            payment_method
        )
        
        if not shopify_order:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order in Shopify"
            )
        
        # Save order locally
        new_order = Order(
            shopify_order_id=shopify_order.get("id"),
            customer_id=customer.id,
            product_id=product.id,
            barcode=barcode,
            title=product.title,
            quantity=quantity,
            price=product.price,
            payment_method=payment_method,
            status="completed"
        )
        
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        
        print(f"✅ Order saved to local DB: Order #{new_order.id}")
        
        return {
            "status": "success",
            "message": f"Order created for {product.title} ({payment_method})",
            "order": new_order.to_dict(),
            "shopify_order_number": shopify_order.get("order_number")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating order: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Order creation failed: {str(e)}"
        )


@app.get("/orders", tags=["Orders"])
async def get_all_orders_local(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all orders from local database with pagination
    """
    orders = db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    total = db.query(Order).count()
    
    return {
        "status": "success",
        "total": total,
        "showing": len(orders),
        "orders": [order.to_dict() for order in orders]
    }


@app.get("/orders/{order_id}", tags=["Orders"])
async def get_order_by_id(order_id: int, db: Session = Depends(get_db)):
    """
    Get order by local database ID
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found"
        )
    
    return {
        "status": "success",
        "order": order.to_dict()
    }


@app.post("/orders/manual-create", tags=["Orders"])
async def create_manual_order_endpoint(
    request_data: ManualOrder,
    db: Session = Depends(get_db)
):
    """
    Create a manual order for a product NOT in Shopify inventory
    Useful for custom items, services, or products without barcode
    
    Request body:
    {
        "title": "Custom T-Shirt",
        "size": "XL",  // Optional
        "price": 150.0,
        "quantity": 1,  // Optional, default 1
        "payment_method": "cash",  // or "pos"
        "email": "customer@example.com",  // Optional
        "discount": 0  // Optional
    }
    """
    try:
        # Extract and validate request data
        title = request_data.title
        size = request_data.size
        price = request_data.price
        quantity = request_data.quantity
        payment_method = request_data.payment_method
        email = request_data.email
        discount = request_data.discount
        
        # Validate required fields
        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product title is required"
            )
        
        if price <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Price must be greater than 0"
            )
        
        if payment_method not in ["cash", "pos"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment method. Must be 'cash' or 'pos'."
            )
        
        if quantity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity must be at least 1"
            )
        
        # Calculate totals
        item_total = price * quantity
        if discount >= item_total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Discount ({discount}) cannot be greater than or equal to total ({item_total})"
            )
        
        final_amount = item_total - discount
        
        # Find or search customer
        customer = None
        if email:
            customer = db.query(Customer).filter(Customer.email == email).first()
            
            if not customer:
                print(f"🔍 Customer not found locally, searching Shopify: {email}")
                shopify_customers = shopify_api.search_customer_by_email(email)
                
                if shopify_customers:
                    c = shopify_customers[0]
                    address_str = None
                    city = None
                    country = None
                    
                    if c.get("addresses") and len(c["addresses"]) > 0:
                        addr = c["addresses"][0]
                        address_parts = []
                        if addr.get("address1"):
                            address_parts.append(addr["address1"])
                        if addr.get("address2"):
                            address_parts.append(addr["address2"])
                        address_str = " ".join(address_parts) if address_parts else None
                        city = addr.get("city")
                        country = addr.get("country")
                    
                    customer = Customer(
                        shopify_id=c["id"],
                        first_name=c.get("first_name"),
                        last_name=c.get("last_name"),
                        email=c.get("email"),
                        phone=c.get("phone"),
                        address=address_str,
                        city=city,
                        country=country
                    )
                    db.add(customer)
                    db.commit()
                    db.refresh(customer)
                    print(f"✅ Customer saved to local DB: {customer.email}")
        
        print(f"📝 Creating manual order: {title} {f'- {size}' if size else ''} x{quantity} = {item_total} TL")
        if discount > 0:
            print(f"💰 Discount: -{discount} TL → Final: {final_amount} TL")
        
        # Create order in Shopify
        shopify_order = shopify_api.create_manual_order(
            title=title,
            size=size,
            price=price,
            quantity=quantity,
            customer=customer.to_dict() if customer else None,
            payment_method=payment_method,
            discount=discount
        )
        
        if not shopify_order:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create manual order in Shopify"
            )
        
        # Save locally
        full_title = f"{title} - {size}" if size else title
        new_order = Order(
            shopify_order_id=shopify_order.get("id"),
            customer_id=customer.id if customer else None,
            product_id=None,  # No product ID for manual orders
            barcode=None,  # No barcode for manual orders
            title=full_title,
            quantity=quantity,
            price=price,
            payment_method=payment_method,
            status="completed"
        )
        
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        
        print(f"✅ Manual order saved to local DB: Order #{new_order.id}")
        
        response_data = {
            "status": "success",
            "message": f"Manual order created for '{full_title}' ({payment_method})",
            "shopify_order_id": shopify_order.get("id"),
            "shopify_order_number": shopify_order.get("order_number"),
            "order": new_order.to_dict(),
            "original_amount": item_total,
            "final_amount": final_amount
        }
        
        if discount > 0:
            response_data["discount_applied"] = discount
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating manual order: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual order creation failed: {str(e)}"
        )


@app.get("/orders/stats/today", tags=["Orders"])
async def get_today_stats(db: Session = Depends(get_db)):
    """
    Get today's sales statistics from Shopify
    Fetches all orders created today from Shopify API (including online store orders)
    """
    from datetime import datetime, timedelta
    
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # End date should be end of today (23:59:59)
        today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Format dates for Shopify API (ISO 8601)
        start_date_str = today_start.strftime("%Y-%m-%dT%H:%M:%S")
        end_date_str = today_end.strftime("%Y-%m-%dT%H:%M:%S")
        
        print(f"📊 Fetching today's orders from Shopify: {today_start.date()} (00:00:00 to 23:59:59)")
        print(f"   Date range: {start_date_str} to {end_date_str}")
        
        # Fetch orders from Shopify (get a bit more to account for timezone differences)
        # Fetch from yesterday to tomorrow to catch all today's orders regardless of timezone
        yesterday_start = (today_start - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
        tomorrow_end = (today_end + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59")
        
        shopify_orders_all = shopify_api.get_orders_by_date_range(
            start_date=yesterday_start,
            end_date=tomorrow_end,
            status="any"
        )
        
        print(f"   📦 Total orders fetched from Shopify (extended range): {len(shopify_orders_all)}")
        
        # Filter orders created today (check both created_at and order date)
        shopify_orders = []
        today_date_str = today_start.date().isoformat()
        
        for order in shopify_orders_all:
            order_created_at = order.get("created_at", "")
            if order_created_at:
                # Parse the date from ISO format (handle timezone)
                try:
                    # Try parsing ISO format with timezone
                    if 'T' in order_created_at:
                        order_dt_str = order_created_at.split('T')[0]
                        if order_dt_str == today_date_str:
                            shopify_orders.append(order)
                    else:
                        # Fallback: simple string comparison
                        if order_created_at.startswith(today_date_str):
                            shopify_orders.append(order)
                except Exception as e:
                    print(f"   ⚠️  Error parsing order date: {e}")
                    # Fallback: simple string comparison
                    if order_created_at.startswith(today_date_str):
                        shopify_orders.append(order)
        
        print(f"   ✅ Orders created today: {len(shopify_orders)}")
        
        # Filter out cancelled/voided orders (but keep all others including unpaid)
        active_orders = [
            order for order in shopify_orders 
            if order.get("financial_status") != "voided" and 
               order.get("cancelled_at") is None
        ]
        
        cancelled_orders = [
            order for order in shopify_orders 
            if order.get("financial_status") == "voided" or 
               order.get("cancelled_at") is not None
        ]
        
        print(f"   ✅ Active orders: {len(active_orders)}, Cancelled: {len(cancelled_orders)}")
        
        # Calculate refund information
        total_refunded_amount = 0.0
        
        for order in active_orders:
            refunds = order.get("refunds", [])
            if refunds:
                order_refund_total = sum(
                    sum(float(transaction.get("amount", 0)) for transaction in refund.get("transactions", []))
                    for refund in refunds
                )
                if order_refund_total > 0:
                    total_refunded_amount += order_refund_total
        
        # Calculate gross and net revenue
        total_gross_revenue = sum(float(order.get("total_price", 0)) for order in active_orders)
        total_net_revenue = total_gross_revenue - total_refunded_amount
        
        # Payment method breakdown (from tags)
        cash_orders = [o for o in active_orders if "cash" in o.get("tags", "").lower()]
        pos_orders = [o for o in active_orders if "pos" in o.get("tags", "").lower()]
        online_orders = [o for o in active_orders if "cash" not in o.get("tags", "").lower() and "pos" not in o.get("tags", "").lower()]
        
        cash_sales = sum(float(order.get("total_price", 0)) for order in cash_orders)
        pos_sales = sum(float(order.get("total_price", 0)) for order in pos_orders)
        online_sales = sum(float(order.get("total_price", 0)) for order in online_orders)
        
        # Apply refunds to payment methods (approximate)
        # Note: This is an approximation since refunds don't specify payment method
        if total_gross_revenue > 0:
            cash_refunded = (cash_sales / total_gross_revenue) * total_refunded_amount if total_gross_revenue > 0 else 0
            pos_refunded = (pos_sales / total_gross_revenue) * total_refunded_amount if total_gross_revenue > 0 else 0
            online_refunded = (online_sales / total_gross_revenue) * total_refunded_amount if total_gross_revenue > 0 else 0
            
            cash_sales -= cash_refunded
            pos_sales -= pos_refunded
            online_sales -= online_refunded
        
        # Product sales breakdown
        product_sales = {}
        total_products_sold = 0
        
        for order in active_orders:
            for item in order.get("line_items", []):
                product_title = item.get("title", "Unknown Product")
                quantity = item.get("quantity", 0)
                price = float(item.get("price", 0))
                total = quantity * price
                
                if product_title not in product_sales:
                    product_sales[product_title] = {
                        "product_name": product_title,
                        "total_quantity": 0,
                        "total_revenue": 0.0,
                        "order_count": 0,
                        "sku": item.get("sku"),
                        "variant_title": item.get("variant_title")
                    }
                
                product_sales[product_title]["total_quantity"] += quantity
                product_sales[product_title]["total_revenue"] += total
                product_sales[product_title]["order_count"] += 1
                total_products_sold += quantity
        
        # Sort products by revenue
        top_products = sorted(
            product_sales.values(),
            key=lambda x: x["total_revenue"],
            reverse=True
        )
        
        return {
            "status": "success",
            "date": today_start.date().isoformat(),
            "total_orders": len(active_orders),
            "gross_revenue": round(total_gross_revenue, 2),
            "total_refunded": round(total_refunded_amount, 2),
            "net_revenue": round(total_net_revenue, 2),
            "total_sales": round(total_net_revenue, 2),  # Same as net_revenue for backward compatibility
            "cash_sales": round(cash_sales, 2),
            "pos_sales": round(pos_sales, 2),
            "online_sales": round(online_sales, 2),
            "cancelled_orders": len(cancelled_orders),
            "total_products_sold": total_products_sold,
            "unique_products": len(product_sales),
            "payment_breakdown": {
                "cash": {
                    "count": len(cash_orders),
                    "amount": round(cash_sales, 2)
                },
                "pos": {
                    "count": len(pos_orders),
                    "amount": round(pos_sales, 2)
                },
                "online": {
                    "count": len(online_orders),
                    "amount": round(online_sales, 2)
                }
            },
            "product_sales": top_products  # All products sold today
        }
        
    except Exception as e:
        print(f"❌ Error fetching today's stats: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch today's stats: {str(e)}"
        )


@app.get("/orders/reports/weekly", tags=["Orders", "Reports"])
async def get_weekly_orders_report(db: Session = Depends(get_db)):
    """
    Get weekly orders report (last 7 days)
    Fetches orders from Shopify for the past week
    """
    from datetime import datetime, timedelta
    
    try:
        # Calculate date range (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Format dates for Shopify API (ISO 8601)
        start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
        end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")
        
        print(f"📊 Fetching weekly orders report: {start_date.date()} to {end_date.date()}")
        
        # Fetch orders from Shopify
        shopify_orders = shopify_api.get_orders_by_date_range(
            start_date=start_date_str,
            end_date=end_date_str,
            status="any"
        )
        
        # Filter out cancelled orders for accurate revenue calculation
        active_orders = [
            order for order in shopify_orders 
            if order.get("financial_status") != "voided" and 
               order.get("cancelled_at") is None
        ]
        
        cancelled_orders = [
            order for order in shopify_orders 
            if order.get("financial_status") == "voided" or 
               order.get("cancelled_at") is not None
        ]
        
        # Calculate refund information
        total_refunded_amount = 0.0
        partially_refunded_orders = []
        fully_refunded_orders = []
        
        for order in active_orders:
            refunds = order.get("refunds", [])
            if refunds:
                order_refund_total = sum(
                    sum(float(transaction.get("amount", 0)) for transaction in refund.get("transactions", []))
                    for refund in refunds
                )
                
                if order_refund_total > 0:
                    total_refunded_amount += order_refund_total
                    
                    # Prepare line items for refund order
                    line_items_details = []
                    for item in order.get("line_items", []):
                        item_detail = {
                            "title": item.get("title", "Unknown Product"),
                            "quantity": item.get("quantity", 0),
                            "price": float(item.get("price", 0)),
                            "total": float(item.get("price", 0)) * item.get("quantity", 0),
                            "sku": item.get("sku"),
                            "variant_title": item.get("variant_title"),
                            "variant_id": item.get("variant_id"),
                            "product_id": item.get("product_id"),
                            "image": item.get("image") or None
                        }
                        line_items_details.append(item_detail)
                    
                    customer = order.get("customer", {})
                    order_info = {
                        "order_number": order.get("order_number"),
                        "order_id": order.get("id"),
                        "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Guest",
                        "customer_first_name": customer.get("first_name"),
                        "customer_last_name": customer.get("last_name"),
                        "customer_email": customer.get("email"),
                        "customer_phone": customer.get("phone"),
                        "original_total": float(order.get("total_price", 0)),
                        "refunded_amount": order_refund_total,
                        "net_payment": float(order.get("total_price", 0)) - order_refund_total,
                        "financial_status": order.get("financial_status"),
                        "refund_count": len(refunds),
                        "line_items": line_items_details,  # Product details for refunded order
                        "created_at": order.get("created_at")
                    }
                    
                    # Check if fully or partially refunded
                    if order.get("financial_status") == "refunded":
                        fully_refunded_orders.append(order_info)
                    elif order.get("financial_status") == "partially_refunded":
                        partially_refunded_orders.append(order_info)
        
        # Calculate statistics (from active orders minus refunds)
        total_orders = len(active_orders)
        total_gross_revenue = sum(float(order.get("total_price", 0)) for order in active_orders)
        total_net_revenue = total_gross_revenue - total_refunded_amount
        total_revenue = total_net_revenue  # Use net revenue as the main revenue
        
        # Group by day (only active orders)
        orders_by_day = {}
        for order in active_orders:
            order_date = order.get("created_at", "")[:10]  # Extract YYYY-MM-DD
            if order_date not in orders_by_day:
                orders_by_day[order_date] = {
                    "count": 0,
                    "revenue": 0.0,
                    "orders": []
                }
            orders_by_day[order_date]["count"] += 1
            orders_by_day[order_date]["revenue"] += float(order.get("total_price", 0))
            
            # Prepare line items with product details
            line_items_details = []
            for item in order.get("line_items", []):
                item_detail = {
                    "title": item.get("title", "Unknown Product"),
                    "quantity": item.get("quantity", 0),
                    "price": float(item.get("price", 0)),
                    "total": float(item.get("price", 0)) * item.get("quantity", 0),
                    "sku": item.get("sku"),
                    "variant_title": item.get("variant_title"),
                    "variant_id": item.get("variant_id"),
                    "product_id": item.get("product_id"),
                    "image": item.get("image") or None  # Product image URL
                }
                line_items_details.append(item_detail)
            
            customer = order.get("customer", {})
            orders_by_day[order_date]["orders"].append({
                "order_number": order.get("order_number"),
                "order_id": order.get("id"),
                "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Guest",
                "customer_first_name": customer.get("first_name"),
                "customer_last_name": customer.get("last_name"),
                "customer_email": customer.get("email"),
                "customer_phone": customer.get("phone"),
                "total": float(order.get("total_price", 0)),
                "items_count": len(order.get("line_items", [])),
                "line_items": line_items_details,  # Detailed product information
                "financial_status": order.get("financial_status"),
                "created_at": order.get("created_at")
            })
        
        # Payment method breakdown (only active orders)
        cash_orders = [o for o in active_orders if "cash" in o.get("tags", "").lower()]
        pos_orders = [o for o in active_orders if "pos" in o.get("tags", "").lower()]
        
        # Product sales breakdown (only active orders)
        product_sales = {}
        product_daily_sales = {}
        
        for order in active_orders:
            order_date = order.get("created_at", "")[:10]
            
            for item in order.get("line_items", []):
                product_title = item.get("title", "Unknown Product")
                quantity = item.get("quantity", 0)
                price = float(item.get("price", 0))
                total = quantity * price
                
                # Overall product sales
                if product_title not in product_sales:
                    product_sales[product_title] = {
                        "product_name": product_title,
                        "total_quantity": 0,
                        "total_revenue": 0.0,
                        "order_count": 0,
                        "sku": item.get("sku"),
                        "variant_title": item.get("variant_title")
                    }
                
                product_sales[product_title]["total_quantity"] += quantity
                product_sales[product_title]["total_revenue"] += total
                product_sales[product_title]["order_count"] += 1
                
                # Daily product sales
                if order_date not in product_daily_sales:
                    product_daily_sales[order_date] = {}
                
                if product_title not in product_daily_sales[order_date]:
                    product_daily_sales[order_date][product_title] = {
                        "quantity": 0,
                        "revenue": 0.0
                    }
                
                product_daily_sales[order_date][product_title]["quantity"] += quantity
                product_daily_sales[order_date][product_title]["revenue"] += total
        
        # Sort products by revenue
        top_products = sorted(
            product_sales.values(),
            key=lambda x: x["total_revenue"],
            reverse=True
        )
        
        return {
            "status": "success",
            "period": "weekly",
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "summary": {
                "total_orders": total_orders,
                "gross_revenue": round(total_gross_revenue, 2),
                "total_refunded": round(total_refunded_amount, 2),
                "net_revenue": round(total_net_revenue, 2),
                "total_revenue": round(total_revenue, 2),  # Same as net_revenue
                "average_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
                "cash_orders": len(cash_orders),
                "pos_orders": len(pos_orders),
                "total_products_sold": sum(p["total_quantity"] for p in product_sales.values()),
                "unique_products": len(product_sales),
                "cancelled_orders": len(cancelled_orders),
                "cancelled_revenue": round(sum(float(order.get("total_price", 0)) for order in cancelled_orders), 2),
                "partially_refunded_count": len(partially_refunded_orders),
                "fully_refunded_count": len(fully_refunded_orders),
                "total_refund_transactions": len(partially_refunded_orders) + len(fully_refunded_orders)
            },
            "daily_breakdown": orders_by_day,
            "refund_details": {
                "partially_refunded": partially_refunded_orders,
                "fully_refunded": fully_refunded_orders,
                "total_refunded_amount": round(total_refunded_amount, 2)
            },
            "top_products": top_products[:20],  # Top 20 products
            "product_daily_sales": product_daily_sales,
            "orders": [
                {
                    "order_number": order.get("order_number"),
                    "order_id": order.get("id"),
                    "customer_name": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip() or "Guest",
                    "customer_first_name": order.get("customer", {}).get("first_name"),
                    "customer_last_name": order.get("customer", {}).get("last_name"),
                    "customer_email": order.get("customer", {}).get("email"),
                    "customer_phone": order.get("customer", {}).get("phone"),
                    "total": float(order.get("total_price", 0)),
                    "items_count": len(order.get("line_items", [])),
                    "line_items": [
                        {
                            "title": item.get("title", "Unknown Product"),
                            "quantity": item.get("quantity", 0),
                            "price": float(item.get("price", 0)),
                            "total": float(item.get("price", 0)) * item.get("quantity", 0),
                            "sku": item.get("sku"),
                            "variant_title": item.get("variant_title"),
                            "variant_id": item.get("variant_id"),
                            "product_id": item.get("product_id"),
                            "image": item.get("image") or None  # Product image URL
                        }
                        for item in order.get("line_items", [])
                    ],
                    "financial_status": order.get("financial_status"),
                    "tags": order.get("tags"),
                    "created_at": order.get("created_at"),
                    "cancelled_at": order.get("cancelled_at")
                }
                for order in active_orders  # Only show active orders in the list
            ]
        }
        
    except Exception as e:
        print(f"❌ Error fetching weekly report: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch weekly report: {str(e)}"
        )


@app.get("/orders/reports/monthly", tags=["Orders", "Reports"])
async def get_monthly_orders_report(db: Session = Depends(get_db)):
    """
    Get monthly orders report (last 30 days)
    Fetches orders from Shopify for the past month
    """
    from datetime import datetime, timedelta
    
    try:
        # Calculate date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Format dates for Shopify API (ISO 8601)
        start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
        end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")
        
        print(f"📊 Fetching monthly orders report: {start_date.date()} to {end_date.date()}")
        
        # Fetch orders from Shopify
        shopify_orders = shopify_api.get_orders_by_date_range(
            start_date=start_date_str,
            end_date=end_date_str,
            status="any"
        )
        
        # Filter out cancelled orders for accurate revenue calculation
        active_orders = [
            order for order in shopify_orders 
            if order.get("financial_status") != "voided" and 
               order.get("cancelled_at") is None
        ]
        
        cancelled_orders = [
            order for order in shopify_orders 
            if order.get("financial_status") == "voided" or 
               order.get("cancelled_at") is not None
        ]
        
        # Calculate refund information
        total_refunded_amount = 0.0
        partially_refunded_orders = []
        fully_refunded_orders = []
        
        for order in active_orders:
            refunds = order.get("refunds", [])
            if refunds:
                order_refund_total = sum(
                    sum(float(transaction.get("amount", 0)) for transaction in refund.get("transactions", []))
                    for refund in refunds
                )
                
                if order_refund_total > 0:
                    total_refunded_amount += order_refund_total
                    
                    # Prepare line items for refund order
                    line_items_details = []
                    for item in order.get("line_items", []):
                        item_detail = {
                            "title": item.get("title", "Unknown Product"),
                            "quantity": item.get("quantity", 0),
                            "price": float(item.get("price", 0)),
                            "total": float(item.get("price", 0)) * item.get("quantity", 0),
                            "sku": item.get("sku"),
                            "variant_title": item.get("variant_title"),
                            "variant_id": item.get("variant_id"),
                            "product_id": item.get("product_id"),
                            "image": item.get("image") or None
                        }
                        line_items_details.append(item_detail)
                    
                    customer = order.get("customer", {})
                    order_info = {
                        "order_number": order.get("order_number"),
                        "order_id": order.get("id"),
                        "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Guest",
                        "customer_first_name": customer.get("first_name"),
                        "customer_last_name": customer.get("last_name"),
                        "customer_email": customer.get("email"),
                        "customer_phone": customer.get("phone"),
                        "original_total": float(order.get("total_price", 0)),
                        "refunded_amount": order_refund_total,
                        "net_payment": float(order.get("total_price", 0)) - order_refund_total,
                        "financial_status": order.get("financial_status"),
                        "refund_count": len(refunds),
                        "line_items": line_items_details,  # Product details for refunded order
                        "created_at": order.get("created_at")
                    }
                    
                    # Check if fully or partially refunded
                    if order.get("financial_status") == "refunded":
                        fully_refunded_orders.append(order_info)
                    elif order.get("financial_status") == "partially_refunded":
                        partially_refunded_orders.append(order_info)
        
        # Calculate statistics (from active orders minus refunds)
        total_orders = len(active_orders)
        total_gross_revenue = sum(float(order.get("total_price", 0)) for order in active_orders)
        total_net_revenue = total_gross_revenue - total_refunded_amount
        total_revenue = total_net_revenue  # Use net revenue as the main revenue
        
        # Group by week (only active orders)
        orders_by_week = {}
        for order in active_orders:
            order_datetime = datetime.fromisoformat(order.get("created_at", "").replace("Z", "+00:00"))
            week_number = order_datetime.strftime("%Y-W%U")  # Year-WeekNumber
            week_start = (order_datetime - timedelta(days=order_datetime.weekday())).date().isoformat()
            
            if week_number not in orders_by_week:
                orders_by_week[week_number] = {
                    "week_start": week_start,
                    "count": 0,
                    "revenue": 0.0
                }
            orders_by_week[week_number]["count"] += 1
            orders_by_week[week_number]["revenue"] += float(order.get("total_price", 0))
        
        # Payment method breakdown (only active orders)
        cash_orders = [o for o in active_orders if "cash" in o.get("tags", "").lower()]
        pos_orders = [o for o in active_orders if "pos" in o.get("tags", "").lower()]
        
        # Top customers (only active orders)
        customer_sales = {}
        for order in active_orders:
            customer = order.get("customer", {})
            customer_id = customer.get("id")
            if customer_id:
                customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                if customer_id not in customer_sales:
                    customer_sales[customer_id] = {
                        "name": customer_name,
                        "email": customer.get("email"),
                        "orders_count": 0,
                        "total_spent": 0.0
                    }
                customer_sales[customer_id]["orders_count"] += 1
                customer_sales[customer_id]["total_spent"] += float(order.get("total_price", 0))
        
        # Sort top customers by total spent
        top_customers = sorted(
            customer_sales.values(),
            key=lambda x: x["total_spent"],
            reverse=True
        )[:10]
        
        # Product sales breakdown (only active orders)
        product_sales = {}
        product_weekly_sales = {}
        
        for order in active_orders:
            order_datetime = datetime.fromisoformat(order.get("created_at", "").replace("Z", "+00:00"))
            week_number = order_datetime.strftime("%Y-W%U")
            
            for item in order.get("line_items", []):
                product_title = item.get("title", "Unknown Product")
                quantity = item.get("quantity", 0)
                price = float(item.get("price", 0))
                total = quantity * price
                
                # Overall product sales
                if product_title not in product_sales:
                    product_sales[product_title] = {
                        "product_name": product_title,
                        "total_quantity": 0,
                        "total_revenue": 0.0,
                        "order_count": 0,
                        "sku": item.get("sku"),
                        "variant_title": item.get("variant_title")
                    }
                
                product_sales[product_title]["total_quantity"] += quantity
                product_sales[product_title]["total_revenue"] += total
                product_sales[product_title]["order_count"] += 1
                
                # Weekly product sales
                if week_number not in product_weekly_sales:
                    product_weekly_sales[week_number] = {}
                
                if product_title not in product_weekly_sales[week_number]:
                    product_weekly_sales[week_number][product_title] = {
                        "quantity": 0,
                        "revenue": 0.0
                    }
                
                product_weekly_sales[week_number][product_title]["quantity"] += quantity
                product_weekly_sales[week_number][product_title]["revenue"] += total
        
        # Sort products by revenue
        top_products = sorted(
            product_sales.values(),
            key=lambda x: x["total_revenue"],
            reverse=True
        )
        
        return {
            "status": "success",
            "period": "monthly",
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "summary": {
                "total_orders": total_orders,
                "gross_revenue": round(total_gross_revenue, 2),
                "total_refunded": round(total_refunded_amount, 2),
                "net_revenue": round(total_net_revenue, 2),
                "total_revenue": round(total_revenue, 2),  # Same as net_revenue
                "average_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
                "cash_orders": len(cash_orders),
                "pos_orders": len(pos_orders),
                "total_products_sold": sum(p["total_quantity"] for p in product_sales.values()),
                "unique_products": len(product_sales),
                "cancelled_orders": len(cancelled_orders),
                "cancelled_revenue": round(sum(float(order.get("total_price", 0)) for order in cancelled_orders), 2),
                "partially_refunded_count": len(partially_refunded_orders),
                "fully_refunded_count": len(fully_refunded_orders),
                "total_refund_transactions": len(partially_refunded_orders) + len(fully_refunded_orders)
            },
            "weekly_breakdown": orders_by_week,
            "top_customers": top_customers,
            "refund_details": {
                "partially_refunded": partially_refunded_orders,
                "fully_refunded": fully_refunded_orders,
                "total_refunded_amount": round(total_refunded_amount, 2)
            },
            "top_products": top_products[:20],  # Top 20 products
            "product_weekly_sales": product_weekly_sales,
            "orders": [
                {
                    "order_number": order.get("order_number"),
                    "order_id": order.get("id"),
                    "customer_name": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip() or "Guest",
                    "customer_first_name": order.get("customer", {}).get("first_name"),
                    "customer_last_name": order.get("customer", {}).get("last_name"),
                    "customer_email": order.get("customer", {}).get("email"),
                    "customer_phone": order.get("customer", {}).get("phone"),
                    "total": float(order.get("total_price", 0)),
                    "items_count": len(order.get("line_items", [])),
                    "line_items": [
                        {
                            "title": item.get("title", "Unknown Product"),
                            "quantity": item.get("quantity", 0),
                            "price": float(item.get("price", 0)),
                            "total": float(item.get("price", 0)) * item.get("quantity", 0),
                            "sku": item.get("sku"),
                            "variant_title": item.get("variant_title"),
                            "variant_id": item.get("variant_id"),
                            "product_id": item.get("product_id"),
                            "image": item.get("image") or None  # Product image URL
                        }
                        for item in order.get("line_items", [])
                    ],
                    "financial_status": order.get("financial_status"),
                    "tags": order.get("tags"),
                    "created_at": order.get("created_at"),
                    "cancelled_at": order.get("cancelled_at")
                }
                for order in active_orders  # Only show active orders in the list
            ]
        }
        
    except Exception as e:
        print(f"❌ Error fetching monthly report: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch monthly report: {str(e)}"
        )


@app.get("/orders/reports/custom", tags=["Orders", "Reports"])
async def get_custom_date_range_report(
    start_date: str,
    end_date: str,
    db: Session = Depends(get_db)
):
    """
    Get orders report for custom date range
    
    Query parameters:
    - start_date: Start date in YYYY-MM-DD format
    - end_date: End date in YYYY-MM-DD format
    
    Example: /orders/reports/custom?start_date=2024-11-01&end_date=2024-11-15
    """
    from datetime import datetime
    
    try:
        # Validate and parse dates
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD format."
            )
        
        # Format dates for Shopify API
        start_date_str = start_dt.strftime("%Y-%m-%dT00:00:00")
        end_date_str = end_dt.strftime("%Y-%m-%dT23:59:59")
        
        print(f"📊 Fetching custom date range report: {start_date} to {end_date}")
        
        # Fetch orders from Shopify
        shopify_orders = shopify_api.get_orders_by_date_range(
            start_date=start_date_str,
            end_date=end_date_str,
            status="any"
        )
        
        # Filter out cancelled orders for accurate revenue calculation
        active_orders = [
            order for order in shopify_orders 
            if order.get("financial_status") != "voided" and 
               order.get("cancelled_at") is None
        ]
        
        cancelled_orders = [
            order for order in shopify_orders 
            if order.get("financial_status") == "voided" or 
               order.get("cancelled_at") is not None
        ]
        
        # Calculate refund information
        total_refunded_amount = 0.0
        partially_refunded_orders = []
        fully_refunded_orders = []
        
        for order in active_orders:
            refunds = order.get("refunds", [])
            if refunds:
                order_refund_total = sum(
                    sum(float(transaction.get("amount", 0)) for transaction in refund.get("transactions", []))
                    for refund in refunds
                )
                
                if order_refund_total > 0:
                    total_refunded_amount += order_refund_total
                    
                    # Prepare line items for refund order
                    line_items_details = []
                    for item in order.get("line_items", []):
                        item_detail = {
                            "title": item.get("title", "Unknown Product"),
                            "quantity": item.get("quantity", 0),
                            "price": float(item.get("price", 0)),
                            "total": float(item.get("price", 0)) * item.get("quantity", 0),
                            "sku": item.get("sku"),
                            "variant_title": item.get("variant_title"),
                            "variant_id": item.get("variant_id"),
                            "product_id": item.get("product_id"),
                            "image": item.get("image") or None
                        }
                        line_items_details.append(item_detail)
                    
                    customer = order.get("customer", {})
                    order_info = {
                        "order_number": order.get("order_number"),
                        "order_id": order.get("id"),
                        "customer_name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip() or "Guest",
                        "customer_first_name": customer.get("first_name"),
                        "customer_last_name": customer.get("last_name"),
                        "customer_email": customer.get("email"),
                        "customer_phone": customer.get("phone"),
                        "original_total": float(order.get("total_price", 0)),
                        "refunded_amount": order_refund_total,
                        "net_payment": float(order.get("total_price", 0)) - order_refund_total,
                        "financial_status": order.get("financial_status"),
                        "refund_count": len(refunds),
                        "line_items": line_items_details,  # Product details for refunded order
                        "created_at": order.get("created_at")
                    }
                    
                    # Check if fully or partially refunded
                    if order.get("financial_status") == "refunded":
                        fully_refunded_orders.append(order_info)
                    elif order.get("financial_status") == "partially_refunded":
                        partially_refunded_orders.append(order_info)
        
        # Calculate statistics (from active orders minus refunds)
        total_orders = len(active_orders)
        total_gross_revenue = sum(float(order.get("total_price", 0)) for order in active_orders)
        total_net_revenue = total_gross_revenue - total_refunded_amount
        total_revenue = total_net_revenue  # Use net revenue as the main revenue
        
        # Payment method breakdown (only active orders)
        cash_orders = [o for o in active_orders if "cash" in o.get("tags", "").lower()]
        pos_orders = [o for o in active_orders if "pos" in o.get("tags", "").lower()]
        
        # Product sales breakdown (only active orders)
        product_sales = {}
        product_date_sales = {}
        
        for order in active_orders:
            order_date = order.get("created_at", "")[:10]
            
            for item in order.get("line_items", []):
                product_title = item.get("title", "Unknown Product")
                quantity = item.get("quantity", 0)
                price = float(item.get("price", 0))
                total = quantity * price
                
                # Overall product sales
                if product_title not in product_sales:
                    product_sales[product_title] = {
                        "product_name": product_title,
                        "total_quantity": 0,
                        "total_revenue": 0.0,
                        "order_count": 0,
                        "sku": item.get("sku"),
                        "variant_title": item.get("variant_title")
                    }
                
                product_sales[product_title]["total_quantity"] += quantity
                product_sales[product_title]["total_revenue"] += total
                product_sales[product_title]["order_count"] += 1
                
                # Daily product sales
                if order_date not in product_date_sales:
                    product_date_sales[order_date] = {}
                
                if product_title not in product_date_sales[order_date]:
                    product_date_sales[order_date][product_title] = {
                        "quantity": 0,
                        "revenue": 0.0
                    }
                
                product_date_sales[order_date][product_title]["quantity"] += quantity
                product_date_sales[order_date][product_title]["revenue"] += total
        
        # Sort products by revenue
        top_products = sorted(
            product_sales.values(),
            key=lambda x: x["total_revenue"],
            reverse=True
        )
        
        return {
            "status": "success",
            "period": "custom",
            "start_date": start_date,
            "end_date": end_date,
            "summary": {
                "total_orders": total_orders,
                "gross_revenue": round(total_gross_revenue, 2),
                "total_refunded": round(total_refunded_amount, 2),
                "net_revenue": round(total_net_revenue, 2),
                "total_revenue": round(total_revenue, 2),  # Same as net_revenue
                "average_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0,
                "cash_orders": len(cash_orders),
                "pos_orders": len(pos_orders),
                "total_products_sold": sum(p["total_quantity"] for p in product_sales.values()),
                "unique_products": len(product_sales),
                "cancelled_orders": len(cancelled_orders),
                "cancelled_revenue": round(sum(float(order.get("total_price", 0)) for order in cancelled_orders), 2),
                "partially_refunded_count": len(partially_refunded_orders),
                "fully_refunded_count": len(fully_refunded_orders),
                "total_refund_transactions": len(partially_refunded_orders) + len(fully_refunded_orders)
            },
            "refund_details": {
                "partially_refunded": partially_refunded_orders,
                "fully_refunded": fully_refunded_orders,
                "total_refunded_amount": round(total_refunded_amount, 2)
            },
            "top_products": top_products[:20],  # Top 20 products
            "product_date_sales": product_date_sales,
            "orders": [
                {
                    "order_number": order.get("order_number"),
                    "order_id": order.get("id"),
                    "customer_name": f"{order.get('customer', {}).get('first_name', '')} {order.get('customer', {}).get('last_name', '')}".strip() or "Guest",
                    "customer_first_name": order.get("customer", {}).get("first_name"),
                    "customer_last_name": order.get("customer", {}).get("last_name"),
                    "customer_email": order.get("customer", {}).get("email"),
                    "customer_phone": order.get("customer", {}).get("phone"),
                    "total": float(order.get("total_price", 0)),
                    "items_count": len(order.get("line_items", [])),
                    "line_items": [
                        {
                            "title": item.get("title", "Unknown Product"),
                            "quantity": item.get("quantity", 0),
                            "price": float(item.get("price", 0)),
                            "total": float(item.get("price", 0)) * item.get("quantity", 0),
                            "sku": item.get("sku"),
                            "variant_title": item.get("variant_title"),
                            "variant_id": item.get("variant_id"),
                            "product_id": item.get("product_id"),
                            "image": item.get("image") or None  # Product image URL
                        }
                        for item in order.get("line_items", [])
                    ],
                    "financial_status": order.get("financial_status"),
                    "tags": order.get("tags"),
                    "created_at": order.get("created_at"),
                    "cancelled_at": order.get("cancelled_at")
                }
                for order in active_orders  # Only show active orders in the list
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching custom date range report: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch custom date range report: {str(e)}"
        )


# ==================== WEBHOOK ENDPOINTS ====================

def verify_shopify_webhook(request_body: bytes, hmac_header: str, secret: str) -> bool:
    """
    Verify Shopify webhook HMAC signature
    """
    try:
        computed_hmac = base64.b64encode(
            hmac.new(
                secret.encode('utf-8'),
                request_body,
                hashlib.sha256
            ).digest()
        ).decode()
        
        return hmac.compare_digest(computed_hmac, hmac_header)
    except Exception as e:
        print(f"❌ HMAC verification error: {e}")
        return False


@app.post("/webhooks/{topic:path}", tags=["Webhooks"])
async def handle_webhook(topic: str, request: Request, db: Session = Depends(get_db)):
    """
    Generic Shopify Webhook handler
    
    Supported topics:
    - products/create
    - products/update
    - products/delete
    - inventory_levels/update
    - customers/create
    - customers/update
    - orders/create
    - orders/paid
    - orders/cancelled
    
    Automatically updates local database based on webhook payload.
    """
    try:
        # Get raw body for HMAC verification
        raw_body = await request.body()
        
        # Optional: Verify Shopify HMAC signature for production security
        # Uncomment the following lines to enable HMAC verification:
        # 
        # webhook_secret = os.getenv("SHOPIFY_WEBHOOK_SECRET")
        # if webhook_secret:
        #     hmac_header = request.headers.get("X-Shopify-Hmac-SHA256")
        #     if not hmac_header or not verify_shopify_webhook(raw_body, hmac_header, webhook_secret):
        #         print(f"❌ Invalid HMAC signature for webhook: {topic}")
        #         raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Parse JSON payload
        payload = json.loads(raw_body)
        
        print(f"\n{'='*60}")
        print(f"📡 Received Shopify Webhook: {topic}")
        print(f"{'='*60}")
        print(f"Payload keys: {list(payload.keys())}")
        
        # Extract resource ID for logging
        resource_id = payload.get("id")
        
        # Create webhook event log
        webhook_log = WebhookEvent(
            topic=topic,
            shopify_id=resource_id,
            payload=json.dumps(payload),
            status="processing"
        )
        db.add(webhook_log)
        db.commit()
        
        # Route to appropriate handler
        try:
            if topic in ["products/create", "products/update"]:
                handle_product_webhook(payload, db)
            elif topic == "products/delete":
                handle_product_delete(payload, db)
            elif topic == "inventory_levels/update":
                handle_inventory_update(payload, db)
            elif topic in ["customers/create", "customers/update"]:
                handle_customer_webhook(payload, db)
            elif topic in ["orders/create", "orders/paid", "orders/cancelled"]:
                handle_order_webhook(payload, db)
            else:
                print(f"⚠️  Unhandled webhook topic: {topic}")
                webhook_log.status = "skipped"
                webhook_log.error_message = f"Unhandled topic: {topic}"
                db.commit()
                return {"status": "skipped", "topic": topic, "message": "Topic not handled"}
            
            # Mark as processed
            webhook_log.status = "processed"
            db.commit()
            
            print(f"✅ Webhook processed successfully: {topic}")
            print(f"{'='*60}\n")
            
            return {
                "status": "ok",
                "topic": topic,
                "resource_id": resource_id,
                "message": "Webhook processed successfully"
            }
            
        except Exception as handler_error:
            # Mark as failed
            webhook_log.status = "failed"
            webhook_log.error_message = str(handler_error)
            db.commit()
            raise
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        db.rollback()
        print(f"❌ Webhook error for {topic}: {e}")
        print(f"{'='*60}\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhooks/logs", tags=["Webhooks"])
async def get_webhook_logs(
    limit: int = 50,
    topic: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get webhook event logs
    
    Query parameters:
    - limit: Number of logs to return (default: 50)
    - topic: Filter by webhook topic (e.g. "products/create")
    - status: Filter by status ("processed", "failed", "skipped")
    """
    query = db.query(WebhookEvent)
    
    if topic:
        query = query.filter(WebhookEvent.topic == topic)
    if status:
        query = query.filter(WebhookEvent.status == status)
    
    logs = query.order_by(WebhookEvent.created_at.desc()).limit(limit).all()
    
    return {
        "status": "success",
        "count": len(logs),
        "logs": [log.to_dict() for log in logs]
    }


@app.get("/webhooks/stats", tags=["Webhooks"])
async def get_webhook_stats(db: Session = Depends(get_db)):
    """
    Get webhook statistics
    """
    from sqlalchemy import func
    
    total_webhooks = db.query(WebhookEvent).count()
    
    # Count by status
    status_counts = db.query(
        WebhookEvent.status,
        func.count(WebhookEvent.id)
    ).group_by(WebhookEvent.status).all()
    
    # Count by topic
    topic_counts = db.query(
        WebhookEvent.topic,
        func.count(WebhookEvent.id)
    ).group_by(WebhookEvent.topic).all()
    
    return {
        "status": "success",
        "total_webhooks": total_webhooks,
        "by_status": {status: count for status, count in status_counts},
        "by_topic": {topic: count for topic, count in topic_counts}
    }


if __name__ == "__main__":
    # Get port from environment variable (Render sets PORT automatically)
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

