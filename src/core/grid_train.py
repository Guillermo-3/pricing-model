from src.core.stats_extract import calc_day_stats
from src.core.init_config import build_cfg
from src.core.backtest import BackTester
import itertools
import pandas as pd
import matplotlib.pyplot as plt
SYMBOL = "BTCUSDT"
TICK   = 0.01

TRAIN  = "logs/market_data_20250729.jsonl"
TEST   = "logs/market_data_20250730.jsonl"

stats = calc_day_stats(TRAIN, SYMBOL)
base  = build_cfg(stats, tick=TICK) # Build with our median and voltaility from data

A_vals = [0.1, 0.3, 0.5]
B_vals = [0.0, 0.05, 0.1]
K_vals = [-0.05*TICK, 0.0, 0.05*TICK]
results = []
best_pnl, best_cfg = -1e9, None
for a,b,k in itertools.product(A_vals, B_vals, K_vals):
    cfg = base
    cfg.a_unc   = a
    cfg.b_impact= b
    cfg.kappa   = k
    res = BackTester(TRAIN, SYMBOL, cfg).run()
    pnl  = res["pnl"]
    trades  = res["trades"]

    results.append({
        "a_unc": a,
        "b_impact": b,
        "kappa": k,
        "pnl": pnl,
        "trades": trades
    })
    if pnl > best_pnl:
        best_pnl, best_cfg = pnl, cfg

print("\n=== OUT-OF-SAMPLE TEST ON 30-JUL ===")
test_pnl = BackTester(TEST, SYMBOL, best_cfg).run()
print("test pnl:", test_pnl)

df = pd.DataFrame(results)
plt.figure()
for b in B_vals:
    sub = df[df["b_impact"] == b]
    plt.plot(sub["a_unc"], sub["pnl"], marker='o', label=f"b={b}")
plt.xlabel("a_unc (risk aversion)")
plt.ylabel("In-sample PnL")
plt.title("PnL vs Risk Aversion by Imbalance Weight")
plt.legend()
plt.tight_layout()
plt.show()

# --- Plot 2: Trades vs a_unc for each b_impact ---
plt.figure()
for b in B_vals:
    sub = df[df["b_impact"] == b]
    plt.plot(sub["a_unc"], sub["trades"], marker='x', label=f"b={b}")
plt.xlabel("a_unc (risk aversion)")
plt.ylabel("Number of Trades")
plt.title("Fill Count vs Risk Aversion by Imbalance Weight")
plt.legend()
plt.tight_layout()
plt.show()

# --- Plot 3: Heatmaps of PnL for each kappa ---
for k in K_vals:
    sub   = df[df["kappa"] == k]
    pivot = sub.pivot(index="a_unc", columns="b_impact", values="pnl")
    plt.figure()
    plt.imshow(pivot, origin='lower', aspect='auto')
    plt.colorbar(label="PnL")
    plt.xticks(range(len(pivot.columns)), pivot.columns)
    plt.yticks(range(len(pivot.index)), pivot.index)
    plt.xlabel("b_impact")
    plt.ylabel("a_unc")
    plt.title(f"PnL Heatmap (kappa={k:.4f})")
    plt.tight_layout()
    plt.show()

# --- Out-of-sample test ---
test_res = BackTester(TEST, SYMBOL, best_cfg, "poisson").run()
print("\nOut-of-sample performance:", test_res)

# --- Plot 4: In-sample vs Out-of-sample PnL ---
plt.figure()
plt.bar(
    ["In-sample Best", "Out-of-sample"],
    [best_pnl, test_res["pnl"]],
    color=['tab:blue','tab:orange']
)
plt.ylabel("PnL")
plt.title("In-sample vs Out-of-sample PnL")
plt.tight_layout()
plt.show()