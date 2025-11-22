"""
Shopify API integration module
"""
import os
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ShopifyAPI:
    """
    Shopify REST Admin API client
    """

    def __init__(self):
        self.api_key = os.getenv("SHOPIFY_API_KEY")
        self.api_secret = os.getenv("SHOPIFY_API_SECRET")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.shop_url = os.getenv("SHOPIFY_SHOP_URL")
        self.api_version = "2024-10"

        if not all([self.access_token, self.shop_url]):
            raise ValueError("Missing required Shopify credentials in environment variables")

        self.base_url = f"https://{self.shop_url}/admin/api/{self.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """
        Make HTTP request to Shopify API
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Shopify API request failed: {e}")
            # Try to get detailed error message from response
            try:
                error_detail = response.json()
                print(f"Shopify error details: {error_detail}")
            except:
                pass
            raise

    def get_all_products(self) -> List[Dict]:
        """
        Fetch all products from Shopify with pagination
        Returns list of all products with their variants
        """
        all_products = []
        url = f"{self.base_url}/products.json?limit=250"
        page_count = 0
        
        while url:
            try:
                page_count += 1
                print(f"  📄 Fetching products page {page_count}...")
                
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                products = data.get("products", [])
                
                if not products:
                    break
                
                all_products.extend(products)
                print(f"  ✓ Page {page_count}: {len(products)} products (total: {len(all_products)})")
                
                # Check for next page link in Link header
                link_header = response.headers.get("Link", "")
                url = None
                
                if link_header:
                    # Parse Link header for 'next' relation
                    links = link_header.split(",")
                    for link in links:
                        if 'rel="next"' in link:
                            # Extract URL from <URL>
                            url = link.split(";")[0].strip().strip("<>")
                            break
                
            except Exception as e:
                print(f"Error fetching products page {page_count}: {e}")
                break
        
        print(f"  ✅ Total products fetched: {len(all_products)}")
        return all_products

    def get_product(self, product_id: int) -> Optional[Dict]:
        """
        Get a single product by Shopify product ID
        """
        try:
            response = self._make_request("GET", f"products/{product_id}.json")
            return response.get("product")
        except Exception as e:
            print(f"Error fetching product {product_id}: {e}")
            return None

    def update_inventory(self, inventory_item_id: int, location_id: int, quantity: int) -> bool:
        """
        Update inventory quantity for a specific item
        """
        try:
            data = {
                "location_id": location_id,
                "inventory_item_id": inventory_item_id,
                "available": quantity
            }
            self._make_request("POST", "inventory_levels/set.json", data=data)
            return True
        except Exception as e:
            print(f"Error updating inventory: {e}")
            return False

    def get_locations(self) -> List[Dict]:
        """
        Get all store locations
        """
        try:
            response = self._make_request("GET", "locations.json")
            return response.get("locations", [])
        except Exception as e:
            print(f"Error fetching locations: {e}")
            return []

    # ==================== CUSTOMER MANAGEMENT ====================

    def get_all_customers(self) -> List[Dict]:
        """
        Fetch all customers from Shopify with pagination
        Returns list of all customers
        """
        all_customers = []
        url = f"{self.base_url}/customers.json?limit=250"
        page_count = 0
        
        while url:
            try:
                page_count += 1
                print(f"  📄 Fetching customers page {page_count}...")
                
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                customers = data.get("customers", [])
                
                if not customers:
                    break
                
                all_customers.extend(customers)
                print(f"  ✓ Page {page_count}: {len(customers)} customers (total: {len(all_customers)})")
                
                # Check for next page link in Link header
                link_header = response.headers.get("Link", "")
                url = None
                
                if link_header:
                    # Parse Link header for 'next' relation
                    links = link_header.split(",")
                    for link in links:
                        if 'rel="next"' in link:
                            # Extract URL from <URL>
                            url = link.split(";")[0].strip().strip("<>")
                            break
                
            except Exception as e:
                print(f"Error fetching customers page {page_count}: {e}")
                break
        
        print(f"  ✅ Total customers fetched: {len(all_customers)}")
        return all_customers

    def search_customer_by_email(self, email: str) -> List[Dict]:
        """
        Search customer by email from Shopify
        """
        try:
            response = self._make_request("GET", f"customers/search.json", params={"query": f"email:{email}"})
            return response.get("customers", [])
        except Exception as e:
            print(f"Error searching customer by email: {e}")
            return []

    def search_customer_by_phone(self, phone: str) -> List[Dict]:
        """
        Search customer by phone from Shopify
        """
        try:
            response = self._make_request("GET", f"customers/search.json", params={"query": f"phone:{phone}"})
            return response.get("customers", [])
        except Exception as e:
            print(f"Error searching customer by phone: {e}")
            return []

    def search_customer_by_name(self, first_name: Optional[str] = None, last_name: Optional[str] = None, name: Optional[str] = None) -> List[Dict]:
        """
        Search customer by name from Shopify
        
        Args:
            first_name: First name to search
            last_name: Last name to search
            name: Full name (first + last) to search (if provided, first_name and last_name are ignored)
        
        Returns:
            List of matching customers
        """
        try:
            if name:
                # Search by full name (Shopify searches both first_name and last_name)
                query_str = name
            elif first_name and last_name:
                # Search by both first and last name
                query_str = f"{first_name} {last_name}"
            elif first_name:
                query_str = f"first_name:{first_name}"
            elif last_name:
                query_str = f"last_name:{last_name}"
            else:
                return []
            
            response = self._make_request("GET", f"customers/search.json", params={"query": query_str})
            return response.get("customers", [])
        except Exception as e:
            print(f"Error searching customer by name: {e}")
            return []

    def create_customer(self, customer_data: Dict) -> Optional[Dict]:
        """
        Create new customer in Shopify
        customer_data should contain: first_name, last_name, email, phone, etc.
        """
        try:
            payload = {"customer": customer_data}
            response = self._make_request("POST", "customers.json", data=payload)
            return response.get("customer")
        except Exception as e:
            print(f"Error creating customer: {e}")
            return None

    def get_customer(self, customer_id: int) -> Optional[Dict]:
        """
        Get a single customer by Shopify customer ID
        """
        try:
            response = self._make_request("GET", f"customers/{customer_id}.json")
            return response.get("customer")
        except Exception as e:
            print(f"Error fetching customer {customer_id}: {e}")
            return None

    def update_customer(self, customer_id: int, customer_data: Dict) -> Optional[Dict]:
        """
        Update existing customer in Shopify
        """
        try:
            payload = {"customer": customer_data}
            response = self._make_request("PUT", f"customers/{customer_id}.json", data=payload)
            return response.get("customer")
        except Exception as e:
            print(f"Error updating customer {customer_id}: {e}")
            return None

    # ==================== ORDER MANAGEMENT ====================

    def create_order(self, product: Dict, customer: Optional[Dict], payment_method: str) -> Optional[Dict]:
        """
        Create new order in Shopify for in-store sale
        payment_method: "cash" or "pos"
        Adds tags: ["in-store", "cash"] or ["in-store", "pos"]
        """
        try:
            # Build line items
            line_items = [{
                "title": product.get("title"),
                "quantity": 1,
                "price": str(product.get("price", 0)),
                "variant_id": product.get("shopify_id"),
            }]
            
            # Build order payload
            order_payload = {
                "order": {
                    "line_items": line_items,
                    "tags": f"in-store, {payment_method}",
                    "financial_status": "paid",
                    "transactions": [{
                        "kind": "sale",
                        "status": "success",
                        "amount": str(product.get("price", 0)),
                        "gateway": "cash" if payment_method == "cash" else "pos"
                    }]
                }
            }
            
            # Add customer info if available
            if customer:
                if customer.get("email"):
                    order_payload["order"]["email"] = customer["email"]
                if customer.get("shopify_id"):
                    order_payload["order"]["customer"] = {"id": customer["shopify_id"]}
            
            print(f"📦 Creating order in Shopify: {product.get('title')} ({payment_method})")
            
            response = self._make_request("POST", "orders.json", data=order_payload)
            order = response.get("order")
            
            if order:
                print(f"✅ Order created in Shopify: #{order.get('order_number')}")
            
            return order
            
        except Exception as e:
            print(f"❌ Error creating order: {e}")
            return None

    def get_order(self, order_id: int) -> Optional[Dict]:
        """
        Get a single order by Shopify order ID
        """
        try:
            response = self._make_request("GET", f"orders/{order_id}.json")
            return response.get("order")
        except Exception as e:
            print(f"Error fetching order {order_id}: {e}")
            return None

    def get_all_orders(self, status: str = "any") -> List[Dict]:
        """
        Fetch all orders from Shopify with pagination
        status: "open", "closed", "cancelled", "any"
        """
        all_orders = []
        url = f"{self.base_url}/orders.json?limit=250&status={status}"
        page_count = 0
        
        while url:
            try:
                page_count += 1
                print(f"  📄 Fetching orders page {page_count}...")
                
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                orders = data.get("orders", [])
                
                if not orders:
                    break
                
                all_orders.extend(orders)
                print(f"  ✓ Page {page_count}: {len(orders)} orders (total: {len(all_orders)})")
                
                # Check for next page link in Link header
                link_header = response.headers.get("Link", "")
                url = None
                
                if link_header:
                    links = link_header.split(",")
                    for link in links:
                        if 'rel="next"' in link:
                            url = link.split(";")[0].strip().strip("<>")
                            break
                
            except Exception as e:
                print(f"Error fetching orders page {page_count}: {e}")
                break
        
        print(f"  ✅ Total orders fetched: {len(all_orders)}")
        return all_orders

    def get_orders_by_date_range(
        self, 
        start_date: str, 
        end_date: str, 
        status: str = "any"
    ) -> List[Dict]:
        """
        Fetch orders within a date range from Shopify
        
        Args:
            start_date: Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            end_date: End date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            status: Order status filter ("open", "closed", "cancelled", "any")
        
        Returns:
            List of orders within the date range
        """
        all_orders = []
        url = f"{self.base_url}/orders.json?limit=250&status={status}&created_at_min={start_date}&created_at_max={end_date}"
        page_count = 0
        
        print(f"📦 Fetching orders from {start_date} to {end_date}...")
        
        while url:
            try:
                page_count += 1
                
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                orders = data.get("orders", [])
                
                if not orders:
                    break
                
                all_orders.extend(orders)
                print(f"  ✓ Page {page_count}: {len(orders)} orders (total: {len(all_orders)})")
                
                # Check for next page using Link header
                link_header = response.headers.get("Link", "")
                url = None
                
                if link_header:
                    links = link_header.split(",")
                    for link in links:
                        if 'rel="next"' in link:
                            # Extract URL from <URL>
                            url = link.split(";")[0].strip().strip("<>")
                            break
                
            except Exception as e:
                print(f"Error fetching orders page {page_count}: {e}")
                break
        
        print(f"  ✅ Total orders fetched: {len(all_orders)}")
        return all_orders

    def create_manual_order(
        self, 
        title: str, 
        size: str, 
        price: float, 
        quantity: int,
        customer: Optional[Dict], 
        payment_method: str,
        discount: float = 0
    ) -> Optional[Dict]:
        """
        Create a manual order in Shopify with custom line item
        For products not in inventory
        Adds tags: in-store, manual, and payment method ("cash" or "pos")
        """
        try:
            # Build line item title
            line_item_title = f"{title} - {size}" if size else title
            
            # Calculate final price
            item_total = price * quantity
            final_amount = item_total - discount
            
            # Build line items
            line_items = [{
                "title": line_item_title,
                "quantity": quantity,
                "price": str(price)
            }]
            
            # Build order payload
            order_payload = {
                "order": {
                    "line_items": line_items,
                    "tags": f"in-store, manual, {payment_method}",
                    "financial_status": "paid",
                    "transactions": [{
                        "kind": "sale",
                        "status": "success",
                        "amount": str(final_amount),
                        "gateway": "cash" if payment_method == "cash" else "pos"
                    }]
                }
            }
            
            # Add customer info if available
            if customer:
                if customer.get("email"):
                    order_payload["order"]["email"] = customer["email"]
                if customer.get("shopify_id"):
                    order_payload["order"]["customer"] = {"id": customer["shopify_id"]}
            
            # Add discount if provided
            if discount > 0:
                order_payload["order"]["note"] = f"Manual order - Discount applied: {discount} TL"
                order_payload["order"]["line_items"].append({
                    "title": "Discount",
                    "quantity": 1,
                    "price": str(-discount)
                })
            
            print(f"📝 Creating manual order in Shopify: {line_item_title} ({payment_method})")
            
            response = self._make_request("POST", "orders.json", data=order_payload)
            order = response.get("order")
            
            if order:
                print(f"✅ Manual order created in Shopify: #{order.get('order_number')}")
            
            return order
            
        except Exception as e:
            print(f"❌ Error creating manual order: {e}")
            return None


# Create a singleton instance
shopify_api = ShopifyAPI()

