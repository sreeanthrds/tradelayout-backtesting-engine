"""
Billing API - Read-only billing information
Provides subscription and usage data for UI display
"""
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import hashlib
import hmac
import json
import os

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Request models
class CheckoutRequest(BaseModel):
    plan_id: str

class AddonPurchaseRequest(BaseModel):
    pack_type: str  # "ADDON-100", "ADDON-500", "ADDON-1000"

# Razorpay webhook secret (should be environment variable)
RAZORPAY_WEBHOOK_SECRET = "razorpay_webhook_secret_key"  # TODO: Move to env

# Import database service
from src.services.billing_db_service import billing_db_service

# Mock data for now - will integrate with real services later
def get_mock_billing_data() -> Dict[str, Any]:
    """Get mock billing data for development"""
    # TODO: Get real user data from database
    # For now, return FREE plan (will be updated by webhook)
    
    # Get add-on wallet to include in response
    addon_wallet = billing_db_service.get_addon_wallet("test_user")
    
    # Calculate available credits
    addon_backtests_available = (addon_wallet['backtests_purchased'] - addon_wallet['backtests_consumed']) if addon_wallet else 0
    addon_live_available = (addon_wallet['live_purchased'] - addon_wallet['live_consumed']) if addon_wallet else 0
    
    return {
        "plan": "FREE",
        "status": "ACTIVE", 
        "expires_at": "2025-02-01T00:00:00Z",
        "usage": {
            "backtests_used": 12,
            "backtests_limit": 50,
            "live_used": 1,
            "live_limit": 5
        },
        "addons": {
            "backtests_purchased": addon_wallet['backtests_purchased'] if addon_wallet else 0,
            "backtests_consumed": addon_wallet['backtests_consumed'] if addon_wallet else 0,
            "backtests_available": addon_backtests_available,
            "live_purchased": addon_wallet['live_purchased'] if addon_wallet else 0,
            "live_consumed": addon_wallet['live_consumed'] if addon_wallet else 0,
            "live_available": addon_live_available
        }
    }

def verify_razorpay_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    """Verify Razorpay webhook signature"""
    try:
        # Construct the signature string
        signature_string = f"{razorpay_order_id}|{razorpay_payment_id}"
        
        # Generate expected signature
        expected_signature = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode(),
            signature_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures securely
        return hmac.compare_digest(expected_signature, razorpay_signature)
        
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False

def activate_subscription(user_id: str, plan_id: str) -> Dict[str, Any]:
    """Activate subscription for user"""
    plan_config = get_plan_config(plan_id)
    
    # Calculate expiry (1 month from now for PRO, 1 year for ENTERPRISE)
    if plan_id == "PRO":
        expires_at = datetime.now() + timedelta(days=30)
    elif plan_id == "ENTERPRISE":
        expires_at = datetime.now() + timedelta(days=365)
    else:
        expires_at = datetime.now() + timedelta(days=30)
    
    # Store subscription in database
    subscription_data = billing_db_service.create_subscription(user_id, plan_id, expires_at)
    
    # Reset usage counters in database
    usage_data = billing_db_service.reset_usage_counters(user_id)
    
    # Get plan limits
    plan_limits = get_plan_config(plan_id)
    
    print(f"Subscription activated for {user_id}: {plan_id} (DB)")
    
    return {
        "user_id": user_id,
        "plan": plan_id,
        "status": "ACTIVE",
        "expires_at": subscription_data['expiry_date'],
        "usage": {
            "backtests_used": usage_data['backtests_used'],
            "backtests_limit": plan_limits["backtests_limit"],
            "live_used": usage_data['live_used'],
            "live_limit": plan_limits["live_limit"]
        }
    }

def get_plan_config(plan_id: str) -> Dict[str, Any]:
    plans = {
        "PRO": {
            "name": "PRO",
            "price": 49900,  # ₹499.00 in paise
            "currency": "INR",
            "backtests_limit": 500,
            "live_limit": 25
        },
        "ENTERPRISE": {
            "name": "ENTERPRISE", 
            "price": 199900,  # ₹1,999.00 in paise
            "currency": "INR",
            "backtests_limit": 2000,
            "live_limit": 100
        }
    }
    
    if plan_id not in plans:
        raise ValueError(f"Invalid plan_id: {plan_id}")
    
    return plans[plan_id]

def get_addon_pack_config(pack_type: str) -> Dict[str, Any]:
    packs = {
        "ADDON-100": {
            "name": "Add-on 100 Executions",
            "backtests": 100,
            "live": 5,
            "price": 29900,  # ₹299.00 in paise
            "currency": "INR"
        },
        "ADDON-500": {
            "name": "Add-on 500 Executions",
            "backtests": 500,
            "live": 25,
            "price": 99900,  # ₹999.00 in paise
            "currency": "INR"
        },
        "ADDON-1000": {
            "name": "Add-on 1000 Executions",
            "backtests": 1000,
            "live": 50,
            "price": 179900,  # ₹1799.00 in paise
            "currency": "INR"
        }
    }
    
    if pack_type not in packs:
        raise ValueError(f"Invalid pack_type: {pack_type}")
    
    return packs[pack_type]

