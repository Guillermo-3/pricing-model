from src.core.reader import load_jsonl

def calc_day_stats(path: str, symbol: str):
    df = load_jsonl(path)
    df = df[df.symbol == symbol].sort_values("t_arrive_ns")

    df["spread"] = df["ask"] - df["bid"]
    median_spread = float(df["spread"].median())

    
    df["t_s"] = (df["t_arrive_ns"] / 1e9).astype(int)
    mids_1s   = df.groupby("t_s")["mid"].mean()
    mid_diff  = mids_1s.diff().dropna()
    var_1s    = float(mid_diff.var(ddof=0))

    return {"median_spread": median_spread, "var_1s": var_1s}
