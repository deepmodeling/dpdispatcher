import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
__package__ = 'tests'
from .context import retry, RetrySignal

class TestRetry(unittest.TestCase):
    def test_retry_fail(self):
        """Always retry"""
        @retry(max_retry=3, sleep=0.05, catch_exception=RetrySignal)
        def some_method():
            raise RetrySignal("Failed to do something")
        with self.assertRaises(RuntimeError):
            some_method()

    def test_retry_success(self):
        """Retry less than 3 times"""
        retry_times = [0]

        @retry(max_retry=3, sleep=0.05, catch_exception=RetrySignal)
        def some_method(retry_times):
            if retry_times[0] < 2:
                retry_times[0] += 1
                raise RetrySignal("Failed to do something")
        some_method(retry_times)