@router.get("/summary")
async def get_billing_summary():
    """
    Get billing summary for current user
    
    Returns subscription plan, status, usage, and add-on credits
    """
    try:
        # TODO: Get user_id from auth middleware
        user_id = "test_user"  # Placeholder
        
        # Get subscription from database
        subscription = billing_db_service.get_subscription(user_id)
        
        # Get usage counters from database
        usage = billing_db_service.get_usage_counters(user_id)
        
        # Get add-on wallet from database
        addon_wallet = billing_db_service.get_addon_wallet(user_id)
        
        if subscription:
            # Get plan limits
            plan_config = get_plan_config(subscription['plan'])
            
            # Calculate add-on available credits
            addon_backtests_available = (addon_wallet['backtests_purchased'] - addon_wallet['backtests_consumed']) if addon_wallet else 0
            addon_live_available = (addon_wallet['live_purchased'] - addon_wallet['live_consumed']) if addon_wallet else 0
            
            return {
                "plan": subscription['plan'],
                "status": subscription['status'],
                "expires_at": subscription['expiry_date'],
                "usage": {
                    "backtests_used": usage['backtests_used'] if usage else 0,
                    "backtests_limit": plan_config["backtests_limit"],
                    "live_used": usage['live_used'] if usage else 0,
                    "live_limit": plan_config["live_limit"]
                },
                "addons": {
                    "backtests_purchased": addon_wallet['backtests_purchased'] if addon_wallet else 0,
                    "backtests_consumed": addon_wallet['backtests_consumed'] if addon_wallet else 0,
                    "backtests_available": addon_backtests_available,
                    "live_purchased": addon_wallet['live_purchased'] if addon_wallet else 0,
                    "live_consumed": addon_wallet['live_consumed'] if addon_wallet else 0,
                    "live_available": addon_live_available
                }
            }
        
        # Return default FREE plan if no subscription found
        billing_data = get_mock_billing_data()
        return billing_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch billing summary: {str(e)}"
        )

@router.post("/checkout")
async def create_checkout_session(request: CheckoutRequest):
    """
    Create Razorpay checkout session
    
    Creates order and returns payment details for UI
    """
    try:
        # Validate plan
        plan_config = get_plan_config(request.plan_id)
        
        # TODO: Get user_id from auth middleware
        user_id = "test_user"  # Placeholder
        
        # Mock Razorpay order creation (will integrate with real Razorpay)
        order_id = f"order_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_id[:8]}"
        
        # TODO: Store order in database with user_id and plan_id
        # For now, just return mock data with correct Razorpay test keys
        checkout_response = {
            "key": "rzp_test_1DP5mmOlF5G5ag",  # Valid Razorpay test key
            "order_id": order_id,
            "amount": plan_config["price"],
            "currency": plan_config["currency"],
            "plan_id": request.plan_id,
            "user_id": user_id
        }
        
        return checkout_response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create checkout session: {str(e)}"
        )

@router.post("/addon/checkout")
async def create_addon_checkout(request: AddonPurchaseRequest):
    """
    Create checkout session for add-on execution pack purchase
    """
    try:
        # Validate pack type
        pack_config = get_addon_pack_config(request.pack_type)
        
        # TODO: Get user_id from auth middleware
        user_id = "test_user"  # Placeholder
        
        # Mock Razorpay order creation (will integrate with real Razorpay)
        order_id = f"addon_order_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_id[:8]}"
        
        # TODO: Store order in database with user_id and pack_type
        # For now, just return mock data with correct Razorpay test keys
        checkout_response = {
            "key": "rzp_test_1DP5mmOlF5G5ag",  # Valid Razorpay test key
            "order_id": order_id,
            "amount": pack_config["price"],
            "currency": pack_config["currency"],
            "pack_type": request.pack_type,
            "pack_name": pack_config["name"],
            "backtests": pack_config["backtests"],
            "live": pack_config["live"],
            "user_id": user_id
        }
        
        return checkout_response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create add-on checkout: {str(e)}"
        )

