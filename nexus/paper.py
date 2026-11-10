import math


class PaperWallet:
    def __init__(self, cash=10000.0):
        cash = float(cash)
        if not math.isfinite(cash) or cash < 0:
            raise ValueError("Initial virtual cash must be a finite non-negative number")
        self.cash = cash
        self.positions = {}

    @staticmethod
    def _validate_order(symbol, quantity, price):
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Symbol must be a non-empty string")
        quantity = float(quantity)
        price = float(price)
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be a finite positive number")
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Price must be a finite positive number")
        return symbol.strip(), quantity, price

    def buy(self, symbol, quantity, price):
        symbol, quantity, price = self._validate_order(symbol, quantity, price)
        cost = quantity * price
        if not math.isfinite(cost) or cost > self.cash:
            raise ValueError("Insufficient virtual cash or invalid order value")
        self.cash -= cost
        self.positions[symbol] = self.positions.get(symbol, 0.0) + quantity

    def sell(self, symbol, quantity, price):
        symbol, quantity, price = self._validate_order(symbol, quantity, price)
        held = self.positions.get(symbol, 0.0)
        if quantity > held:
            raise ValueError("Insufficient position")
        proceeds = quantity * price
        if not math.isfinite(proceeds):
            raise ValueError("Invalid order value")
        remaining = held - quantity
        if remaining <= 1e-12:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = remaining
        self.cash += proceeds
