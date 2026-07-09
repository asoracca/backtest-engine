"""Event types that flow through the backtest queue."""


class MarketEvent:
    def __init__(self):
        self.type = "MARKET"


class SignalEvent:
    def __init__(self, symbol, dt, direction):
        self.type = "SIGNAL"
        self.symbol = symbol
        self.dt = dt
        self.direction = direction  # LONG, EXIT (SHORT reserved)


class OrderEvent:
    def __init__(self, symbol, quantity, direction, order_type="MKT"):
        self.type = "ORDER"
        self.symbol = symbol
        self.quantity = int(quantity)
        self.direction = direction  # BUY / SELL
        self.order_type = order_type


class FillEvent:
    def __init__(self, dt, symbol, quantity, direction, fill_price, commission):
        self.type = "FILL"
        self.dt = dt
        self.symbol = symbol
        self.quantity = int(quantity)
        self.direction = direction
        self.fill_price = float(fill_price)
        self.commission = float(commission)
