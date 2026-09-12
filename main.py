"""
APPLICATION ATELIER VITRAGE - Version Kivy (Android, 100% autonome)

Aucune dépendance externe hors Kivy lui-même : ni ezdxf, ni matplotlib,
ni pandas/numpy. C'est volontaire — chaque dépendance ajoutée est un
risque de plus que la compilation Android échoue. moteur.py et
nesting.py sont réutilisés tels quels (aucune dépendance, déjà validés).

Ce fichier n'a PAS pu être testé dans l'environnement où il a été écrit
(pas de Kivy installé, pas d'écran). Il faut le tester réellement sur
GitHub Actions / un appareil Android avant de considérer que c'est
fonctionnel — voir GUIDE_APK.md pour la marche à suivre.
"""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp
from kivy.core.window import Window

import os

from moteur import (BASES, CATEGORIES, compute_polygon, is_valid, bbox, rectangle_marge,
                     offset_rectiligne, appliquer_arrondis)
from nesting import pack_panels
from dxf_writer import save_dxf

try:
    # Dossier propre a l'application, dans le stockage externe : accessible
    # via cable USB/gestionnaire de fichiers, mais NE NECESSITE AUCUNE
    # permission speciale sur Android 11+ (contrairement a Download/ qui
    # demanderait la permission MANAGE_EXTERNAL_STORAGE, a accorder
    # manuellement dans les parametres). C'est le choix le plus fiable.
    from jnius import autoclass  # type: ignore
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    contexte = PythonActivity.mActivity
    dossier_java = contexte.getExternalFilesDir(None)
    DOSSIER_EXPORT = dossier_java.getAbsolutePath()
except Exception:
    try:
        # Repli : dossier public Download (necessite la permission
        # "Gestion de tous les fichiers" accordee manuellement dans
        # Parametres > Applications > GEO > Autorisations, si le repli
        # ci-dessus echoue pour une raison quelconque).
        from android.storage import primary_external_storage_path  # type: ignore
        DOSSIER_EXPORT = os.path.join(primary_external_storage_path(), "Download", "GEO")
    except Exception:
        # Hors Android (test sur PC) : dossier local classique.
        DOSSIER_EXPORT = os.path.join(os.path.expanduser("~"), "GEO")

os.makedirs(DOSSIER_EXPORT, exist_ok=True)


# =====================================================================
# Style commun des champs de saisie (theme sombre)
# =====================================================================
COULEUR_FOND_CHAMP = (0.16, 0.20, 0.26, 1)
COULEUR_TEXTE_CHAMP = (1, 1, 1, 1)
COULEUR_CURSEUR = (0.96, 0.62, 0.04, 1)


def champ_saisie(**kwargs):
    """TextInput pre-style pour le theme sombre (texte blanc sur fond
    sombre) - evite de repeter les couleurs a chaque champ."""
    kwargs.setdefault("multiline", False)
    return TextInput(background_color=COULEUR_FOND_CHAMP,
                      foreground_color=COULEUR_TEXTE_CHAMP,
                      cursor_color=COULEUR_CURSEUR,
                      hint_text_color=(0.55, 0.60, 0.66, 1),
                      **kwargs)


