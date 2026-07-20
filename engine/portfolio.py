"""Portfolio accounting, target-weight sizing, reservations, and ledgers."""

from __future__ import annotations

from .events import OrderEvent


class Portfolio:
    def __init__(self, data, events, initial_capital=100_000.0, reserve_buffer=0.02):
        self.data = data
        self.events = events
        self.symbols = data.symbols
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.positions = {symbol: 0 for symbol in self.symbols}
        self.reserve_buffer = float(reserve_buffer)
        self.reserved_cash = 0.0
        self._reservations = {}
        self._next_order_id = 1

        self.orders = []
        self.fills = []
        self.trades = []
        self.positions_ledger = []
        self.cash_ledger = []
        self.equity_curve = []
        self.rejections = []

    def _equity(self) -> float:
        market_value = sum(
            self.positions[symbol] * self.data.get_latest_close(symbol) for symbol in self.symbols
        )
        return self.cash + market_value

    def _pending_sell_proceeds(self) -> float:
        """Conservative proceeds from sells scheduled before pending buys."""
        return sum(
            max(
                0.0,
                order["quantity"] * order["reference_price"] * (1.0 - self.reserve_buffer) - 1.0,
            )
            for order in self.orders
            if order["status"] == "pending" and order["direction"] == "SELL"
        )

    def update_signal(self, event) -> None:
        symbol = event.symbol
        price = self.data.get_latest_close(symbol)
        equity = self._equity()
        if not 0.0 <= event.target_weight <= 1.0:
            raise ValueError("this portfolio supports long-only target weights in [0, 1]")
        target_quantity = int(equity * event.target_weight / price)
        quantity_delta = target_quantity - self.positions[symbol]
        if quantity_delta == 0:
            return

        direction = "BUY" if quantity_delta > 0 else "SELL"
        requested = abs(quantity_delta)
        quantity = requested
        if direction == "SELL":
            quantity = min(quantity, self.positions[symbol])
        else:
            available = max(
                0.0,
                self.cash + self._pending_sell_proceeds() - self.reserved_cash,
            )
            estimated_unit_cost = price * (1.0 + self.reserve_buffer)
            quantity = min(quantity, int(max(0.0, available - 1.0) // estimated_unit_cost))

        if quantity <= 0:
            self._reject(None, symbol, requested, "insufficient_cash")
            return
        if quantity < requested:
            self._reject(None, symbol, requested - quantity, "partially_sized_for_cash")

        order_id = f"O{self._next_order_id:05d}"
        self._next_order_id += 1
        if direction == "BUY":
            reservation = quantity * price * (1.0 + self.reserve_buffer) + 1.0
            self._reservations[order_id] = reservation
            self.reserved_cash += reservation

        order = OrderEvent(
            order_id=order_id,
            symbol=symbol,
            quantity=quantity,
            direction=direction,
            submitted_dt=event.dt,
            reference_price=price,
        )
        self.orders.append(
            {
                "order_id": order_id,
                "submitted_dt": event.dt,
                "symbol": symbol,
                "direction": direction,
                "quantity": quantity,
                "reference_price": price,
                "status": "pending",
            }
        )
        self.events.put(order)

    def update_fill(self, event) -> None:
        reservation = self._reservations.pop(event.order_id, 0.0)
        self.reserved_cash = max(0.0, self.reserved_cash - reservation)
        quantity = event.quantity

        if event.direction == "BUY":
            affordable = int(max(0.0, self.cash - event.commission) // event.fill_price)
            if affordable < quantity:
                self._reject(event.order_id, event.symbol, quantity - affordable, "gap_exceeded_cash")
                quantity = affordable
            if quantity <= 0:
                self._set_order_status(event.order_id, "rejected")
                return
            commission = event.commission * quantity / event.quantity
            self.positions[event.symbol] += quantity
            self.cash -= quantity * event.fill_price + commission
            cash_flow = -(quantity * event.fill_price + commission)
        else:
            quantity = min(quantity, self.positions[event.symbol])
            if quantity <= 0:
                self._reject(event.order_id, event.symbol, event.quantity, "no_position_to_sell")
                self._set_order_status(event.order_id, "rejected")
                return
            commission = event.commission * quantity / event.quantity
            self.positions[event.symbol] -= quantity
            self.cash += quantity * event.fill_price - commission
            cash_flow = quantity * event.fill_price - commission

        slippage_cost = abs(event.fill_price - event.reference_price) * quantity
        record = {
            "order_id": event.order_id,
            "submitted_dt": event.submitted_dt,
            "fill_dt": event.dt,
            "symbol": event.symbol,
            "direction": event.direction,
            "quantity": quantity,
            "reference_price": event.reference_price,
            "fill_price": event.fill_price,
            "commission": commission,
            "slippage_cost": slippage_cost,
            "cash_flow": cash_flow,
        }
        self.fills.append(record)
        self.trades.append(record.copy())
        self._set_order_status(event.order_id, "filled" if quantity == event.quantity else "partially_filled")

    def mark_to_market(self, event) -> None:
        equity = self._equity()
        self.equity_curve.append({"dt": event.dt, "equity": equity})
        self.cash_ledger.append(
            {"dt": event.dt, "cash": self.cash, "reserved_cash": self.reserved_cash, "equity": equity}
        )
        for symbol in self.symbols:
            close = self.data.get_latest_close(symbol)
            self.positions_ledger.append(
                {
                    "dt": event.dt,
                    "symbol": symbol,
                    "quantity": self.positions[symbol],
                    "close": close,
                    "market_value": self.positions[symbol] * close,
                }
            )

    def cancel_order(self, order, reason="end_of_data") -> None:
        reservation = self._reservations.pop(order.order_id, 0.0)
        self.reserved_cash = max(0.0, self.reserved_cash - reservation)
        self._set_order_status(order.order_id, "cancelled")
        self._reject(order.order_id, order.symbol, order.quantity, reason)

    def _set_order_status(self, order_id, status) -> None:
        for order in self.orders:
            if order["order_id"] == order_id:
                order["status"] = status
                return

    def _reject(self, order_id, symbol, quantity, reason) -> None:
        self.rejections.append(
            {
                "dt": self.data.current_dt,
                "order_id": order_id,
                "symbol": symbol,
                "quantity": quantity,
                "reason": reason,
            }
        )
