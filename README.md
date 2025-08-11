🤖 Binance P2P & Market Data Telegram Bot

A powerful and easy-to-use Telegram bot built with Python for quick access to Binance P2P offers and real-time market data. This bot helps you monitor P2P rates for USDT/ETB and get instant crypto conversions and coin details without needing to open the Binance app.

✨ Features

The bot provides a set of simple commands to get the information you need, fast.

/start & /help: Get a welcome message and a list of available commands.

/p2p_usdt_top [buy|sell]: Shows the top P2P offers for the USDT <-> ETB pair. By default, it displays BUY offers.

/p2p_usdt_amount <amount><unit> [buy|sell]: Lists the top 10 P2P offers for a specific amount.

Examples: /p2p_usdt_amount 5000ETB or /p2p_usdt_amount 50USDT sell

/convert <from_symbol> <to_symbol> [amount]: Converts one cryptocurrency to another.

Examples: /convert BTC USDT 0.01 or /convert TON SOL 10

/coininfo <symbol>: Displays basic market information for a given cryptocurrency, including its current price, market cap, and 24-hour change.

🛠️ Dependencies

This project relies on the following Python packages:

python-telegram-bot (v20+)

aiohttp

python-dotenv (optional, for managing environment variables)

🚀 Setup & Usage

Follow these simple steps to get your bot up and running.

Install the dependencies:

pip install python-telegram-bot aiohttp python-dotenv


Set up your Telegram Bot Token:
Get your token from BotFather and set it as an environment variable.

export TELEGRAM_TOKEN="<your_token>"


Alternatively, you can create a .env file in the project's root directory with the following content:

TELEGRAM_TOKEN="<your_token>"


Run the bot:

python telegram_binance_p2p_bot.py
