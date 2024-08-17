class FloatRange:
    def __init__(self, start, stop=None, step=1.0):
        if stop is None:
            self.start, self.stop = 0.0, start
        else:
            self.start, self.stop = start, stop
        self.step = step

        if self.step == 0:
            raise ValueError("Step cannot be zero")

        epsilon = 1e-10
        self.length = max(0, int((self.stop - self.start + epsilon) / self.step) + 1)

    def __len__(self):
        return self.length

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]

        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("FloatRange index out of range")

        value = self.start + index * self.step
        return min(value, self.stop)

    def __iter__(self):
        return (self[i] for i in range(len(self)))


def frange(start, stop=None, step=1.0):
    return FloatRange(start, stop, step)
