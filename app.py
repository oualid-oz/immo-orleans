"""Application Streamlit : affichage uniquement, les calculs sont dans calculs.py."""

import plotly.express as px
import streamlit as st

from calculs import (
    carte_communes,
    charger,
    comparables,
    evolution,
    filtrer,
    indicateurs,
    par_commune,
    par_section,
    surface_pour_budget,
    tendance,
    ventes_section,
)
from modele import charger_metriques, charger_modele, predire

# Couleurs Okabe-Ito choisies pour leur contraste (>= 3:1 sur fond clair et sombre).
# L'orange #E69F00 n'est qu'à 2,2:1 sur blanc : on prend le vermillon.
BLEU = "#0072B2"
VERMILLON = "#D55E00"
NB_COMMUNES = 20
# Carte, de la moins chère à la plus chère. Orange, bleu ciel et pourpre sont trop clairs
# sur le fond de carte (< 3:1) : bleu 5,0:1, vert 3,3:1, vermillon 3,7:1, noir 20:1.
COULEURS_CARTE = [BLEU, "#009E73", VERMILLON, "#000000"]
TAILLE_TEXTE = 12  # px, minimum pour tout le texte des graphiques


def nombre(x: float) -> str:
    """Formate un nombre à la française : 1 234."""
    return f"{x:,.0f}".replace(",", " ")


def lisible(fig):
    """Tailles de texte explicites (>= 12 px) : le thème Streamlit ne peut pas les réduire."""
    fig.update_layout(
        font_size=TAILLE_TEXTE,
        title_font_size=16,
        hoverlabel_font_size=TAILLE_TEXTE,
    )
    fig.update_xaxes(tickfont_size=TAILLE_TEXTE, title_font_size=TAILLE_TEXTE)
    fig.update_yaxes(tickfont_size=TAILLE_TEXTE, title_font_size=TAILLE_TEXTE)
    fig.update_traces(textfont_size=TAILLE_TEXTE)
    return fig


# ---------- Données et agrégats en cache ----------


@st.cache_data
def charger_donnees():
    return charger()


@st.cache_data
def vue_filtree(type_bien, budget_max, surface_min, annees):
    return filtrer(charger_donnees(), type_bien, budget_max, surface_min, annees)


@st.cache_data
def codes_communes_cache():
    """Nom de commune -> code INSEE (le modèle utilise le code)."""
    df = charger_donnees()
    return dict(zip(df["nom_commune"], df["code_commune"]))


@st.cache_data
def communes_cache(vue, n_min):
    return par_commune(vue, n_min)


@st.cache_data
def carte_cache(vue, n_min):
    return carte_communes(vue, n_min)


@st.cache_data
def sections_cache(vue, commune, n_min):
    return par_section(vue, commune, n_min)


@st.cache_data
def evolution_cache(vue, n_min):
    return evolution(vue, n_min)


# ---------- Page et filtres ----------

st.set_page_config(page_title="Immo Orléans", layout="wide")
st.title("Où acheter autour d'Orléans avec notre budget ?")

onglet_communes, onglet_prix = st.tabs(
    ["Où chercher ?", "Ce prix est-il raisonnable ?"], key="onglets"
)
pied = st.container()  # sous les onglets

with st.sidebar:
    st.header("Nos critères")
    st.caption("Ces filtres s'appliquent à l'onglet « Où chercher ? ».")
    type_bien = st.radio("Type de bien", ["Maison", "Appartement"], key="type")
    budget_max = st.slider(
        "Budget maximum (€)", 50_000, 2_000_000, 300_000, step=10_000, key="budget"
    )
    surface_min = st.slider("Surface minimum (m²)", 0, 200, 0, step=5, key="surface")
    annees = st.slider("Années de vente", 2021, 2025, (2021, 2025), key="annees")
    n_min = st.slider(
        "Ventes minimum par groupe",
        3,
        50,
        10,
        key="n_min",
        help="Les communes, sections et années avec moins de ventes sont masquées.",
    )


# ---------- Pied de page : méthode, limites et source (rempli avant les st.stop) ----------

