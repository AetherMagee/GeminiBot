from typing import List


def sparkline(numbers: List[float]) -> str:
    bars = "▁▂▃▄▅▆▇█"
    if not numbers:
        return ""
    mn, mx = min(numbers), max(numbers)
    extent = mx - mn
    if extent == 0:
        return bars[0] * len(numbers)
    return "".join(bars[int((n - mn) / extent * (len(bars) - 1))] for n in numbers)
