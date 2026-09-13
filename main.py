"""
GEO - Numerisation de gabarits pour decoupe verre
Application Kivy (Android)

Navigation : Accueil / Mes projets / Parametres / A propos
Aucune dependance externe hors Kivy (moteur.py, projets.py, dxf_writer.py
sont locaux et sans dependance).
"""
import os
from datetime import datetime

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
from kivy.clock import Clock

from moteur import (BASES, compute_polygon, is_valid, bbox, rectangle_marge,
                     offset_rectiligne, appliquer_arrondis)
from dxf_writer import save_dxf
import projets


# =====================================================================
# THEME
# =====================================================================
class Theme:
    mode_nuit = True
    echelle_texte = 1.0

    BLEU_FONCE = (0.10, 0.23, 0.42, 1)
    BLEU_VIF = (0.15, 0.39, 0.79, 1)
    BLEU_CLAIR = (0.49, 0.83, 0.99, 1)
    ORANGE = (0.96, 0.62, 0.04, 1)
    ROUGE = (0.89, 0.29, 0.29, 1)
    VERT = (0.62, 0.88, 0.80, 1)

    @classmethod
    def fond(cls):
        return (0.09, 0.12, 0.16, 1) if cls.mode_nuit else (0.95, 0.96, 0.98, 1)

    @classmethod
    def fond_champ(cls):
        return (0.16, 0.20, 0.26, 1) if cls.mode_nuit else (1, 1, 1, 1)

    @classmethod
    def texte(cls):
        return (1, 1, 1, 1) if cls.mode_nuit else (0.08, 0.12, 0.18, 1)

    @classmethod
    def texte_doux(cls):
        return (0.56, 0.64, 0.71, 1) if cls.mode_nuit else (0.35, 0.42, 0.50, 1)

    @classmethod
    def sp(cls, taille):
        return dp(taille) * cls.echelle_texte


def etiquette(texte, taille=14, gras=False, couleur=None, **kwargs):
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(30) * Theme.echelle_texte)
    return Label(text=texte, font_size=Theme.sp(taille), bold=gras,
                 color=couleur or Theme.texte(), **kwargs)


def champ_saisie(numerique=False, **kwargs):
    kwargs.setdefault("multiline", False)
    if numerique:
        kwargs.setdefault("input_filter", "float")
        kwargs.setdefault("input_type", "number")
        kwargs.setdefault("keyboard_suggestions", False)
    return TextInput(background_color=Theme.fond_champ(),
                      foreground_color=Theme.texte(),
                      cursor_color=Theme.ORANGE,
                      hint_text_color=Theme.texte_doux(),
                      font_size=Theme.sp(16),
                      **kwargs)


def bouton(texte, action=None, taille=15, hauteur=48, couleur_fond=None, **kwargs):
    b = Button(text=texte, font_size=Theme.sp(taille),
               size_hint_y=kwargs.pop("size_hint_y", None),
               height=dp(hauteur) * Theme.echelle_texte, **kwargs)
    if couleur_fond:
        b.background_color = couleur_fond
    if action:
        b.bind(on_release=lambda inst: action())
    return b


def message(titre, texte):
    contenu = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
    lbl = Label(text=texte, font_size=Theme.sp(15), halign="center", valign="middle")
    lbl.bind(size=lambda i, v: setattr(i, "text_size", (i.width, None)))
    contenu.add_widget(lbl)
    popup = Popup(title=titre, content=contenu, size_hint=(0.85, 0.5))
    contenu.add_widget(bouton("Fermer", popup.dismiss, hauteur=46))
    popup.open()
    return popup


def demander_confirmation(titre, texte, action_si_oui):
    contenu = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
    lbl = Label(text=texte, font_size=Theme.sp(15), halign="center", valign="middle")
    lbl.bind(size=lambda i, v: setattr(i, "text_size", (i.width, None)))
    contenu.add_widget(lbl)

    popup = Popup(title=titre, content=contenu, size_hint=(0.85, 0.55))

    ligne = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
    ligne.add_widget(bouton("Annuler", popup.dismiss, hauteur=48))

    def confirmer():
        popup.dismiss()
        action_si_oui()

    ligne.add_widget(bouton("Confirmer", confirmer, hauteur=48, couleur_fond=Theme.BLEU_VIF))
    contenu.add_widget(ligne)
    popup.open()


