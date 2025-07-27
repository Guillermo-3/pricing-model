import asyncio, json
from src.connectors import binance, okx
from src.core.fair_price import FairPriceEngine

SYMBOLS = ["BTCUSDT"]

async def consumer(q, engine):
    while True:
        venue, symbol, snap = await q.get()
        engine.update(venue, symbol, snap)
        quote = engine.quote(symbol)
        if quote:
            print(json.dumps(quote))  # reminder: later append to parquet

async def main():
    q = asyncio.Queue()
    eng = FairPriceEngine(a=1.0, b=0.5, kappa=1e-6)
    tasks = [consumer(q, eng)]
    for s in SYMBOLS:
        tasks += [binance.stream(q, s), okx.stream(q, s)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
