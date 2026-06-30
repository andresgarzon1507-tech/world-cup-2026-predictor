"""Official Annex C allocation of the eight best third-placed teams."""
import json
from functools import lru_cache
from itertools import combinations
from pathlib import Path
GROUP_WINNERS = ("A","B","D","E","G","I","K","L")

@lru_cache(maxsize=1)
def annex_c():
    rows = json.loads(Path(__file__).with_name("annex_c.json").read_text(encoding="utf-8"))
    table = {}
    for row in rows:
        allocation = [cell.removeprefix("3") for cell in row[-8:]]
        groups = frozenset(cell for cell in row[1:-8] if len(cell) == 1 and cell in "ABCDEFGHIJKL")
        if len(groups) != 8 or len(set(allocation)) != 8:
            raise ValueError(f"Invalid Annex C row {row[0]}")
        table[groups] = dict(zip(GROUP_WINNERS, allocation, strict=True))
    expected = {frozenset(c) for c in combinations("ABCDEFGHIJKL", 8)}
    if len(table) != 495 or set(table) != expected:
        raise ValueError("Annex C must contain all 495 combinations")
    return table

def allocate_third_placed(thirds):
    thirds = list(thirds)
    by_group = {row["group"]: row["team"] for row in thirds}
    if len(thirds) != 8 or len(by_group) != 8:
        raise ValueError("Exactly eight thirds from distinct groups are required")
    allocation = annex_c()[frozenset(by_group)]
    return {f"3{winner}": by_group[third] for winner, third in allocation.items()}
