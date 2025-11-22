"""
PDF Receipt Generator for Shopify POS Orders
Generates 10cm x 10cm printable receipts for Zebra printer
"""

from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os
from typing import Dict, List
import unicodedata


def normalize_turkish_text(text: str) -> str:
    """
    Normalize Turkish characters to ASCII-compatible versions for PDF printing.
    Replaces Turkish-specific characters with their ASCII equivalents.
    """
    if not text:
        return text
    
    # Turkish character mapping
    turkish_map = {
        'ç': 'c', 'Ç': 'C',
        'ğ': 'g', 'Ğ': 'G',
        'ı': 'i', 'İ': 'I',
        'ö': 'o', 'Ö': 'O',
        'ş': 's', 'Ş': 'S',
        'ü': 'u', 'Ü': 'U',
    }
    
    result = text
    for turkish_char, ascii_char in turkish_map.items():
        result = result.replace(turkish_char, ascii_char)
    
    return result


def generate_order_pdf(order_data: Dict) -> str:
    """
    Generates a 10×10 cm PDF receipt for an order.
    
    Args:
        order_data: Dictionary containing order information
            Required keys:
                - shopify_order_number: Order number from Shopify
                - shopify_order_id: Shopify order ID
                - customer_name: Customer full name
                - email: Customer email
                - payment_method: Payment method (cash/pos)
                - discount_applied: Discount amount
                - original_amount: Original total amount
                - final_amount: Final amount after discount
                - items: List of order items [{"title": str, "quantity": int, "price": float}]
    
    Returns:
        str: Path to the generated PDF file
    """
    
    # Ensure output folder exists
    os.makedirs("receipts", exist_ok=True)
    
    # Generate filename
    order_number = order_data.get('shopify_order_number', 'unknown')
    filename = f"receipts/order_{order_number}.pdf"
    
    # Create PDF with 10cm x 10cm page size
    page_width = 10 * cm
    page_height = 15 * cm
    pdf = canvas.Canvas(filename, pagesize=(page_width, page_height))
    
    # Enable UTF-8 encoding for Turkish characters
    # Use Helvetica with proper encoding
    pdf.setFont("Helvetica-Bold", 10)
    
    # Starting position (from top)
    y = 9.5 * cm
    margin_left = 0.5 * cm
    margin_right = 9.5 * cm
    line_height = 0.35 * cm
    
    # Header - Store Name
    header_text = "Meezy Archive - POS Receipt"
    pdf.drawString(margin_left, y, header_text)
    y -= line_height * 1.2
    
    # Separator line
    pdf.setLineWidth(0.5)
    pdf.line(margin_left, y, margin_right, y)
    y -= line_height * 0.8
    
    # Order Information
    pdf.setFont("Helvetica", 8)
    pdf.drawString(margin_left, y, f"Order No: {order_data.get('shopify_order_number', 'N/A')}")
    y -= line_height * 0.9
    
    pdf.setFont("Helvetica", 7)
    pdf.drawString(margin_left, y, f"Shopify ID: {order_data.get('shopify_order_id', 'N/A')}")
    y -= line_height * 0.9
    
    # Date
    current_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    pdf.drawString(margin_left, y, f"Date: {current_date}")
    y -= line_height * 1.1
    
    # Customer Information
    pdf.setFont("Helvetica-Bold", 8)
    customer_name = normalize_turkish_text(order_data.get('customer_name', '-'))
    if len(customer_name) > 35:
        customer_name = customer_name[:32] + "..."
    pdf.drawString(margin_left, y, f"Customer: {customer_name}")
    y -= line_height * 0.9
    
    pdf.setFont("Helvetica", 7)
    email = normalize_turkish_text(order_data.get('email', '-'))
    if len(email) > 35:
        email = email[:32] + "..."
    pdf.drawString(margin_left, y, f"Email: {email}")
    y -= line_height * 1.1
    
    # Separator line
    pdf.setLineWidth(0.5)
    pdf.line(margin_left, y, margin_right, y)
    y -= line_height * 0.8
    
    # Items Section
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(margin_left, y, "Items:")
    y -= line_height * 0.9
    
    pdf.setFont("Helvetica", 7)
    items = order_data.get("items", [])
    
    for item in items:
        title = normalize_turkish_text(item.get('title', 'Unknown Item'))
        quantity = item.get('quantity', 1)
        price = item.get('price', 0.0)
        
        # Truncate long item names
        if len(title) > 30:
            title = title[:27] + "..."
        
        # Format item line
        item_line = f"• {title}"
        pdf.drawString(margin_left + 0.2 * cm, y, item_line)
        y -= line_height * 0.85
        
        # Quantity and price on next line
        qty_price = f"  {quantity} x TL{price:.2f} = TL{quantity * price:.2f}"
        pdf.drawString(margin_left + 0.4 * cm, y, qty_price)
        y -= line_height * 0.95
        
        # Check if we need a new page
        if y < 2.5 * cm:
            pdf.showPage()
            pdf.setFont("Helvetica", 7)
            y = 9.5 * cm
    
    # Add some space before totals
    y -= line_height * 0.3
    
    # Separator line
    pdf.setLineWidth(0.5)
    pdf.line(margin_left, y, margin_right, y)
    y -= line_height * 0.8
    
    # Totals Section
    pdf.setFont("Helvetica", 8)
    
    # Subtotal
    original_amount = order_data.get('original_amount', 0.0)
    pdf.drawString(margin_left, y, "Subtotal:")
    pdf.drawRightString(margin_right, y, f"TL{original_amount:.2f}")
    y -= line_height * 0.9
    
    # Discount (if any)
    discount = order_data.get('discount_applied', 0.0)
    if discount > 0:
        # Keep black color (no red)
        pdf.drawString(margin_left, y, "Discount:")
        pdf.drawRightString(margin_right, y, f"-TL{discount:.2f}")
        y -= line_height * 0.9
    
    # Total
    pdf.setFont("Helvetica-Bold", 9)
    final_amount = order_data.get('final_amount', 0.0)
    pdf.drawString(margin_left, y, "TOTAL:")
    pdf.drawRightString(margin_right, y, f"TL{final_amount:.2f}")
    y -= line_height * 1.1
    
    # Payment Method
    pdf.setFont("Helvetica", 8)
    payment_method = order_data.get('payment_method', 'unknown').upper()
    payment_display = "NAKIT" if payment_method == "CASH" else "POS/KART"
    pdf.drawString(margin_left, y, f"Payment: {payment_display}")
    y -= line_height * 1.1
    
    # Bottom Separator
    pdf.setLineWidth(0.5)
    pdf.line(margin_left, y, margin_right, y)
    y -= line_height * 0.8
    
    # Thank you message
    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawCentredString(page_width / 2, y, "Thank you for shopping!")
    y -= line_height * 0.7
    pdf.drawCentredString(page_width / 2, y, "Meezy Archive")
    
    # Save PDF
    pdf.save()
    
    return filename


def generate_order_pdf_simple(
    order_number: str,
    order_id: int,
    customer_name: str,
    email: str,
    items: List[Dict],
    original_amount: float,
    discount: float,
    final_amount: float,
    payment_method: str
) -> str:
    """
    Simplified wrapper for generate_order_pdf with direct parameters.
    
    Args:
        order_number: Shopify order number
        order_id: Shopify order ID
        customer_name: Customer full name
        email: Customer email
        items: List of items [{"title": str, "quantity": int, "price": float}]
        original_amount: Original total
        discount: Discount amount
        final_amount: Final amount after discount
        payment_method: Payment method (cash/pos)
    
    Returns:
        str: Path to generated PDF
    """
    order_data = {
        "shopify_order_number": order_number,
        "shopify_order_id": order_id,
        "customer_name": customer_name,
        "email": email,
        "payment_method": payment_method,
        "discount_applied": discount,
        "original_amount": original_amount,
        "final_amount": final_amount,
        "items": items
    }
    
    return generate_order_pdf(order_data)

