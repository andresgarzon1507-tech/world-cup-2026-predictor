from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Standing:
    team: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    conduct: int = 0

    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against

    def as_dict(self):
        return {"team": self.team, "played": self.played, "won": self.won,
                "drawn": self.drawn, "lost": self.lost, "gf": self.goals_for,
                "ga": self.goals_against, "gd": self.goal_difference,
                "pts": self.points, "conduct": self.conduct}

@dataclass(frozen=True, slots=True)
class BracketMatch:
    number: int
    phase: str
    home: str | None
    away: str | None
    home_source: str
    away_source: str
