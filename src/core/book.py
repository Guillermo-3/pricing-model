import asyncio, json, time, heapq
from typing import List, Tuple, Dict, Optional

def _topk_imbalance(bids: List[Tuple[float,float]],
                    asks: List[Tuple[float,float]], k:int=5) -> float:
    bq = sum(q for _ , q in bids[:k])
    aq = sum(q for _ , q in asks[:k])
    return 0. if (bq+aq)==0 else (bq-aq)/(bq+aq)

def _now_ns() -> int:
    return time.time_ns()
EPS        = 1e-3
STALE_NS   = 500_000_000         
MAX_HALF   = 5.0                  


class BinanceBook:
    """
    Handles stateless snapshot data from Binance's @depth5 stream.
    """
    def __init__(self, symbol:str):
        self.symbol = symbol.upper()
        self.bids : List[Tuple[float,float]]=[]
        self.asks : List[Tuple[float,float]]=[]
        self.t_arrive_ns = 0

    def apply_snapshot(self, data:dict, t_arrive_ns:int):
        self.bids = [(float(p),float(q)) for p,q in data["bids"]]
        self.asks = [(float(p),float(q)) for p,q in data["asks"]]
        self.t_arrive_ns = t_arrive_ns

    def view(self):
        if not self.bids or not self.asks: return None
        best_bid, best_ask = self.bids[0][0], self.asks[0][0]
        if best_bid > best_ask: return None
        mid = (best_bid+best_ask)/2
        imb = _topk_imbalance(self.bids,self.asks,5)
        return {"venue":"binance","symbol":self.symbol,
                "bid":best_bid,"ask":best_ask,"mid":mid,
                "bids5":self.bids,"asks5":self.asks,"imbalance5":imb,
                "t_arrive_ns":self.t_arrive_ns}

class OKXBook:
    def __init__(self, symbol:str):
        self.symbol = symbol.upper()
        self.bids : List[Tuple[float,float]]=[]
        self.asks : List[Tuple[float,float]]=[]
        self.t_arrive_ns = 0

    def apply_snapshot(self, data:dict, t_arrive_ns:int):
        self.bids = [(float(p),float(q)) for p,q,*_ in data["bids"][:5]]
        self.asks = [(float(p),float(q)) for p,q,*_ in data["asks"][:5]]
        self.t_arrive_ns = t_arrive_ns

    def view(self):
        if not self.bids or not self.asks: return None
        best_bid, best_ask = self.bids[0][0], self.asks[0][0]
        if best_bid > best_ask: return None
        mid = (best_bid+best_ask)/2
        imb = _topk_imbalance(self.bids,self.asks,5)
        return {"venue":"okx","symbol":self.symbol,
                "bid":best_bid,"ask":best_ask,"mid":mid,
                "bids5":self.bids,"asks5":self.asks,"imbalance5":imb,
                "t_arrive_ns":self.t_arrive_ns}