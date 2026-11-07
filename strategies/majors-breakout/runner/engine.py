"""Majors Breakout signal engine: the strategy.md §2-§4 rules, written to match backtest/bt.py
run(U6, REGIME=False) line for line. Pure functions, no I/O. test_parity.py checks it against bt.py.
"""
BAR = 28800  # 8h
N_IN, N_OUT, ATR_N, STOP_ATR, TREND_N = 20, 10, 14, 2.0, 90
RISK, CAP, MAXPOS = 0.01, 0.25, 4
MIN_HIST = max(N_IN, ATR_N, TREND_N) + 1


def bars8h(rows4h, now=None):
    """rows4h: iterable of (start_s, o, h, l, c). Returns {bar_start_s: [o,h,l,c]} of closed 8h bars only.
    A bar counts only when both of its 4h halves are present and the second has closed."""
    b, n = {}, {}
    for t, o, h, l, c in sorted(rows4h):
        if now is not None and t + 14400 > now:
            continue  # forming 4h candle
        k = t - t % BAR
        if k not in b:
            b[k] = [o, h, l, c]; n[k] = 1 if t == k else -1
        else:
            x = b[k]; x[1] = max(x[1], h); x[2] = min(x[2], l); x[3] = c; n[k] = 2 if n[k] == 1 else -1
    return {k: v for k, v in b.items() if n[k] == 2}


def levels(H):
    """H: list of [o,h,l,c] closed 8h bars, newest last. Returns the strategy.md §3 levels, or None if too short."""
    if len(H) < MIN_HIST:
        return None
    c = H[-1][3]
    hi = max(x[1] for x in H[-N_IN - 1:-1])
    lo = min(x[2] for x in H[-N_OUT - 1:-1])
    sma = sum(x[3] for x in H[-TREND_N:]) / TREND_N
    trs = [max(H[i][1] - H[i][2], abs(H[i][1] - H[i - 1][3]), abs(H[i][2] - H[i - 1][3])) for i in range(-ATR_N, 0)]
    atr = sum(trs) / ATR_N
    return dict(close=c, hi20=hi, lo10=lo, sma90=sma, atr14=atr)


def exit_reason(L, stop):
    """Rule exit for a held coin, or None. bt.py checks lo10 with only N_OUT+1 bars; held coins always have more."""
    if L is None:
        return None
    if L["close"] < L["lo10"]:
        return f"close {L['close']:g} < lo10 {L['lo10']:g}"
    if L["close"] < stop:
        return f"close {L['close']:g} < stop {stop:g}"
    return None


def entry_signal(L):
    """Returns (strength, weight, stop) if the coin signals an entry, else None."""
    if L is None:
        return None
    c, atr = L["close"], L["atr14"]
    if c > L["hi20"] and c > L["sma90"] and atr > 0:
        stopd = STOP_ATR * atr / c
        return ((c - L["hi20"]) / atr, min(CAP, RISK / stopd), c - STOP_ATR * atr)
    return None


def decide(lv, held):
    """Rules only. lv: {sym: levels or None}; held: {sym: stop}. Returns (exits {sym: reason},
    entries [(sym, weight, stop, strength)]) in bt.py order: exits first; entries strongest first while
    held-after-exits < MAXPOS. The overlay is applied by the caller and can only remove entries or add exits,
    so an early exit never frees a slot for an entry the rules didn't pick."""
    exits = {}
    for s, stop in held.items():
        r = exit_reason(lv.get(s), stop)
        if r:
            exits[s] = r
    still = set(held) - set(exits)
    cands = []
    for s, L in lv.items():
        if s in held:
            continue
        e = entry_signal(L)
        if e:
            cands.append((e[0], s, e[1], e[2]))
    entries = []
    for strength, s, w, stop in sorted(cands, reverse=True):
        if len(still) >= MAXPOS:
            break
        entries.append((s, w, stop, strength)); still.add(s)
    return exits, entries
