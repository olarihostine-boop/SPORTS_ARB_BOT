import os
import time
import sqlite3
import logging
import asyncio
import httpx
from dotenv import load_dotenv

# Ingest all configurations from your local secure .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PREMIUM_CHANNEL_ID = os.getenv("PREMIUM_CHANNEL_ID")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

PRICE_1DAY = float(os.getenv("SUBSCRIPTION_PRICE_1DAY", 50.0))
PRICE_30DAY = float(os.getenv("SUBSCRIPTION_PRICE_30DAY", 500.0))


def init_db():
    """Initializes the database schemas for subscription and transaction tracking."""
    conn = sqlite3.connect("subscriptions.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            status TEXT,
            expires_at REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            reference TEXT PRIMARY KEY,
            user_id INTEGER,
            phone TEXT,
            amount REAL,
            plan TEXT,
            status TEXT,
            created_at REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_states (
            user_id INTEGER PRIMARY KEY,
            state TEXT,
            plan TEXT
        )
    """)
    conn.commit()
    conn.close()


def normalize_phone(phone_str: str) -> str:
    """Cleans and formats a phone number to standard international format (e.g. +254712345678)."""
    clean = "".join(c for c in phone_str if c.isdigit())
    if clean.startswith("07") or clean.startswith("01"):
        return "+254" + clean[1:]
    elif clean.startswith("254") and len(clean) == 12:
        return "+" + clean
    elif clean.startswith("7") and len(clean) == 9:
        return "+254" + clean
    return "+" + clean


async def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None) -> bool:
    """Dispatches a text message to a specific Telegram user."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            return resp.status_code == 200
    except Exception as e:
        logging.error(f"Error sending Telegram message to {chat_id}: {e}")
        return False


async def generate_invite_link(user_id: int) -> str:
    """Generates a single-use invite link for the Premium channel."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/createChatInviteLink"
    payload = {
        "chat_id": PREMIUM_CHANNEL_ID,
        "member_limit": 1,
        "name": f"VIP Pass - User {user_id}"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                res = resp.json()
                if res.get("ok"):
                    return res["result"]["invite_link"]
                else:
                    logging.error(f"Telegram invite link API rejected: {res.get('description')}")
    except Exception as e:
        logging.error(f"Failed to generate Telegram invite link: {e}")
    return None


async def trigger_mpesa_stk_push(user_id: int, phone: str, amount_kes: float, plan: str) -> dict:
    """Triggers an M-Pesa STK push via Paystack's charge API."""
    url = "https://api.paystack.co/charge"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "email": f"subscriber_{user_id}@nexusdigital.com",
        "amount": int(amount_kes * 100),  # Paystack expects KES cents/subunits
        "mobile_money": {
            "phone": phone,
            "provider": "mpesa"
        }
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            else:
                logging.error(f"Paystack STK push HTTP error {resp.status_code}: {resp.text}")
                return None
    except Exception as e:
        logging.error(f"Failed to communicate with Paystack: {e}")
        return None


async def verify_transaction_task(user_id: int, reference: str, amount_kes: float, plan: str, username: str):
    """Background task to poll Paystack verification endpoint until status updates."""
    max_attempts = 20  # 20 attempts * 3 seconds = 60 seconds (STK prompts expire after 60s)
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    
    logging.info(f"Started polling verification for user {user_id}, reference: {reference}")
    
    for attempt in range(max_attempts):
        await asyncio.sleep(3)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    res = resp.json()
                    if res.get("status") is True:
                        status = res["data"]["status"]
                        if status == "success":
                            # Payment Successful!
                            duration = 86400 if plan == "1day" else 30 * 86400
                            expires_at = time.time() + duration
                            
                            conn = sqlite3.connect("subscriptions.db")
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR REPLACE INTO subscriptions (user_id, username, status, expires_at) VALUES (?, ?, ?, ?)",
                                           (user_id, username, "active", expires_at))
                            cursor.execute("UPDATE transactions SET status = 'success' WHERE reference = ?", (reference,))
                            conn.commit()
                            conn.close()
                            
                            invite_link = await generate_invite_link(user_id)
                            if invite_link:
                                msg = (
                                    f"✅ *Payment Verified Successfully!* \n\n"
                                    f"Thank you! Your `{plan.upper()}` VIP subscription is now active.\n"
                                    f"Click the link below to join the Premium VIP Channel:\n\n"
                                    f"👉 {invite_link}\n\n"
                                    f"⚠️ _Note: This is a single-use invite link. It will expire once you join._"
                                )
                                await send_telegram_message(user_id, msg)
                            else:
                                msg = (
                                    f"✅ *Payment Verified Successfully!* \n\n"
                                    f"Your `{plan.upper()}` VIP subscription is active, but we had trouble generating an invite link.\n"
                                    f"Please contact support with your Transaction Reference: `{reference}`."
                                )
                                await send_telegram_message(user_id, msg)
                            return
                        elif status == "failed":
                            conn = sqlite3.connect("subscriptions.db")
                            cursor = conn.cursor()
                            cursor.execute("UPDATE transactions SET status = 'failed' WHERE reference = ?", (reference,))
                            conn.commit()
                            conn.close()
                            await send_telegram_message(user_id, "❌ *Payment Failed:* The transaction was declined or canceled on your mobile phone.")
                            return
        except Exception as e:
            logging.error(f"Error checking transaction {reference}: {e}")
            
    # Timeout
    conn = sqlite3.connect("subscriptions.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE transactions SET status = 'failed' WHERE reference = ?", (reference,))
    conn.commit()
    conn.close()
    await send_telegram_message(user_id, "⌛ *Payment Verification Timeout:* We did not receive confirmation of your payment PIN. Please try again.")


