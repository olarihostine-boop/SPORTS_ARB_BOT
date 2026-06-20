import os
import random
import asyncio
import logging
import time
import sqlite3
import httpx
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Ingest all configurations from your local secure .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# --- CONFIGURATIONS ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PREMIUM_CHANNEL_ID = os.getenv("PREMIUM_CHANNEL_ID")
FREE_CHANNEL_ID = os.getenv("FREE_CHANNEL_ID")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

BOOKMAKER_A_URL = os.getenv("BOOKMAKER_A_URL")
BOOKMAKER_B_URL = os.getenv("BOOKMAKER_B_URL")
BASE_SCAN_DELAY = int(os.getenv("SCAN_DELAY_SECONDS", 10))

PRICE_1DAY = float(os.getenv("SUBSCRIPTION_PRICE_1DAY", 50.0))
PRICE_30DAY = float(os.getenv("SUBSCRIPTION_PRICE_30DAY", 500.0))


# ==========================================
# PART 1: DATABASE & AUXILIARY HELPERS
# ==========================================

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


async def transmit_telegram_broadcast(target_chat_id: str, message: str):
    """Dispatches arbitrage signal payload to specific channel nodes anonymously."""
    if not TELEGRAM_BOT_TOKEN or not target_chat_id:
        logging.warning("Telegram routing properties missing. Broadcast bypassed.")
        return
    
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, json=payload, timeout=12)
            if response.status_code == 200:
                logging.info(f"✅ Success: Dispatched broadcast data to channel gateway: {target_chat_id}")
            else:
                logging.error(f"Telegram transmission rejected: {response.text}")
    except Exception as e:
        logging.error(f"Telegram communication latency error: {e}")


# ==========================================
# PART 2: ARBITRAGE SCANNER ENGINE (bot.py)
# ==========================================

async def run_arbitrage_engine(match_title: str, status: str, odds_1: float, odds_2: float):
    """Computes cross-market probabilities and routes signals based on value metrics."""
    prob_1 = 1 / odds_1
    prob_2 = 1 / odds_2
    arbitrage_ratio = prob_1 + prob_2

    if arbitrage_ratio < 1.0:
        margin_percent = (1 - arbitrage_ratio) * 100
        
        # Guard filters against manual typos or unhedged pricing adjustments
        if margin_percent > 20.0 or margin_percent < 1.5:
            return 

        calc_link = os.getenv('CALCULATOR_URL', 'https://olarihostine-boop.github.io/SPORTS_ARB_BOT/')
        
        if margin_percent <= 4.0:
            free_msg = (
                f"🆓 *DAILY FREE COUPLING PICK* 🆓\n"
                f"Status: `{status.upper()}`\n\n"
                f"🏆 *Match:* `{match_title}`\n"
                f"📈 *Guaranteed Profit Yield:* `+{margin_percent:.2f}%` risk-free\n\n"
                f"👉 *SportyBet Odds (Outcome 1):* `{odds_1:.2f}`\n"
                f"👉 *Betika Odds (Outcome 2):* `{odds_2:.2f}`\n\n"
                f"🧮 *Verify Math or Calculate Stakes For Free Here:* {calc_link}\n\n"
                f"🔥 _Want high-yield 5% to 20% premium signals all day? Unlock VIP inside our shop:_ @Your_Billing_Bot"
            )
            await transmit_telegram_broadcast(FREE_CHANNEL_ID, free_msg)
            
        else:
            premium_msg = (
                f"👑 *PREMIUM VIP HIGH-YIELD SIGNAL* 👑\n"
                f"Status: `{status.upper()}`\n\n"
                f"🏆 *Match:* `{match_title}`\n"
                f"📈 *Guaranteed Premium Yield:* `+{margin_percent:.2f}%` risk-free\n\n"
                f"👉 *SportyBet Odds (Outcome 1):* `{odds_1:.2f}`\n"
                f"👉 *Betika Odds (Outcome 2):* `{odds_2:.2f}`\n\n"
                f"🧮 *Calculate Your Stakes Instantly:* {calc_link}"
            )
            await transmit_telegram_broadcast(PREMIUM_CHANNEL_ID, premium_msg)
            
        print(f"\n[+] Executed System Distribution: {match_title} | Yield: {margin_percent:.2f}%")


