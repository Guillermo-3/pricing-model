import json, pathlib, math, pandas as pd
from src.core.reader import load_jsonl
from src.core.fair_price import FairPriceEngine, STALE_NS
from src.core.init_config import MMConfig
import random

class BackTester:
    def __init__(self, data_path: str, symbol: str, cfg: MMConfig, fill_mode: str ="deterministic"):
        self.df     = load_jsonl(data_path)
        self.df     = self.df[self.df.symbol == symbol].sort_values("t_arrive_ns")
        self.eng    = FairPriceEngine(cfg)
        self.symbol = symbol
        self.cash    = 0.0
        self.inv    = 0.0
        self.last_mid = None
        self.last_q = None
        self.next_q_time = 0
        self.trades = 0

        self.fill_mode = fill_mode
        self.lmbda0 = 2.0
        self.alpha = 4.0

    def deterministic_fill(self, row):
        if row.mid >= self.last_q["ask"]:               # we sell 1
            self.cash += self.last_q["ask"]
            self.inv  -= 1
            self.trades += 1
        elif row.mid <= self.last_q["bid"]:             # we buy 1
            self.cash -= self.last_q["bid"]
            self.inv  += 1
            self.trades += 1
    def poisson_fill(self, row, dt: float):
        best_bid = row.bid
        best_ask = row.ask

        dist_bid_ticks = max(0.0, (best_bid - self.last_q["bid"]) / 0.01)  # assume 0.01 tick
        pbuy = self.poisson_prob(dist_bid_ticks, dt)
        if random.random() < pbuy:                    # got hit, we buy
            self.cash -= self.last_q["bid"]
            self.inv  += 1
            self.trades += 1

        dist_ask_ticks = max(0.0, (self.last_q["ask"] - best_ask) / 0.01)
        psell = self.poisson_prob(dist_ask_ticks, dt)
        if random.random() < psell:                   # got lifted, we sell
            self.cash += self.last_q["ask"]
            self.inv  -= 1
            self.trades += 1

    def poisson_prob(self, dist_ticks: float, dt: float) -> float:
        rate = self.lmbda0 * math.exp(-self.alpha * dist_ticks)
        return 1.0 - math.exp(-rate * dt)
    
    def run(self):
        prev_ts = None
        for _, row in self.df.iterrows():
            ts = int(row.t_arrive_ns)
            mid = float(row.mid)
            self.last_mid = mid
            snap = {
                "symbol": row.symbol,
                "mid"   : mid,
                "bid"   : row.bid,
                "ask"   : row.ask,
                "bids5" : [], "asks5": [],
                "t_arrive_ns": ts,
            }
            self.eng.update(row.venue, row.symbol, snap)

            if ts >= self.next_q_time:
                self.last_q = self.eng.quote(self.symbol)
                self.next_q_time = ts + 100_000_000  # 100 ms

                

            if not self.last_q:
                prev_ts = ts
                continue

            if self.fill_mode == "deterministic":
                self.deterministic_fill(row)
            else:
                dt = 0 if prev_ts is None else (ts - prev_ts) / 1e9
                self.poisson_fill(row,dt)
            prev_ts = ts
        m2m_pnl = self.cash + self.inv * self.last_mid
        return {"pnl": m2m_pnl, "cash": self.cash, "inv": self.inv, "trades": self.trades}
        
        