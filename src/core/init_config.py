from dataclasses import dataclass

@dataclass
class MMConfig:
    q_process: float
    r0: float; r1: float; r2: float
    vol_halflife_s: float
    h_secs: float
    a_unc: float
    b_impact: float
    kappa: float
    min_half: float
    max_half: float
    ann_factor: float
def build_cfg(stats: dict, tick: float) -> MMConfig:
    r0 = (tick / 2) ** 2
    return MMConfig(
        q_process      = stats["var_1s"] * 0.10,
        r0             = r0,
        r1             = r0 * 0.4,
        r2             = 0.15,
        vol_halflife_s = 60.0,
        h_secs         = 1.0,
        a_unc          = 0.3,
        b_impact       = 0.1,
        kappa          = 0.01 * tick,
        min_half       = tick,
        max_half       = 3 * stats["median_spread"],
        ann_factor=1.0
    )