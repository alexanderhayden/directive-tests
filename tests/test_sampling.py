import unittest

from harness.sampling import run_with_retries


class SamplingTests(unittest.TestCase):
    def test_retry_failures_are_preserved(self):
        calls = 0
        sleeps = []

        def operation():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError(f"failure-{calls}")
            return "ok"

        outcome = run_with_retries(
            operation, max_attempts=4, retryable=(RuntimeError,), sleeper=sleeps.append
        )
        self.assertEqual(outcome.value, "ok")
        self.assertEqual(outcome.attempts, 3)
        self.assertEqual([row["error"] for row in outcome.failures], ["failure-1", "failure-2"])
        self.assertEqual(sleeps, [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
