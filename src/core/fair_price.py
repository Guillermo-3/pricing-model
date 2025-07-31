import time
from src.core.book import _topk_imbalance
from typing import Any
from src.core.kalman import Kalman1D
from src.core.ewma import EWMA
from src.core.inventory import InventoryManager
from src.core.init_config import MMConfig
import math
STALE_NS = 500_000_000 # check if last update > 0.5s (rid of stale data)
EPS = 1e-3
 
class FairPriceEngine:
    """
    Maintains the latest per venue snapshots from book classes, produces
    latency adjusted fair mid to favor recent information and bid asks
    """
    def __init__(self, config: MMConfig):
        self.config = config
        self.books: dict[str, dict] = {}
        self.kf: dict[str, Kalman1D]= {}
        self.inv = InventoryManager()
        self.vol: dict[str, EWMA] = {}
        self.last_fair_values: dict[str, float] = {}
        self._sim_ts_ns = None
    def create(self, symbol: str):
        if symbol not in self.kf:
            self.kf[symbol] = Kalman1D(q_process=self.config.q_process)
            self.vol[symbol] = EWMA(halflife_s= self.config.vol_halflife_s)
            print(f"Initialized filters for {symbol}")
    
    def update(self, venue: str, symbol: str, snapshot: dict):
        """ Whenever a new book.view arrives call this to update"""
        self.create(symbol)
        self.books[venue] = snapshot
        self._sim_ts_ns = snapshot["t_arrive_ns"]


    def quote(self, symbol: str):
        """logic for fair mid adjusted for latency and bid and ask, returns none if no fresh venues"""
        now = getattr(self, "_sim_ts_ns", time.time_ns())
        
        #something for config, idk and ifx the bottom
        fresh = [(v, b) for v, b in self.books.items() if b["symbol"] == symbol and (now - b["t_arrive_ns"]) <= STALE_NS]
        
        if not fresh:
            return None
        
        meas = []
        
        weights, mids, imbs, venues = [], [], [], []
        for v, b in fresh:
            age = (now - b["t_arrive_ns"]) / 1e9
            w = 1.0 / (age + EPS)
            spread = b["ask"] - b["bid"]
            R = (
                self.config.r0 +
                self.config.r1 * w +
                self.config.r2 * spread**2
            )
            meas.append((b["mid"], R))
            weights.append(w); mids.append(b["mid"]); venues.append(v)
            imbs.append(b.get("imbalance5", b.get("imbalance5", 0.0)))
        # favor the more recent venue
        fair, P = self.kf[symbol].step(meas)
        if fair is None:
            return None

        sigma = sigma = 0.0
        prev  = self.last_fair_values.get(symbol)
        
        if prev and prev > 0 and fair > 0:
            r2   = math.log(fair / prev) ** 2
            sig2 = self.vol[symbol].update(r2 * self.config.ann_factor)
            sigma = math.sqrt(sig2)
        self.last_fair_values[symbol] = fair

        avg_imb = sum(imbs) / len(imbs)

        h_unc = self.config.a_unc * math.sqrt(P + sigma**2 * self.config.h_secs)
        h_imp = self.config.b_impact * abs(avg_imb)

        half  = min(
            max(h_unc + h_imp, self.config.min_half),
            self.config.max_half
        )
        inv      = self.inv.get(symbol)
        mid_star = fair - self.config.kappa * inv

        return {
            "t_ns": now,
            "mid": fair,
            "symbol": symbol,
            "kalman_var": P,
            "bid": mid_star - half,
            "ask": mid_star + half,
            "inv": inv,
            "imbalance": avg_imb,
            "sigma": sigma,
            "venues_used": venues,
        }