async def handle_update(update: dict):
    """Processes incoming Telegram messages and button callback queries."""
    # Handle Button Clicks (Callback Queries)
    if "callback_query" in update:
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        username = cq["from"].get("username", "User")
        data = cq["data"]
        
        # Clear loading animation in user's Telegram client
        ans_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
        async with httpx.AsyncClient() as client:
            await client.post(ans_url, json={"callback_query_id": cq["id"]})
            
        if data in ["plan_1day", "plan_30day"]:
            plan = "1day" if data == "plan_1day" else "30day"
            
            # Save user state
            conn = sqlite3.connect("subscriptions.db")
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO user_states (user_id, state, plan) VALUES (?, ?, ?)",
                           (user_id, "AWAITING_PHONE", plan))
            conn.commit()
            conn.close()
            
            plan_label = "1-Day VIP Pass" if plan == "1day" else "30-Day VIP Pass"
            price = PRICE_1DAY if plan == "1day" else PRICE_30DAY
            
            await send_telegram_message(
                user_id,
                f"🛒 *Selected Plan:* `{plan_label}` (KES {price:.2f})\n\n"
                f"Please reply with your M-Pesa phone number in the format `07XXXXXXXX` to trigger the payment prompt."
            )
        return

    # Handle Text Messages
    if "message" in update:
        msg = update["message"]
        user_id = msg["chat"]["id"]
        username = msg["from"].get("username", "User")
        text = msg.get("text", "").strip()
        
        if not text:
            return
            
        if text.startswith("/start") or text.startswith("/subscribe"):
            # Clear any active state
            conn = sqlite3.connect("subscriptions.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            # Send subscription options
            welcome_msg = (
                f"👋 *Welcome to Nexus Digital Arbitrage Billing Portal!*\n\n"
                f"Get guaranteed risk-free sports betting arbitrage alerts delivered to your phone.\n"
                f"Please select a subscription plan below to unlock the Premium Channel:"
            )
            keyboard = {
                "inline_keyboard": [
                    [{"text": f"🎟️ 1-Day VIP Pass (KES {PRICE_1DAY:.0f})", "callback_data": "plan_1day"}],
                    [{"text": f"👑 30-Day VIP Pass (KES {PRICE_30DAY:.0f})", "callback_data": "plan_30day"}]
                ]
            }
            await send_telegram_message(user_id, welcome_msg, keyboard)
            return
            
        # Check User State
        conn = sqlite3.connect("subscriptions.db")
        cursor = conn.cursor()
        cursor.execute("SELECT state, plan FROM user_states WHERE user_id = ?", (user_id,))
        state_row = cursor.fetchone()
        conn.close()
        
        if state_row and state_row[0] == "AWAITING_PHONE":
            plan = state_row[1]
            amount = PRICE_1DAY if plan == "1day" else PRICE_30DAY
            
            # Reset state
            conn = sqlite3.connect("subscriptions.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            phone = normalize_phone(text)
            # Basic validation
            if len(phone) < 12:
                await send_telegram_message(
                    user_id, 
                    "❌ *Invalid Phone Number:* Please enter a valid Safaricom number starting with `07...` or `2547...`. Type `/subscribe` to restart."
                )
                return
                
            await send_telegram_message(user_id, "⌛ *Initiating M-Pesa payment...* Please wait.")
            
            # Trigger STK Push
            res = await trigger_mpesa_stk_push(user_id, phone, amount, plan)
            if res and res.get("status") is True:
                # Paystack returns 'pending' status for mobile money charge initiation
                reference = res["data"]["reference"]
                
                # Log transaction
                conn = sqlite3.connect("subscriptions.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO transactions (reference, user_id, phone, amount, plan, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (reference, user_id, phone, amount, plan, "pending", time.time()))
                conn.commit()
                conn.close()
                
                await send_telegram_message(
                    user_id,
                    f"📲 *M-Pesa STK Push Sent!*\n\n"
                    f"Check your phone for a PIN prompt asking to pay *KES {amount:.2f}* to Paystack.\n"
                    f"Enter your M-Pesa PIN to complete the purchase. Your channel access link will be sent here automatically."
                )
                
                # Start polling Paystack status in background
                asyncio.create_task(verify_transaction_task(user_id, reference, amount, plan, username))
            else:
                await send_telegram_message(
                    user_id,
                    "❌ *Billing Gateway Error:* We could not initiate the payment prompt. Please try again later by typing `/subscribe`."
                )


async def auto_expiration_worker():
    """Background task to remove expired users from the Premium Telegram channel."""
    while True:
        try:
            now = time.time()
            conn = sqlite3.connect("subscriptions.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username FROM subscriptions WHERE status = 'active' AND expires_at < ?", (now,))
            expired_users = cursor.fetchall()
            
            for user_id, username in expired_users:
                # Kick (ban) user to remove from channel
                ban_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/banChatMember"
                ban_payload = {
                    "chat_id": PREMIUM_CHANNEL_ID,
                    "user_id": user_id,
                    "revoke_messages": False
                }
                async with httpx.AsyncClient() as client:
                    await client.post(ban_url, json=ban_payload)
                    
                    # Unban immediately so they can rejoin later if they purchase another subscription
                    unban_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/unbanChatMember"
                    unban_payload = {
                        "chat_id": PREMIUM_CHANNEL_ID,
                        "user_id": user_id,
                        "only_if_banned": True
                    }
                    await client.post(unban_url, json=unban_payload)
                    
                # Update DB
                cursor.execute("UPDATE subscriptions SET status = 'expired' WHERE user_id = ?", (user_id,))
                conn.commit()
                
                logging.info(f"User {user_id} ({username}) subscription expired. Removed from VIP channel.")
                await send_telegram_message(
                    user_id,
                    "⚠️ *Your Premium VIP Subscription has expired.*\n\n"
                    "To continue receiving risk-free sports arbitrage alerts, please click `/subscribe` to buy a new pass."
                )
            conn.close()
        except Exception as e:
            logging.error(f"Error in auto-expiration worker: {e}")
            
        # Check every 10 minutes
        await asyncio.sleep(600)


async def poll_telegram():
    """Long-polling cycle to process updates from the Telegram Bot API."""
    offset = 0
    logging.info("Telegram long-poll billing listener started.")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=35)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            await handle_update(update)
        except Exception as e:
            logging.error(f"Telegram long-polling connection error: {e}")
        await asyncio.sleep(1)


async def main():
    init_db()
    # Run Telegram listener and Auto-expiration checker concurrently
    await asyncio.gather(
        poll_telegram(),
        auto_expiration_worker()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Billing modules suspended.")
    except Exception as e:
        logging.error(f"Fatal execution crash: {e}")
