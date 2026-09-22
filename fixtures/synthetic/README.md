# Synthetic fixture v1

`ohlc.csv` contains invented prices for two symbols over four daily bars. It is
not historical or live market data. Open and Close drive the engine; High and
Low make the fixture a readable OHLC source but are not execution inputs.

From the repository root after installing dependencies:

```bash
python run_offline.py
python run_offline.py > fixtures/synthetic/expected.txt
python -m unittest discover -s tests -v
```

The second command intentionally regenerates the committed golden output.
Review changes to it; do not regenerate merely to silence a failing test.
Float output is formatted to six decimals for readability. Replay compares the
full serialized float values, events and all seven ledgers.

A closes at 10 on January 1. Its buy fills at the January 2 open of 12, plus
10 bps adverse slippage: 8 shares at 12.012 with a 1.00 commission. Cash becomes
2.904; marking 8 shares at the close of 13 produces equity of 106.904.
B's competing buy is rejected for insufficient cash. A exits at the January 3
open with adverse sell slippage and a second commission; final cash and equity
are 113.792. These invented prices demonstrate accounting, not strategy returns.
