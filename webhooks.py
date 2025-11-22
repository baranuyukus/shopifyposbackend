"""
Shopify Webhook Handler Functions
Handles real-time updates from Shopify webhooks
"""

from sqlalchemy.orm import Session
from models import Product, Customer, Order
from typing import Dict, Optional
from datetime import datetime


def handle_product_webhook(payload: Dict, db: Session) -> None:
    """
    Handles product creation or update webhook
    Topics: products/create, products/update
    """
    try:
        product_id = payload.get("id")
        title = payload.get("title")
        variants = payload.get("variants", [])
        
        print(f"  📦 Processing product: {title} (ID: {product_id})")
        print(f"  📦 Variants count: {len(variants)}")
        
        for variant in variants:
            variant_id = variant.get("id")
            
            # Check if variant already exists
            existing = db.query(Product).filter(
                Product.shopify_id == variant_id
            ).first()
            
            # Extract variant data
            sku = variant.get("sku")
            barcode = variant.get("barcode")
            price = float(variant.get("price") or 0)
            inventory_quantity = variant.get("inventory_quantity", 0)
            variant_title = variant.get("title")
            image_url = None
            
            # Get image from variant or product
            if variant.get("image_id") and payload.get("images"):
                for img in payload.get("images", []):
                    if img.get("id") == variant.get("image_id"):
                        image_url = img.get("src")
                        break
            elif payload.get("image"):
                image_url = payload["image"].get("src")
            
            if existing:
                # Update existing product
                print(f"    ✏️  Updating variant: {variant_title} (Barcode: {barcode})")
                existing.title = title
                existing.sku = sku
                existing.barcode = barcode
                existing.price = price
                existing.inventory_quantity = inventory_quantity
                existing.variant_title = variant_title
                existing.image_url = image_url
            else:
                # Create new product
                print(f"    ➕ Creating new variant: {variant_title} (Barcode: {barcode})")
                new_product = Product(
                    shopify_id=variant_id,
                    shopify_product_id=product_id,
                    title=title,
                    sku=sku,
                    barcode=barcode,
                    price=price,
                    inventory_quantity=inventory_quantity,
                    variant_title=variant_title,
                    image_url=image_url
                )
                db.add(new_product)
        
        print(f"  ✅ Product webhook processed successfully")
        
    except Exception as e:
        print(f"  ❌ Error processing product webhook: {e}")
        raise


def handle_product_delete(payload: Dict, db: Session) -> None:
    """
    Handles product deletion webhook
    Topic: products/delete
    """
    try:
        product_id = payload.get("id")
        print(f"  🗑️  Deleting product with Shopify ID: {product_id}")
        
        # Delete all variants of this product
        deleted_count = db.query(Product).filter(
            Product.shopify_product_id == product_id
        ).delete()
        
        print(f"  ✅ Deleted {deleted_count} variant(s)")
        
    except Exception as e:
        print(f"  ❌ Error deleting product: {e}")
        raise


def handle_inventory_update(payload: Dict, db: Session) -> None:
    """
    Handles inventory level update webhook
    Topic: inventory_levels/update
    """
    try:
        inventory_item_id = payload.get("inventory_item_id")
        available = payload.get("available")
        
        print(f"  📊 Updating inventory for item ID: {inventory_item_id} -> {available}")
        
        # Find product by inventory_item_id (which is the variant ID in our case)
        product = db.query(Product).filter(
            Product.shopify_id == inventory_item_id
        ).first()
        
        if product:
            old_quantity = product.inventory_quantity
            product.inventory_quantity = available
            print(f"  ✅ Updated {product.title} inventory: {old_quantity} -> {available}")
        else:
            print(f"  ⚠️  Product not found for inventory_item_id: {inventory_item_id}")
        
    except Exception as e:
        print(f"  ❌ Error updating inventory: {e}")
        raise


