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


async def transmit_telegram_broadcast(target_chat_id: str, message: str):
    """Dispatches payload to specific channel nodes asynchronously."""
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


async def run_arbitrage_engine(match_title: str, status: str, odds_1: float, odds_2: float):
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
            await transmit_telegram_broadcast(FREE_CHANNEL_ID, free_msg)
            
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
        page.set_default_timeout(30000)
        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
        
        # Human Action Simulation: Subtle natural scrolling to clear advanced heuristics
        for _ in range(random.randint(1, 3)):
            await page.mouse.wheel(0, random.randint(200, 400))
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
        # Execute fast browser-side JS parsing in V8 engine
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
    logging.info(f"Stealth Dual-Stream SaaS Engine Online and Initialized (Warm Browser).")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
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
                            # Fuzzy matching fallback
                            for betika_key, item in betika_matrix.items():
                                if matches_are_same(sporty_item["title"], item["title"]):
                                    betika_item = item
                                    break
                                    
                        if betika_item:
                            status = sporty_item["status"]
                            # Check SportyBet home win vs Betika away win
                            await run_arbitrage_engine(sporty_item["title"], status, sporty_item["home_odds"], betika_item["away_odds"])
                            # Check Betika home win vs SportyBet away win
                            await run_arbitrage_engine(sporty_item["title"], status, betika_item["home_odds"], sporty_item["away_odds"])
                            
                except Exception as loop_error:
                    logging.error(f"Global processing loop exception handled: {loop_error}")
                    
                dynamic_jitter = BASE_SCAN_DELAY + random.uniform(1.5, 6.0)
                await asyncio.sleep(dynamic_jitter)
        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(runtime_loop())
    except KeyboardInterrupt:
        logging.info("SaaS tracking modules suspended.")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
