# Design

The engine separates market data, strategy logic, portfolio accounting, and execution through typed queue events. This makes timing observable and lets each component be replaced independently.

## Bar lifecycle

For each timestamp, the data handler publishes a market event. The broker first fills orders that were pending from an earlier timestamp at the current open. The strategy then observes the current close and may publish target weights. The portfolio converts changed targets to orders, which remain pending until another market event. Finally, the portfolio marks cash and positions at the current close.

An order submitted on the final bar is cancelled with `end_of_data`; it is never silently filled at the same close.

## Accounting invariants

- Long-only positions cannot fall below zero.
- New buy orders reserve estimated cash.
- Gaps beyond the reserve buffer cause a smaller fill or rejection, never negative cash.
- Equity equals cash plus each position valued at the current close.
- Every order ends as filled, partially filled, rejected, or cancelled.

## Intentionally excluded

Version 1 does not add more strategies. Its goal is a reliable engine boundary, auditable ledgers, and honest evaluation—not a strategy catalogue.