def matches_are_same(title_a: str, title_b: str) -> bool:
    """Checks if two match titles refer to the same event by analyzing team names."""
    delims = [" vs ", " - "]
    parts_a, parts_b = None, None
    for delim in delims:
        if delim in title_a.lower():
            parts_a = title_a.lower().split(delim)
        if delim in title_b.lower():
            parts_b = title_b.lower().split(delim)
            
    if not parts_a or not parts_b or len(parts_a) != 2 or len(parts_b) != 2:
        return False
        
    team_a1, team_a2 = parts_a[0].strip(), parts_a[1].strip()
    team_b1, team_b2 = parts_b[0].strip(), parts_b[1].strip()
    
    def team_match(t1: str, t2: str) -> bool:
        if t1 == t2 or t1 in t2 or t2 in t1:
            return True
        abbrevs = {"man": "manchester", "utd": "united", "fc": "", "afc": "", "real": ""}
        def clean_words(t):
            w_list = []
            for w in t.split():
                w = w.replace(".", "")
                if w in abbrevs:
                    if abbrevs[w]:
                        w_list.append(abbrevs[w])
                elif w not in ["fc", "afc", "club", "de", "sports", "sport", "sv", "sc"]:
                    w_list.append(w)
            return set(w_list)
            
        cw1 = clean_words(t1)
        cw2 = clean_words(t2)
        if not cw1 or not cw2:
            return t1 == t2
        return len(cw1.intersection(cw2)) >= min(len(cw1), len(cw2), 1)
        
    return (team_match(team_a1, team_b1) and team_match(team_a2, team_b2)) or \
           (team_match(team_a1, team_b2) and team_match(team_a2, team_b1))


async def scrape_full_spectrum_board(browser, url: str, site_name: str) -> dict:
    """Layout-independent stealth web browser data scraper reusing warm browser."""
    context = None
    try:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": random.randint(1366, 1440), "height": random.randint(768, 900)},
            locale="en-KE",
            timezone_id="Africa/Nairobi"
        )
        page = await context.new_page()
        page.set_default_timeout(35000)
        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
        
        # Subtle natural scrolling to clear advanced heuristics
        for _ in range(random.randint(1, 2)):
            await page.mouse.wheel(0, random.randint(200, 400))
            await asyncio.sleep(random.uniform(0.4, 0.9))
            
        # Fast browser-side JS DOM parsing in V8 engine
        market_data = await page.evaluate("""() => {
            const marketData = {};
            const elements = document.querySelectorAll('div, tr, a');
            for (const el of elements) {
                try {
                    const blockText = el.innerText;
                    if (!blockText || !blockText.includes(' vs ')) continue;
                    
                    const lines = blockText.split('\\n').map(l => l.trim()).filter(Boolean);
                    if (lines.length === 0) continue;
                    
                    const teamsList = lines.filter(l => l.toLowerCase().includes(' vs '));
                    if (teamsList.length === 0) continue;
                    
                    const oddsList = [];
                    for (const line of lines) {
                        const cleanLine = line.replace(',', '.');
                        if (/^\\d+(\\.\\d+)?$/.test(cleanLine)) {
                            const val = parseFloat(cleanLine);
                            if (val > 1.05 && val < 25.0) {
                                oddsList.push(val);
                            }
                        }
                    }
                    
                    if (oddsList.length >= 2) {
                        const matchTitle = teamsList[0];
                        const matchKey = matchTitle.toLowerCase().replace(/\\s+/g, '').replace('vs', 'vs');
                        
                        const isLive = lines.some(l => l.toLowerCase().includes('live') || l.includes("'"));
                        const statusLabel = isLive ? "Live" : "Upcoming";
                        
                        const homeOdds = oddsList[0];
                        const awayOdds = oddsList[oddsList.length - 1];
                        
                        marketData[matchKey] = {
                            title: matchTitle,
                            home_odds: homeOdds,
                            away_odds: awayOdds,
                            status: statusLabel
                        };
                    }
                } catch (e) {}
            }
            return marketData;
        }""")
        return market_data
    except Exception as e:
        logging.error(f"Error parsing global sports feed for {site_name}: {e}")
        return {}
    finally:
        if context:
            await context.close()


async def runtime_loop():
    """Continuous loop running scraper checks for arbitrage windows using warm browser."""
    logging.info(f"Stealth Scraper Loop Initialized (Warm Browser).")
    async with async_playwright() as playwright:
        # Optimized launch arguments to minimize RAM/CPU usage on Render's Free tier
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--single-process",
                "--disable-extensions"
            ]
        )
        try:
            while True:
                try:
                    tasks = [
                        scrape_full_spectrum_board(browser, BOOKMAKER_A_URL, "SportyBet"),
                        scrape_full_spectrum_board(browser, BOOKMAKER_B_URL, "Betika")
                    ]
                    sporty_matrix, betika_matrix = await asyncio.gather(*tasks)
                    
                    if not sporty_matrix or not betika_matrix:
                        logging.info("Scanning full matrix... Markets balanced. (Waiting for adjustments)")
                        await asyncio.sleep(BASE_SCAN_DELAY + random.uniform(2.0, 5.0))
                        continue
                    
                    for sporty_key, sporty_item in sporty_matrix.items():
                        betika_item = None
                        if sporty_key in betika_matrix:
                            betika_item = betika_matrix[sporty_key]
                        else:
                            for betika_key, item in betika_matrix.items():
                                if matches_are_same(sporty_item["title"], item["title"]):
                                    betika_item = item
                                    break
                                    
                        if betika_item:
                            status = sporty_item["status"]
                            await run_arbitrage_engine(sporty_item["title"], status, sporty_item["home_odds"], betika_item["away_odds"])
                            await run_arbitrage_engine(sporty_item["title"], status, betika_item["home_odds"], sporty_item["away_odds"])
                            
                except Exception as loop_error:
                    logging.error(f"Global processing loop exception handled: {loop_error}")
                    
                dynamic_jitter = BASE_SCAN_DELAY + random.uniform(1.5, 6.0)
                await asyncio.sleep(dynamic_jitter)
        finally:
            await browser.close()


