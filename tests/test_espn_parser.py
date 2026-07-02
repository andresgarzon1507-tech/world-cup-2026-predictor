import unittest

from models.espn_parser import parse_statistics, teams_match


class EspnParserTests(unittest.TestCase):
    def test_curazao_alias_matches_espn(self):
        self.assertTrue(teams_match("Curazao", "Curaçao"))

    def test_bosnia_alias_matches_hyphenated_espn_name(self):
        self.assertTrue(
            teams_match("Bosnia y Herzegovina", "Bosnia-Herzegovina")
        )

    def test_statistics_fallback_from_header_competitors(self):
        summary = {"header": {"competitions": [{"competitors": [
            {"homeAway": "home", "team": {"displayName": "Germany"},
             "statistics": [
                 {"label": "totalShots", "displayValue": "22"},
                 {"name": "shotsOnTarget", "displayValue": "12"},
                 {"name": "possessionPct", "displayValue": "68.5"}]},
            {"homeAway": "away", "team": {"displayName": "Curaçao"},
             "statistics": [
                 {"name": "totalShots", "displayValue": "6"},
                 {"name": "shotsOnTarget", "displayValue": "2"},
                 {"name": "possessionPct", "displayValue": "31.5"}]}
        ]}]}}
        stats = parse_statistics(summary, "Alemania")
        self.assertEqual(22, stats["home_shots"])
        self.assertEqual(2, stats["away_shots_on"])
        self.assertEqual(68.5, stats["home_possession"])

    def test_unknown_statistics_are_not_reported_as_success(self):
        summary = {"boxscore": {"teams": [
            {"team": {"displayName": "Germany"}, "statistics": []},
            {"team": {"displayName": "Curaçao"}, "statistics": []},
        ]}}
        self.assertIsNone(parse_statistics(summary, "Alemania"))


if __name__ == "__main__":
    unittest.main()
