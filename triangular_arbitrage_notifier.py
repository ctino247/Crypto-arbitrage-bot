
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
INVESTMENT = 100  # Simulated trade size in USDT
FEE_RATE = 0.003  # 0.3% total fees for 3 trades

# === Global storage ===
PRICES = {}
TRIANGLES = []
OPEN_OPPORTUNITIES = {}

# === Send Telegram Message ===
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

# === Build Triangle Paths ===
def build_triangles():
    exchange = ccxt.binance()
    markets = exchange.load_markets()
    symbols = list(markets.keys())

    triangles = []
    pairs = [s.replace("/", "") for s in symbols if s.count("/") == 1]

    for a in pairs:
        for b in pairs:
            for c in pairs:
                if a != b and b != c and c != a:
                    try:
                        base1, quote1 = a[:-3], a[-3:]
                        base2, quote2 = b[:-3], b[-3:]
                        base3, quote3 = c[:-3], c[-3:]

                        if base1 == quote3 and quote1 == base2 and quote2 == base3:
                            triangles.append((a.lower(), b.lower(), c.lower()))
                    except:
                        continue
    return list(set(triangles))

# === Arbitrage Logic ===
def simulate_arbitrage(path):
    a, b, c = path
    try:
        if all(x in PRICES for x in [a, b, c]):
            amt_a = INVESTMENT / PRICES[a]['ask']
            amt_b = amt_a / PRICES[b]['ask']
            final = amt_b * PRICES[c]['bid']

            final_after_fee = final * (1 - FEE_RATE)
            profit = final_after_fee - INVESTMENT

            return profit
    except:
        pass
    return None

# === WebSocket Handler ===
async def stream_prices(triangle_pairs):
    stream_url = "wss://stream.binance.com:9443/stream?streams="
    stream_url += "/".join([f"{pair}@bookTicker" for pair in triangle_pairs])

    async with websockets.connect(stream_url) as ws:
        while True:
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
                            duration = 0
                            send_telegram_message(
                                f"🔁 *Arbitrage Opportunity Found!*

"
                                f"🧩 *Path:* `{triangle[0].upper()} → {triangle[1].upper()} → {triangle[2].upper()}`
"
                                f"💵 *Profit on $100:* `${profit:.2f}`
"
                                f"⏳ *Open:* Just now"
                            )
                    else:
                        if key in OPEN_OPPORTUNITIES:
                            start_time = OPEN_OPPORTUNITIES.pop(key)
                            duration = time.time() - start_time
                            print(f"Opportunity closed: {key} lasted {duration:.2f}s")
    return

# === Main Runner ===
async def main():
    global TRIANGLES
    print("Building triangle paths...")
    TRIANGLES = build_triangles()
    unique_pairs = set()
    for tri in TRIANGLES:
        unique_pairs.update(tri)
    print(f"Tracking {len(TRIANGLES)} triangles using {len(unique_pairs)} pairs...")

    await stream_prices(list(unique_pairs))

# === Start Bot ===
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user.")
