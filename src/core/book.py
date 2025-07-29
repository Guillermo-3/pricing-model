import time


def _topk_imbalance(bids, asks, k=5):
    # bids/asks: list[(price, qty)] best-first
    bq = sum(q for _, q in bids[:k])
    aq = sum(q for _, q in asks[:k])
    if bq + aq == 0:
        return 0.0
    return (bq - aq) / (bq + aq)


class BinanceBook:
    """
    Maintain a local copy of Biannce order book using diff depth stream.
    We take in a snapshot and then apply diffs with sequence checks.
    """
    def __init__(self, symbol):
        self.symbol = symbol.upper()
        self.bids = {}
        self.asks = {}
        self.last_update_id = 0
        self.t_arrive_ns = 0
    
    def load_snapshot(self,last_update_id, bids, asks):
        self.last_update_id = last_update_id
        self.bids = {p:q for p,q in bids}
        self.asks = {p:q for p,q in asks}

    def apply_diff(self, msg, t_arrive_ns):
        # Binance diff has : U (first update ID) and u(final), b (bids), a (asks)
        U, u = msg['U'], msg['u']
        # Ignore events before our current snapshot
        if u <= self.last_update_id:
            return
        # First valid event has to satisfy the following
        if self.last_update_id and U > self.last_update_id + 1:
            raise ValueError("SEQ_GAP") # Trigger a rebuild upstream
        if u < U:
            return # not formed correctly final less than first update id
        for p, q in msg['b']:
            if float(q) == 0.0:
                self.bids.pop(p,None)
            else:
                self.bids[p] = q
        for p,q in msg['a']:
            if float(q) == 0.0:
                self.asks.pop(p,None)
            else:
                self.asks[p] = q
        self.last_update_id = u 
        self.t_arrive_ns = t_arrive_ns

    def _top_levels(self, k=5):
        bids5 = sorted(((float(p), float(q)) for p,q in self.bids.items()),
                        key=lambda x: x[0], reverse=True)[:k]
        asks5 = sorted(((float(p), float(q)) for p,q in self.asks.items()),
                        key=lambda x: x[0])[:k]
        return bids5, asks5
    
    def view(self):
        bids5, asks5 = self._top_levels(5)
        if not bids5 or asks5:
            return None
        best_bid, best_ask = bids5[0][0], asks5[0][0]
        mid = (best_bid + best_ask) / 2.0
        imb5 = _topk_imbalance(bids5, asks5, 5)
        return {
            "venue": "binance",
            "symbol": self.symbol,
            "bid": best_bid,
            "ask": best_ask,
            "mid": mid,
            "bids5": bids5,
            "asks5": asks5,
            "imbalance5": imb5,
            "t_arrive_ns": self.t_arrive_ns
        } 

class OKXBook:
    def __init__(self, symbol):
        self.symbol = symbol.upper()
        self.bids = []
        self.asks = []
        self.t_arrive_ns = 0
    
    def apply_snapshot(self, data, t_arrive_ns):
        # data bids and data for asks are lists in format [[price, size, liq]]
        # gather top 5 levels
        self.bids = [(float(p), float(q)) for p,q, *_ in data["bids"][:5]]
        self.asks = [(float(p), float(q)) for p,q, *_ in data["asks"][:5]]
        self.t_arrive_ns = t_arrive_ns

    def view(self):
        best_bid = self.bids[0][0]
        best_ask = self.asks[0][0]
        mid = (best_bid + best_ask)/2
        imbalance = _topk_imbalance(self.bids, self.asks, 5)
        return {
            "venue": "okx",
            "symbol": self.symbol,
            "bid": best_bid,
            "ask": best_ask,
            "mid": mid,
            "bids5": self.bids,
            "asks5": self.asks,
            "imbalance5": imbalance,
            "t_arrive_ns": self.t_arrive_ns
        }