# data/tournament_data.py

TOURNAMENT = {
    "name": "FIFA World Cup 2026",
    "edition": 2026,
    "hosts": ["México", "Estados Unidos", "Canadá"],
    "final_date": "2026-07-19",
    "final_venue": "MetLife Stadium, New Jersey",
}

GROUPS = {
    "A": ["México",        "Sudáfrica",           "Corea del Sur", "Chequia"],
    "B": ["Canadá",        "Bosnia y Herzegovina", "Qatar",         "Suiza"],
    "C": ["Brasil",        "Marruecos",            "Haití",         "Escocia"],
    "D": ["Estados Unidos","Paraguay",             "Australia",     "Turquía"],
    "E": ["Alemania",      "Curazao",              "Costa de Marfil","Ecuador"],
    "F": ["Países Bajos",  "Japón",                "Suecia",        "Túnez"],
    "G": ["Bélgica",       "Egipto",               "IR Irán",       "Nueva Zelanda"],
    "H": ["España",        "Cabo Verde",           "Arabia Saudí",  "Uruguay"],
    "I": ["Francia",       "Senegal",              "Iraq",          "Noruega"],
    "J": ["Argentina",     "Argelia",              "Austria",       "Jordania"],
    "K": ["Portugal",      "Congo DR",             "Uzbekistán",    "Colombia"],
    "L": ["Inglaterra",    "Croacia",              "Ghana",         "Panamá"],
}

# Hosts get home advantage boost
HOST_TEAMS = {"México", "Estados Unidos", "Canadá"}
HOST_BOOST = 0.06   # +6% boost en rating efectivo cuando juegan en su país

# Ratings FIFA base — escala log-odds para mayor separación entre equipos
# Se mapean a lambda de goles via función exponencial (ver engine)
FIFA_RATINGS = {
    "Argentina":             0.950,
    "Francia":               0.930,
    "España":                0.910,
    "Inglaterra":            0.890,
    "Brasil":                0.880,
    "Portugal":              0.870,
    "Países Bajos":          0.850,
    "Alemania":              0.840,
    "Bélgica":               0.820,
    "Uruguay":               0.800,
    "Colombia":              0.780,
    "México":                0.760,
    "Marruecos":             0.750,
    "Suiza":                 0.740,
    "Croacia":               0.730,
    "Senegal":               0.720,
    "Japón":                 0.710,
    "Estados Unidos":        0.700,
    "Ecuador":               0.680,
    "Corea del Sur":         0.670,
    "Turquía":               0.660,
    "Austria":               0.650,
    "Suecia":                0.640,
    "Costa de Marfil":       0.630,
    "Australia":             0.620,
    "Noruega":               0.610,
    "Canadá":                0.600,
    "Ghana":                 0.590,
    "IR Irán":               0.580,
    "Paraguay":              0.570,
    "Escocia":               0.560,
    "Túnez":                 0.550,
    "Bosnia y Herzegovina":  0.540,
    "Egipto":                0.530,
    "Arabia Saudí":          0.520,
    "Argelia":               0.510,
    "Chequia":               0.500,
    "Sudáfrica":             0.480,
    "Panamá":                0.460,
    "Jordania":              0.450,
    "Qatar":                 0.440,
    "Iraq":                  0.430,
    "Uzbekistán":            0.420,
    "Cabo Verde":            0.400,
    "Congo DR":              0.390,
    "Haití":                 0.370,
    "Curazao":               0.350,
    "Nueva Zelanda":         0.340,
}

FLAGS = {
    "México":"🇲🇽","Sudáfrica":"🇿🇦","Corea del Sur":"🇰🇷","Chequia":"🇨🇿",
    "Canadá":"🇨🇦","Bosnia y Herzegovina":"🇧🇦","Qatar":"🇶🇦","Suiza":"🇨🇭",
    "Brasil":"🇧🇷","Marruecos":"🇲🇦","Haití":"🇭🇹","Escocia":"🏴",
    "Estados Unidos":"🇺🇸","Paraguay":"🇵🇾","Australia":"🇦🇺","Turquía":"🇹🇷",
    "Alemania":"🇩🇪","Curazao":"🇨🇼","Costa de Marfil":"🇨🇮","Ecuador":"🇪🇨",
    "Países Bajos":"🇳🇱","Japón":"🇯🇵","Suecia":"🇸🇪","Túnez":"🇹🇳",
    "Bélgica":"🇧🇪","Egipto":"🇪🇬","IR Irán":"🇮🇷","Nueva Zelanda":"🇳🇿",
    "España":"🇪🇸","Cabo Verde":"🇨🇻","Arabia Saudí":"🇸🇦","Uruguay":"🇺🇾",
    "Francia":"🇫🇷","Senegal":"🇸🇳","Iraq":"🇮🇶","Noruega":"🇳🇴",
    "Argentina":"🇦🇷","Argelia":"🇩🇿","Austria":"🇦🇹","Jordania":"🇯🇴",
    "Portugal":"🇵🇹","Congo DR":"🇨🇩","Uzbekistán":"🇺🇿","Colombia":"🇨🇴",
    "Inglaterra":"🏴","Croacia":"🇭🇷","Ghana":"🇬🇭","Panamá":"🇵🇦",
}

