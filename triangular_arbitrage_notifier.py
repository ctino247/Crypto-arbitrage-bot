import asyncio
import websockets
import ccxt
import json
import time
import requests

# === Telegram Config ===
TELEGRAM_TOKEN = "8105265421:AAGzjXqjJrzibjxC6fdBWIOq5N-vMOSfBwU"
CHAT_ID = "7528994947"

# === Arbitrage Parameters ===
INVESTMENT = 100
FEE_RATE = 0.003  # 0.3% total fees

PRICES = {}
TRIANGLES = []
OPEN_OPPORTUNITIES = {}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def build_triangles():
    exchange = ccxt.binance()
    markets = exchange.load_markets()
    symbols = [s.replace("/", "") for s in markets.keys() if "/" in s]
    quote_assets = {"USDT", "BTC", "ETH", "BNB"}

    triangles = []
    for base in quote_assets:
        pairs1 = [s for s in symbols if s.endswith(base)]
        for a in pairs1:
            quote1 = base
            mid = a[:-len(quote1)]
            pairs2 = [s for s in symbols if s.startswith(mid) and s != a]
            for b in pairs2:
                quote2 = b[len(mid):]
                c = quote2 + quote1
                if c in symbols:
                    triangles.append((a.lower(), b.lower(), c.lower()))
    return list(set(triangles))

def simulate_arbitrage(path):
    a, b, c = path
    try:
        if all(x in PRICES for x in [a, b, c]):
            amt_a = INVESTMENT / PRICES[a]['ask']
            amt_b = amt_a / PRICES[b]['ask']
            final = amt_b * PRICES[c]['bid']
            final_after_fee = final * (1 - FEE_RATE)
            return final_after_fee - INVESTMENT
    except Exception as e:
        print(f"Simulation error: {e}")
    return None

async def stream_prices(pairs):
    if not pairs:
        print("No pairs to track. Exiting...")
        return

    streams = "/".join([f"{pair}@bookTicker" for pair in pairs])
    stream_url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    try:
        async with websockets.connect(stream_url) as ws:
            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)['data']
                    symbol = data['s'].lower()
                    PRICES[symbol] = {
                        'bid': float(data['b']),
                        'ask': float(data['a']),
                    }

                    for triangle in TRIANGLES:
                        if all(p in PRICES for p in triangle):
                            profit = simulate_arbitrage(triangle)
                            key = "_".join(triangle)
                            if profit and profit > 0:
                                if key not in OPEN_OPPORTUNITIES:
                                    OPEN_OPPORTUNITIES[key] = time.time()
                                    send_telegram_message(
                                        "🔁 *Arbitrage Opportunity Found!*\\n\\n"
                                        f"🧩 *Path:* `{triangle[0].upper()} → {triangle[1].upper()} → {triangle[2].upper()}`\\n"
                                        f"💵 *Profit on $100:* `${profit:.2f}`\\n"
                                        "⏳ *Open:* Just now"
                                    )
                            else:
                                if key in OPEN_OPPORTUNITIES:
                                    start_time = OPEN_OPPORTUNITIES.pop(key)
                                    duration = time.time() - start_time
                                    print(f"Opportunity closed: {key} lasted {duration:.2f}s")
                except Exception as e:
                    print(f"WebSocket error: {e}")
    except Exception as e:
        print(f"Connection failed: {e}")

async def main():
    global TRIANGLES
    print("Building triangle paths...")
    TRIANGLES = build_triangles()
    print(f"Found {len(TRIANGLES)} triangles.")

    unique_pairs = set()
    for tri in TRIANGLES:
        unique_pairs.update(tri)

    await stream_prices(list(unique_pairs))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
