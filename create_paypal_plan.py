import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# Set these in your .env file
PAYPAL_CLIENT_ID = os.getenv("VITE_PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_API_BASE = "https://api-m.paypal.com"  # Use https://api-m.sandbox.paypal.com for testing

def get_access_token():
    print("Getting PayPal Access Token...")
    response = requests.post(
        f"{PAYPAL_API_BASE}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"}
    )
    if response.status_code != 200:
        raise Exception(f"Failed to get access token: {response.text}")
    return response.json()["access_token"]

def create_product(token):
    print("Creating Organic Marketing AI Product...")
    payload = {
        "name": "Organic Marketing AI - Pro Plan",
        "description": "Unlimited access to the AI video studio, brand analysis, and social automation platform.",
        "type": "SERVICE",
        "category": "SOFTWARE"
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Prefer": "return=representation"
    }
    response = requests.post(f"{PAYPAL_API_BASE}/v1/catalogs/products", headers=headers, json=payload)
    if response.status_code not in (200, 201):
        raise Exception(f"Failed to create product: {response.text}")
    product_id = response.json()["id"]
    print(f"✅ Product Created: {product_id}")
    return product_id

def create_plan(token, product_id):
    print("Creating $17/mo Subscription Plan...")
    payload = {
        "product_id": product_id,
        "name": "Pro Monthly Plan",
        "description": "$17/month subscription",
        "status": "ACTIVE",
        "billing_cycles": [
            {
                "frequency": {
                    "interval_unit": "MONTH",
                    "interval_count": 1
                },
                "tenure_type": "REGULAR",
                "sequence": 1,
                "total_cycles": 0,
                "pricing_scheme": {
                    "fixed_price": {
                        "value": "17.00",
                        "currency_code": "USD"
                    }
                }
            }
        ],
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee": {
                "value": "0.00",
                "currency_code": "USD"
            },
            "setup_fee_failure_action": "CONTINUE",
            "payment_failure_threshold": 3
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Prefer": "return=representation"
    }
    response = requests.post(f"{PAYPAL_API_BASE}/v1/billing/plans", headers=headers, json=payload)
    if response.status_code not in (200, 201):
        raise Exception(f"Failed to create plan: {response.text}")
    
    plan_id = response.json()["id"]
    print(f"✅ Plan Created: {plan_id}")
    print("\n" + "="*50)
    print(f"🎉 SUCCESS! Add the following to your frontend .env file:")
    print(f"VITE_PAYPAL_PLAN_ID={plan_id}")
    print("="*50 + "\n")
    return plan_id

if __name__ == "__main__":
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        print("❌ ERROR: VITE_PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set in your .env file")
        exit(1)
        
    try:
        token = get_access_token()
        product_id = create_product(token)
        create_plan(token, product_id)
    except Exception as e:
        print(f"❌ ERROR: {e}")
