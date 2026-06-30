import unittest

from data.tournament_data import GROUP_FIXTURES
from models.prediction_engine import run_monte_carlo


class MonteCarloTests(unittest.TestCase):
    def test_probabilities_and_phase_progression(self):
        matches = []
        identifier = 1
        for group, fixtures in GROUP_FIXTURES.items():
            for home, away in fixtures:
                matches.append({"id": identifier, "phase": "groups",
                                "group_letter": group, "match_number": identifier,
                                "home_team": home, "away_team": away,
                                "home_goals": None, "away_goals": None, "played": 0})
                identifier += 1
        result = run_monte_carlo(matches, n_sims=20, seed=7)
        self.assertAlmostEqual(100.0, sum(row["prob"] for row in result["champion_probs"]), delta=2.0)
        for phases in result["phase_probs"].values():
            values = [phases[key] for key in ("r32","r16","qf","sf","final","champion")]
            self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(list(range(73, 89)),
                         [row["number"] for row in result["projected_r32"]])


if __name__ == "__main__":
    unittest.main()
