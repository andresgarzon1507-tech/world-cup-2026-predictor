import tempfile
import unittest
from pathlib import Path

from data import database


class DatabaseCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database.DB_PATH = str(Path(self.temp.name) / "test.db")
        database.init_database()
        database.init_ko_matches()
        database.update_ko_teams("r32", 1, "A", "B")

    def tearDown(self):
        self.temp.cleanup()

    def test_tie_requires_penalty_winner(self):
        with self.assertRaises(ValueError):
            database.save_ko_result("r32", 1, 1, 1)
        database.save_ko_result("r32", 1, 1, 1,
                                winner_team="B", decided_by="penalties")
        self.assertEqual("B", database.get_ko_winner("r32", 1))

    def test_changing_teams_clears_old_result(self):
        database.save_ko_result("r32", 1, 2, 0)
        database.update_ko_teams("r32", 1, "C", "D")
        match = database.get_ko_matches("r32")[0]
        self.assertEqual(0, match["played"])
        self.assertIsNone(match["winner_team"])


if __name__ == "__main__":
    unittest.main()
