"""
Écrivain DXF minimal, 100% Python, aucune dépendance externe.
Volontairement sans ezdxf : sur Android (compilation via python-for-android),
chaque dépendance externe est un risque d'échec de compilation en plus.
Ce format minimal (section ENTITIES uniquement) s'ouvre correctement dans
la plupart des logiciels CAO/CNC (déjà utilisé pour la version web plus
tôt dans la conversation).
"""

def build_dxf(shape_points, stock_rect_or_none, ref):
    ents = []

    def poly(pts, layer):
        ents.append(f"0\nLWPOLYLINE\n8\n{layer}\n90\n{len(pts)}\n70\n1\n")
        for x, y in pts:
            ents.append(f"10\n{x:.2f}\n20\n{y:.2f}\n")

    poly(shape_points, "DECOUPE")
    if stock_rect_or_none:
        poly(stock_rect_or_none, "PLAQUE_BRUTE")
        origin = (stock_rect_or_none[0][0] + 10, stock_rect_or_none[0][1] + 10)
    else:
        xs = [p[0] for p in shape_points]; ys = [p[1] for p in shape_points]
        origin = (min(xs) + 10, min(ys) + 10)
    ents.append(f"0\nTEXT\n8\nREPERE\n10\n{origin[0]:.2f}\n20\n{origin[1]:.2f}\n40\n25\n1\n{ref}\n")

    return "0\nSECTION\n2\nENTITIES\n" + "".join(ents) + "0\nENDSEC\n0\nEOF\n"


def save_dxf(shape_points, stock_rect_or_none, ref, chemin):
    contenu = build_dxf(shape_points, stock_rect_or_none, ref)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    return chemin


if __name__ == "__main__":
    pts = [(0, 0), (1000, 0), (1000, 700), (0, 700)]
    rect = [(-40, -40), (1040, -40), (1040, 740), (-40, 740)]
    print(build_dxf(pts, rect, "test")[:200], "...")