with pied:
    metriques = charger_metriques()
    with st.expander("Méthode et limites"):
        st.markdown(
            f"""
- **Source** : DGFiP, DVF (Demandes de valeurs foncières), Licence Ouverte 2.0.
  46 022 ventes dans le Loiret, 2021-2025.
- **Filtres appliqués à la source** : une seule habitation par vente, prix entre 10 000 € et
  2 000 000 €, surface entre 9 et 400 m², prix entre 300 et 8 000 €/m².
- **Médianes, jamais de moyennes** : une vente très chère ou très bon marché ne déforme pas le
  résultat.
- **Groupes trop petits masqués** : une commune, une section ou une année avec moins de
  {n_min} ventes n'est pas affichée (réglage « Ventes minimum par groupe »).
- **Ce que DVF ne dit pas** : l'état du logement, l'étage, le DPE, les travaux à prévoir.
  Un prix bas peut cacher un bien à rénover.
- **Localisation** : la section cadastrale est le niveau le plus fin, pas d'adresse. Sur la
  carte, chaque cercle est placé à la position médiane des ventes de la commune ; les 4 couleurs
  sont 4 tranches de même effectif, dont les bornes sont écrites dans la légende.
- **Surface pour notre budget** : budget ÷ prix médian au m². Ordre de grandeur seulement :
  ni frais de notaire (environ 7 à 8 % dans l'ancien), ni travaux.
- **Modèle de prix** : gradient boosting (scikit-learn) sur le type, la commune, la surface,
  les pièces, le terrain et l'année. Validation croisée 5 plis sur
  {nombre(metriques["nb_ventes"])} ventes : erreur médiane
  {nombre(metriques["modele"]["erreur_mediane"])} € (MAPE {metriques["modele"]["mape"]:.0f} %),
  contre {nombre(metriques["reference"]["erreur_mediane"])} € (MAPE
  {metriques["reference"]["mape"]:.0f} %) pour la référence « médiane €/m² de la commune
  × surface ». Le modèle ne voit ni l'état, ni l'étage, ni le DPE.
"""
        )
    st.caption("Source : DGFiP, DVF, Licence Ouverte 2.0.")

# ---------- Onglet 2 : ce prix est-il raisonnable ? ----------

with onglet_prix:
    df = charger_donnees()
    codes_communes = codes_communes_cache()
    st.caption(
        "Les filtres de la barre latérale ne s'appliquent pas ici : "
        "décrivez le bien et son prix demandé."
    )
    with st.form("form_prix"):
        col_a, col_b = st.columns(2)
        # Sur téléphone les colonnes s'empilent : on décrit le bien d'abord, le prix en dernier.
        with col_a:
            st.radio("Type de bien", ["Maison", "Appartement"], key="prix_type", horizontal=True)
            noms = sorted(codes_communes)
            st.selectbox("Commune", noms, index=noms.index("Orléans"), key="prix_commune")
            st.number_input("Surface habitable (m²)", 9, 400, 90, key="prix_surface")
        with col_b:
            st.number_input("Pièces principales", 1, 15, 4, key="prix_pieces")
            st.number_input("Terrain (m², 0 si aucun)", 0, 100_000, 0, step=50, key="prix_terrain")
            st.number_input(
                "Prix demandé (€)", 10_000, 2_000_000, 200_000, step=5_000, key="prix_demande"
            )
        if st.form_submit_button("Estimer", key="prix_estimer"):
            st.session_state["prix_soumis"] = True

    if not st.session_state.get("prix_soumis"):
        st.info("Remplissez le formulaire puis cliquez sur « Estimer ».")
    else:
        etat = st.session_state
        estimation = predire(
            charger_modele(),
            etat["prix_type"],
            codes_communes[etat["prix_commune"]],
            etat["prix_surface"],
            etat["prix_pieces"],
            etat["prix_terrain"],
        )
        ecart = 100 * (etat["prix_demande"] / estimation - 1)
        marge = metriques["modele"]["erreur_mediane_pct"]

        col1, col2, col3 = st.columns(3)
        col1.metric("Prix estimé par le modèle", f"{nombre(estimation)} €")
        col2.metric("Prix demandé", f"{nombre(etat['prix_demande'])} €")
        col3.metric("Écart avec l'estimation", f"{ecart:+.0f} %")

        if abs(ecart) <= marge:
            st.info(
                f"L'écart ({ecart:+.0f} %) est dans l'erreur habituelle du modèle (± {marge:.0f} %).",
                title="Prix cohérent avec le marché",
            )
        elif ecart > 0:
            st.warning(
                f"Le prix demandé est {ecart:.0f} % au-dessus de l'estimation. "
                "Vérifiez ce qui le justifie (état, DPE, étage, travaux) ou négociez.",
                title="Prix au-dessus du marché",
            )
        else:
            st.warning(
                f"Le prix demandé est {abs(ecart):.0f} % sous l'estimation. "
                "Vérifiez l'état du bien et les travaux à prévoir : DVF ne les connaît pas.",
                title="Prix en dessous du marché",
            )

        proches = comparables(df, etat["prix_commune"], etat["prix_type"], etat["prix_surface"])
        if proches.empty:
            st.info("Aucune vente comparable (même commune, même type, surface ± 20 %).")
        else:
            st.subheader(
                f"{len(proches)} ventes comparables à {etat['prix_commune']} : "
                f"médiane {nombre(proches['Prix (€)'].median())} € "
                f"({nombre(proches['Prix (€/m²)'].median())} €/m²)"
            )
            st.caption("Même commune, même type, surface à ± 20 %, les plus proches en surface.")
            st.dataframe(
                proches,
                key="table_comparables",
                alt=(
                    f"Tableau des {len(proches)} ventes comparables à {etat['prix_commune']} : "
                    "date, section, surface, pièces, terrain, prix et prix au m²."
                ),
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "Prix (€)": st.column_config.NumberColumn("Prix (€)", format="%.0f"),
                    "Prix (€/m²)": st.column_config.NumberColumn("Prix (€/m²)", format="%.0f"),
                    "Surface (m²)": st.column_config.NumberColumn("Surface (m²)", format="%.0f"),
                    "Terrain (m²)": st.column_config.NumberColumn("Terrain (m²)", format="%.0f"),
                    "Pièces": st.column_config.NumberColumn("Pièces", format="%.0f"),
                },
            )

    st.caption(
        f"Modèle : erreur médiane {nombre(metriques['modele']['erreur_mediane'])} € "
        f"(MAPE {metriques['modele']['mape']:.0f} %) contre "
        f"{nombre(metriques['reference']['erreur_mediane'])} € pour la référence "
        "(médiane €/m² de la commune et du type × surface), validation croisée 5 plis."
    )

