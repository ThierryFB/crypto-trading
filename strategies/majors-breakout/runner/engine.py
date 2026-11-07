"""Majors Breakout signal engine: the strategy.md §2-§5 rules, written to match backtest/bt_active.py
run(U6, breakout(n_in, n_out, 90)) line for line, once per slice. Pure functions, no I/O.
test_parity.py checks every slice against bt_active.py.
"""
BAR = 28800  # 8h
SLICES = {"fast": (10, 5), "med": (20, 10), "slow": (40, 20)}  # slice -> (N_in, N_out)
ATR_N, STOP_ATR, TREND_N = 14, 2.0, 90
RISK, CAP, MAXPOS = 0.01, 0.25, 4  # per slice, of slice NAV
MIN_HIST = max(max(n for n, _ in SLICES.values()), ATR_N + 1, TREND_N) + 1


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
    """H: list of [o,h,l,c] closed 8h bars, newest last. Returns the strategy.md §4 levels for every slice
    (hi/lo keyed by slice), or None if too short."""
    if len(H) < MIN_HIST:
        return None
    c = H[-1][3]
    sma = sum(x[3] for x in H[-TREND_N:]) / TREND_N
    trs = [max(H[i][1] - H[i][2], abs(H[i][1] - H[i - 1][3]), abs(H[i][2] - H[i - 1][3])) for i in range(-ATR_N, 0)]
    atr = sum(trs) / ATR_N
    hi = {sl: max(x[1] for x in H[-n_in - 1:-1]) for sl, (n_in, _) in SLICES.items()}
    lo = {sl: min(x[2] for x in H[-n_out - 1:-1]) for sl, (_, n_out) in SLICES.items()}
    return dict(close=c, sma90=sma, atr14=atr, hi=hi, lo=lo)


def exit_reason(L, sl, stop):
    """Rule exit for a coin held by slice sl, or None."""
    if L is None:
        return None
    if L["close"] < L["lo"][sl]:
        return f"close {L['close']:g} < lo{SLICES[sl][1]} {L['lo'][sl]:g}"
    if L["close"] < stop:
        return f"close {L['close']:g} < stop {stop:g}"
    return None


def entry_signal(L, sl):
    """Returns (strength, weight, stop) if the coin signals an entry for slice sl, else None."""
    if L is None:
        return None
    c, atr, hi = L["close"], L["atr14"], L["hi"][sl]
    if c > hi and c > L["sma90"] and atr > 0:
        stopd = STOP_ATR * atr / c
        return ((c - hi) / atr, min(CAP, RISK / stopd), c - STOP_ATR * atr)
    return None


def decide(lv, held, sl):
    """Rules only, one slice. lv: {sym: levels or None}; held: {sym: stop} for this slice. Returns
    (exits {sym: reason}, entries [(sym, weight, stop, strength)]) in bt_active.py order: exits first; entries
    strongest first while held-after-exits < MAXPOS. The overlay is applied by the caller and can only remove
    entries or add exits, so an early exit never frees a slot for an entry the rules didn't pick."""
    exits = {}
    for s, stop in held.items():
        r = exit_reason(lv.get(s), sl, stop)
        if r:
            exits[s] = r
    still = set(held) - set(exits)
    cands = []
    for s, L in lv.items():
        if s in held:
            continue
        e = entry_signal(L, sl)
        if e:
            cands.append((e[0], s, e[1], e[2]))
    entries = []
    for strength, s, w, stop in sorted(cands, reverse=True):
        if len(still) >= MAXPOS:
            break
        entries.append((s, w, stop, strength)); still.add(s)
    return exits, entries
