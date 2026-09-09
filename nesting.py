"""
Optimisation du nombre de plaques nécessaires — portage Python du même
algorithme (shelf packing / FFDH avec rotation) déjà vérifié côté
application web. Aucune dépendance externe.
"""

def pack_panels(panels, plate_w, plate_h, spacing):
    """panels : liste de dicts {"ref":str, "w":float, "h":float}
    Retourne (plates, errors).
    plates : liste de plaques, chacune = liste d'items placés
             {"ref","x","y","w","h","rot"}
    errors : références des pièces qui ne rentrent dans aucune plaque
    """
    items = [{"ref": p["ref"], "w": p["w"] + spacing, "h": p["h"] + spacing} for p in panels]
    items.sort(key=lambda it: max(it["w"], it["h"]), reverse=True)

    plates = []  # chaque plaque : {"shelves": [...]}
    errors = []

    for item in items:
        placed = False
        for plate in plates:
            for shelf in plate["shelves"]:
                for w, h, rot in [(item["w"], item["h"], False), (item["h"], item["w"], True)]:
                    if h <= shelf["height"] + 0.01 and shelf["used_width"] + w <= plate_w + 0.01:
                        shelf["items"].append({"ref": item["ref"], "x": shelf["used_width"], "y": shelf["y"],
                                                "w": w, "h": h, "rot": rot})
                        shelf["used_width"] += w
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break
            used_height = sum(s["height"] for s in plate["shelves"])
            for w, h, rot in [(item["w"], item["h"], False), (item["h"], item["w"], True)]:
                if used_height + h <= plate_h + 0.01 and w <= plate_w + 0.01:
                    plate["shelves"].append({"y": used_height, "height": h, "used_width": w,
                                              "items": [{"ref": item["ref"], "x": 0, "y": used_height,
                                                         "w": w, "h": h, "rot": rot}]})
                    placed = True
                    break
            if placed:
                break
        if not placed:
            ok = False
            for w, h, rot in [(item["w"], item["h"], False), (item["h"], item["w"], True)]:
                if h <= plate_h + 0.01 and w <= plate_w + 0.01:
                    plates.append({"shelves": [{"y": 0, "height": h, "used_width": w,
                                                 "items": [{"ref": item["ref"], "x": 0, "y": 0,
                                                            "w": w, "h": h, "rot": rot}]}]})
                    ok = True
                    break
            if not ok:
                errors.append(item["ref"])

    return plates, errors


if __name__ == "__main__":
    panels = [{"ref": f"p{i}", "w": 1000, "h": 800} for i in range(5)]
    plates, errors = pack_panels(panels, 3210, 2250, 10)
    print(f"{len(plates)} plaque(s), erreurs: {errors}")
