import os
import asyncio
import logging
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load parameters securely from the local .env root file
load_dotenv()

# Configure uniform system logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# Extract environment parameters
BOOKMAKER_A_URL = os.getenv("BOOKMAKER_A_URL")
BOOKMAKER_B_URL = os.getenv("BOOKMAKER_B_URL")
TOTAL_BANKROLL = float(os.getenv("TOTAL_BANKROLL", 5000.0))
SCAN_DELAY = int(os.getenv("SCAN_DELAY_SECONDS", 15))


def run_arbitrage_engine(odds_1: float, odds_2: float):
    """
    Executes standard probability matrix computations in KES.
    Filters out obvious bookmaker typos and outputs copy-paste templates.
    """
    prob_1 = 1 / odds_1
    prob_2 = 1 / odds_2
    arbitrage_ratio = prob_1 + prob_2

    if arbitrage_ratio < 1.0:
        margin_percent = (1 - arbitrage_ratio) * 100
        
        # --- PROFIT MARGIN FILTERS (PROTECTION CORE) ---
        MIN_PROFIT_MARGIN = 1.5   # Drops tiny margins that aren't worth transaction times
        MAX_PROFIT_MARGIN = 20.0  # Drops dangerous typos that bookmakers will cancel/void

        if margin_percent > MAX_PROFIT_MARGIN:
            logging.warning(f"⚠️ PALPABLE ERROR DROPPED: Silently skipped a highly suspicious {margin_percent:.2f}% gap to protect user accounts.")
            return 
            
        if margin_percent < MIN_PROFIT_MARGIN:
            return 
        # -----------------------------------------------

        # Prints out a universal, budget-inclusive copy-paste template for your channel
        print("\n" + "="*50)
        print("📋 COPY-PASTE SUBSCRIBER TELEGRAM TEMPLATE:")
        print("="*50)
        print(f"🚨 *NEW LIVE ARBITRAGE SIGNAL DETECTED* 🚨\n")
        print(f"📈 *Guaranteed Profit Yield:* `+{margin_percent:.2f}%` risk-free\n")
        print(f"👉 *SportyBet Odds (Player 1):* `{odds_1:.2f}`")
        print(f"👉 *Betika Odds (Player 2):* `{odds_2:.2f}`\n")
        print(f"🧮 *Calculate Your Exact Stakes Here:* [Paste Your Hosted Form URL Link Here]")
        print("="*50 + "\n")
    else:
        logging.info(f"Scanning Kenyan platforms... Market flat. Ratio: {arbitrage_ratio:.4f}")


async def scrape_sportybet(playwright) -> dict:
    """Launches an invisible browser to grab the top live match tennis odds from SportyBet."""
    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto(BOOKMAKER_A_URL, timeout=30000, wait_until="domcontentloaded")
        
        await page.wait_for_selector(".m-outcome-odds", timeout=15000)
        # Isolates selection strictly to the first active match container to prevent game mixing
        raw_elements = await page.locator(".m-outcome-odds").first.locator("span").all_inner_texts()
        await browser.close()
        
        clean_odds = [float(x.strip()) for x in raw_elements if x.strip().replace('.', '', 1).isdigit()]
        
        if len(clean_odds) >= 2:
            return {"Player_1": clean_odds, "Player_2": clean_odds}
        return None
    except Exception as e:
        logging.error(f"SportyBet structural extraction issue: {e}")
        return None


async def scrape_betika(playwright) -> dict:
    """Launches an invisible browser with generic text extraction failsafes for Betika."""
    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        await page.goto(BOOKMAKER_B_URL, timeout=45000, wait_until="domcontentloaded")
        
        target_selector = None
        for selector in [".odds__button", "button", ".live-match__odds"]:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                target_selector = selector
                break
            except:
                continue
                
        if not target_selector:
            await browser.close()
            logging.error("Betika layout detection timed out across selectors.")
            return None
            
        # Isolates selection strictly to the first active match container to prevent game mixing
        raw_elements = await page.locator(target_selector).first.locator("span").all_inner_texts()
        await browser.close()
        
        clean_odds = [float(x.strip()) for x in raw_elements if x.strip().replace('.', '', 1).isdigit() and float(x.strip()) > 1.0]
        
        if len(clean_odds) >= 2:
            return {"Player_1": clean_odds, "Player_2": clean_odds}
        return None
    except Exception as e:
        logging.error(f"Betika alternative tracker issue: {e}")
        return None


async def runtime_loop():
    logging.info(f"Initializing Anonymized African Tracker Engine. Base Pool: KES {TOTAL_BANKROLL}")
    async with async_playwright() as playwright:
        while True:
            try:
                # Gather live data concurrently from both sites
                tasks = [scrape_sportybet(playwright), scrape_betika(playwright)]
                extracted_payloads = await asyncio.gather(*tasks)
                
                # Cleanly unpack array components into separate variables
                odds_a = extracted_payloads[0]
                odds_b = extracted_payloads[1]
                
                # --- CRITICAL FAIL-SAFE VALIDATION CHECK ---
                if odds_a is None or odds_b is None:
                    logging.warning("⚠️ One of the target crawlers returned empty datasets. Skipping loop to maintain stability...")
                    await asyncio.sleep(SCAN_DELAY)
                    continue
                # --------------------------------------------
                
                # Safely cross-compare specific top rows without array collision crashes
                best_p1_a = odds_a["Player_1"][0] if len(odds_a["Player_1"]) > 0 else 0
                best_p2_b = odds_b["Player_2"][1] if len(odds_b["Player_2"]) > 1 else (odds_b["Player_2"][0] if len(odds_b["Player_2"]) > 0 else 0)
                
                best_p1_b = odds_b["Player_1"][0] if len(odds_b["Player_1"]) > 0 else 0
                best_p2_a = odds_a["Player_2"][1] if len(odds_a["Player_2"]) > 1 else (odds_a["Player_2"][0] if len(odds_a["Player_2"]) > 0 else 0)
                
                if best_p1_a > 0 and best_p2_b > 0:
                    run_arbitrage_engine(best_p1_a, best_p2_b)
                if best_p1_b > 0 and best_p2_a > 0:
                    run_arbitrage_engine(best_p1_b, best_p2_a)
                
            except Exception as loop_error:
                logging.error(f"Internal processing exception handled safely: {loop_error}")
                
            await asyncio.sleep(SCAN_DELAY)


if __name__ == "__main__":
    try:
        asyncio.run(runtime_loop())
    except KeyboardInterrupt:
        logging.info("Background processes cleanly suspended.")
