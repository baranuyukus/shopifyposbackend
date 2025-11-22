"""
SQLAlchemy models for local database
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, BigInteger, ForeignKey, Text
from sqlalchemy.sql import func
from database import Base


class Product(Base):
    """
    Product model for storing Shopify product variants locally
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    shopify_id = Column(BigInteger, index=True, nullable=False)
    shopify_product_id = Column(BigInteger, index=True)
    title = Column(String, nullable=False)
    sku = Column(String, index=True)
    barcode = Column(String, index=True)  # Removed unique constraint - multiple variants can have same barcode
    price = Column(Float, nullable=False, default=0.0)
    inventory_quantity = Column(Integer, default=0)
    variant_title = Column(String)
    image_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Product(id={self.id}, title='{self.title}', barcode='{self.barcode}')>"

    def to_dict(self):
        """
        Convert model to dictionary
        """
        return {
            "id": self.id,
            "shopify_id": self.shopify_id,
            "shopify_product_id": self.shopify_product_id,
            "title": self.title,
            "sku": self.sku,
            "barcode": self.barcode,
            "price": self.price,
            "inventory_quantity": self.inventory_quantity,
            "variant_title": self.variant_title,
            "image_url": self.image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Customer(Base):
    """
    Customer model for storing Shopify customers locally
    """
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    shopify_id = Column(BigInteger, unique=True, index=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, index=True)
    phone = Column(String)
    address = Column(String)
    city = Column(String)
    country = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Customer(id={self.id}, email='{self.email}', name='{self.first_name} {self.last_name}')>"

    def to_dict(self):
        """
        Convert model to dictionary
        """
        return {
            "id": self.id,
            "shopify_id": self.shopify_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "city": self.city,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Order(Base):
    """
    Order model for storing POS transactions locally
    """
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    shopify_order_id = Column(BigInteger, index=True, nullable=True)  # Not unique - multiple items can share same order
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    barcode = Column(String, index=True)
    title = Column(String)
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)
    payment_method = Column(String, nullable=False)  # "cash" or "pos"
    status = Column(String, default="completed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Order(id={self.id}, shopify_order_id={self.shopify_order_id}, payment='{self.payment_method}')>"

    def to_dict(self):
        """
        Convert model to dictionary
        """
        return {
            "id": self.id,
            "shopify_order_id": self.shopify_order_id,
            "customer_id": self.customer_id,
            "product_id": self.product_id,
            "barcode": self.barcode,
            "title": self.title,
            "quantity": self.quantity,
            "price": self.price,
            "payment_method": self.payment_method,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WebhookEvent(Base):
    """
    Webhook event log for tracking all incoming Shopify webhooks
    """
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, nullable=False, index=True)  # e.g. "products/create"
    shopify_id = Column(BigInteger, index=True)  # ID of the resource (product, customer, order)
    payload = Column(Text)  # Full JSON payload as string
    status = Column(String, default="processed")  # "processed", "failed", "skipped"
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<WebhookEvent(id={self.id}, topic='{self.topic}', status='{self.status}')>"

    def to_dict(self):
        """
        Convert model to dictionary
        """
        return {
            "id": self.id,
            "topic": self.topic,
            "shopify_id": self.shopify_id,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