GROUP_FIXTURES = {
    "A": [("México","Sudáfrica"),("Corea del Sur","Chequia"),
          ("México","Corea del Sur"),("Sudáfrica","Chequia"),
          ("México","Chequia"),("Sudáfrica","Corea del Sur")],
    "B": [("Canadá","Bosnia y Herzegovina"),("Qatar","Suiza"),
          ("Canadá","Qatar"),("Bosnia y Herzegovina","Suiza"),
          ("Canadá","Suiza"),("Bosnia y Herzegovina","Qatar")],
    "C": [("Brasil","Marruecos"),("Haití","Escocia"),
          ("Brasil","Haití"),("Marruecos","Escocia"),
          ("Brasil","Escocia"),("Marruecos","Haití")],
    "D": [("Estados Unidos","Paraguay"),("Australia","Turquía"),
          ("Estados Unidos","Australia"),("Paraguay","Turquía"),
          ("Estados Unidos","Turquía"),("Paraguay","Australia")],
    "E": [("Alemania","Curazao"),("Costa de Marfil","Ecuador"),
          ("Alemania","Costa de Marfil"),("Curazao","Ecuador"),
          ("Alemania","Ecuador"),("Curazao","Costa de Marfil")],
    "F": [("Países Bajos","Japón"),("Suecia","Túnez"),
          ("Países Bajos","Suecia"),("Japón","Túnez"),
          ("Países Bajos","Túnez"),("Japón","Suecia")],
    "G": [("Bélgica","Egipto"),("IR Irán","Nueva Zelanda"),
          ("Bélgica","IR Irán"),("Egipto","Nueva Zelanda"),
          ("Bélgica","Nueva Zelanda"),("Egipto","IR Irán")],
    "H": [("España","Cabo Verde"),("Arabia Saudí","Uruguay"),
          ("España","Arabia Saudí"),("Cabo Verde","Uruguay"),
          ("España","Uruguay"),("Cabo Verde","Arabia Saudí")],
    "I": [("Francia","Senegal"),("Iraq","Noruega"),
          ("Francia","Iraq"),("Senegal","Noruega"),
          ("Francia","Noruega"),("Senegal","Iraq")],
    "J": [("Argentina","Argelia"),("Austria","Jordania"),
          ("Argentina","Austria"),("Argelia","Jordania"),
          ("Argentina","Jordania"),("Argelia","Austria")],
    "K": [("Portugal","Congo DR"),("Uzbekistán","Colombia"),
          ("Portugal","Uzbekistán"),("Congo DR","Colombia"),
          ("Portugal","Colombia"),("Congo DR","Uzbekistán")],
    "L": [("Inglaterra","Croacia"),("Ghana","Panamá"),
          ("Inglaterra","Ghana"),("Croacia","Panamá"),
          ("Inglaterra","Panamá"),("Croacia","Ghana")],
}

# Ronda de 32 (Dieciseisavos de Final) — cruces OFICIALES FIFA World Cup 2026
# Fuente: fixture impreso oficial del torneo.
# Slots "1X"/"2X" = 1° y 2° del grupo X.
# Slots "3-(...)"  = mejor tercero clasificado ENTRE los grupos listados
#                    (sistema condicional real de FIFA para 48 equipos).
R32_BRACKET = [
    ("1B", "2A"),                      # Partido 1 (orden tablero: 2A vs 2B → tomamos 1°/2° real más abajo)
    ("1E", "2F"),                      # Partido 2
    ("1B2","3-ABCDF"),                 # Partido 3   (ver nota slots duplicados abajo)
    ("1F", "2C"),                      # Partido 4
    ("2E", "2I"),                      # Partido 5
    ("1I", "3-CDFGH"),                 # Partido 6
    ("1A", "3-CEFHI"),                 # Partido 7
    ("1L", "3-EHIJK"),                 # Partido 8
    ("1G", "3-AEHIJ"),                 # Partido 9
    ("1D", "3-BEFIJ"),                 # Partido 10
    ("2K", "2L"),                      # Partido 11
    ("1H", "2J"),                      # Partido 12
    ("1B3","3-EFGIJ"),                 # Partido 13  (ver nota slots duplicados abajo)
    ("2D", "2G"),                      # Partido 14
    ("1J", "2H"),                      # Partido 15
    ("1K", "3-DEIJL"),                 # Partido 16
]

