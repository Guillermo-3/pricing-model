import pandas as pd, json, pathlib

def load_jsonl(path: str) -> pd.DataFrame:
    """Return DataFrame with numeric mid/bid/ask and ns timestamps."""
    rows = []
    with pathlib.Path(path).open() as fh:
        for line in fh:
            rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    df = df[["t_arrive_ns", "mid", "bid", "ask", "symbol", "venue"]]
    df["mid"]  = df["mid"].astype(float)
    df["bid"]  = df["bid"].astype(float)
    df["ask"]  = df["ask"].astype(float)
    return df