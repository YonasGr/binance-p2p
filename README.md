"""
Telegram bot (Python) — Binance P2P + market data helper

Features implemented:
- /start, /help
- /p2p_usdt_top [buy|sell] : show top P2P offers for USDT <-> ETB (default: BUY offers)
- /p2p_usdt_amount <amount><unit> [buy|sell] : show top 10 offers for specific amount.
   Examples: "/p2p_usdt_amount 5000ETB" or "/p2p_usdt_amount 50USDT sell"
- /convert <from_symbol> <to_symbol> [amount]
   Examples: "/convert BTC USDT 0.01" or "/convert TON SOL 10"
- /coininfo <symbol> : basic market info (price, market cap, 24h change)

Notes:
- P2P data is fetched from Binance P2P endpoint used by their web UI (no API key required).
- Public market price data is fetched from Binance public REST endpoints where possible; CoinGecko is used as fallback for metadata.

Dependencies:
- python-telegram-bot (v20+)
- aiohttp
- python-dotenv (optional)

Run:
1. pip install python-telegram-bot aiohttp python-dotenv
2. export TELEGRAM_TOKEN="<your token>"  (or create a .env file)
3. python telegram_binance_p2p_bot.py

"""
