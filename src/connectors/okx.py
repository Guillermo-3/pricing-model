import asyncio, json, time, websockets
from src.core.book import OKXBook

WS = "wss://ws.okx.com:8443/ws/v5/public"

def inst(symbol):
    return symbol.replace("USDT","-USDT")

async def stream(queue, symbol="BTCUSDT"):
    book = OKXBook(symbol)
    sub = {"op":"subscribe", "args":[{"channel":"books5", "instId":inst(symbol)}]}

    while True:
        try:
            async with websockets.connect(WS, ping_interval=20, max_size=2**20) as ws:
                await ws.send(json.dumps(sub))
                async for raw in ws:
                    msg = json.loads(raw)
                    if "arg" in msg and msg.get("data"):
                        t_arrive = time.time_ns()
                        snap = msg["data"][0]
                        book.apply_snapshot(snap, t_arrive)
                        await queue.put(("okx", symbol, book.view()))
        except Exception:
            await asyncio.sleep(0.5); continue