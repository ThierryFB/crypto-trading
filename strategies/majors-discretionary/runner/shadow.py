"""Rules-only shadow book (strategy.md §6, risk-policy.md L11) and the buy-and-hold BTC benchmark. Places no orders.

The merged 3-speed breakout (`strategies/majors-breakout/`), one virtual book per slice from a third of $2,000,
filled at 8h candle closes at 0.15% per side, sized as the breakout runner sizes (its config.json), with the
catastrophe stop at entry − 4×ATR checked on each closed candle's low. It starts with paper (the first strategy
order, risk-policy.md §2) and acts on every 8h close after that, catching up closes between wakes.
"""
import json, os
from inputs import engine
import runner as mb

MB_CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(mb.__file__)), "config.json")))
INST = dict(step="0.0000000001", min_qty=0, min_amt=5.0)


def new(sleeve, last_bar, t):
    return dict(started=t, last_bar=last_bar, books={sl: dict(cash=sleeve / len(engine.SLICES), pos={}, closed=[]) for sl in engine.SLICES})


def book_nav(b, marks):
    return b["cash"] + sum(p["qty"] * marks.get(s, p["entry_px"]) for s, p in b["pos"].items())


def nav(sh, marks):
    return sum(book_nav(b, marks) for b in sh["books"].values())


def step(sh, bars, fee):
    """bars: {SYM: {bar_start: [o,h,l,c]}} closed 8h candles. Acts on every close after sh['last_bar'].
    Returns the moves made, as text."""
    L, moves = MB_CFG["limits"], []
    common = sorted(set.intersection(*(set(b) for b in bars.values()))) if bars else []
    keys = {s: sorted(b) for s, b in bars.items()}
    for bar in [k for k in common if k > sh["last_bar"]]:
        H = {s: [bars[s][k] for k in keys[s] if k <= bar] for s in bars}
        lv = {s: engine.levels(h) for s, h in H.items()}
        if any(v is None for v in lv.values()):
            sh["last_bar"] = bar; continue
        cl = {s: v["close"] for s, v in lv.items()}
        for sl, b in sh["books"].items():  # catastrophe stops, then the rule exits
            for s, p in list(b["pos"].items()):
                o, lo = H[s][-1][0], H[s][-1][2]
                if p["bar"] < bar and lo <= p["cat_px"]:
                    _close(b, s, min(p["cat_px"], o), fee, f"catastrophe stop {p['cat_px']:g}", bar, moves, sl)
            ex, _ = engine.decide(lv, {s: p["stop"] for s, p in b["pos"].items()}, sl)
            for s, why in ex.items():
                _close(b, s, cl[s], fee, why, bar, moves, sl)
        sleeve = nav(sh, cl)
        for sl, b in sh["books"].items():
            _, en = engine.decide(lv, {s: p["stop"] for s, p in b["pos"].items()}, sl)
            for s, w, stop, _ in en:
                other = sum(x["pos"][s]["qty"] * cl[s] for y, x in sh["books"].items() if y != sl and s in x["pos"])
                q = float(mb.entry_qty(MB_CFG, w, book_nav(b, cl), b["cash"], cl[s], stop, INST, other, sleeve)[0])
                if q * cl[s] < INST["min_amt"]:
                    continue
                b["cash"] -= q * cl[s] * (1 + fee)
                b["pos"][s] = dict(qty=q, entry_px=cl[s], stop=stop, bar=bar, cat_px=cl[s] - L["catastrophe_atr"] * lv[s]["atr14"])
                moves.append(f"{sl} buy {s[:-4]} @ {cl[s]:g}")
        sh["last_bar"] = bar
    return moves


def _close(b, s, px, fee, why, bar, moves, sl):
    p = b["pos"].pop(s)
    b["cash"] += p["qty"] * px * (1 - fee)
    b["closed"].append(dict(p, sym=s, exit_px=px, exit_bar=bar, why=why))
    moves.append(f"{sl} sell {s[:-4]} @ {px:g} ({why})")


def render(sh, marks, bh, start_nav):
    if not sh:
        return "**Shadow book and BTC benchmark:** not started; both start with the first strategy order (risk-policy.md §2)."
    n = nav(sh, marks)
    held = "; ".join(f"{sl}: " + (", ".join(f"{s[:-4]} (stop {p['stop']:.6g})" for s, p in b["pos"].items()) or "flat")
                     for sl, b in sh["books"].items())
    s = f"**Shadow book** (rules-only 3-speed breakout, since {sh['started']}): ${n:,.2f} ({n / start_nav - 1:+.2%}) · {held}"
    if bh:
        v = bh["qty"] * marks.get("BTCUSDT", bh["px"])
        s += f"\n**BTC buy-and-hold** (from {bh['t']} @ {bh['px']:g}): ${v:,.2f} ({v / start_nav - 1:+.2%})"
    return s