@router.post("/webhook")
async def razorpay_webhook(request: Request):
    """
    Razorpay webhook endpoint
    
    Handles payment events and activates subscriptions
    """
    try:
        # Get webhook body
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # Get signature from headers
        razorpay_signature = request.headers.get('x-razorpay-signature')
        if not razorpay_signature:
            print("Webhook error: Missing signature")
            raise HTTPException(status_code=400, detail="Missing signature")
        
        # Parse webhook data
        webhook_data = json.loads(body_str)
        
        # Verify this is a payment.captured event
        if webhook_data.get('event') != 'payment.captured':
            print(f"Ignoring non-payment event: {webhook_data.get('event')}")
            return {"status": "ignored"}
        
        # Extract payment details
        payment = webhook_data.get('payload', {}).get('payment', {}).get('entity', {})
        razorpay_order_id = payment.get('order_id')
        razorpay_payment_id = payment.get('id')
        
        if not razorpay_order_id or not razorpay_payment_id:
            print("Webhook error: Missing order_id or payment_id")
            raise HTTPException(status_code=400, detail="Missing payment details")
        
        # Verify signature
        if not verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            print(f"Webhook error: Invalid signature for order {razorpay_order_id}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Extract user_id and plan_id from order_id (mock logic)
        # TODO: Get from database using order_id
        user_id = "test_user"  # Extracted from order_id in real implementation
        
        # Check if this is an add-on purchase or subscription
        if "addon_order" in razorpay_order_id:
            # Handle add-on purchase
            pack_type = "ADDON-500"  # Extracted from order_id in real implementation
            
            print(f"Processing add-on purchase: order={razorpay_order_id}, payment={razorpay_payment_id}, user={user_id}, pack={pack_type}")
            
            # Get pack configuration
            pack_config = get_addon_pack_config(pack_type)
            
            # Add credits to user's add-on wallet
            addon_wallet = billing_db_service.add_addon_credits(
                user_id=user_id,
                backtests=pack_config["backtests"],
                live=pack_config["live"]
            )
            
            print(f"Add-on credits added: {addon_wallet}")
            
            return {
                "status": "success",
                "order_id": razorpay_order_id,
                "payment_id": razorpay_payment_id,
                "pack_type": pack_type,
                "credits_added": {
                    "backtests": pack_config["backtests"],
                    "live": pack_config["live"]
                }
            }
        else:
            # Handle subscription purchase
            plan_id = "PRO"  # Extracted from order_id in real implementation
            
            print(f"Processing subscription: order={razorpay_order_id}, payment={razorpay_payment_id}, user={user_id}, plan={plan_id}")
            
            # Store payment record in database
            payment_record = billing_db_service.create_payment(
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                user_id=user_id,
                plan_id=plan_id,
                amount=payment.get('amount', 0),
                currency=payment.get('currency', 'INR'),
                webhook_payload=webhook_data
            )
            
            print(f"Payment stored: {payment_record}")
            
            # Activate subscription (idempotent)
            subscription = activate_subscription(user_id, plan_id)
            
            print(f"Subscription activated: {subscription}")
            
            return {
                "status": "success",
                "order_id": razorpay_order_id,
                "payment_id": razorpay_payment_id,
                "subscription": subscription
            }
        
    except json.JSONDecodeError:
        print("Webhook error: Invalid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing failed: {str(e)}"
        )

# === MINIMAL RAZORPAY PAYMENT ENDPOINTS ===

@router.post("/create-order")
async def create_order():
    """Create Razorpay order for payment"""
    try:
        import razorpay
        from dotenv import load_dotenv
        
        load_dotenv()
        
        client = razorpay.Client(
            auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
        )
        
        order_data = {
            "amount": 50000,  # ₹500 in paise
            "currency": "INR",
            "receipt": f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "notes": {
                "plan": "launch_offer"
            }
        }
        
        order = client.order.create(data=order_data)
        
        print(f"✅ Razorpay order created: {order['id']}")
        
        return {
            "success": True,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"]
        }
        
    except Exception as e:
        print(f"❌ Order creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")

@router.post("/razorpay-webhook")
async def razorpay_webhook(request: Request):
    """Handle Razorpay webhook - verify and log payment"""
    try:
        import razorpay
        import hmac
        import hashlib
        
        body = await request.body()
        signature = request.headers.get("x-razorpay-signature")
        
        if not signature:
            raise HTTPException(status_code=400, detail="Missing signature")
        
        # Load Razorpay credentials
        from dotenv import load_dotenv
        load_dotenv()
        
        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        
        # Verify signature
        expected_signature = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Parse webhook
        webhook_data = json.loads(body.decode())
        
        if webhook_data.get("event") == "payment.captured":
            payment = webhook_data["payload"]["payment"]["entity"]
            print(f"🎉 PAYMENT SUCCESS!")
            print(f"   Payment ID: {payment['id']}")
            print(f"   Order ID: {payment['order_id']}")
            print(f"   Amount: ₹{payment['amount']/100}")
            print(f"   Status: {payment['status']}")
            
            return {"success": True, "processed": True}
        
        return {"success": True, "processed": False}
        
    except Exception as e:
        print(f"❌ Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook failed: {str(e)}")