# ==========================================
# PART 3: AUTOMATED BILLING MODULES (Paystack)
# ==========================================

async def trigger_mpesa_stk_push(user_id: int, phone: str, amount_kes: float, plan: str) -> dict:
    """Triggers an M-Pesa STK push via Paystack's charge API."""
    url = "https://api.paystack.co/charge"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "email": f"subscriber_{user_id}@nexusdigital.com",
        "amount": int(amount_kes * 100),
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
    max_attempts = 20
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
            
    conn = sqlite3.connect("subscriptions.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE transactions SET status = 'failed' WHERE reference = ?", (reference,))
    conn.commit()
    conn.close()
    await send_telegram_message(user_id, "⌛ *Payment Verification Timeout:* We did not receive confirmation of your payment PIN. Please try again.")


async def handle_update(update: dict):
    """Processes incoming Telegram messages and button callback queries."""
    if "callback_query" in update:
        cq = update["callback_query"]
        user_id = cq["from"]["id"]
        username = cq["from"].get("username", "User")
        data = cq["data"]
        
        ans_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
        async with httpx.AsyncClient() as client:
            await client.post(ans_url, json={"callback_query_id": cq["id"]})
            
        if data in ["plan_1day", "plan_30day"]:
            plan = "1day" if data == "plan_1day" else "30day"
            
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

    if "message" in update:
        msg = update["message"]
        user_id = msg["chat"]["id"]
        username = msg["from"].get("username", "User")
        text = msg.get("text", "").strip()
        
        if not text:
            return
            
        if text.startswith("/start") or text.startswith("/subscribe"):
            conn = sqlite3.connect("subscriptions.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            
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
            
        conn = sqlite3.connect("subscriptions.db")
        cursor = conn.cursor()
        cursor.execute("SELECT state, plan FROM user_states WHERE user_id = ?", (user_id,))
        state_row = cursor.fetchone()
        conn.close()
        
        if state_row and state_row[0] == "AWAITING_PHONE":
            plan = state_row[1]
            amount = PRICE_1DAY if plan == "1day" else PRICE_30DAY
            
            conn = sqlite3.connect("subscriptions.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            phone = normalize_phone(text)
            if len(phone) < 12:
                await send_telegram_message(
                    user_id, 
                    "❌ *Invalid Phone Number:* Please enter a valid Safaricom number starting with `07...` or `2547...`. Type `/subscribe` to restart."
                )
                return
                
            await send_telegram_message(user_id, "⌛ *Initiating M-Pesa payment...* Please wait.")
            
            res = await trigger_mpesa_stk_push(user_id, phone, amount, plan)
            if res and res.get("status") is True:
                reference = res["data"]["reference"]
                
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
                ban_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/banChatMember"
                ban_payload = {
                    "chat_id": PREMIUM_CHANNEL_ID,
                    "user_id": user_id,
                    "revoke_messages": False
                }
                async with httpx.AsyncClient() as client:
                    await client.post(ban_url, json=ban_payload)
                    
                    unban_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/unbanChatMember"
                    unban_payload = {
                        "chat_id": PREMIUM_CHANNEL_ID,
                        "user_id": user_id,
                        "only_if_banned": True
                    }
                    await client.post(unban_url, json=unban_payload)
                    
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


async def handle_health_check(reader, writer):
    """Processes HTTP requests from Render to satisfy deployment health checks."""
    try:
        await reader.read(1024)
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 2\r\n"
            "Connection: close\r\n\r\n"
            "OK"
        )
        writer.write(response.encode())
        await writer.drain()
    except Exception as e:
        logging.error(f"Health server error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def start_health_server():
    """Starts the basic web server on the port defined by Render ($PORT)."""
    port = int(os.getenv("PORT", 8080))
    try:
        server = await asyncio.start_server(handle_health_check, '0.0.0.0', port)
        logging.info(f"Render health check server online on port {port}")
        async with server:
            await server.serve_forever()
    except Exception as e:
        logging.error(f"Failed to start health check server: {e}")


# ==========================================
# PART 4: MAIN STARTUP ENTRYPOINT
# ==========================================

async def main():
    init_db()
    # Concurrently run the Telegram poller, Subscription expiration checker,
    # Render health server, AND the Arbitrage Scraper loop!
    await asyncio.gather(
        poll_telegram(),
        auto_expiration_worker(),
        start_health_server(),
        runtime_loop()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Core system modules suspended.")
    except Exception as e:
        logging.error(f"Fatal execution crash: {e}")
