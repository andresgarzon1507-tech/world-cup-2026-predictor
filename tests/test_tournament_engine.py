import unittest
from itertools import combinations

from engine.bracket import build_official_bracket, source_local_matches
from engine.groups import rank_group, rank_third_placed
from engine.third_place import allocate_third_placed, annex_c


class TournamentEngineTests(unittest.TestCase):
    def test_annex_c_contains_every_combination(self):
        table = annex_c()
        expected = {frozenset(value) for value in combinations("ABCDEFGHIJKL", 8)}
        self.assertEqual(495, len(table))
        self.assertEqual(expected, set(table))
        for qualified, allocation in table.items():
            self.assertEqual(qualified, set(allocation.values()))

    def test_annex_c_known_final_row(self):
        thirds = [{"group": group, "team": f"Third {group}"} for group in "ABCDEFGH"]
        allocation = allocate_third_placed(thirds)
        self.assertEqual("Third H", allocation["3A"])
        self.assertEqual("Third G", allocation["3B"])
        self.assertEqual("Third B", allocation["3D"])
        self.assertEqual("Third C", allocation["3E"])
        self.assertEqual("Third A", allocation["3G"])
        self.assertEqual("Third F", allocation["3I"])
        self.assertEqual("Third D", allocation["3K"])
        self.assertEqual("Third E", allocation["3L"])

    def test_official_bracket_and_dependencies(self):
        slots = {f"{position}{group}": f"{position}{group}"
                 for group in "ABCDEFGHIJKL" for position in (1, 2)}
        thirds = [{"group": group, "team": f"3{group}"} for group in "ABCDEFGH"]
        matches = {match.number: match for match in build_official_bracket(slots, thirds)}
        self.assertEqual(("2A", "2B"), (matches[73].home, matches[73].away))
        self.assertEqual(("1E", "3C"), (matches[74].home, matches[74].away))
        self.assertEqual((2, 5), source_local_matches("r16", 1))
        self.assertEqual((1, 3), source_local_matches("r16", 2))
        self.assertEqual((1, 2), source_local_matches("qf", 1))

    def test_head_to_head_precedes_overall_goal_difference(self):
        matches = [
            {"home_team":"A","away_team":"B","home_goals":1,"away_goals":0,"played":1},
            {"home_team":"A","away_team":"C","home_goals":0,"away_goals":5,"played":1},
            {"home_team":"A","away_team":"D","home_goals":1,"away_goals":0,"played":1},
            {"home_team":"B","away_team":"C","home_goals":3,"away_goals":0,"played":1},
            {"home_team":"B","away_team":"D","home_goals":3,"away_goals":0,"played":1},
            {"home_team":"C","away_team":"D","home_goals":1,"away_goals":0,"played":1},
        ]
        ranked = rank_group(["A","B","C","D"], matches)
        order = [row.team for row in ranked]
        self.assertLess(order.index("B"), order.index("A"))

    def test_third_place_ranking_uses_conduct_then_fifa_ranking(self):
        thirds = [
            {"team":"A","pts":4,"gd":0,"gf":2,"conduct":-3},
            {"team":"B","pts":4,"gd":0,"gf":2,"conduct":-1},
            {"team":"C","pts":4,"gd":0,"gf":2,"conduct":-1},
        ]
        ranked = rank_third_placed(thirds, fifa_ranking={"B":10,"C":20})
        self.assertEqual(["C","B","A"], [row["team"] for row in ranked])


if __name__ == "__main__":
    unittest.main()