# =====================================================================
# CROQUIS
# =====================================================================
class Croquis(Widget):
    """Croquis d'un polygone a n cotes. Vignette : contour seul.
    Detaille : numeros des cotes, diagonales, point de depart."""

    def __init__(self, n_cotes=4, detaille=False, **kwargs):
        super().__init__(**kwargs)
        self.n_cotes = n_cotes
        self.detaille = detaille
        self.bind(size=self._redessiner, pos=self._redessiner)

    def definir(self, n_cotes):
        self.n_cotes = n_cotes
        self._redessiner()

    def _redessiner(self, *args):
        self.canvas.clear()
        for enfant in list(self.children):
            self.remove_widget(enfant)
        if self.n_cotes < 3 or self.width < 10:
            return

        import math
        cx, cy = self.center_x, self.center_y
        facteur = 0.30 if self.detaille else 0.36
        rayon = min(self.width, self.height) * facteur
        n = self.n_cotes
        angles = [(-math.pi / 2) + (2 * math.pi * i / n) for i in range(n)]
        sommets = [(cx + rayon * math.cos(a), cy + rayon * math.sin(a)) for a in angles]

        with self.canvas:
            Color(0.06, 0.16, 0.26, 1)
            Rectangle(pos=self.pos, size=self.size)

            Color(*Theme.BLEU_CLAIR)
            pts = []
            for s in sommets + [sommets[0]]:
                pts += [s[0], s[1]]
            Line(points=pts, width=dp(2) if self.detaille else dp(1.5))

            if self.detaille:
                Color(*Theme.ORANGE)
                for k in range(2, n - 1):
                    Line(points=[sommets[0][0], sommets[0][1], sommets[k][0], sommets[k][1]],
                         width=dp(1.1), dash_length=6, dash_offset=4)
                Color(*Theme.ROUGE)
                Line(circle=(sommets[0][0], sommets[0][1], dp(5)), width=dp(3))

        if not self.detaille:
            return

        for i in range(n):
            a, b = sommets[i], sommets[(i + 1) % n]
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = mx - cx, my - cy
            norme = math.hypot(dx, dy) or 1
            self._poser(str(i + 1), mx + dx / norme * dp(20), my + dy / norme * dp(20), Theme.VERT)

        for j, k in enumerate(range(2, n - 1)):
            mx = (sommets[0][0] + sommets[k][0]) / 2
            my = (sommets[0][1] + sommets[k][1]) / 2
            self._poser("d%d" % (j + 1), mx, my, Theme.ORANGE)

        self._poser("départ", sommets[0][0], sommets[0][1] - dp(18), Theme.ROUGE)

    def _poser(self, texte, x, y, couleur):
        lbl = Label(text=texte, color=couleur, font_size=Theme.sp(12), bold=True,
                    size_hint=(None, None), size=(dp(54), dp(22)))
        lbl.center = (x, y)
        self.add_widget(lbl)


def afficher_croquis_detaille(n_cotes):
    contenu = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
    croquis = Croquis(n_cotes=n_cotes, detaille=True, size_hint_y=1)
    contenu.add_widget(croquis)

    legende = Label(
        text="[color=9fe1cb]1 à %d[/color] : côtés     [color=f59e0b]d1 à d%d[/color] : diagonales\n"
             "Pars du point rouge, tourne toujours dans le même sens."
             % (n_cotes, max(n_cotes - 3, 0)),
        markup=True, font_size=Theme.sp(13), size_hint_y=None,
        height=dp(56) * Theme.echelle_texte, halign="center")
    legende.bind(size=lambda i, v: setattr(i, "text_size", (i.width, None)))
    contenu.add_widget(legende)

    popup = Popup(title="Croquis — %d côtés" % n_cotes, content=contenu, size_hint=(0.92, 0.9))
    contenu.add_widget(bouton("Fermer", popup.dismiss, hauteur=50))
    popup.open()
    Clock.schedule_once(lambda dt: croquis.definir(n_cotes), 0.05)