def handle_customer_webhook(payload: Dict, db: Session) -> None:
    """
    Handles customer creation or update webhook
    Topics: customers/create, customers/update
    """
    try:
        customer_id = payload.get("id")
        email = payload.get("email")
        
        print(f"  👤 Processing customer: {email} (ID: {customer_id})")
        
        # Check if customer already exists
        existing = db.query(Customer).filter(
            Customer.shopify_id == customer_id
        ).first()
        
        # Extract address information
        address_str = None
        city = None
        country = None
        
        if payload.get("addresses") and len(payload["addresses"]) > 0:
            addr = payload["addresses"][0]
            address_parts = []
            if addr.get("address1"):
                address_parts.append(addr["address1"])
            if addr.get("address2"):
                address_parts.append(addr["address2"])
            address_str = " ".join(address_parts) if address_parts else None
            city = addr.get("city")
            country = addr.get("country")
        
        if existing:
            # Update existing customer
            print(f"    ✏️  Updating customer: {email}")
            existing.first_name = payload.get("first_name")
            existing.last_name = payload.get("last_name")
            existing.email = email
            existing.phone = payload.get("phone")
            existing.address = address_str
            existing.city = city
            existing.country = country
        else:
            # Create new customer
            print(f"    ➕ Creating new customer: {email}")
            new_customer = Customer(
                shopify_id=customer_id,
                first_name=payload.get("first_name"),
                last_name=payload.get("last_name"),
                email=email,
                phone=payload.get("phone"),
                address=address_str,
                city=city,
                country=country
            )
            db.add(new_customer)
        
        print(f"  ✅ Customer webhook processed successfully")
        
    except Exception as e:
        print(f"  ❌ Error processing customer webhook: {e}")
        raise


def handle_order_webhook(payload: Dict, db: Session) -> None:
    """
    Handles order creation and payment updates webhook
    Topics: orders/create, orders/paid, orders/cancelled
    """
    try:
        shopify_order_id = payload.get("id")
        financial_status = payload.get("financial_status", "pending")
        
        print(f"  🛒 Processing order: {shopify_order_id} (Status: {financial_status})")
        
        # Check if order already exists
        existing_orders = db.query(Order).filter(
            Order.shopify_order_id == shopify_order_id
        ).all()
        
        if existing_orders:
            # Update existing order status
            print(f"    ✏️  Updating order status to: {financial_status}")
            for order in existing_orders:
                order.status = financial_status
        else:
            # Create new order entries for each line item
            line_items = payload.get("line_items", [])
            
            if not line_items:
                print(f"    ⚠️  No line items in order")
                return
            
            # Try to find customer
            customer_id = None
            if payload.get("customer"):
                customer_shopify_id = payload["customer"].get("id")
                customer = db.query(Customer).filter(
                    Customer.shopify_id == customer_shopify_id
                ).first()
                if customer:
                    customer_id = customer.id
            
            # Determine payment method from tags or gateway
            payment_method = "pos"  # default
            tags = payload.get("tags", "").lower()
            if "cash" in tags:
                payment_method = "cash"
            elif payload.get("gateway"):
                gateway = payload["gateway"].lower()
                if "cash" in gateway:
                    payment_method = "cash"
            
            print(f"    ➕ Creating {len(line_items)} order item(s)")
            
            for item in line_items:
                variant_id = item.get("variant_id")
                
                # Try to find product
                product_id = None
                barcode = None
                if variant_id:
                    product = db.query(Product).filter(
                        Product.shopify_id == variant_id
                    ).first()
                    if product:
                        product_id = product.id
                        barcode = product.barcode
                
                new_order = Order(
                    shopify_order_id=shopify_order_id,
                    customer_id=customer_id,
                    product_id=product_id,
                    barcode=barcode,
                    title=item.get("title"),
                    quantity=item.get("quantity", 1),
                    price=float(item.get("price") or 0),
                    payment_method=payment_method,
                    status=financial_status
                )
                db.add(new_order)
                print(f"      - {item.get('title')} x{item.get('quantity')}")
        
        print(f"  ✅ Order webhook processed successfully")
        
    except Exception as e:
        print(f"  ❌ Error processing order webhook: {e}")
        raise

