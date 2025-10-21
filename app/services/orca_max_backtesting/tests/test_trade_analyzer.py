import csv
import os
import unittest

from app.services.orca_max_backtesting.trade_analyzer import TradeAnalyzer
from app.utils.decorators.timing.time import time_it

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@time_it
def read_csv(filename):
    """Reads the CSV file and loads data."""
    with open(filename, mode="r", newline="") as csvfile:
        csv_reader = csv.DictReader(csvfile)
        _data = list(csv_reader)
    return _data


class TestTradeAnalyzer(unittest.TestCase):

    def setUp(self):
        # Example data for testing
        self.data = read_csv(
            os.path.join(
                FIXTURES_DIR, "input/BreakThrough_long_20_7_20240824_114001.csv"
            )
        )
        self.max_consecutive_reach = 3
        self.tp = 400  # Example: Take Profit amount
        self.sl = 140  # Example: Stop Loss amount
        self.analyzer = TradeAnalyzer(
            self.data, self.max_consecutive_reach, self.tp, self.sl, 20
        )

    def test_clean_and_sort_data(self):
        expected_sorted_data = read_csv(
            os.path.join(
                FIXTURES_DIR,
                "output /cleand_BreakThrough_long_20_7_20240824_114001.csv",
            )
        )
        self.assertEqual(self.analyzer.sorted_data, expected_sorted_data)

    def test_calculate_profit(self):
        expected_results = {
            3: {
                "win": 21,
                "lost": 28,
                "Won_amount": 8400,
                "Lost_amount": 3920,
                "Total": 4480,
            },
            2: {
                "win": 15,
                "lost": 20,
                "Won_amount": 6000,
                "Lost_amount": 2800,
                "Total": 3200,
            },
        }
        results = self.analyzer.calculate_profit()
        self.assertEqual(results, expected_results)


if __name__ == "__main__":
    unittest.main()