# =====================================================================
# APERCU
# =====================================================================
class ApercuPanneau(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.points = []
        self.rect_marge = None
        self.bind(size=self._redessiner, pos=self._redessiner)

    def definir(self, points, rect_marge):
        self.points = points
        self.rect_marge = rect_marge
        self._redessiner()

    def _redessiner(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.06, 0.16, 0.26, 1)
            Rectangle(pos=self.pos, size=self.size)
        if not self.points or self.width < 10:
            return

        contour = self.rect_marge if self.rect_marge else self.points
        minx, maxx, miny, maxy = bbox(contour)
        largeur = max(maxx - minx, 1)
        hauteur = max(maxy - miny, 1)
        marge_px = dp(30)
        echelle = min((self.width - marge_px) / largeur, (self.height - marge_px) / hauteur)

        def vers_ecran(pt):
            return (self.x + marge_px / 2 + (pt[0] - minx) * echelle,
                    self.y + marge_px / 2 + (pt[1] - miny) * echelle)

        with self.canvas:
            if self.rect_marge:
                Color(*Theme.ORANGE)
                pts = []
                for p in self.rect_marge + [self.rect_marge[0]]:
                    x, y = vers_ecran(p)
                    pts += [x, y]
                Line(points=pts, width=dp(1.2), dash_length=8, dash_offset=4)

            Color(*Theme.BLEU_CLAIR)
            pts = []
            for p in self.points + [self.points[0]]:
                x, y = vers_ecran(p)
                pts += [x, y]
            Line(points=pts, width=dp(2.2))


# =====================================================================
# APPLICATION
# =====================================================================
class GeoRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.nom_projet = ""
        self.commande = []
        self.base_type = "ngon_4"
        self.champs_cotes = {}
        self.arrondis = []

        self._construire_barre()
        self.zone_contenu = BoxLayout()
        self.add_widget(self.zone_contenu)

        self._restaurer_brouillon()
        self.afficher_page("accueil")

    # ---------------- Barre + menu ----------------
    def _construire_barre(self):
        barre = BoxLayout(size_hint_y=None, height=dp(56) * Theme.echelle_texte,
                           padding=[dp(8), 0], spacing=dp(8))
        with barre.canvas.before:
            Color(*Theme.BLEU_FONCE)
            self._fond_barre = Rectangle(pos=barre.pos, size=barre.size)
        barre.bind(pos=lambda i, v: setattr(self._fond_barre, "pos", v),
                   size=lambda i, v: setattr(self._fond_barre, "size", v))

        barre.add_widget(bouton("Menu", self.ouvrir_menu, taille=14, hauteur=44,
                                 size_hint_x=None, width=dp(72) * Theme.echelle_texte))
        self.titre_barre = Label(text="GEO", font_size=Theme.sp(18), bold=True,
                                  color=(1, 1, 1, 1), halign="left", valign="middle")
        self.titre_barre.bind(size=lambda i, v: setattr(i, "text_size", (i.width, None)))
        barre.add_widget(self.titre_barre)
        self.add_widget(barre)

    def ouvrir_menu(self):
        contenu = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        popup = Popup(title="Menu", content=contenu, size_hint=(0.7, 0.75))

        def aller(page):
            popup.dismiss()
            self.afficher_page(page)

        for libelle, page in [("Accueil", "accueil"), ("Mes projets", "projets"),
                               ("Paramètres", "parametres"), ("À propos", "apropos")]:
            contenu.add_widget(bouton(libelle, lambda p=page: aller(p), taille=16, hauteur=54))

        contenu.add_widget(bouton("Fermer", popup.dismiss, taille=14, hauteur=46))
        popup.open()

    def afficher_page(self, page):
        self.zone_contenu.clear_widgets()
        titres = {"accueil": "GEO", "projets": "Mes projets",
                  "parametres": "Paramètres", "apropos": "À propos"}
        self.titre_barre.text = titres.get(page, "GEO")

        if page == "accueil":
            self.zone_contenu.add_widget(self._page_accueil())
        elif page == "projets":
            self.zone_contenu.add_widget(self._page_projets())
        elif page == "parametres":
            self.zone_contenu.add_widget(self._page_parametres())
        else:
            self.zone_contenu.add_widget(self._page_apropos())

    # ---------------- ACCUEIL ----------------
    def _page_accueil(self):
        racine = BoxLayout(orientation="horizontal")

        col_formes = ScrollView(size_hint_x=0.3)
        grille = GridLayout(cols=1, size_hint_y=None, spacing=dp(8), padding=dp(8))
        grille.bind(minimum_height=grille.setter("height"))
        grille.add_widget(etiquette("Forme", 14, gras=True))

        for key, base in BASES.items():
            n = int(key.split("_")[1])
            ligne = BoxLayout(size_hint_y=None, height=dp(64) * Theme.echelle_texte, spacing=dp(4))
            ligne.add_widget(Croquis(n_cotes=n, detaille=False, size_hint_x=None,
                                      width=dp(56) * Theme.echelle_texte))
            b = bouton(base["label"], lambda k=key: self.choisir_forme(k), taille=15, hauteur=60)
            if key == self.base_type:
                b.background_color = Theme.BLEU_VIF
            ligne.add_widget(b)
            ligne.add_widget(bouton("+", lambda nn=n: afficher_croquis_detaille(nn),
                                     taille=18, hauteur=60, size_hint_x=None,
                                     width=dp(44) * Theme.echelle_texte))
            grille.add_widget(ligne)

        col_formes.add_widget(grille)
        racine.add_widget(col_formes)

        col_saisie = ScrollView(size_hint_x=0.42)
        form = GridLayout(cols=1, size_hint_y=None, spacing=dp(8), padding=dp(10))
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(etiquette("Nom du projet", 13, couleur=Theme.texte_doux()))
        self.champ_projet = champ_saisie(text=self.nom_projet, hint_text="ex. villa_dupont",
                                          size_hint_y=None, height=dp(48) * Theme.echelle_texte)
        self.champ_projet.bind(text=lambda i, v: self._maj_nom_projet(v))
        form.add_widget(self.champ_projet)

        form.add_widget(etiquette("Référence du panneau", 13, couleur=Theme.texte_doux()))
        self.champ_ref = champ_saisie(hint_text="ex. volee1_p3", size_hint_y=None,
                                       height=dp(48) * Theme.echelle_texte)
        form.add_widget(self.champ_ref)

        form.add_widget(etiquette("Cotes (mm)", 14, gras=True))
        self.zone_cotes = GridLayout(cols=2, size_hint_y=None, spacing=dp(6))
        self.zone_cotes.bind(minimum_height=self.zone_cotes.setter("height"))
        form.add_widget(self.zone_cotes)

        form.add_widget(etiquette("Arrondi de coin", 14, gras=True))
        self.zone_arrondis = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        self.zone_arrondis.bind(minimum_height=self.zone_arrondis.setter("height"))
        form.add_widget(self.zone_arrondis)
        form.add_widget(bouton("+ Ajouter un arrondi", self.ajouter_arrondi, taille=14, hauteur=44))

        form.add_widget(etiquette("Options", 14, gras=True))

        ligne_marge = BoxLayout(size_hint_y=None, height=dp(48) * Theme.echelle_texte, spacing=dp(4))
        self.case_marge = CheckBox(active=True, size_hint_x=None, width=dp(46))
        self.case_marge.bind(active=lambda i, v: self.rafraichir_apercu())
        ligne_marge.add_widget(self.case_marge)
        ligne_marge.add_widget(Label(text="Marge", font_size=Theme.sp(14), color=Theme.texte()))
        self.champ_marge = champ_saisie(numerique=True, text="40", size_hint_x=None,
                                         width=dp(86) * Theme.echelle_texte)
        self.champ_marge.bind(text=lambda i, v: self.rafraichir_apercu())
        ligne_marge.add_widget(self.champ_marge)
        form.add_widget(ligne_marge)

        ligne_rect = BoxLayout(size_hint_y=None, height=dp(48) * Theme.echelle_texte, spacing=dp(4))
        self.case_rect = CheckBox(active=False, size_hint_x=None, width=dp(46))
        self.case_rect.bind(active=lambda i, v: self.rafraichir_apercu())
        ligne_rect.add_widget(self.case_rect)
        ligne_rect.add_widget(Label(text="Rectiligne", font_size=Theme.sp(14), color=Theme.texte()))
        self.champ_rect = champ_saisie(numerique=True, text="3", size_hint_x=None,
                                        width=dp(86) * Theme.echelle_texte)
        self.champ_rect.bind(text=lambda i, v: self.rafraichir_apercu())
        ligne_rect.add_widget(self.champ_rect)
        form.add_widget(ligne_rect)

        form.add_widget(etiquette("Aperçu", 14, gras=True))
        self.apercu = ApercuPanneau(size_hint_y=None, height=dp(220) * Theme.echelle_texte)
        form.add_widget(self.apercu)

        self.label_etat = etiquette("", 13, couleur=Theme.ORANGE)
        form.add_widget(self.label_etat)

        form.add_widget(bouton("Ajouter à la commande", self.ajouter_commande,
                                taille=16, hauteur=54, couleur_fond=Theme.ORANGE))

        col_saisie.add_widget(form)
        racine.add_widget(col_saisie)

        col_cmd = ScrollView(size_hint_x=0.28)
        self.zone_commande = GridLayout(cols=1, size_hint_y=None, spacing=dp(8), padding=dp(8))
        self.zone_commande.bind(minimum_height=self.zone_commande.setter("height"))
        col_cmd.add_widget(self.zone_commande)
        racine.add_widget(col_cmd)

        Clock.schedule_once(lambda dt: self._init_accueil(), 0.05)
        return racine

    def _init_accueil(self):
        self._construire_champs_cotes()
        self._rafraichir_commande()

    def _maj_nom_projet(self, valeur):
        self.nom_projet = valeur.strip()
        self._sauver_brouillon()

    def choisir_forme(self, key):
        self.base_type = key
        self.arrondis = []
        self.afficher_page("accueil")

    def _construire_champs_cotes(self):
        base = BASES[self.base_type]
        self.zone_cotes.clear_widgets()
        self.zone_arrondis.clear_widgets()
        self.champs_cotes = {}

        champs = []
        for param in base["parametres"]:
            est_diag = param.startswith("diagonale")
            couleur = Theme.ORANGE if est_diag else Theme.VERT
            self.zone_cotes.add_widget(
                Label(text=param.replace("_", " "), font_size=Theme.sp(13), color=couleur,
                      size_hint_y=None, height=dp(48) * Theme.echelle_texte))
            champ = champ_saisie(numerique=True, text="", hint_text="mm",
                                  size_hint_y=None, height=dp(48) * Theme.echelle_texte)
            champ.bind(text=lambda i, v: self.rafraichir_apercu())
            self.zone_cotes.add_widget(champ)
            self.champs_cotes[param] = champ
            champs.append(champ)

        for i, champ in enumerate(champs[:-1]):
            suivant = champs[i + 1]
            champ.bind(on_text_validate=lambda inst, s=suivant: setattr(s, "focus", True))

        self.rafraichir_apercu()

    def ajouter_arrondi(self):
        n = self._nb_coins()
        entree = {"coin": 0, "rayon": 50}
        self.arrondis.append(entree)

        ligne = BoxLayout(size_hint_y=None, height=dp(48) * Theme.echelle_texte, spacing=dp(4))
        ligne.add_widget(Label(text="Coin", font_size=Theme.sp(13), color=Theme.texte(),
                                size_hint_x=0.25))
        champ_coin = champ_saisie(numerique=True, text="1", size_hint_x=0.25)
        ligne.add_widget(champ_coin)
        ligne.add_widget(Label(text="Rayon", font_size=Theme.sp(13), color=Theme.texte(),
                                size_hint_x=0.25))
        champ_rayon = champ_saisie(numerique=True, text="50", size_hint_x=0.25)
        ligne.add_widget(champ_rayon)

        def maj(*args):
            try:
                entree["coin"] = max(1, min(n, int(float(champ_coin.text or 1)))) - 1
            except ValueError:
                entree["coin"] = 0
            try:
                entree["rayon"] = float(champ_rayon.text or 0)
            except ValueError:
                entree["rayon"] = 0
            self.rafraichir_apercu()

        champ_coin.bind(text=maj)
        champ_rayon.bind(text=maj)
        self.zone_arrondis.add_widget(ligne)
        self.rafraichir_apercu()

    def _nb_coins(self):
        return int(self.base_type.split("_")[1])

    def _params_actuels(self):
        params = {}
        for k, champ in self.champs_cotes.items():
            try:
                params[k] = float(champ.text)
            except ValueError:
                params[k] = 0.0
        return params

    def _geometrie(self, base_type, params, arrondis, marge, rectiligne):
        points = compute_polygon(base_type, params)
        if arrondis:
            points = appliquer_arrondis(points, arrondis)
        points = offset_rectiligne(points, rectiligne)
        rect = rectangle_marge(points, marge) if marge > 0 else None
        return points, rect

    def rafraichir_apercu(self, *args):
        try:
            params = self._params_actuels()
            if not params or all(v == 0 for v in params.values()):
                self.label_etat.text = "Saisis les cotes du gabarit."
                self.apercu.definir([], None)
                return
            if not is_valid(self.base_type, params):
                self.label_etat.text = "Cotes incohérentes : vérifie les mesures."
                self.apercu.definir([], None)
                return
            self.label_etat.text = ""
            marge = float(self.champ_marge.text or 0) if self.case_marge.active else 0
            rectiligne = float(self.champ_rect.text or 0) if self.case_rect.active else 0
            points, rect = self._geometrie(self.base_type, params, self.arrondis, marge, rectiligne)
            self.apercu.definir(points, rect)
        except Exception:
            self.label_etat.text = "Saisie incomplète ou invalide."
            self.apercu.definir([], None)

    # ---------------- Commande ----------------
    def ajouter_commande(self):
        ref = self.champ_ref.text.strip()
        params = self._params_actuels()

        if not ref:
            message("Référence manquante", "Donne une référence au panneau.")
            return
        if any(p["ref"] == ref for p in self.commande):
            message("Référence déjà utilisée",
                     "Un panneau nommé « %s » existe déjà\ndans cette commande." % ref)
            return
        if not is_valid(self.base_type, params):
            if any(v == 0 for v in params.values()):
                message("Cotes manquantes", "Toutes les cotes doivent être renseignées.")
            else:
                message("Cotes incohérentes", "Ces mesures ne permettent pas\nde fermer la forme.")
            return

        marge = float(self.champ_marge.text or 0) if self.case_marge.active else 0
        rectiligne = float(self.champ_rect.text or 0) if self.case_rect.active else 0
        points, rect = self._geometrie(self.base_type, params, self.arrondis, marge, rectiligne)
        minx, maxx, miny, maxy = bbox(rect if rect else points)

        self.commande.append({
            "ref": ref, "base_type": self.base_type, "base_params": dict(params),
            "arrondis": [dict(a) for a in self.arrondis],
            "marge": marge, "rectiligne": rectiligne,
            "w": round(maxx - minx), "h": round(maxy - miny),
        })

        self.champ_ref.text = ""
        self._sauver_brouillon()
        self._rafraichir_commande()

    def _rafraichir_commande(self):
        self.zone_commande.clear_widgets()
        n = len(self.commande)
        self.zone_commande.add_widget(etiquette("Commande (%d)" % n, 15, gras=True))

        if not self.commande:
            self.zone_commande.add_widget(
                etiquette("Aucun panneau.", 13, couleur=Theme.texte_doux()))
            return

        surface = sum(p["w"] * p["h"] for p in self.commande) / 1000000.0
        self.zone_commande.add_widget(
            etiquette("Surface : %.2f m²" % surface, 13, couleur=Theme.texte_doux()))

        for i, p in enumerate(self.commande):
            carte = BoxLayout(orientation="vertical", size_hint_y=None,
                               height=dp(88) * Theme.echelle_texte, padding=dp(4), spacing=dp(2))
            carte.add_widget(Label(text=p["ref"], font_size=Theme.sp(14), bold=True,
                                    color=Theme.texte(), size_hint_y=None,
                                    height=dp(26) * Theme.echelle_texte))
            carte.add_widget(Label(text="%d x %d mm" % (p["w"], p["h"]), font_size=Theme.sp(12),
                                    color=Theme.texte_doux(), size_hint_y=None,
                                    height=dp(22) * Theme.echelle_texte))
            actions = BoxLayout(size_hint_y=None, height=dp(40) * Theme.echelle_texte, spacing=dp(4))
            actions.add_widget(bouton("DXF", lambda pp=p: self.exporter_un_dxf(pp),
                                       taille=13, hauteur=38))
            actions.add_widget(bouton("Suppr.", lambda idx=i: self.supprimer_panneau(idx),
                                       taille=13, hauteur=38))
            carte.add_widget(actions)
            self.zone_commande.add_widget(carte)

        self.zone_commande.add_widget(
            bouton("Valider le projet", self.valider_projet, taille=16, hauteur=54,
                   couleur_fond=Theme.BLEU_VIF))

    def supprimer_panneau(self, index):
        if index >= len(self.commande):
            return
        ref = self.commande[index]["ref"]

        def confirmer():
            self.commande.pop(index)
            self._sauver_brouillon()
            self._rafraichir_commande()

        demander_confirmation("Supprimer le panneau",
                               "Supprimer « %s » de la commande ?" % ref, confirmer)

    # ---------------- Export ----------------
    def _dossier_sortie(self):
        if self.nom_projet:
            dossier = projets.dossier_projet(self.nom_projet)
        else:
            dossier = projets.dossier_telechargements()
        os.makedirs(dossier, exist_ok=True)
        return dossier

    def exporter_un_dxf(self, panneau):
        try:
            points, rect = self._geometrie(panneau["base_type"], panneau["base_params"],
                                            panneau["arrondis"], panneau["marge"],
                                            panneau["rectiligne"])
            chemin = os.path.join(self._dossier_sortie(), "%s.dxf" % panneau["ref"])
            save_dxf(points, rect, panneau["ref"], chemin,
                     self.nom_projet or None, datetime.now().strftime("%Y-%m-%d"))
            message("Export réussi", "%s.dxf\nenregistré dans :\n%s" % (panneau["ref"], chemin))
        except Exception:
            message("Échec de l'export",
                     "Impossible d'enregistrer le fichier.\nVérifie les autorisations de stockage.")

    def valider_projet(self):
        if not self.commande:
            message("Commande vide", "Ajoute au moins un panneau.")
            return
        if not self.nom_projet:
            message("Nom de projet manquant", "Renseigne le nom du projet avant de valider.")
            return

        refs = [p["ref"] for p in self.commande]
        doublons = sorted(set(r for r in refs if refs.count(r) > 1))
        if doublons:
            message("Références en double",
                     "Utilisées plusieurs fois :\n%s" % ", ".join(doublons))
            return

        surface = sum(p["w"] * p["h"] for p in self.commande) / 1000000.0
        recap = ("Projet : %s\n%d panneau(x)\nSurface totale : %.2f m²\n\nGénérer tous les DXF ?"
                 % (self.nom_projet, len(self.commande), surface))
        demander_confirmation("Valider le projet", recap, self._executer_validation)

    def _executer_validation(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        try:
            dossier = projets.dossier_projet(self.nom_projet)
            os.makedirs(dossier, exist_ok=True)
        except Exception:
            message("Échec", "Impossible de créer le dossier du projet.")
            return

        reussis, echecs = 0, []
        for p in self.commande:
            try:
                points, rect = self._geometrie(p["base_type"], p["base_params"],
                                                p["arrondis"], p["marge"], p["rectiligne"])
                save_dxf(points, rect, p["ref"],
                         os.path.join(dossier, "%s.dxf" % p["ref"]),
                         self.nom_projet, date_str)
                reussis += 1
            except Exception:
                echecs.append(p["ref"])

        try:
            projets.sauvegarder_projet(self.nom_projet, self.commande)
        except Exception:
            pass

        texte = "%d fichier(s) DXF générés dans :\nTéléchargements/%s/" % (reussis, self.nom_projet)
        if echecs:
            texte += "\n\nÉchecs : %s" % ", ".join(echecs)
        message("Projet validé", texte)

    # ---------------- Brouillon ----------------
    def _sauver_brouillon(self):
        try:
            projets.sauvegarder_brouillon(self.nom_projet, self.commande)
        except Exception:
            pass

    def _restaurer_brouillon(self):
        try:
            nom, panneaux = projets.charger_brouillon()
            if panneaux:
                self.nom_projet = nom or ""
                self.commande = panneaux
        except Exception:
            pass

    # ---------------- MES PROJETS ----------------
    def _page_projets(self):
        scroll = ScrollView()
        grille = GridLayout(cols=1, size_hint_y=None, spacing=dp(10), padding=dp(12))
        grille.bind(minimum_height=grille.setter("height"))

        try:
            liste = projets.lister_projets()
        except Exception:
            liste = []

        if not liste:
            grille.add_widget(etiquette("Aucun projet enregistré.", 15, couleur=Theme.texte_doux()))
            grille.add_widget(etiquette("Un projet est créé quand tu valides une commande.",
                                         13, couleur=Theme.texte_doux()))
        else:
            grille.add_widget(etiquette("%d projet(s)" % len(liste), 15, gras=True))
            for nom, nb, date in liste:
                carte = BoxLayout(orientation="vertical", size_hint_y=None,
                                   height=dp(98) * Theme.echelle_texte, padding=dp(6), spacing=dp(2))
                carte.add_widget(Label(text=nom, font_size=Theme.sp(15), bold=True,
                                        color=Theme.texte(), size_hint_y=None,
                                        height=dp(28) * Theme.echelle_texte))
                carte.add_widget(Label(text="%d panneau(x)   ·   %s" % (nb, date),
                                        font_size=Theme.sp(12), color=Theme.texte_doux(),
                                        size_hint_y=None, height=dp(24) * Theme.echelle_texte))
                carte.add_widget(bouton("Ouvrir pour modifier", lambda n=nom: self.ouvrir_projet(n),
                                         taille=14, hauteur=42))
                grille.add_widget(carte)

        scroll.add_widget(grille)
        return scroll

    def ouvrir_projet(self, nom):
        panneaux = projets.charger_projet(nom)
        if panneaux is None:
            message("Projet illisible", "Impossible de lire « %s »." % nom)
            return

        def confirmer():
            self.nom_projet = nom
            self.commande = panneaux
            for p in self.commande:
                if "w" not in p or "h" not in p:
                    try:
                        pts, rect = self._geometrie(p["base_type"], p["base_params"],
                                                     p.get("arrondis", []), p.get("marge", 0),
                                                     p.get("rectiligne", 0))
                        minx, maxx, miny, maxy = bbox(rect if rect else pts)
                        p["w"] = round(maxx - minx)
                        p["h"] = round(maxy - miny)
                    except Exception:
                        p["w"], p["h"] = 0, 0
            self._sauver_brouillon()
            self.afficher_page("accueil")

        if self.commande:
            demander_confirmation(
                "Ouvrir le projet",
                "La commande en cours (%d panneaux)\nsera remplacée. Continuer ?" % len(self.commande),
                confirmer)
        else:
            confirmer()

    # ---------------- PARAMETRES ----------------
    def _page_parametres(self):
        scroll = ScrollView()
        grille = GridLayout(cols=1, size_hint_y=None, spacing=dp(14), padding=dp(14))
        grille.bind(minimum_height=grille.setter("height"))

        grille.add_widget(etiquette("Affichage", 16, gras=True))

        ligne_nuit = BoxLayout(size_hint_y=None, height=dp(52) * Theme.echelle_texte)
        case = CheckBox(active=Theme.mode_nuit, size_hint_x=None, width=dp(50))
        ligne_nuit.add_widget(case)
        lbl = Label(text="Mode nuit", font_size=Theme.sp(15), color=Theme.texte(),
                    halign="left", valign="middle")
        lbl.bind(size=lambda i, v: setattr(i, "text_size", (i.width, None)))
        ligne_nuit.add_widget(lbl)
        grille.add_widget(ligne_nuit)

        def basculer(instance, valeur):
            Theme.mode_nuit = valeur
            Window.clearcolor = Theme.fond()
            self._reconstruire("parametres")

        case.bind(active=basculer)

        grille.add_widget(etiquette("Taille du texte", 16, gras=True))
        ligne_taille = BoxLayout(size_hint_y=None, height=dp(56) * Theme.echelle_texte, spacing=dp(6))
        for libelle, valeur in [("Petit", 0.85), ("Normal", 1.0), ("Grand", 1.2), ("Très grand", 1.4)]:
            b = bouton(libelle, lambda v=valeur: self._changer_taille(v), taille=14, hauteur=50)
            if abs(Theme.echelle_texte - valeur) < 0.01:
                b.background_color = Theme.BLEU_VIF
            ligne_taille.add_widget(b)
        grille.add_widget(ligne_taille)

        grille.add_widget(etiquette("Les changements s'appliquent immédiatement.",
                                     12, couleur=Theme.texte_doux()))
        scroll.add_widget(grille)
        return scroll

    def _changer_taille(self, valeur):
        Theme.echelle_texte = valeur
        self._reconstruire("parametres")

    def _reconstruire(self, page):
        self.clear_widgets()
        self._construire_barre()
        self.zone_contenu = BoxLayout()
        self.add_widget(self.zone_contenu)
        self.afficher_page(page)

    # ---------------- A PROPOS ----------------
    def _page_apropos(self):
        scroll = ScrollView()
        grille = GridLayout(cols=1, size_hint_y=None, spacing=dp(12), padding=dp(16))
        grille.bind(minimum_height=grille.setter("height"))

        grille.add_widget(etiquette("GEO", 24, gras=True, height=dp(46)))
        grille.add_widget(etiquette("Dessin de gabarits", 15, couleur=Theme.texte_doux()))
        grille.add_widget(etiquette("Version 1.0", 13, couleur=Theme.texte_doux()))

        texte = ("GEO transforme les cotes relevées sur un gabarit\n"
                 "en fichier DXF prêt pour la découpe.\n\n"
                 "Formes de 3 à 8 côtés, mesurées par leurs côtés\n"
                 "et leurs diagonales, sans logiciel de CAO.\n\n"
                 "Les fichiers sont enregistrés dans Téléchargements,\n"
                 "dans un sous-dossier au nom du projet.\n\n"
                 "Vérifie toujours les cotes du DXF avant découpe.")
        lbl = Label(text=texte, font_size=Theme.sp(13), color=Theme.texte(),
                    size_hint_y=None, halign="center", valign="top")
        lbl.bind(size=lambda i, v: setattr(i, "text_size", (i.width, None)),
                 texture_size=lambda i, v: setattr(i, "height", v[1]))
        grille.add_widget(lbl)

        scroll.add_widget(grille)
        return scroll


class GeoApp(App):
    def build(self):
        self.title = "GEO"
        Window.clearcolor = Theme.fond()
        return GeoRoot()


if __name__ == "__main__":
    GeoApp().run()
