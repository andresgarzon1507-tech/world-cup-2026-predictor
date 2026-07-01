import unittest

from models.prediction_engine import (
    exact_score_probs,
    match_probabilities_dc,
    score_matrix_dc,
)


class ScoreModelTests(unittest.TestCase):
    def test_dixon_coles_matrix_is_normalized(self):
        matrix = score_matrix_dc(0.82, 0.74)
        self.assertAlmostEqual(1.0, sum(matrix.values()), places=10)

    def test_match_probabilities_use_the_same_score_matrix(self):
        matrix = score_matrix_dc(0.82, 0.74)
        expected = (
            sum(p for (h, a), p in matrix.items() if h > a),
            sum(p for (h, a), p in matrix.items() if h == a),
            sum(p for (h, a), p in matrix.items() if h < a),
        )
        actual = match_probabilities_dc(0.82, 0.74)
        for actual_value, expected_value in zip(actual, expected):
            self.assertAlmostEqual(expected_value, actual_value, places=10)

    def test_exact_scores_apply_dixon_coles_correction(self):
        corrected = {
            row["score"]: row["prob"]
            for row in exact_score_probs(0.82, 0.74, top_n=81)
        }
        independent = {
            row["score"]: row["prob"]
            for row in exact_score_probs(
                0.82,
                0.74,
                top_n=81,
                rho=0.0,
            )
        }
        self.assertNotEqual(corrected["0-0"], independent["0-0"])
        self.assertNotEqual(corrected["1-1"], independent["1-1"])


if __name__ == "__main__":
    unittest.main()
