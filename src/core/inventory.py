class InventoryManager:
    """
    A simple class to track inventory for different symbols.
    """
    def __init__(self):
        self.inventory: dict[str, float] = {}

    def get(self, symbol: str) -> float:
        """Gets the current inventory for a symbol."""
        return self.inventory.get(symbol, 0.0)

    def update(self, symbol: str, quantity: float, side: int):
        """
        Updates inventory based on a fill.
        
        Args:
            symbol: The trading symbol.
            quantity: The amount filled.
            side: +1 if we sold (inventory decreases), -1 if we bought (inventory increases).
        """
        # If we sold (side=+1), our inventory of the base asset decreases.
        # If we bought (side=-1), our inventory of the base asset increases.
        change = -side * quantity
        self.inventory[symbol] = self.get(symbol) + change
