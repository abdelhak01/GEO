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


def build_dxf(shape_points, stock_rect_or_none, ref, nom_projet=None, date_str=None):
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
    out.append(_ligne(1, "AC1009"))          # DXF R12 : format tres largement supporte
    out.append(_ligne(9, "$INSBASE"))
    out.append(_ligne(10, "0.0")); out.append(_ligne(20, "0.0")); out.append(_ligne(30, "0.0"))
    out.append(_ligne(9, "$EXTMIN"))
    out.append(_ligne(10, f"{min_x:.4f}")); out.append(_ligne(20, f"{min_y:.4f}")); out.append(_ligne(30, "0.0"))
    out.append(_ligne(9, "$EXTMAX"))
    out.append(_ligne(10, f"{max_x:.4f}")); out.append(_ligne(20, f"{max_y:.4f}")); out.append(_ligne(30, "0.0"))
    out.append(_ligne(9, "$INSUNITS"))
    out.append(_ligne(70, 4))                # 4 = millimetres
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
        """POLYLINE + VERTEX + SEQEND : format R12, compris par tous les
        logiciels (LWPOLYLINE n'existe qu'a partir de R14)."""
        out.append(_ligne(0, "POLYLINE"))
        out.append(_ligne(8, calque))
        out.append(_ligne(66, 1))
        out.append(_ligne(70, 1))            # 1 = polyligne fermee
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

    def texte(contenu, x, y, hauteur):
        out.append(_ligne(0, "TEXT"))
        out.append(_ligne(8, "REPERE"))
        out.append(_ligne(10, f"{x:.4f}"))
        out.append(_ligne(20, f"{y:.4f}"))
        out.append(_ligne(30, "0.0"))
        out.append(_ligne(40, f"{hauteur:.1f}"))
        out.append(_ligne(1, contenu))

    texte(ref, origine[0], origine[1], 25.0)

    # Tracabilite : projet et date, en plus petit sous la reference
    ligne_info = []
    if nom_projet:
        ligne_info.append(nom_projet)
    if date_str:
        ligne_info.append(date_str)
    if ligne_info:
        texte(" - ".join(ligne_info), origine[0], origine[1] - 32, 14.0)

    out.append(_ligne(0, "ENDSEC"))
    out.append(_ligne(0, "EOF"))

    return "".join(out)


def save_dxf(shape_points, stock_rect_or_none, ref, chemin, nom_projet=None, date_str=None):
    contenu = build_dxf(shape_points, stock_rect_or_none, ref, nom_projet, date_str)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    return chemin


if __name__ == "__main__":
    pts = [(0, 0), (1000, 0), (1000, 700), (0, 700)]
    rect = [(-40, -40), (1040, -40), (1040, 740), (-40, 740)]
    contenu = build_dxf(pts, rect, "test")
    print(f"Taille : {len(contenu)} octets, {contenu.count(chr(10))} lignes")
    print("Sections presentes :",
          [s for s in ["HEADER", "TABLES", "ENTITIES"] if s in contenu])
    
