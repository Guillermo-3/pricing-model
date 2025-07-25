import time


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
    
    def best_bid(self):
        return max(self.bids.keys(), key=float)
    
    def best_ask(self):
        return min(self.asks.keys(), key=float)
    
    def view(self):
        bid = float(self.best_bid())
        ask = float(self.best_ask())
        return{
            "venue": "binance",
            "symbol": self.symbol,
            "bid": bid,
            "ask": ask,
            "mid": (bid + ask)/2,
            "t_arrive_ns": self.t_arrive_ns
        } 

class OKXBook:
    def __init__(self, symbol):
        self.symbol = symbol.upper()
        self.bid = None; self.ask = None; self.t_arrive_ns = 0
    
    def apply_snapshot(self, data, t_arrive_ns):
        self.bid = float(data["bids"][0][0])
        self.ask = float(data["asks"][0][0])
        self.t_arrive_ns = t_arrive_ns

    def view(self):
        return {"venue": "okx", "symbol": self.symbol,
                "bid": self.bid, "ask" : self.ask,
                "mid": (self.bid + self.ask) / 2,
                "t_arrive_ns": self.t_arrive_ns}