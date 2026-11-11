"""24 h forecasts (strategy.md §2 step 3, §7.2): store, resolve, score. Pure except where bars are passed in.

A forecast made at wake time t on a coin with mid m resolves on the close of the 8h candle containing t + 24 h:
outcome 1 if that close > m, else 0. Scored with the Brier score against a coin flip (0.25) and the coin's
90-day up-24h base rate, with a block bootstrap by UTC day (risk-policy.md §2: 10,000 resamples).
"""
import random

BAR = 28800


def resolve_close_t(t):
    """Close time of the 8h candle that contains t + 24 h."""
    return (int(t + 86400) // BAR) * BAR + BAR


def record(wake_t, forecasts, mids, base):
    return [dict(t=wake_t, coin=c, p=float(p), px0=mids[c], base=base.get(c), resolve_t=resolve_close_t(wake_t), y=None)
            for c, p in sorted(forecasts.items())]


def resolve(rows, closes):
    """closes: {coin: {bar_close_t: close}}. Fills y where the resolving candle has closed. Returns rows resolved now."""
    done = []
    for r in rows:
        if r["y"] is None:
            c = closes.get(r["coin"], {}).get(r["resolve_t"])
            if c is not None:
                r["y"], r["px1"] = int(c > r["px0"]), c
                done.append(r)
    return done


def brier(rows, key="p"):
    R = [r for r in rows if r["y"] is not None and r.get(key) is not None]
    return sum((r[key] - r["y"]) ** 2 for r in R) / len(R) if R else None


def day(t):
    return int(t // 86400)


def bootstrap(rows, n=10000, seed=7):
    """Brier over UTC-day blocks resampled with replacement. Returns (lo10, hi90) or None."""
    R = [r for r in rows if r["y"] is not None]
    if not R:
        return None
    by = {}
    for r in R:
        by.setdefault(day(r["t"]), []).append((r["p"] - r["y"]) ** 2)
    blocks = list(by.values())
    rng, out = random.Random(seed), []
    for _ in range(n):
        s = [rng.choice(blocks) for _ in blocks]
        out.append(sum(sum(b) for b in s) / sum(len(b) for b in s))
    out.sort()
    return out[int(0.1 * n)], out[int(0.9 * n) - 1]


def calibration(rows):
    """[(bucket_lo, n, mean_p, hit_rate)] in 10-point buckets."""
    B = {}
    for r in rows:
        if r["y"] is not None:
            B.setdefault(min(int(r["p"] * 10), 9), []).append(r)
    return [(k / 10, len(v), sum(r["p"] for r in v) / len(v), sum(r["y"] for r in v) / len(v)) for k, v in sorted(B.items())]


def score_block(rows):
    R = [r for r in rows if r["y"] is not None]
    if not R:
        return f"Forecasts: {len(rows)} logged, none resolved yet."
    b, base, ci = brier(R), brier(R, "base"), bootstrap(R)
    days = len({day(r["t"]) for r in R})
    s = (f"Forecasts: {len(R)} resolved over {days} UTC days · Brier **{b:.4f}** (80% interval {ci[0]:.4f}–{ci[1]:.4f}) · "
         f"coin flip 0.2500 · base rate {base:.4f}" if base is not None else f"Brier **{b:.4f}**")
    cal = " · ".join(f"{lo:.0%}–{lo + 0.1:.0%}: n={n}, p̄={mp:.2f}, hit={h:.0%}" for lo, n, mp, h in calibration(R))
    return s + ("\nCalibration: " + cal if cal else "")
