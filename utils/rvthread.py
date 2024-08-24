import sys
import threading


class ReturnValueThread(threading.Thread):
    def __init__(self, target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = None
        self.target = target

    def run(self):
        if not self.target:
            return
        try:
            self.result = self.target(*self._args, **self._kwargs)
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
