import math

class EWMA:
    """
    Exponentially Weighted Moving Average (EWMA) calculator.
    Used for calculating volatility (the EWMA of squared returns).
    """
    def __init__(self, halflife_s: float, initial_val: float = 0.0):
        """
        Args:
            halflife_s: The half-life of the average in seconds.
            initial_val: The starting value for the EWMA.
        """
        # alpha is our decay factor, calculated from the half-life
        self.alpha = 1.0 - math.exp(math.log(0.5) / (halflife_s if halflife_s > 0 else 1.0))
        self.val = initial_val
        self.is_warmed_up = False

    def update(self, new_point: float) -> float:
        """Updates the EWMA with a new data point."""
        if not self.is_warmed_up:
            self.val = new_point
            self.is_warmed_up = True
        else:
            self.val = self.alpha * new_point + (1.0 - self.alpha) * self.val
        return self.val