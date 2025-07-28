# src/connectors/binance.py
import asyncio, json, time, httpx, websockets
from collections import deque
from src.core.book import BinanceBook

REST = "https://api.binance.us/api/v3/depth"
WS   = "wss://stream.binance.us:9443/ws/{sym}@depth@100ms"
STALE_RETRY = 0.05

async def get_snapshot(symbol: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(REST, params={"symbol": symbol.upper(), "limit": 1000})
        r.raise_for_status()
        j = r.json()
        if isinstance(j, dict) and "code" in j:
            raise RuntimeError(f"Binance API error {j.get('code')}: {j.get('msg')}")
        return j["lastUpdateId"], j["bids"], j["asks"]

async def stream(queue: asyncio.Queue, symbol: str = "BTCUSDT"):
    url  = WS.format(sym=symbol.lower())
    book = BinanceBook(symbol)

    while True:
        pump_task = None
        try:
            buf = deque()  
            async with websockets.connect(url, ping_interval=20, max_size=2**22) as ws:
                async def pump():
                    async for raw in ws:
                        t = time.time_ns()
                        msg = json.loads(raw)
                        ev  = msg.get("data", msg) 
                        if ev.get("e") == "depthUpdate" and "U" in ev and "u" in ev:
                            buf.append((t, ev))
                pump_task = asyncio.create_task(pump())

                while not buf:
                    await asyncio.sleep(0.01)
                first_U = buf[0][1]["U"]

                while True:
                    last_id, bids, asks = await get_snapshot(symbol)
                    if last_id >= first_U:
                        break
                    await asyncio.sleep(STALE_RETRY)

                book.load_snapshot(last_id, bids, asks)

                while buf and buf[0][1]["u"] <= last_id:
                    buf.popleft()

                while not buf or not (buf[0][1]["U"] <= last_id + 1 <= buf[0][1]["u"]):
                    await asyncio.sleep(0.01)
                    if len(buf) > 5000:
                        raise RuntimeError("Gate mismatch; restarting sync")

                while buf:
                    t_arrive, ev = buf.popleft()
                    book.apply_diff(ev, t_arrive)
                    last_id = book.last_update_id
                    await queue.put(("binance", symbol, book.view()))

                while True:
                    while buf:
                        t_arrive, ev = buf.popleft()
                        book.apply_diff(ev, t_arrive)
                        last_id = book.last_update_id
                        await queue.put(("binance", symbol, book.view()))
                    await asyncio.sleep(0.001)

        except Exception:
            if pump_task:
                with contextlib.suppress(Exception):
                    pump_task.cancel()
            await asyncio.sleep(0.5)
            continue
