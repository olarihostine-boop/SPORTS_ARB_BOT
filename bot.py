import os
import random
import asyncio
import logging
import httpx
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Ingest all configurations from your local secure .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

BOOKMAKER_A_URL = os.getenv("BOOKMAKER_A_URL")
BOOKMAKER_B_URL = os.getenv("BOOKMAKER_B_URL")
TOTAL_BANKROLL = float(os.getenv("TOTAL_BANKROLL", 5000.0))
BASE_SCAN_DELAY = int(os.getenv("SCAN_DELAY_SECONDS", 10))

# Anonymous API Routing Parameters
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PREMIUM_CHANNEL_ID = os.getenv("PREMIUM_CHANNEL_ID")
FREE_CHANNEL_ID = os.getenv("FREE_CHANNEL_ID")


def transmit_telegram_broadcast(target_chat_id: str, message: str):
    """Dispatches payload to specific channel nodes anonymously."""
    if not TELEGRAM_BOT_TOKEN or not target_chat_id:
        logging.warning("Telegram routing properties missing. Broadcast bypassed.")
        return
    
    endpoint = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = httpx.post(endpoint, json=payload, timeout=12)
        if response.status_code == 200:
            logging.info(f"✅ Success: Dispatched broadcast data to channel gateway: {target_chat_id}")
        else:
            logging.error(f"Telegram transmission rejected: {response.text}")
    except Exception as e:
        logging.error(f"Telegram communication latency error: {e}")


def run_arbitrage_engine(match_title: str, status: str, odds_1: float, odds_2: float):
    """
    Computes cross-market probabilities and routes signals based on value metrics.
    Splits free low-margin picks from high-yielding premium selections automatically.
    """
    prob_1 = 1 / odds_1
    prob_2 = 1 / odds_2
    arbitrage_ratio = prob_1 + prob_2

    if arbitrage_ratio < 1.0:
        margin_percent = (1 - arbitrage_ratio) * 100
        
        # Guard filters against manual typos or unhedged pricing adjustments
        if margin_percent > 20.0 or margin_percent < 1.5:
            return 

        # Extract your live hosted GitHub Pages calculator form domain URL link
        calc_link = os.getenv('CALCULATOR_URL', 'https://olarihostine-boop.github.io/SPORTS_ARB_BOT/')
        
        # --- ANONYMOUS SAAS FREEMIUM ROUTING CORE ---
        if margin_percent <= 4.0:
            # BROADCAST TO PUBLIC FREE HUB FOR MARKETING ACQUISITION
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
            transmit_telegram_broadcast(FREE_CHANNEL_ID, free_msg)
            
        else:
            # ROUTE TO SECURE LOCKED PREMIUM VIP CHANNELS
            premium_msg = (
                f"👑 *PREMIUM VIP HIGH-YIELD SIGNAL* 👑\n"
                f"Status: `{status.upper()}`\n\n"
                f"🏆 *Match:* `{match_title}`\n"
                f"📈 *Guaranteed Premium Yield:* `+{margin_percent:.2f}%` risk-free\n\n"
                f"👉 *SportyBet Odds (Outcome 1):* `{odds_1:.2f}`\n"
                f"👉 *Betika Odds (Outcome 2):* `{odds_2:.2f}`\n\n"
                f"🧮 *Calculate Your Stakes Instantly:* {calc_link}"
            )
            transmit_telegram_broadcast(PREMIUM_CHANNEL_ID, premium_msg)
            
        print(f"\n[+] Executed System Distribution: {match_title} | Yield: {margin_percent:.2f}%")


async def scrape_full_spectrum_board(playwright, url: str, site_name: str) -> dict:
    """Layout-independent stealth web browser data scraper."""
    market_data = {}
    browser = None
    context = None
    page = None
    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": random.randint(1366, 1440), "height": random.randint(768, 900)},
            locale="en-KE",
            timezone_id="Africa/Nairobi"
        )
        page = await context.new_page()
        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
        
        # Human Action Simulation: Subtle natural scrolling to clear advanced heuristics
        for _ in range(random.randint(2, 4)):
            await page.mouse.wheel(0, random.randint(200, 400))
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        elements = await page.locator("div, row, button, a").all_inner_texts()
        
        for block in elements:
            try:
                lines = [line.strip() for line in block.split('\n') if line.strip()]
                if not lines:
                    continue
                
                teams_list = [l for l in lines if len(l) > 3 and ("vs" in l.lower() or "-" in l) and not l.replace('.', '', 1).isdigit()]
                odds_list = [float(l) for l in lines if l.replace('.', '', 1).isdigit() and 1.05 < float(l) < 25.0]
                
                is_live = any("live" in l.lower() or "'" in l for l in lines)
                status_label = "Live" if is_live else "Upcoming"
                
                if teams_list and len(odds_list) >= 2:
                    match_title = teams_list
                    match_key = match_title.lower().replace(" ", "").replace("-", "vs")
                    market_data[match_key] = {
                        "title": match_title,
                        "home_odds": odds_list,
                        "away_odds": odds_list,
                        "status": status_label
                    }
            except:
                continue
                
        return market_data
    except Exception as e:
        logging.error(f"Error parsing global sports feed for {site_name}: {e}")
        return {}
    finally:
        # Ensure proper cleanup of resources
        if page:
            try:
                await page.close()
            except:
                pass
        if context:
            try:
                await context.close()
            except:
                pass
        if browser:
            try:
                await browser.close()
            except:
                pass


async def runtime_loop():
    logging.info(f"Stealth Dual-Stream SaaS Engine Online and Initialized.")
    async with async_playwright() as playwright:
        try:
            while True:
                try:
                    tasks = [
                        scrape_full_spectrum_board(playwright, BOOKMAKER_A_URL, "SportyBet"),
                        scrape_full_spectrum_board(playwright, BOOKMAKER_B_URL, "Betika")
                    ]
                    sporty_matrix, betika_matrix = await asyncio.gather(*tasks)
                    
                    if not sporty_matrix or not betika_matrix:
                        logging.info("Scanning full matrix... Markets balanced. (Waiting for adjustments)")
                        await asyncio.sleep(BASE_SCAN_DELAY + random.uniform(2.0, 5.0))
                        continue
                    
                    for match_key, sporty_item in sporty_matrix.items():
                        if match_key in betika_matrix:
                            betika_item = betika_matrix[match_key]
                            status = sporty_item["status"]
                            
                            run_arbitrage_engine(sporty_item["title"], status, sporty_item["home_odds"], betika_item["away_odds"])
                            run_arbitrage_engine(sporty_item["title"], status, betika_item["home_odds"], sporty_item["away_odds"])
                            
                except Exception as loop_error:
                    logging.error(f"Global processing loop exception handled: {loop_error}")
                    
                dynamic_jitter = BASE_SCAN_DELAY + random.uniform(1.5, 6.0)
                await asyncio.sleep(dynamic_jitter)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logging.info("Gracefully shutting down async loop...")
            raise


if __name__ == "__main__":
    import warnings
    # Suppress ResourceWarning from asyncio cleanup on Windows
    warnings.filterwarnings("ignore", category=ResourceWarning)
    
    try:
        asyncio.run(runtime_loop())
    except KeyboardInterrupt:
        logging.info("SaaS tracking modules suspended.")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
    finally:
        # Ensure all pending tasks are cleaned up on exit
        if asyncio.get_event_loop().is_running():
            asyncio.get_event_loop().stop()
