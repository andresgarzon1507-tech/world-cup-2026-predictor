from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class KnockoutResult:
    home_goals: int
    away_goals: int
    winner: str
    decided_by: str = "regular"

def validate_knockout_result(home, away, result):
    if result.winner not in (home, away):
        raise ValueError("Winner is not a participant")
    if result.home_goals == result.away_goals and result.decided_by != "penalties":
        raise ValueError("A tied knockout score requires a penalty winner")
    if result.home_goals != result.away_goals:
        score_winner = home if result.home_goals > result.away_goals else away
        if result.winner != score_winner:
            raise ValueError("Winner contradicts score")
