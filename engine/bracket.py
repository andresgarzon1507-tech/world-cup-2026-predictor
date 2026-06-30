"""Single source of truth for FIFA World Cup 2026 knockout matches."""
from .models import BracketMatch
from .third_place import allocate_third_placed
R32_SOURCES={73:("2A","2B"),74:("1E","3E"),75:("1F","2C"),76:("1C","2F"),
77:("1I","3I"),78:("2E","2I"),79:("1A","3A"),80:("1L","3L"),
81:("1D","3D"),82:("1G","3G"),83:("2K","2L"),84:("1H","2J"),
85:("1B","3B"),86:("1J","2H"),87:("1K","3K"),88:("2D","2G")}
DEPENDENCIES={89:(74,77),90:(73,75),91:(76,78),92:(79,80),93:(83,84),
94:(81,82),95:(86,88),96:(85,87),97:(89,90),98:(93,94),99:(91,92),
100:(95,96),101:(97,98),102:(99,100),104:(101,102)}

def build_official_bracket(group_slots, qualified_thirds, *, winners=None, losers=None):
    winners, losers = winners or {}, losers or {}
    slots = dict(group_slots); slots.update(allocate_third_placed(qualified_thirds))
    matches = [BracketMatch(n,"r32",slots.get(h),slots.get(a),h,a)
               for n,(h,a) in R32_SOURCES.items()]
    def phase(n): return "r16" if n<97 else "qf" if n<101 else "sf" if n<103 else "final"
    matches += [BracketMatch(n,phase(n),winners.get(h),winners.get(a),f"W{h}",f"W{a}")
                for n,(h,a) in DEPENDENCIES.items()]
    matches.append(BracketMatch(103,"third_place",losers.get(101),losers.get(102),"L101","L102"))
    return sorted(matches,key=lambda m:m.number)

def local_to_fifa_match(phase, number):
    return {"r32":72,"r16":88,"qf":96,"sf":100,"third_place":102,"final":103}[phase]+number

PHASE_START = {"r32":72,"r16":88,"qf":96,"sf":100,"third_place":102,"final":103}

def source_local_matches(phase, number):
    """Return previous-phase local match numbers feeding a knockout match."""
    fifa_number = PHASE_START[phase] + number
    sources = (101, 102) if fifa_number == 103 else DEPENDENCIES[fifa_number]
    previous = {"r16":"r32","qf":"r16","sf":"qf","final":"sf","third_place":"sf"}[phase]
    return tuple(source - PHASE_START[previous] for source in sources)

