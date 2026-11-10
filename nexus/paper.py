class PaperWallet:
    def __init__(self, cash=10000.0):
        self.cash = float(cash)
        self.positions = {}

    def buy(self, symbol, quantity, price):
        cost = float(quantity) * float(price)
        if cost > self.cash:
            raise ValueError("Insufficient virtual cash")
        self.cash -= cost
        self.positions[symbol] = self.positions.get(symbol, 0.0) + float(quantity)

    def sell(self, symbol, quantity, price):
        quantity = float(quantity)
        held = self.positions.get(symbol, 0.0)
        if quantity > held:
            raise ValueError("Insufficient position")
        self.positions[symbol] = held - quantity
        self.cash += quantity * float(price)
