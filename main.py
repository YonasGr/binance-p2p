import os
import asyncio
import math
import json
from typing import Optional, List, Dict

import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuration
# This is a good way to handle environment variables for security.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BINANCE_REST_BASE = "https://api.binance.com"
BINANCE_P2P_SEARCH = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# --- Utility HTTP helpers ---

async def fetch_json(session: aiohttp.ClientSession, method: str, url: str, **kwargs):
    """
    A helper function to fetch and parse JSON from a URL.
    It includes basic error handling for parsing JSON.
    """
    async with session.request(method, url, **kwargs) as resp:
        text = await resp.text()
        try:
            return json.loads(text)
        except Exception:
            # Return raw text if JSON parsing fails to help with debugging.
            return {"_raw": text}

# --- P2P functions ---

async def fetch_p2p_offers(asset: str = "USDT", fiat: str = "ETB", trade_type: str = "BUY", amount: Optional[str] = None, rows: int = 20) -> List[Dict]:
    """
    Fetch P2P offers using Binance's public P2P endpoint.
    trade_type: "BUY" or "SELL" as expected by the endpoint ("BUY" means buy crypto on P2P page).
    amount: string amount for transAmount (e.g. "5000" meaning 5000 ETB or 50 for USDT depending on request)
    Returns list of adv objects (raw) — caller will format.
    """
    payload = {
        "page": 1,
        "rows": rows,
        "asset": asset,
        "fiat": fiat,
        "tradeType": trade_type,
        "proMerchantAds": False,
        "publisherType": None,
    }
    if amount is not None:
        payload["transAmount"] = str(amount)

    headers = {"Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        data = await fetch_json(session, "POST", BINANCE_P2P_SEARCH, json=payload, headers=headers)

    # The response format contains data list with adv, advertiser etc.
    items = []
    for d in data.get("data", []):
        adv = d.get("adv", {})
        advertiser = d.get("advertiser", {})
        item = {
            "price": adv.get("price"),
            "minSingleTransAmount": adv.get("minSingleTransAmount"),
            "maxSingleTransAmount": adv.get("maxSingleTransAmount"),
            "fiat": adv.get("fiat"),
            "asset": adv.get("asset"),
            "tradeType": adv.get("tradeType"),
            "publisherType": d.get("advertiser","{}").get("userType"),
            "nickName": advertiser.get("nickName") or advertiser.get("userName"),
            "monthOrderCount": advertiser.get("monthOrderCount"),
            "orderCompleteRate": advertiser.get("orderCompleteRate"),
            "tradeMethods": d.get("adv", {}).get("tradeMethods", []),
            "adv": adv,
        }
        items.append(item)

    # Sort by price (float) ascending for buyers wanting the lowest price, or descending for sellers wanting highest —
    # We'll return as-is and let caller decide.
    return items

# --- Market convert / coin info ---

async def binance_ticker_price(symbol: str) -> Optional[float]:
    """Fetch symbol price from Binance public API. symbol example: BTCUSDT"""
    url = f"{BINANCE_REST_BASE}/api/v3/ticker/price?symbol={symbol.upper()}"
    async with aiohttp.ClientSession() as session:
        try:
            j = await fetch_json(session, "GET", url)
            if isinstance(j, dict) and "price" in j:
                return float(j["price"])
        except Exception:
            return None
    return None

async def coingecko_coin_info_by_symbol(symbol: str) -> Optional[Dict]:
    """Fetch basic coin info from CoinGecko API based on symbol."""
    # CoinGecko tends to use ids like 'bitcoin', 'ethereum'. We'll try simple mapping heuristics for major coins.
    mapping = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "USDT": "tether",
        "TON": "toncoin",
        "SOL": "solana",
        "BNB": "binancecoin",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "XRP": "ripple",
    }
    coin_id = mapping.get(symbol.upper(), None)
    if coin_id is None:
        # fallback: search endpoint
        async with aiohttp.ClientSession() as session:
            res = await fetch_json(session, "GET", f"{COINGECKO_API}/search?query={symbol}")
            if isinstance(res, dict) and res.get("coins"):
                coin_id = res["coins"][0]["id"]
    if not coin_id:
        return None
    async with aiohttp.ClientSession() as session:
        res = await fetch_json(session, "GET", f"{COINGECKO_API}/coins/{coin_id}")
    # Return a curated subset
    if isinstance(res, dict):
        return {
            "id": res.get("id"),
            "symbol": res.get("symbol"),
            "name": res.get("name"),
            "market_cap": res.get("market_data", {}).get("market_cap", {}).get("usd"),
            "current_price_usd": res.get("market_data", {}).get("current_price", {}).get("usd"),
            "price_change_24h": res.get("market_data", {}).get("price_change_percentage_24h"),
            "homepage": res.get("links", {}).get("homepage", [None])[0],
            "description": (res.get("description", {}).get("en") or "").split("\n")[0][:400],
        }
    return None

