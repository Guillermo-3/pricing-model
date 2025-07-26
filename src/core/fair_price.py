import time

STALE_NS = 500_000_000 # check if last update > 0.5s (rid of stale data)
EPS = 1e-3

class FairPriceEngine:
    """
    Maintains the latest per venue snapshots from book classes, produces
    latency adjusted fair mid to favor recent information and bid asks
    """
    def __init__(self, half_spread_map=None):
        self.books = {}
        self.half_spread_map = half_spread_map or {
            "BTCUSDT": 0.50,
            "ETHUSDT": 0.05,
            "SOLUSDT": 0.005,
        }

    def update(self, venue: str, symbol: str, snapshot: dict):
        """ Whenever a new book.view arrives call this to update"""
        self.books[(venue, symbol)] = snapshot

    def quote(self, symbol: str):
        """logic for fair mid adjusted for latency and bid and ask, returns none if no fresh venues"""
        now = time.time_ns()
        fresh = []
        for(v, s), b in self.books.items():
            if s != symbol:
                continue
            if now - b["t_arrive_ns"] <= STALE_NS:
                fresh.append((v,b))
        if not fresh:
            return None
        
        weights, mids, venues = [], [], []
        for v, b in fresh:
            age = (now - b["t_arrive_ns"]) / 1e9
            w = 1.0 / (age + EPS)
            weights.append(w); mids.append(b["mid"]); venues.append(v)
        # favor the more recent venue
        fair_mid = sum(w*m for w, m in zip(weights, mids)) / sum(weights)
        half = self.half_spread_map.get(symbol, 0.01)
        return {
            "mid": fair_mid,
            "symbol": symbol,
            "bid": fair_mid - half,
            "ask": fair_mid + half,
            "venues_used": venues,
        }
