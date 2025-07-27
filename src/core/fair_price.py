import time, math

STALE_NS = 500_000_000 # check if last update > 0.5s (rid of stale data)
EPS = 1e-3

class VolTracker:
    def __init__(self, lam=0.97):
        self.lam = lam
        self.last_sec = None
        self.last_mid = None
        self.var = 0.0
    
    def update(self, mid, t_ns):
        sec = t_ns // 1_000_000_000
        if self.last_sec is None:
            self.last_sec, self.last_mid = sec,mid
            return math.sqrt(self.var)
        if sec > self.last_sec:
            r = mid - self.last_mid
            self.var = self.lam * self.var + (1 - self.lam) * (r*r)
            self.last_sec, self.last_mid = sec,mid
        return math.sqrt(self.var)
    
class FairPriceEngine:
    """
    Maintains the latest per venue snapshots from book classes, produces
    latency adjusted fair mid to favor recent information and bid asks
    """
    def __init__(self, half_spread_map=None, a=1.0, b=0.5, kappa=1e-6):
        self.books = {}
        self.vol = {}
        self.inv = {}
        self.half_spread_map = half_spread_map or { "BTCUSDT": 0.50, "ETHUSDT": 0.05, "SOLUSDT": 0.005}
        self.a, self.b, self.kappa = a,b, kappa

    def update(self, venue: str, symbol: str, snapshot: dict):
        """ Whenever a new book.view arrives call this to update"""
        self.books[(venue, symbol)] = snapshot
        if symbol not in self.vol: self.vol[symbol] = VolTracker()
        self.vol[symbol].update(snapshot["mid"], snapshot["t_arrive_ns"])


    def quote(self, symbol: str):
        """logic for fair mid adjusted for latency and bid and ask, returns none if no fresh venues"""
        now = time.time_ns()
        fresh = [(v, s, b) for (v, s), b in self.books.items() if s == symbol and (now - b["t_arrive_ns"]) <= STALE_NS]

        if not fresh:
            return None
        
        weights, mids, imbs, venues = [], [], [], []
        for v, _, b in fresh:
            age = (now - b["t_arrive_ns"]) / 1e9
            w = 1.0 / (age + EPS)
            weights.append(w); mids.append(b["mid"]); venues.append(v)
            imbs.append(b.get("imbalance5", b.get("imbalance", 0.0)))
        # favor the more recent venue
        fair_mid = sum(w*m for w, m in zip(weights, mids)) / sum(weights)

        sigma = self.vol[symbol].update(fair_mid, now)
        imb = sum(imbs)/len(imbs) if imbs else 0.0
        base_half = self.a * sigma
        impact_half = self.b * abs(imb)
        half = max(min(base_half + impact_half, 5.0), 0.01)
        inv = self.inv.get(symbol, 0.0)
        skewed_mid = fair_mid - self.kappa * inv

        half = max(half, self.half_spread_map.get(symbol, 0.0))
        return {
            "mid": skewed_mid,
            "symbol": symbol,
            "bid": skewed_mid - half,
            "ask": skewed_mid + half,
            "imbalance": imb,
            "sigma": sigma,
            "venues_used": venues,
        }