# ---------- Onglet 1 : où chercher ? ----------

with onglet_communes:
    st.caption(
        "Budget, surface, type et années se règlent dans le panneau « Nos critères » "
        "(sur téléphone : bouton › en haut à gauche)."
    )
    vue = vue_filtree(type_bien, budget_max, surface_min, annees)

    if vue.empty:
        st.warning("Aucune vente ne correspond à ces critères. Élargissez le budget ou la surface.")
        st.stop()

    # ---------- Indicateurs ----------

    ind = indicateurs(vue)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ventes correspondantes", nombre(ind["nb_ventes"]))
    col2.metric("Prix médian au m²", f"{nombre(ind['prix_m2_median'])} €/m²")
    col3.metric("Prix médian", f"{nombre(ind['prix_median'])} €")
    col4.metric(
        "Surface pour notre budget",
        f"{nombre(budget_max / ind['prix_m2_median'])} m²",
        help="Budget ÷ prix médian au m². Indicatif : hors frais de notaire et travaux.",
    )

    # ---------- Niveau 1 : communes (classement ou carte) ----------

    communes = surface_pour_budget(communes_cache(vue, n_min), budget_max)
    if communes.empty:
        st.warning(f"Aucune commune n'a au moins {n_min} ventes avec ces critères.")
        st.stop()

    affichage = st.segmented_control(
        "Affichage des communes",
        ["Classement", "Carte"],
        default="Classement",
        required=True,
        key="affichage",
    )

    if affichage == "Carte":
        carte = surface_pour_budget(carte_cache(vue, n_min), budget_max)
        moins_chere = carte.iloc[0]
        plus_chere = carte.iloc[-1]
        constat = (
            f"{len(carte)} communes, {nombre(carte['n'].sum())} ventes : de "
            f"{nombre(moins_chere['prix_m2_med'])} €/m² ({moins_chere['nom_commune']})"
        )
        suite = f"à {nombre(plus_chere['prix_m2_med'])} €/m² ({plus_chere['nom_commune']})"
        titre = f"{constat} {suite}"
        fig = px.scatter_map(
            carte,
            lat="latitude",
            lon="longitude",
            color="tranche",
            size="n",
            size_max=30,
            hover_name="nom_commune",
            hover_data={
                "prix_m2_med": ":,.0f",
                "n": True,
                "surface_budget": ":.0f",
                "tranche": False,
                "latitude": False,
                "longitude": False,
            },
            custom_data=["nom_commune"],
            labels={
                "prix_m2_med": "Prix médian (€/m²)",
                "n": "Ventes",
                "surface_budget": "m² pour notre budget",
                "tranche": "Prix médian au m²",
            },
            # Ordre des tranches = ordre des lignes (de la moins chère à la plus chère).
            category_orders={"tranche": list(dict.fromkeys(carte["tranche"]))},
            color_discrete_sequence=COULEURS_CARTE,
            map_style="carto-positron",
            zoom=7.5,
            center={"lat": carte["latitude"].median(), "lon": carte["longitude"].median()},
            title=f"{constat}<br>{suite}",
        )
        fig.update_layout(height=650, legend={"title": "Prix médian au m²"})
        lisible(fig)
        aide = "Cliquez sur un cercle pour voir le détail de la commune, ou choisissez-la plus bas."
        alt = (
            f"Carte des communes du Loiret, chaque cercle coloré selon sa tranche de prix médian "
            f"au m² (du bleu, la moins chère, au noir) et dimensionné selon le nombre de ventes. "
            f"{titre}."
        )
        config = {"scrollZoom": False}  # sur téléphone, le doigt fait défiler la page, pas la carte
    else:
        top = communes.head(NB_COMMUNES)
        moins_chere = top.iloc[0]
        constat = (
            f"{moins_chere['nom_commune']} : {nombre(moins_chere['prix_m2_med'])} €/m² médian "
            f"sur {moins_chere['n']} ventes"
        )
        titre = f"{constat}, la moins chère"
        etiquettes = [
            f"{nombre(p)} €/m² ({n} ventes)" for p, n in zip(top["prix_m2_med"], top["n"])
        ]
        fig = px.bar(
            top.assign(etiquette=etiquettes),
            x="prix_m2_med",
            y="nom_commune",
            orientation="h",
            text="etiquette",
            # Plotly ne coupe pas les titres : retour à la ligne pour les écrans étroits.
            title=f"{constat},<br>la moins chère",
            labels={
                "prix_m2_med": "Prix médian (€/m²)",
                "nom_commune": "Commune",
                "n": "Ventes",
                "surface_budget": "m² pour notre budget",
            },
            hover_data={
                "n": True,
                "prix_med": ":,.0f",
                "surface_budget": ":.0f",
                "etiquette": False,
            },
            custom_data=["nom_commune"],
            color_discrete_sequence=[BLEU],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            yaxis={"categoryorder": "total descending"},  # la moins chère en haut
            height=650,
            margin={"r": 170},
        )
        lisible(fig)
        aide = "Cliquez sur une barre pour voir le détail de la commune, ou choisissez-la plus bas."
        alt = (
            f"Barres horizontales des {len(top)} communes les moins chères au m² pour ces "
            f"critères. {titre}."
        )
        config = None

    st.caption(aide)
    evenement = st.plotly_chart(
        fig,
        on_select="rerun",
        selection_mode="points",
        key=f"communes_{affichage}",  # une clé par affichage : chaque graphique garde son état
        alt=alt,
        config=config,
    )

    # Un nouveau clic (barre ou cercle) choisit la commune dans la liste déroulante.
    # On retient le dernier clic, sinon il écraserait un choix fait ensuite dans la liste.
    # Le nom de la commune est dans customdata, pour la barre comme pour le cercle.
    points = evenement.selection.points
    clic = points[0]["customdata"][0] if points else None
    if clic and clic != st.session_state.get("dernier_clic"):
        st.session_state["commune"] = clic
    st.session_state["dernier_clic"] = clic

    # ---------- Niveau 2 : la commune choisie ----------

    options = sorted(communes["nom_commune"])
    if st.session_state.get("commune") not in options:
        # Par défaut : la commune avec le plus de ventes, pour que les 3 niveaux soient remplis.
        st.session_state["commune"] = communes.loc[communes["n"].idxmax(), "nom_commune"]
    commune = st.selectbox("Commune", options, key="commune")

    vue_commune = vue[vue["nom_commune"] == commune]
    st.header(commune)
    ligne = communes[communes["nom_commune"] == commune].iloc[0]
    col1, col2, col3 = st.columns(3)
    col1.metric("Ventes", nombre(ligne["n"]))
    col2.metric("Prix médian au m²", f"{nombre(ligne['prix_m2_med'])} €/m²")
    col3.metric(f"Surface pour {nombre(budget_max)} €", f"{nombre(ligne['surface_budget'])} m²")
    st.caption(
        "Surface = budget ÷ prix médian au m² des ventes de la commune qui correspondent à nos "
        "critères. Indicatif : sans les frais de notaire (environ 7 à 8 % dans l'ancien) ni travaux."
    )

    col_evo, col_sections = st.columns(2)

    with col_evo:
        evo = evolution_cache(vue_commune, n_min)
        tend = tendance(evo)
        if tend is None:
            st.info(f"Pas assez d'années avec au moins {n_min} ventes pour montrer une évolution.")
        else:
            variation = tend["variation_pct"]
            if abs(variation) < 1:
                sens = "Prix stables"  # sinon on écrirait « en baisse de 0 % »
            elif variation < 0:
                sens = f"Prix en baisse de {abs(variation):.0f} %"
            else:
                sens = f"Prix en hausse de {variation:.0f} %"
            periode = f"{sens} entre {tend['debut']} et {tend['fin']}"
            detail = (
                f"{nombre(tend['prix_debut'])} → {nombre(tend['prix_fin'])} €/m², "
                f"{nombre(evo['n'].sum())} ventes"
            )
            titre_evo = f"{periode} ({detail})"
            fig_evo = px.line(
                evo,
                x="annee",
                y="prix_m2_med",
                markers=True,
                text=[f"{n} ventes" for n in evo["n"]],
                title=f"{periode}<br>({detail})",  # sur deux lignes : colonne étroite
                labels={"annee": "Année", "prix_m2_med": "Prix médian (€/m²)", "n": "Ventes"},
                hover_data={"n": True},
                color_discrete_sequence=[VERMILLON],
            )
            fig_evo.update_traces(textposition="top center", marker_size=10)
            fig_evo.update_layout(xaxis={"dtick": 1})
            lisible(fig_evo)
            st.plotly_chart(
                fig_evo,
                key="evolution",
                alt=f"Courbe du prix médian au m² par année à {commune}. {titre_evo}.",
            )

    with col_sections:
        sections = sections_cache(vue, commune, n_min)
        st.subheader("Prix par section cadastrale")
        if sections.empty:
            st.info(f"Aucune section n'a au moins {n_min} ventes avec ces critères.")
        else:
            st.caption(
                f"{len(sections)} sections avec au moins {n_min} ventes, de la moins chère à la plus "
                "chère. La section est le niveau le plus fin publié (pas d'adresse)."
            )
            st.dataframe(
                sections,
                key="table_sections",
                alt=(
                    f"Tableau des {len(sections)} sections cadastrales ({commune}) : "
                    "nombre de ventes, prix médian au m² et prix médian."
                ),
                hide_index=True,
                column_config={
                    "section": "Section",
                    "n": "Ventes",
                    "prix_m2_med": st.column_config.NumberColumn(
                        "Prix médian (€/m²)", format="%.0f"
                    ),
                    "prix_med": st.column_config.NumberColumn("Prix médian (€)", format="%.0f"),
                },
            )

    # ---------- Niveau 3 : les ventes d'une section ----------

    if not sections.empty:
        options_sections = list(sections["section"])
        # Une clé par commune : la section "AB" de Gien n'est pas celle d'Orléans.
        cle_section = f"section_{commune}"
        if st.session_state.get(cle_section) not in options_sections:
            st.session_state[cle_section] = options_sections[0]
        section = st.selectbox("Section cadastrale", options_sections, key=cle_section)
        ventes = ventes_section(vue, commune, section)
        st.subheader(f"{commune}, section {section} : {len(ventes)} ventes")
        st.dataframe(
            ventes,
            key="table_ventes",
            alt=f"Tableau des {len(ventes)} ventes de la section {section} à {commune}.",
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "Prix (€)": st.column_config.NumberColumn("Prix (€)", format="%.0f"),
                "Prix (€/m²)": st.column_config.NumberColumn("Prix (€/m²)", format="%.0f"),
                "Surface (m²)": st.column_config.NumberColumn("Surface (m²)", format="%.0f"),
                "Pièces": st.column_config.NumberColumn("Pièces", format="%.0f"),
            },
        )
