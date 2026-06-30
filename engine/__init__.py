"""Regulation-correct FIFA World Cup 2026 tournament engine."""
from .bracket import build_official_bracket
from .groups import rank_group, rank_third_placed
from .third_place import allocate_third_placed
__all__ = ["allocate_third_placed", "build_official_bracket", "rank_group", "rank_third_placed"]
