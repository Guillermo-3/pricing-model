import asyncio, json, time, websockets
from src.core.book import BinanceBook

# Using a simpler, stateless stream from Binance
WS_URL_TEMPLATE = "wss://stream.binance.us:9443/ws/{}@depth5@100ms"

async def stream(queue, symbol="BTCUSDT"):
    book = BinanceBook(symbol)
    url = WS_URL_TEMPLATE.format(symbol.lower())
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                async for raw in ws:
                    t_arrive = time.time_ns()
                    msg = json.loads(raw)
                    if "bids" in msg:
                        book.apply_snapshot(msg, t_arrive)
                        await queue.put(("binance", symbol, book.view()))
        except Exception as e:
            print(f"Binance connector error: {e}. Retrying...")
            await asyncio.sleep(1)