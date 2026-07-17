"""
Natural-language backtesting: describe a strategy in English, an LLM converts it
into validated parameters, and the engine runs a real backtest.

Design note: the model does NOT write or run code. It emits STRUCTURED params
(chosen from a whitelist of strategies), which we validate and map to real
Strategy classes. Safe by construction.

    export GEMINI_API_KEY=...
    python nl_backtest.py "buy AAPL when the 10-day average crosses above the 30-day, sell on the reverse"
"""
import os
import sys
import json
import urllib.request
from engine.backtest import Backtest
from engine.strategy import MovingAverageCross, RSIMeanReversion
from engine.metrics import performance

STRATEGIES = {"ma_cross": MovingAverageCross, "rsi": RSIMeanReversion}


def parse_idea(description):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("Set GEMINI_API_KEY first (export GEMINI_API_KEY=...).")
    schema = {
        "type": "OBJECT",
        "properties": {
            "strategy": {"type": "STRING", "enum": ["ma_cross", "rsi"]},
            "symbol": {"type": "STRING"},
            "short": {"type": "NUMBER"}, "long": {"type": "NUMBER"},
            "period": {"type": "NUMBER"}, "oversold": {"type": "NUMBER"}, "overbought": {"type": "NUMBER"},
        },
        "required": ["strategy", "symbol"],
    }
    body = {
        "systemInstruction": {"parts": [{"text":
            "Convert a plain-English trading idea into structured backtest parameters. "
            "Use strategy 'ma_cross' for moving-average crossovers or 'rsi' for RSI mean-reversion. "
            "Fill only the relevant numeric fields and pick sensible defaults if unspecified. "
            "Extract the ticker as symbol in uppercase."}]},
        "contents": [{"role": "user", "parts": [{"text": description}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema, "thinkingConfig": {"thinkingBudget": 0}},
    }
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key=" + key
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=30)
    text = json.loads(resp.read())["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def main():
    desc = " ".join(sys.argv[1:]) or "buy AAPL when the 20-day average crosses above the 50-day, sell on the reverse"
    print("Idea: " + desc)
    spec = parse_idea(desc)
    print("AI parsed -> " + json.dumps(spec))

    strat = spec.get("strategy", "ma_cross")
    symbol = str(spec.get("symbol", "AAPL")).upper()
    cls = STRATEGIES.get(strat, MovingAverageCross)
    if strat == "rsi":
        kwargs = {"period": int(spec.get("period") or 14), "oversold": float(spec.get("oversold") or 30), "overbought": float(spec.get("overbought") or 70)}
    else:
        kwargs = {"short": int(spec.get("short") or 20), "long": int(spec.get("long") or 50)}

    bt = Backtest([symbol], "2018-01-01", 100000.0, cls, **kwargs)
    stats, _ = performance(bt.run(), 100000.0)
    print("-" * 50)
    print("Backtest: %s on %s  %s" % (strat, symbol, json.dumps(kwargs)))
    print("  Total return: %+.1f%%" % (stats["total_return"] * 100))
    print("  Sharpe:       %.2f" % stats["sharpe"])
    print("  Max drawdown: %.1f%%" % (stats["max_drawdown"] * 100))


if __name__ == "__main__":
    main()
