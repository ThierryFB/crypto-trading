#!/usr/bin/env python3
"""Offline checks of the ticket gate (risk-policy.md L1-L10, D1-D3) and the forecast scoring. No network."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tickets, forecasts  # noqa: E402

CFG = json.load(open(os.path.join(HERE, "config.json")))
NOW = tickets.ts("2026-11-13T08:06Z")
F6 = {"BTC": 0.55, "ETH": 0.5, "SOL": 0.62, "XRP": 0.45, "DOGE": 0.5, "ADA": 0.5}


def ctx(**kw):
    c = dict(nav=2000.0, cash=2000.0, week_start_nav=2000.0, week_cost=0.0, day_loss=0.0, halted=[], now=NOW,
             prev_wake=tickets.ts("2026-11-13T00:05Z"), lots={}, forecasts=dict(F6), entries_this_wake=0,
             touch={"BTC": (74000.0, 74010.0), "SOL": (200.0, 200.1), "ETH": (2000.0, 2000.5), "XRP": (1.0, 1.0001),
                    "DOGE": (0.07, 0.07001), "ADA": (0.17, 0.17002)},
             inst={c: dict(min_qty=0, min_amt=5) for c in F6})
    c.update(kw)
    return c


def entry(**kw):
    t = {"type": "entry", "coin": "SOL", "risk_usd": 12.0, "entry": "touch", "stop": 190.0, "target": 215.0,
         "forecast_24h": 0.62, "thesis": {"why_now": "x", "invalidated_if": "y",
                                          "sources": [{"what": "a", "url": "u", "at": "2026-11-13T07:40Z"}]}}
    t.update(kw)
    return t


def ok(t, c=None):
    plan, bad = tickets.check(t, c or ctx(), CFG)
    assert not bad, bad
    return plan


def refused(t, c, word):
    plan, bad = tickets.check(t, c, CFG)
    assert plan is None and any(word in b for b in bad), (word, bad)


def main():
    n = 0
    p = ok(entry())  # sized from the stop: $12 / (200.3 - 190) ≈ 1.165 SOL ≈ $233
    assert abs(p["risk"] - 12) < 1e-6 and abs(p["limit"] - 200.1 * 1.001) < 1e-9 and p["value"] < 500; n += 1
    refused(entry(risk_usd=16), ctx(), "L2"); n += 1                      # 0.75% of 2000 = 15
    p = ok(entry(stop=199.0, risk_usd=15))                                  # tight stop -> L4 shrink to $500
    assert abs(p["value"] - 500) < 1e-6 and "L4" in p["note"]; n += 1
    lots = {"L-1": dict(coin="SOL", qty=2.4, entry_px=195.0, stop=196.0)}  # $480 held: room $20 < 2% NAV
    refused(entry(), ctx(lots=lots), "L4"); n += 1
    lots = {"L-1": dict(coin="SOL", qty=1.0, entry_px=195.0, stop=180.0)}  # held, stop below entry
    refused(entry(), ctx(lots=lots), "L5"); n += 1
    lots = {"L-1": dict(coin="SOL", qty=1.0, entry_px=205.0, stop=206.0)}  # add below the average entry
    refused(entry(), ctx(lots=lots), "L5"); n += 1
    lots = {f"L-{i}": dict(coin=c, qty=0.001, entry_px=1.0, stop=1.0) for i, c in enumerate(["BTC", "ETH", "XRP", "ADA"])}
    refused(entry(), ctx(lots=lots), "L6"); n += 1
    refused(entry(), ctx(entries_this_wake=2), "L7"); n += 1
    refused(entry(), ctx(week_cost=3.9), "L8"); n += 1                     # budget $4
    refused(entry(), ctx(day_loss=0.041), "D1"); n += 1
    refused(entry(), ctx(halted=["HALT — desk"]), "halted"); n += 1
    refused(entry(coin="BNB"), ctx(), "L1"); n += 1
    refused(entry(forecast_24h=0.6), ctx(), "≠"); n += 1                   # must match step 3
    refused(entry(coin="XRP", stop=0.95, forecast_24h=0.45), ctx(), "≤ 0.5"); n += 1
    refused(entry(stop=201.0), ctx(), "stop"); n += 1
    refused(entry(target=None), ctx(), "target or a time_limit"); n += 1
    ok(entry(target=None, time_limit_utc="2026-11-16T00:05Z")); n += 1
    refused(entry(entry=205.0), ctx(), "L9"); n += 1                       # limit above the touch
    old = entry(thesis={"why_now": "x", "invalidated_if": "y", "sources": [{"what": "a", "url": "u", "at": "2026-11-12T20:00Z"}]})
    refused(old, ctx(), "older than the previous wake"); n += 1
    refused(entry(thesis={"why_now": "x", "invalidated_if": "", "sources": []}), ctx(), "invalidated_if"); n += 1

    # exits always pass the gates; adjusts never loosen a stop
    lots = {"L-7": dict(coin="SOL", qty=1.0, entry_px=195.0, stop=185.0)}
    assert ok({"type": "exit", "coin": "SOL", "lot": "L-7", "fraction": 1.0, "reason": "r"}, ctx(lots=lots, halted=["x"]))["qty"] == 1.0; n += 1
    refused({"type": "exit", "coin": "SOL", "lot": "L-7", "fraction": 1.5, "reason": "r"}, ctx(lots=lots), "fraction"); n += 1
    refused({"type": "adjust", "coin": "SOL", "lot": "L-7", "stop": 180.0, "reason": "r"}, ctx(lots=lots), "never loosened"); n += 1
    assert ok({"type": "adjust", "coin": "SOL", "lot": "L-7", "stop": 190.0, "reason": "r"}, ctx(lots=lots))["stop"] == 190.0; n += 1
    refused({"type": "adjust", "coin": "SOL", "lot": "L-7", "stop": 201.0, "reason": "r"}, ctx(lots=lots), "use an exit"); n += 1

    # a whole wake: L7 and same-coin within the wake, forecasts complete
    w = {"forecasts": F6, "tickets": [entry(), entry(coin="BTC", stop=72000.0, forecast_24h=0.55, target=None, time_limit_utc="2026-11-15T00:05Z"),
                                      entry(coin="SOL")]}
    fp, res = tickets.check_wake(w, ctx(), CFG)
    assert not fp and not res[0][2] and not res[1][2] and res[2][2], res; n += 1
    w2 = {"forecasts": dict(F6, ADA=None), "tickets": []}
    fp, _ = tickets.check_wake(w2, ctx(), CFG)
    assert fp == ["no forecast for ADA"], fp; n += 1
    fp, _ = tickets.check_wake({"forecasts": dict(F6, BTC=0.99)}, ctx(), CFG)
    assert fp and "outside" in fp[0]; n += 1

    # forecasts: resolution time, Brier, bootstrap by day
    t0 = tickets.ts("2026-11-12T00:05Z")
    assert forecasts.resolve_close_t(t0) == tickets.ts("2026-11-13T08:00Z"); n += 1
    t1 = tickets.ts("2026-11-12T14:35Z")
    assert forecasts.resolve_close_t(t1) == tickets.ts("2026-11-13T16:00Z"); n += 1
    R = forecasts.record(t0, {"BTC": 0.7, "ETH": 0.4}, {"BTC": 100.0, "ETH": 10.0}, {"BTC": 0.5, "ETH": 0.5})
    forecasts.resolve(R, {"BTC": {R[0]["resolve_t"]: 101.0}, "ETH": {R[1]["resolve_t"]: 10.0}})
    assert [r["y"] for r in R] == [1, 0]                                   # a tie is not "higher"
    assert abs(forecasts.brier(R) - (0.09 + 0.16) / 2) < 1e-12 and forecasts.brier(R, "base") == 0.25; n += 1
    lo, hi = forecasts.bootstrap(R, n=200)
    assert lo == hi == forecasts.brier(R); n += 1                          # one day = one block
    print(f"{n} ticket and forecast checks pass")


if __name__ == "__main__":
    main()