# =====================================================================
# Widget de dessin (aperçu de la forme, style "plan bleu")
# =====================================================================
class ApercuForme(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.points = []
        self.rect_marge = None
        self.bind(size=self._redessiner, pos=self._redessiner)

    def definir(self, points, rect_marge):
        self.points = points
        self.rect_marge = rect_marge
        self._redessiner()

    def _vers_ecran(self, pt, minx, miny, echelle):
        return (self.x + dp(20) + (pt[0] - minx) * echelle,
                self.y + dp(20) + (pt[1] - miny) * echelle)

    def _redessiner(self, *args):
        self.canvas.clear()
        if not self.points:
            return
        contour = self.rect_marge if self.rect_marge else self.points
        minx, maxx, miny, maxy = bbox(contour)
        largeur = max(maxx - minx, 1); hauteur = max(maxy - miny, 1)
        marge_ecran = dp(40)
        echelle = min((self.width - marge_ecran) / largeur, (self.height - marge_ecran) / hauteur)

        with self.canvas:
            Color(0.06, 0.16, 0.26, 1)
            Rectangle(pos=self.pos, size=self.size)

            if self.rect_marge:
                Color(0.96, 0.62, 0.04, 1)
                pts_ecran = []
                for p in self.rect_marge + [self.rect_marge[0]]:
                    x, y = self._vers_ecran(p, minx, miny, echelle)
                    pts_ecran += [x, y]
                Line(points=pts_ecran, width=1.3, dash_length=8, dash_offset=4)

            Color(0.49, 0.83, 0.99, 1)
            pts_ecran = []
            for p in self.points + [self.points[0]]:
                x, y = self._vers_ecran(p, minx, miny, echelle)
                pts_ecran += [x, y]
            Line(points=pts_ecran, width=2.2)


# =====================================================================
# Popup simple d'information
# =====================================================================
def afficher_message(titre, texte):
    Popup(title=titre, content=Label(text=texte), size_hint=(0.8, 0.4)).open()


# =====================================================================
# Ecran principal
# =====================================================================
class AtelierVitrageRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.base_type = "ngon_4"
        self.champs_cotes = {}
        self.arrondis = []
        self.commande = []

        # ---- En-tête ----
        entete = Label(text="GEO", font_size=dp(24), bold=True,
                        size_hint_y=None, height=dp(50))
        self.add_widget(entete)

        corps = BoxLayout(orientation="horizontal")
        self.add_widget(corps)

        # ---- Colonne formes ----
        col_formes = ScrollView(size_hint_x=0.35)
        grille_formes = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=dp(6))
        grille_formes.bind(minimum_height=grille_formes.setter("height"))
        for cat, cat_label in CATEGORIES.items():
            grille_formes.add_widget(Label(text=cat_label, bold=True, size_hint_y=None,
                                            height=dp(30), font_size=dp(14)))
            for key, base in BASES.items():
                if base["categorie"] != cat:
                    continue
                btn = Button(text=base["label"], size_hint_y=None, height=dp(48), font_size=dp(18))
                btn.bind(on_release=lambda inst, k=key: self.choisir_forme(k))
                grille_formes.add_widget(btn)
        col_formes.add_widget(grille_formes)
        corps.add_widget(col_formes)

        # ---- Colonne formulaire + apercu (defilable) ----
        col_form_scroll = ScrollView(size_hint_x=0.4)
        col_form = GridLayout(cols=1, size_hint_y=None, padding=dp(8), spacing=dp(8))
        col_form.bind(minimum_height=col_form.setter("height"))
        col_form_scroll.add_widget(col_form)
        corps.add_widget(col_form_scroll)

        col_form.add_widget(Label(text="Référence du panneau", size_hint_y=None, height=dp(28),
                                   halign="left", font_size=dp(15)))
        self.champ_ref = champ_saisie(multiline=False, size_hint_y=None, height=dp(48), font_size=dp(16))
        col_form.add_widget(self.champ_ref)

        col_form.add_widget(Label(text="Cotes (mm)", bold=True, size_hint_y=None, height=dp(30),
                                   font_size=dp(15)))
        self.zone_cotes = GridLayout(cols=2, size_hint_y=None, spacing=dp(6))
        self.zone_cotes.bind(minimum_height=self.zone_cotes.setter("height"))
        col_form.add_widget(self.zone_cotes)

        # arrondi de coin
        col_form.add_widget(Label(text="Arrondi de coin (optionnel)", bold=True, size_hint_y=None,
                                   height=dp(30), font_size=dp(15)))
        self.zone_arrondis = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        self.zone_arrondis.bind(minimum_height=self.zone_arrondis.setter("height"))
        col_form.add_widget(self.zone_arrondis)
        btn_add_arrondi = Button(text="+ Ajouter un arrondi", size_hint_y=None, height=dp(46),
                                  font_size=dp(15))
        btn_add_arrondi.bind(on_release=lambda inst: self.ajouter_arrondi())
        col_form.add_widget(btn_add_arrondi)

        # options
        col_form.add_widget(Label(text="Options", bold=True, size_hint_y=None, height=dp(30),
                                   font_size=dp(15)))

        ligne_marge = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        self.case_marge = CheckBox(active=True, size_hint_x=None, width=dp(48))
        self.case_marge.bind(active=lambda inst, val: self.rafraichir_apercu())
        ligne_marge.add_widget(self.case_marge)
        ligne_marge.add_widget(Label(text="Marge découpe", font_size=dp(14)))
        self.champ_marge = champ_saisie(text="40", multiline=False, input_filter="float",
                                      size_hint_x=None, width=dp(90), font_size=dp(16))
        self.champ_marge.bind(text=lambda inst, val: self.rafraichir_apercu())
        ligne_marge.add_widget(self.champ_marge)
        col_form.add_widget(ligne_marge)

        ligne_rect = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        self.case_rectiligne = CheckBox(active=False, size_hint_x=None, width=dp(48))
        self.case_rectiligne.bind(active=lambda inst, val: self.rafraichir_apercu())
        ligne_rect.add_widget(self.case_rectiligne)
        ligne_rect.add_widget(Label(text="Rectiligne", font_size=dp(14)))
        self.champ_rectiligne = champ_saisie(text="3", multiline=False, input_filter="float",
                                           size_hint_x=None, width=dp(90), font_size=dp(16))
        self.champ_rectiligne.bind(text=lambda inst, val: self.rafraichir_apercu())
        ligne_rect.add_widget(self.champ_rectiligne)
        col_form.add_widget(ligne_rect)

        # apercu : hauteur FIXE (evite qu'il ecrase le reste de la colonne)
        col_form.add_widget(Label(text="Aperçu", bold=True, size_hint_y=None, height=dp(30),
                                   font_size=dp(15)))
        self.apercu = ApercuForme(size_hint_y=None, height=dp(260))
        col_form.add_widget(self.apercu)

        self.label_erreur = Label(text="", color=(0.9, 0.3, 0.2, 1), size_hint_y=None,
                                   height=dp(30), font_size=dp(13))
        col_form.add_widget(self.label_erreur)

        btn_ajouter = Button(text="Ajouter à la commande", size_hint_y=None, height=dp(56),
                              font_size=dp(17), background_color=(0.96, 0.62, 0.04, 1))
        btn_ajouter.bind(on_release=lambda inst: self.ajouter_commande())
        col_form.add_widget(btn_ajouter)

        # ---- Colonne commande (defilable) ----
        col_commande_scroll = ScrollView(size_hint_x=0.25)
        col_commande = GridLayout(cols=1, size_hint_y=None, padding=dp(8), spacing=dp(8))
        col_commande.bind(minimum_height=col_commande.setter("height"))
        col_commande_scroll.add_widget(col_commande)
        corps.add_widget(col_commande_scroll)

        col_commande.add_widget(Label(text="Commande", bold=True, size_hint_y=None,
                                       height=dp(34), font_size=dp(16)))
        self.liste_commande = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        self.liste_commande.bind(minimum_height=self.liste_commande.setter("height"))
        col_commande.add_widget(self.liste_commande)

        btn_nesting = Button(text="Calculer l'optimisation", size_hint_y=None, height=dp(52),
                              font_size=dp(15))
        btn_nesting.bind(on_release=lambda inst: self.calculer_nesting())
        col_commande.add_widget(btn_nesting)
        self.label_nesting = Label(text="", size_hint_y=None, height=dp(140), font_size=dp(13),
                                    halign="left", valign="top")
        self.label_nesting.bind(size=lambda inst, val: setattr(inst, "text_size", (inst.width, None)))
        col_commande.add_widget(self.label_nesting)

        self.choisir_forme(self.base_type)

    # -----------------------------------------------------------
    def choisir_forme(self, key):
        self.base_type = key
        base = BASES[key]
        self.zone_cotes.clear_widgets()
        self.champs_cotes = {}
        self.arrondis = []
        self.zone_arrondis.clear_widgets()
        for param in base["parametres"]:
            self.zone_cotes.add_widget(Label(text=param.replace("_", " "), size_hint_y=None,
                                              height=dp(48), font_size=dp(14)))
            champ = champ_saisie(text="", hint_text="mm", multiline=False, input_filter="float",
                               size_hint_y=None, height=dp(48), font_size=dp(16))
            champ.bind(text=lambda inst, val: self.rafraichir_apercu())
            self.zone_cotes.add_widget(champ)
            self.champs_cotes[param] = champ
        self.rafraichir_apercu()

    def _nb_coins(self):
        return int(self.base_type.split("_")[1]) if self.base_type.startswith("ngon_") else 0

    def ajouter_arrondi(self):
        if self._nb_coins() == 0:
            afficher_message("Info", "Le cercle n'a pas de coin à arrondir.")
            return
        entree = {"coin": 0, "rayon": 50}
        self.arrondis.append(entree)

        ligne = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        champ_coin = champ_saisie(text="1", multiline=False, input_filter="int", size_hint_x=0.3)
        champ_rayon = champ_saisie(text="50", multiline=False, input_filter="float", size_hint_x=0.4)

        def maj_coin(inst, val):
            try:
                c = max(1, min(self._nb_coins(), int(val))) - 1
                entree["coin"] = c
            except ValueError:
                pass
            self.rafraichir_apercu()

        def maj_rayon(inst, val):
            try:
                entree["rayon"] = float(val)
            except ValueError:
                entree["rayon"] = 0
            self.rafraichir_apercu()

        champ_coin.bind(text=maj_coin)
        champ_rayon.bind(text=maj_rayon)
        ligne.add_widget(Label(text="Coin n°", size_hint_x=0.3))
        ligne.add_widget(champ_coin)
        ligne.add_widget(Label(text="Rayon mm", size_hint_x=0.3))
        ligne.add_widget(champ_rayon)
        self.zone_arrondis.add_widget(ligne)
        self.rafraichir_apercu()

    def _params_actuels(self):
        params = {}
        for k, champ in self.champs_cotes.items():
            try:
                params[k] = float(champ.text)
            except ValueError:
                params[k] = 0.0
        return params

    def rafraichir_apercu(self, *args):
        """Recalcule et redessine l'apercu. Protege contre toute erreur
        de saisie (champ vide, cotes incoherentes) : l'app affiche un
        message au lieu de se fermer."""
        try:
            params = self._params_actuels()
            # Aucune cote saisie encore : etat neutre, pas un message d'erreur
            if all(v == 0 for v in params.values()):
                self.label_erreur.text = "Saisis les cotes du gabarit."
                self.apercu.definir([], None)
                return
            if not is_valid(self.base_type, params):
                self.label_erreur.text = "Cotes incohérentes : vérifie les mesures saisies."
                self.apercu.definir([], None)
                return
            self.label_erreur.text = ""
            points = compute_polygon(self.base_type, params)
            if self.base_type != "cercle" and self.arrondis:
                points = appliquer_arrondis(points, self.arrondis)
            rectiligne = float(self.champ_rectiligne.text or 0) if self.case_rectiligne.active else 0
            points = offset_rectiligne(points, rectiligne)
            marge = float(self.champ_marge.text or 0) if self.case_marge.active else 0
            rect = rectangle_marge(points, marge) if self.case_marge.active else None
            self.apercu.definir(points, rect)
        except Exception as e:
            self.label_erreur.text = "Saisie incomplète ou invalide."
            self.apercu.definir([], None)

    def ajouter_commande(self):
        ref = self.champ_ref.text.strip()
        params = self._params_actuels()
        if not ref:
            afficher_message("Erreur", "Donne une référence au panneau.")
            return
        if not is_valid(self.base_type, params):
            if any(v == 0 for v in params.values()):
                afficher_message("Cotes manquantes",
                                  "Toutes les cotes doivent être renseignées\navant d'ajouter le panneau.")
            else:
                afficher_message("Erreur", "Cotes incohérentes, corrige avant d'ajouter.")
            return
        points = compute_polygon(self.base_type, params)
        if self.base_type != "cercle" and self.arrondis:
            points = appliquer_arrondis(points, self.arrondis)
        rectiligne = float(self.champ_rectiligne.text or 0) if self.case_rectiligne.active else 0
        points = offset_rectiligne(points, rectiligne)
        marge = float(self.champ_marge.text or 0) if self.case_marge.active else 0
        rect = rectangle_marge(points, marge) if marge > 0 else None
        contour_final = rect if rect else points
        minx, maxx, miny, maxy = bbox(contour_final)

        panneau = {"ref": ref, "points": points, "rect": rect,
                   "w": round(maxx - minx), "h": round(maxy - miny)}
        self.commande.append(panneau)

        ligne = BoxLayout(size_hint_y=None, height=dp(50))
        ligne.add_widget(Label(text=f"{ref}\n{panneau['w']}x{panneau['h']}mm", font_size=dp(12)))
        btn_export = Button(text="DXF", size_hint_x=0.3)
        btn_export.bind(on_release=lambda inst, p=panneau: self.exporter_dxf(p))
        ligne.add_widget(btn_export)
        self.liste_commande.add_widget(ligne)

        self.champ_ref.text = ""

    def exporter_dxf(self, panneau):
        chemin = os.path.join(DOSSIER_EXPORT, f"{panneau['ref']}.dxf")
        save_dxf(panneau["points"], panneau["rect"], panneau["ref"], chemin)
        afficher_message("Export réussi", f"Fichier enregistré :\n{chemin}")

    def calculer_nesting(self):
        if not self.commande:
            afficher_message("Info", "Ajoute au moins un panneau d'abord.")
            return
        panels = [{"ref": p["ref"], "w": p["w"], "h": p["h"]} for p in self.commande]
        plates, errors = pack_panels(panels, 3210, 2250, 10)
        texte = f"{len(plates)} plaque(s) nécessaire(s)"
        if errors:
            texte += f"\nNe rentrent pas : {', '.join(errors)}"
        self.label_nesting.text = texte


class AtelierVitrageApp(App):
    def build(self):
        Window.clearcolor = (0.09, 0.12, 0.16, 1)
        return AtelierVitrageRoot()


if __name__ == "__main__":
    AtelierVitrageApp().run()
