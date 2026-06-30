"""FIFA 2026 group and best-third ranking rules."""
from collections import defaultdict
from dataclasses import replace
from .models import Standing

def team_conduct_score(yellow=0, indirect_red=0, direct_red=0, yellow_then_direct=0):
    return -(yellow + 3 * indirect_red + 4 * direct_red + 5 * yellow_then_direct)

def calculate_table(teams, matches, conduct=None):
    conduct = conduct or {}
    table = {team: Standing(team=team, conduct=conduct.get(team, 0)) for team in teams}
    for match in matches:
        if not match.get("played"):
            continue
        home, away = match["home_team"], match["away_team"]
        if home not in table or away not in table:
            continue
        hg, ag = int(match["home_goals"]), int(match["away_goals"])
        h, a = table[home], table[away]
        hk = dict(played=h.played+1, goals_for=h.goals_for+hg, goals_against=h.goals_against+ag)
        ak = dict(played=a.played+1, goals_for=a.goals_for+ag, goals_against=a.goals_against+hg)
        if hg > ag:
            hk.update(won=h.won+1, points=h.points+3); ak.update(lost=a.lost+1)
        elif hg < ag:
            ak.update(won=a.won+1, points=a.points+3); hk.update(lost=h.lost+1)
        else:
            hk.update(drawn=h.drawn+1, points=h.points+1)
            ak.update(drawn=a.drawn+1, points=a.points+1)
        table[home], table[away] = replace(h, **hk), replace(a, **ak)
    return table

def _h2h(team, tied, matches):
    pts = gf = ga = 0
    for match in matches:
        if not match.get("played"):
            continue
        h, a = match["home_team"], match["away_team"]
        if h not in tied or a not in tied or team not in (h, a):
            continue
        hg, ag = int(match["home_goals"]), int(match["away_goals"])
        own, other = (hg, ag) if team == h else (ag, hg)
        gf += own; ga += other; pts += 3 if own > other else 1 if own == other else 0
    return pts, gf-ga, gf

def rank_group(teams, matches, *, conduct=None, fifa_ranking=None):
    """Article 13: head-to-head, overall GD/GF, conduct, then FIFA ranking."""
    matches, fifa_ranking = list(matches), fifa_ranking or {}
    table = calculate_table(teams, matches, conduct)
    buckets = defaultdict(list)
    for team, row in table.items():
        buckets[row.points].append(team)
    ordered = []
    for points in sorted(buckets, reverse=True):
        tied = set(buckets[points])
        ordered.extend(sorted(tied, key=lambda team: (
            _h2h(team, tied, matches), table[team].goal_difference,
            table[team].goals_for, table[team].conduct,
            fifa_ranking.get(team, float("-inf"))), reverse=True))
    return [table[team] for team in ordered]

def rank_third_placed(thirds, *, fifa_ranking=None):
    fifa_ranking = fifa_ranking or {}
    def value(row, attr, key):
        return getattr(row, attr) if isinstance(row, Standing) else row.get(key, 0)
    def team(row):
        return row.team if isinstance(row, Standing) else row["team"]
    return sorted(thirds, key=lambda row: (
        value(row,"points","pts"), value(row,"goal_difference","gd"),
        value(row,"goals_for","gf"), value(row,"conduct","conduct"),
        fifa_ranking.get(team(row), float("-inf"))), reverse=True)


def aggregate_conduct(matches, match_stats):
    """Aggregate stored FIFA conduct points for the teams in these matches."""
    result = defaultdict(int)
    match_stats = match_stats or {}
    for match in matches:
        stats = match_stats.get(match.get("id"))
        if not match.get("played") or not stats:
            continue
        for side, team in (("home", match["home_team"]), ("away", match["away_team"])):
            explicit = stats.get(f"{side}_conduct_score")
            if explicit is not None:
                result[team] += int(explicit)
            else:
                result[team] += team_conduct_score(
                    yellow=int(stats.get(f"{side}_yellows") or 0),
                    direct_red=int(stats.get(f"{side}_reds") or 0),
                )
    return dict(result)
