import time
import math
from src.core.fair_price import FairPriceEngine

STALE_NS = 500_000_000   # drop venue if last update > 0.5s old
EPS      = 1e-3

def test_basic_quote():
    fp = FairPriceEngine()
    now = time.time_ns()
   
    fp.update("okx", "BTCUSDT", {"mid": 50010.0, "t_arrive_ns": now - 10_000_000})
    fp.update("binance", "BTCUSDT", {"mid": 50000.0, "t_arrive_ns": now - 200_000_000})
    q = fp.quote("BTCUSDT")
    assert q is not None

    # compute expected
    w1 = 1.0 / (0.01 + EPS)  # ≈100
    w2 = 1.0 / (0.2  + EPS)  # ≈5
    expected_mid = (w1*50010.0 + w2*50000.0) / (w1 + w2)
    expected_bid = expected_mid - fp.half_spread_map["BTCUSDT"]
    expected_ask = expected_mid + fp.half_spread_map["BTCUSDT"]

    # numeric assertions
    assert math.isclose(q["mid"], expected_mid, rel_tol=1e-6)
    assert math.isclose(q["bid"], expected_bid, rel_tol=1e-6)
    assert math.isclose(q["ask"], expected_ask, rel_tol=1e-6)

    # venues order or set
    assert set(q["venues_used"]) == {"okx", "binance"}
