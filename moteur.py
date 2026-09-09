"""
MOTEUR GEOMETRIQUE - Atelier Vitrage (v3 - simplifie)
Uniquement : Cercle + formes generiques de 3 a 8 cotes (cotes mesures
+ diagonales depuis un sommet de reference, aucune supposition d'angle
ou de parallelisme). Les formes specialisees (carre/rectangle/trapeze/
parallelogramme) et le systeme de modifications (chanfrein/encoche/
patte) ont ete retires a la demande de l'utilisateur - un rectangle,
un carre, etc. restent representables via le "Quadrilatere (4 cotes)",
juste avec 1 diagonale a mesurer en plus.
"""
import math

# =====================================================================
# 1) CERCLE
# =====================================================================
def _points_cercle(p, n=48):
    r = p["diametre"] / 2
    pts = [(r + r * math.cos(2 * math.pi * i / n), r + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return {"points": pts, "valid": True}


# =====================================================================
# 2) FORMES GENERIQUES N COTES (3 a 8) - cotes + diagonales depuis un
#    sommet de reference. Verifie contre un polygone regulier connu
#    (heptagone/octogone : erreur 0.000mm) avant integration.
# =====================================================================
def _circle_intersect(c1, r1, c2, r2):
    x1, y1 = c1; x2, y2 = c2
    d = math.hypot(x2 - x1, y2 - y1)
    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return None
    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h_sq = r1**2 - a**2
    if h_sq < 0:
        return None
    h = math.sqrt(h_sq)
    xm, ym = x1 + a * (x2 - x1) / d, y1 + a * (y2 - y1) / d
    return (
        (xm + h * (y2 - y1) / d, ym - h * (x2 - x1) / d),
        (xm - h * (y2 - y1) / d, ym + h * (x2 - x1) / d),
    )

def _angle_from(origin, pt):
    return math.atan2(pt[1] - origin[1], pt[0] - origin[0])

def reconstruct_ngon(sides, diagonals):
    """sides : [S0..S(n-1)] longueurs des n côtés dans l'ordre.
    diagonals : [D0..D(n-4)] longueurs V0-V2, V0-V3, ..., V0-V(n-2).
    Retourne (points, valid)."""
    n = len(sides)
    V = [None] * n
    V[0] = (0, 0)
    V[1] = (sides[0], 0)

    if n == 3:
        a, b, c = sides
        x = (a**2 + c**2 - b**2) / (2 * a)
        y_sq = c**2 - x**2
        valid = y_sq >= 0
        V[2] = (x, math.sqrt(max(y_sq, 0)))
        return V, valid

    a, s1, d0 = sides[0], sides[1], diagonals[0]
    cos_t = max(-1, min(1, (a**2 + d0**2 - s1**2) / (2 * a * d0)))
    theta = math.acos(cos_t)
    V[2] = (d0 * math.cos(theta), d0 * math.sin(theta))

    for k in range(3, n - 1):
        inter = _circle_intersect(V[0], diagonals[k - 2], V[k - 1], sides[k - 1])
        if inter is None:
            return V, False
        c1, c2 = inter
        ang_prev = _angle_from(V[0], V[k - 1])
        cands = [(c1, _angle_from(V[0], c1)), (c2, _angle_from(V[0], c2))]
        better = [c for c in cands if c[1] > ang_prev]
        V[k] = (max(better, key=lambda c: c[1]) if better else max(cands, key=lambda c: c[1]))[0]

    inter = _circle_intersect(V[n - 2], sides[n - 2], V[0], sides[n - 1])
    if inter is None:
        return V, False
    c1, c2 = inter
    ang_prev = _angle_from(V[0], V[n - 2])
    cands = [(c1, _angle_from(V[0], c1)), (c2, _angle_from(V[0], c2))]
    better = [c for c in cands if c[1] > ang_prev]
    V[n - 1] = (max(better, key=lambda c: c[1]) if better else max(cands, key=lambda c: c[1]))[0]

    return V, True


def _make_ngon_entry(n):
    label = f"{n} côtés"
    parametres = [f"cote_{i+1}" for i in range(n)] + [f"diagonale_{i+1}" for i in range(n - 3)]

    def compute(p, n=n):
        sides = [p[f"cote_{i+1}"] for i in range(n)]
        diagonals = [p[f"diagonale_{i+1}"] for i in range(n - 3)]
        points, valid = reconstruct_ngon(sides, diagonals)
        return {"points": points, "valid": valid}

    return {"label": label, "categorie": "mesure", "is_quad": False,
            "parametres": parametres, "compute": compute}


# =====================================================================
# 3) CATALOGUE
# =====================================================================
BASES = {
    "cercle": {"label": "Cercle", "categorie": "simple", "is_quad": False,
               "parametres": ["diametre"], "compute": _points_cercle},
}
for _n in range(3, 9):
    BASES[f"ngon_{_n}"] = _make_ngon_entry(_n)

CATEGORIES = {
    "simple": "Formes géométriques simples",
    "mesure": "Formes par côtés mesurés (3 à 8 côtés)",
}

# =====================================================================
# 4) UTILITAIRES (contour -> points ; validite ; bbox ; marge ; rectiligne)
# =====================================================================
def compute_polygon(base_type, base_params, modifiers=None):
    """modifiers ignoré désormais (plus aucune forme ne le supporte),
    gardé en paramètre pour ne pas casser les appels existants."""
    return BASES[base_type]["compute"](base_params)["points"]

def is_valid(base_type, base_params):
    return BASES[base_type]["compute"](base_params)["valid"]

def bbox(points):
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    return min(xs), max(xs), min(ys), max(ys)

def rectangle_marge(points, marge):
    minx, maxx, miny, maxy = bbox(points)
    return [(minx - marge, miny - marge), (maxx + marge, miny - marge),
            (maxx + marge, maxy + marge), (minx - marge, maxy + marge)]

def _signed_area(points):
    n = len(points)
    return sum(points[i][0]*points[(i+1)%n][1] - points[(i+1)%n][0]*points[i][1] for i in range(n)) / 2

def _line_intersection(P1, dir1, P2, dir2):
    x1, y1 = P1; dx1, dy1 = dir1
    x2, y2 = P2; dx2, dy2 = dir2
    denom = dx1 * dy2 - dy1 * dx2
    if abs(denom) < 1e-9:
        return None
    t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / denom
    return (x1 + t * dx1, y1 + t * dy1)

def offset_rectiligne(points, offset_mm):
    """Surplus de matiere sur chaque cote, coins gardes droits.
    offset_mm=0 -> desactive (contour inchange)."""
    if offset_mm == 0:
        return points
    n = len(points)
    sign = 1 if _signed_area(points) > 0 else -1
    offset_lines = []
    for i in range(n):
        P1, P2 = points[i], points[(i + 1) % n]
        dx, dy = P2[0] - P1[0], P2[1] - P1[1]
        length = math.hypot(dx, dy)
        dx, dy = dx / length, dy / length
        nx, ny = dy * sign, -dx * sign
        offset_lines.append(((P1[0] + nx * offset_mm, P1[1] + ny * offset_mm), (dx, dy)))
    new_points = []
    for i in range(n):
        P_prev, dir_prev = offset_lines[i - 1]
        P_cur, dir_cur = offset_lines[i]
        pt = _line_intersection(P_prev, dir_prev, P_cur, dir_cur)
        new_points.append(pt if pt else points[i])
    return new_points


# =====================================================================
# 6) ARRONDI DE COIN (fillet) - selection d'un ou plusieurs coins +
# rayon. Verifie visuellement avant integration (voir conversation).
# =====================================================================
def _arrondir_coin_unique(points, i, rayon):
    """points de remplacement pour le coin i (arc tangent aux 2 cotes
    adjacents), ou None si le rayon est trop grand pour ce coin."""
    n = len(points)
    P_prev, P_cur, P_next = points[i - 1], points[i], points[(i + 1) % n]

    v1 = (P_prev[0] - P_cur[0], P_prev[1] - P_cur[1])
    v2 = (P_next[0] - P_cur[0], P_next[1] - P_cur[1])
    len1, len2 = math.hypot(*v1), math.hypot(*v2)
    d1, d2 = (v1[0] / len1, v1[1] / len1), (v2[0] / len2, v2[1] / len2)

    cos_a = max(-1, min(1, d1[0] * d2[0] + d1[1] * d2[1]))
    angle = math.acos(cos_a)
    if angle < 1e-6 or angle > math.pi - 1e-6:
        return None

    dist_tangente = rayon / math.tan(angle / 2)
    if dist_tangente >= len1 or dist_tangente >= len2:
        return None

    tangente_prev = (P_cur[0] + d1[0] * dist_tangente, P_cur[1] + d1[1] * dist_tangente)
    tangente_next = (P_cur[0] + d2[0] * dist_tangente, P_cur[1] + d2[1] * dist_tangente)

    bis = (d1[0] + d2[0], d1[1] + d2[1])
    bis_len = math.hypot(*bis)
    bis = (bis[0] / bis_len, bis[1] / bis_len)
    dist_centre = rayon / math.sin(angle / 2)
    centre = (P_cur[0] + bis[0] * dist_centre, P_cur[1] + bis[1] * dist_centre)

    ang_prev = math.atan2(tangente_prev[1] - centre[1], tangente_prev[0] - centre[0])
    ang_next = math.atan2(tangente_next[1] - centre[1], tangente_next[0] - centre[0])
    diff = ang_next - ang_prev
    while diff > math.pi: diff -= 2 * math.pi
    while diff < -math.pi: diff += 2 * math.pi

    n_seg = 16
    arc = [(centre[0] + rayon * math.cos(ang_prev + diff * k / n_seg),
            centre[1] + rayon * math.sin(ang_prev + diff * k / n_seg)) for k in range(n_seg + 1)]
    return [tangente_prev] + arc + [tangente_next]


def appliquer_arrondis(points, arrondis):
    """arrondis : liste de {"coin": index (0-based), "rayon": mm}.
    Un rayon trop grand pour un coin donné laisse ce coin inchangé
    (pas d'erreur bloquante, juste pas d'effet sur ce coin-là)."""
    n = len(points)
    par_coin = {a["coin"]: a["rayon"] for a in arrondis if a.get("rayon", 0) > 0}
    final = []
    for i in range(n):
        if i in par_coin:
            remplacement = _arrondir_coin_unique(points, i, par_coin[i])
            final.extend(remplacement if remplacement else [points[i]])
        else:
            final.append(points[i])
    return final

def arrondi_valide(points, coin, rayon):
    """Pour affichage d'un avertissement cote interface si besoin."""
    if rayon <= 0:
        return True
    return _arrondir_coin_unique(points, coin, rayon) is not None


if __name__ == "__main__":
    print(compute_polygon("cercle", {"diametre": 1000})[:3], "...")
    print(compute_polygon("ngon_4", {"cote_1": 1000, "cote_2": 850, "cote_3": 980, "cote_4": 820, "diagonale_1": 1300}))
    print(is_valid("ngon_3", {"cote_1": 1000, "cote_2": 900, "cote_3": 700}))
