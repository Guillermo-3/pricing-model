import asyncio
import json
from src.connectors import okx, binance
from src.core.fair_price import FairPriceEngine
from src.core.recorder import Recorder

async def consumer(q:asyncio.Queue, engine:FairPriceEngine, recorder: Recorder):
    while True:
        venue, symbol, snap = await q.get()
        recorder.log("market_data", snap)
        engine.update(venue, symbol, snap)
        quote = engine.quote(symbol)
        if quote:
            recorder.log("quotes", quote)
            print(json.dumps(quote, indent=None))

async def main():
    q = asyncio.Queue()
    recorder = Recorder()
    eng = FairPriceEngine(a=1.0, b=0.5, kappa=1e-6)
    tasks = [consumer(q, eng, recorder)]

    binance_okx_symbol = "BTCUSDT"

    tasks.append(okx.stream(q, binance_okx_symbol))
    tasks.append(binance.stream(q, binance_okx_symbol))
    try:
        await asyncio.gather(*tasks)
    finally:
        recorder.close()

if __name__ == "__main__":
    asyncio.run(main())