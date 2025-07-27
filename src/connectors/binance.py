import asyncio, json, time, httpx, websockets
from src.core.book import BinanceBook

REST = "https://api.binance.com/api/v3/depth"
WS   = "wss://stream.binance.com:9443/ws/{sym}@depth@100ms"

async def snapshot(symbol: str = "BTCUSDT"):
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(REST, params={"symbol": symbol.upper(), "limit": 1000})
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "code" in data:
        raise RuntimeError(f"Binance API error {data.get('code')}: {data.get('msg')}")
    return data["lastUpdateId"], data["bids"], data["asks"]

async def stream(queue, symbol="BTCUSDT"):
    book = BinanceBook(symbol)
    url = WS.format(sym=symbol.lower())

    while True:
        try:
            async with websockets.connect(url, ping_interval=20, max_size=2**20) as ws:
                buf = asyncio.Queue(maxsize=20000)

                async def reader():
                    async for raw in ws:
                        msg = json.loads(raw)
                        # only depth updates have U/u
                        if "U" in msg and "u" in msg:
                            await buf.put((time.time_ns(), msg))

                reader_task = asyncio.create_task(reader())

                # Grab the earliest buffered event
                first_t, first_msg = await buf.get()
                U0, u0 = first_msg["U"], first_msg["u"]

                # Snapshot; if it's behind first.U, resnapshot until it's not
                while True:
                    last_id, bids, asks = await snapshot(symbol)
                    if last_id < U0:
                        # snapshot too old vs earliest buffered event; take another
                        first_t, first_msg = await buf.get()
                        U0, u0 = first_msg["U"], first_msg["u"]
                        continue
                    break

                # Load the snapshot
                book.load_snapshot(last_id, bids, asks)

                # Drop buffered events with u <= last_id until we hit U <= last_id <= u
                # Process that one, then continue live.
                apply_queue = [(first_t, first_msg)]
                while apply_queue:
                    t_arrive, msg = apply_queue.pop(0)
                    U, u = msg["U"], msg["u"]
                    if u <= last_id:
                        continue
                    if U <= last_id <= u:
                        book.apply_diff(msg, t_arrive)
                        await queue.put(("binance", symbol, book.view()))
                        last_id = u  # local book update id
                        break
                    # If we’re ahead of the book, our snapshot got invalid; restart outer loop
                    # (rare but per spec – restart if U > last_id).
                    if U > last_id:
                        raise RuntimeError("Binance book desync during sync gate; restarting")

                # Drain remaining buffered, then steady-state
                while True:
                    t_arrive, msg = await buf.get()
                    book.apply_diff(msg, t_arrive)
                    await queue.put(("binance", symbol, book.view()))
        except Exception:
            await asyncio.sleep(0.5)
            continue