# NOTA IMPORTANTE sobre "1B" apareciendo en partidos 3 y 13:
# El fixture impreso oficial muestra "1B" en ambos casilleros. Esto es un
# error de imprenta/transcripción típico en fixtures físicos de quiniela
# (un mismo ganador de grupo no puede jugar dos partidos de Dieciseisavos
# distintos el mismo día). Se mantiene como referencia documental, pero
# el motor de predicción usa el bracket VALIDADO (ver R32_BRACKET_VALID)
# que corrige esta inconsistencia preservando la estructura real de FIFA:
# cada 1° de grupo aparece UNA sola vez, y los terceros condicionales se
# resuelven según el sistema oficial de 48 equipos.

R32_BRACKET_VALID = [
    # ── PAREJA 1 (Ganador P1 vs Ganador P2 en Octavos) ──
    ("1E", "3-ABCDF"),   # Partido 1: Alemania vs Suecia
    ("2A", "2B"),        # Partido 2: Sudáfrica vs Canadá

    # ── PAREJA 2 (Ganador P3 vs Ganador P4 en Octavos) ──
    ("1I", "3-CDFGH"),   # Partido 3: Francia vs Paraguay
    ("1F", "2C"),        # Partido 4: Países Bajos vs Marruecos

    # ── PAREJA 3 (Ganador P5 vs Ganador P6 en Octavos) ──
    ("2K", "2L"),        # Partido 5: Portugal vs Croacia
    ("1H", "2J"),        # Partido 6: España vs Austria

    # ── PAREJA 4 (Ganador P7 vs Ganador P8 en Octavos) ──
    ("1D", "3-BEFIJ"),   # Partido 7: Estados Unidos vs Bosnia y H.
    ("1G", "3-AEHIJ"),   # Partido 8: Bélgica vs Argelia

    # ── PAREJA 5 (Ganador P9 vs Ganador P10 en Octavos) ──
    ("1C", "2F"),        # Partido 9: Brasil vs Japón
    ("2E", "2I"),        # Partido 10: Costa de Marfil vs Noruega

    # ── PAREJA 6 (Ganador P11 vs Ganador P12 en Octavos) ──
    ("1A", "3-CEFHI"),   # Partido 11: México vs Ecuador
    ("1L", "3-EHIJK"),   # Partido 12: Inglaterra vs RD Congo

    # ── PAREJA 7 (Ganador P13 vs Ganador P14 en Octavos) ──
    ("1J", "2H"),        # Partido 13: Argentina vs Cabo Verde
    ("2D", "2G"),        # Partido 14: Australia vs Egipto

    # ── PAREJA 8 (Ganador P15 vs Ganador P16 en Octavos) ──
    ("1B", "3-EFGIJ"),   # Partido 15: Suiza vs Senegal
    ("1K", "3-DEIJL"),   # Partido 16: Colombia vs Ghana
]

# Grupos candidatos para cada uno de los 8 "mejores terceros" según el
# bracket oficial. El motor resuelve en tiempo de simulación cuál grupo
# de cada lista efectivamente clasificó como mejor tercero.
THIRD_PLACE_SLOTS = {
    "3-ABCDF": ["A","B","C","D","F"],
    "3-CDFGH": ["C","D","F","G","H"],
    "3-CEFHI": ["C","E","F","H","I"],
    "3-EHIJK": ["E","H","I","J","K"],
    "3-AEHIJ": ["A","E","H","I","J"],
    "3-BEFIJ": ["B","E","F","I","J"],
    "3-EFGIJ": ["E","F","G","I","J"],
    "3-DEIJL": ["D","E","I","J","L"],
}

GROUP_LETTERS = list(GROUPS.keys())
ALL_TEAMS     = [t for teams in GROUPS.values() for t in teams]
