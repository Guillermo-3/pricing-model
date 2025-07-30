class Kalman1D:
    """
    A simple 1-dimensional Kalman filter.
    Used to fuse multiple noisy measurements of a single state (the fair price).
    """
    def __init__(self, q_process: float = 1e-5):
        """
        Args:
            q_process: Process noise. Represents the variance of the random walk
                       of the state between steps. A higher q means the filter
                       adapts to new measurements faster.
        """
        self.v: float | None = None  
        self.P: float = 1.0          # State variance (our uncertainty about v)
        self.q: float = q_process    

    def step(self, measurements: list[tuple[float, float]]) -> tuple[float | None, float]:
        """
        Performs a full predict-update cycle for a list of new measurements.

        Args:
            measurements: A list of (y, R) tuples, where y is the measurement
                          (e.g., a venue's mid-price) and R is the measurement
                          noise variance for that y.

        Returns:
            A tuple of (new state v, new variance P).
        """
        if not measurements:
            return self.v, self.P

        if self.v is None:
            self.v = measurements[0][0]
            self.P = measurements[0][1]
            measurements = measurements[1:]

        # predict step -> The state evolves by a random walk.
        # Our best guess for the next state is the current state.
        # Our uncertainty increases by the process noise.
        v_hat = self.v
        P_hat = self.P + self.q

        # 2. Update step: Sequentially update with each new measurement.
        v, P = v_hat, P_hat
        for y, R in measurements:
            # K is the Kalman Gain. determines how much we trust the new
            # measurement vs our prediction. If R is large, K is small.
            K = P / (P + R)
            
            # updte the state by blending the prediction and the measurement
            v = v + K * (y - v)
            
            # udate our uncertainty
            P = (1 - K) * P

        self.v, self.P = v, P
        return self.v, self.P