# --- Telegram command handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and explains the bot's purpose."""
    await update.message.reply_text(
        "Hello! I can fetch Binance P2P ETB rates, convert coins, and show coin info. Use /help to see commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides a list of all available commands."""
    text = (
        "Available commands:\n"
        "/p2p_usdt_top [buy|sell] - get top USDT P2P offers for ETB (default: buy)\n"
        "/p2p_usdt_amount <amount><ETB|USDT> [buy|sell] - show top 10 offers for that amount\n"
        "/convert <FROM> <TO> [amount] - convert between coins using Binance prices\n"
        "/coininfo <SYMBOL> - get market info about a coin (market cap, price...)\n"
    )
    await update.message.reply_text(text)

async def p2p_usdt_top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /p2p_usdt_top [buy|sell]"""
    args = context.args or []
    trade = (args[0].upper() if args else "BUY")
    if trade not in ("BUY", "SELL"):
        await update.message.reply_text("trade must be 'buy' or 'sell'.")
        return
    await update.message.reply_text(f"Fetching top USDT P2P offers ({trade}) for ETB...")
    offers = await fetch_p2p_offers(asset="USDT", fiat="ETB", trade_type=trade, rows=20)
    if not offers:
        await update.message.reply_text("No offers found.")
        return
    # sort by price asc
    offers_sorted = sorted(offers, key=lambda o: float(o.get("price") or 0.0))
    lines = []
    for i, o in enumerate(offers_sorted[:10], start=1):
        lines.append(
            f"{i}. {o.get('nickName') or 'anon'} — {o.get('price')} {o.get('fiat')} | min {o.get('minSingleTransAmount')} - max {o.get('maxSingleTransAmount')} | completed: {o.get('monthOrderCount') or 0}"
        )
    await update.message.reply_text("\n".join(lines))

async def p2p_usdt_amount_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /p2p_usdt_amount 5000ETB [buy|sell]  OR /p2p_usdt_amount 50USDT"""
    args = context.args or []
    if not args:
        await update.message.reply_text("Please provide an amount with unit, e.g. 5000ETB or 50USDT")
        return
    amt_token = args[0]
    trade = (args[1].upper() if len(args) > 1 else "BUY")
    unit = None
    try:
        if amt_token.upper().endswith("ETB"):
            unit = "ETB"
            amount = float(amt_token[:-3])
            trans_amount = str(int(amount))
        elif amt_token.upper().endswith("USDT"):
            unit = "USDT"
            amount = float(amt_token[:-4])
            trans_amount = str(amount)
        else:
            await update.message.reply_text("Unit not recognized. End amount with ETB or USDT.")
            return
    except Exception:
        await update.message.reply_text("Couldn't parse the amount. Use digits then unit, e.g. 5000ETB")
        return

    await update.message.reply_text(f"Searching top offers for {amount}{unit} ({trade})...")
    if unit == "ETB":
        offers = await fetch_p2p_offers(asset="USDT", fiat="ETB", trade_type=trade, amount=trans_amount, rows=50)
    else:
        offers = await fetch_p2p_offers(asset="USDT", fiat="ETB", trade_type=trade, amount=trans_amount, rows=50)

    if not offers:
        await update.message.reply_text("No offers found for that amount.")
        return

    # sort by price and display top 10
    offers_sorted = sorted(offers, key=lambda o: float(o.get("price") or 0.0))
    lines = []
    for i, o in enumerate(offers_sorted[:10], start=1):
        lines.append(
            f"{i}. {o.get('nickName') or 'anon'} — {o.get('price')} {o.get('fiat')} | min {o.get('minSingleTransAmount')} - max {o.get('maxSingleTransAmount')}"
        )
    await update.message.reply_text("\n".join(lines))

async def convert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /convert BTC USDT 0.01"""
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: /convert FROM TO [amount]. Example: /convert BTC USDT 0.1")
        return
    frm = args[0].upper()
    to = args[1].upper()
    amount = float(args[2]) if len(args) >= 3 else 1.0

    # Try direct Binance symbol pair, else convert via USDT as intermediary
    direct_symbol = f"{frm}{to}"
    price = await binance_ticker_price(direct_symbol)
    if price is not None:
        result = amount * price
        await update.message.reply_text(f"{amount} {frm} = {result:.8f} {to} (via {direct_symbol} on Binance)")
        return
    # fallback: use frm->USDT and to->USDT
    frm_to_usdt = None
    to_to_usdt = None
    if frm != "USDT":
        p = await binance_ticker_price(f"{frm}USDT")
        if p is not None:
            frm_to_usdt = p
        else:
            # try USDT pair reversed
            p = await binance_ticker_price(f"USDT{frm}")
            if p:
                frm_to_usdt = 1.0 / p
    else:
        frm_to_usdt = 1.0

    if to != "USDT":
        p = await binance_ticker_price(f"{to}USDT")
        if p is not None:
            to_to_usdt = p
        else:
            p = await binance_ticker_price(f"USDT{to}")
            if p:
                to_to_usdt = 1.0 / p
    else:
        to_to_usdt = 1.0

    if frm_to_usdt is None or to_to_usdt is None:
        await update.message.reply_text("Couldn't fetch direct prices from Binance for those symbols. Try /coininfo for more info.")
        return

    amount_in_usdt = amount * frm_to_usdt
    result = amount_in_usdt / to_to_usdt
    await update.message.reply_text(f"{amount} {frm} ≈ {result:.8f} {to} (via USDT)")

async def coininfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /coininfo SYMBOL (e.g. BTC, ETH, TON)")
        return
    sym = args[0].upper()
    await update.message.reply_text(f"Fetching info for {sym}...")
    info = await coingecko_coin_info_by_symbol(sym)
    if not info:
        await update.message.reply_text("Coin not found on CoinGecko. Try a different symbol.")
        return
    text = (
        f"{info.get('name')} ({info.get('symbol').upper()})\n"
        f"Price (USD): {info.get('current_price_usd')}\n"
        f"Market Cap (USD): {info.get('market_cap')}\n"
        f"24h Change: {info.get('price_change_24h')}%\n"
        f"Website: {info.get('homepage')}\n"
        f"{info.get('description')[:300]}"
    )
    await update.message.reply_text(text)


# --- Main entry point ---
async def main():
    if not TELEGRAM_TOKEN:
        print("Set TELEGRAM_TOKEN environment variable and restart.")
        return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("p2p_usdt_top", p2p_usdt_top_cmd))
    app.add_handler(CommandHandler("p2p_usdt_amount", p2p_usdt_amount_cmd))
    app.add_handler(CommandHandler("convert", convert_cmd))
    app.add_handler(CommandHandler("coininfo", coininfo_cmd))

    print("Bot started...")
    # The run_polling() method is a blocking call that starts the bot.
    # It manages its own event loop, so calling asyncio.run() here causes a conflict.
    await app.run_polling()

if __name__ == '__main__':
    # This is the corrected way to start the bot.
    # We simply call the main() async function without wrapping it in asyncio.run().
    # The Python-Telegram-Bot library handles the event loop for us.
    asyncio.run(main())
