import numpy as np

class SlidingAudioBuffer:
    def __init__(self, window_samples: int):
        self.window_samples = window_samples
        self.buffer = None
        self.filled = 0

    def push(self, block: np.ndarray):
        """
        block shape : (Nsamp, Nch)
        """
        ns, nch = block.shape

        if self.buffer is None:
            self.buffer = np.zeros((self.window_samples, nch), dtype=np.float64)

        if ns >= self.window_samples:
            self.buffer[:, :] = block[-self.window_samples:, :]
            self.filled = self.window_samples
        else:
            if ns > 0:
                self.buffer = np.roll(self.buffer, -ns, axis=0)
                self.buffer[-ns:, :] = block
                self.filled = min(self.window_samples, self.filled + ns)

    @property
    def ready(self):
        return self.filled >= self.window_samples

    def get_window_channels_first(self):
        """
        Retourne shape (Nch, Nsamp)
        """
        return self.buffer.T