"""
Ecrivain DXF, 100% Python, aucune dependance externe.

Genere un DXF R12 COMPLET (sections HEADER, TABLES, ENTITIES) plutot
qu'un fichier minimal : beaucoup de logiciels CAO/CNC refusent d'ouvrir
(ou affichent vide) un DXF sans ces sections, meme si les entites sont
correctes. Les calques utilises sont declares dans TABLES, comme
l'exige la norme.
"""


def _ligne(code, valeur):
    return f"{code}\n{valeur}\n"


def build_dxf(shape_points, stock_rect_or_none, ref):
    # --- Calcul des limites du dessin (pour HEADER) ---
    tous_points = list(shape_points)
    if stock_rect_or_none:
        tous_points += list(stock_rect_or_none)
    xs = [p[0] for p in tous_points]
    ys = [p[1] for p in tous_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    out = []

    # ================= SECTION HEADER =================
    out.append(_ligne(0, "SECTION"))
    out.append(_ligne(2, "HEADER"))
    out.append(_ligne(9, "$ACADVER"))
    out.append(_ligne(1, "AC1009"))
    out.append(_ligne(9, "$INSBASE"))
    out.append(_ligne(10, "0.0")); out.append(_ligne(20, "0.0")); out.append(_ligne(30, "0.0"))
    out.append(_ligne(9, "$EXTMIN"))
    out.append(_ligne(10, f"{min_x:.4f}")); out.append(_ligne(20, f"{min_y:.4f}")); out.append(_ligne(30, "0.0"))
    out.append(_ligne(9, "$EXTMAX"))
    out.append(_ligne(10, f"{max_x:.4f}")); out.append(_ligne(20, f"{max_y:.4f}")); out.append(_ligne(30, "0.0"))
    out.append(_ligne(9, "$INSUNITS"))
    out.append(_ligne(70, 4))
    out.append(_ligne(0, "ENDSEC"))

    # ================= SECTION TABLES (calques) =================
    calques = [("DECOUPE", 7), ("PLAQUE_BRUTE", 3), ("REPERE", 2)]

    out.append(_ligne(0, "SECTION"))
    out.append(_ligne(2, "TABLES"))
    out.append(_ligne(0, "TABLE"))
    out.append(_ligne(2, "LTYPE"))
    out.append(_ligne(70, 1))
    out.append(_ligne(0, "LTYPE"))
    out.append(_ligne(2, "CONTINUOUS"))
    out.append(_ligne(70, 64))
    out.append(_ligne(3, "Solid line"))
    out.append(_ligne(72, 65))
    out.append(_ligne(73, 0))
    out.append(_ligne(40, "0.0"))
    out.append(_ligne(0, "ENDTAB"))

    out.append(_ligne(0, "TABLE"))
    out.append(_ligne(2, "LAYER"))
    out.append(_ligne(70, len(calques)))
    for nom, couleur in calques:
        out.append(_ligne(0, "LAYER"))
        out.append(_ligne(2, nom))
        out.append(_ligne(70, 0))
        out.append(_ligne(62, couleur))
        out.append(_ligne(6, "CONTINUOUS"))
    out.append(_ligne(0, "ENDTAB"))
    out.append(_ligne(0, "ENDSEC"))

    # ================= SECTION ENTITIES =================
    out.append(_ligne(0, "SECTION"))
    out.append(_ligne(2, "ENTITIES"))

    def polyligne(points, calque):
        out.append(_ligne(0, "POLYLINE"))
        out.append(_ligne(8, calque))
        out.append(_ligne(66, 1))
        out.append(_ligne(70, 1))
        out.append(_ligne(10, "0.0")); out.append(_ligne(20, "0.0")); out.append(_ligne(30, "0.0"))
        for x, y in points:
            out.append(_ligne(0, "VERTEX"))
            out.append(_ligne(8, calque))
            out.append(_ligne(10, f"{x:.4f}"))
            out.append(_ligne(20, f"{y:.4f}"))
            out.append(_ligne(30, "0.0"))
        out.append(_ligne(0, "SEQEND"))
        out.append(_ligne(8, calque))

    polyligne(shape_points, "DECOUPE")
    if stock_rect_or_none:
        polyligne(stock_rect_or_none, "PLAQUE_BRUTE")
        origine = (stock_rect_or_none[0][0] + 10, stock_rect_or_none[0][1] + 10)
    else:
        origine = (min_x + 10, min_y + 10)

    out.append(_ligne(0, "TEXT"))
    out.append(_ligne(8, "REPERE"))
    out.append(_ligne(10, f"{origine[0]:.4f}"))
    out.append(_ligne(20, f"{origine[1]:.4f}"))
    out.append(_ligne(30, "0.0"))
    out.append(_ligne(40, "25.0"))
    out.append(_ligne(1, ref))

    out.append(_ligne(0, "ENDSEC"))
    out.append(_ligne(0, "EOF"))

    return "".join(out)


def save_dxf(shape_points, stock_rect_or_none, ref, chemin):
    contenu = build_dxf(shape_points, stock_rect_or_none, ref)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    return chemin
