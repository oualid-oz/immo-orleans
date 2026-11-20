"""Application Streamlit : affichage uniquement, les calculs sont dans calculs.py."""

import plotly.express as px
import streamlit as st

from calculs import (
    charger,
    evolution,
    filtrer,
    indicateurs,
    par_commune,
    par_section,
    tendance,
    ventes_section,
)

BLEU = "#0072B2"  # Okabe-Ito
ORANGE = "#E69F00"  # Okabe-Ito
NB_COMMUNES = 20


def nombre(x: float) -> str:
    """Formate un nombre à la française : 1 234."""
    return f"{x:,.0f}".replace(",", " ")


# ---------- Données et agrégats en cache ----------


@st.cache_data
def charger_donnees():
    return charger()


@st.cache_data
def vue_filtree(type_bien, budget_max, surface_min, annees):
    return filtrer(charger_donnees(), type_bien, budget_max, surface_min, annees)


@st.cache_data
def communes_cache(vue, n_min):
    return par_commune(vue, n_min)


@st.cache_data
def sections_cache(vue, commune, n_min):
    return par_section(vue, commune, n_min)


@st.cache_data
def evolution_cache(vue, n_min):
    return evolution(vue, n_min)


# ---------- Page et filtres ----------

st.set_page_config(page_title="Immo Orléans", layout="wide")
st.title("Où acheter autour d'Orléans avec notre budget ?")

with st.sidebar:
    st.header("Nos critères")
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

vue = vue_filtree(type_bien, budget_max, surface_min, annees)

if vue.empty:
    st.warning("Aucune vente ne correspond à ces critères. Élargissez le budget ou la surface.")
    st.stop()

# ---------- Indicateurs ----------

ind = indicateurs(vue)
col1, col2, col3 = st.columns(3)
col1.metric("Ventes correspondantes", nombre(ind["nb_ventes"]))
col2.metric("Prix médian au m²", f"{nombre(ind['prix_m2_median'])} €/m²")
col3.metric("Prix médian", f"{nombre(ind['prix_median'])} €")

# ---------- Niveau 1 : communes ----------

communes = communes_cache(vue, n_min)
if communes.empty:
    st.warning(f"Aucune commune n'a au moins {n_min} ventes avec ces critères.")
    st.stop()

top = communes.head(NB_COMMUNES)
moins_chere = top.iloc[0]
titre = (
    f"{moins_chere['nom_commune']} : {nombre(moins_chere['prix_m2_med'])} €/m² médian "
    f"sur {moins_chere['n']} ventes, la moins chère"
)
etiquettes = [f"{nombre(p)} €/m² ({n} ventes)" for p, n in zip(top["prix_m2_med"], top["n"])]
fig = px.bar(
    top.assign(etiquette=etiquettes),
    x="prix_m2_med",
    y="nom_commune",
    orientation="h",
    text="etiquette",
    title=titre,
    labels={"prix_m2_med": "Prix médian (€/m²)", "nom_commune": "Commune", "n": "Ventes"},
    hover_data={"n": True, "prix_med": ":,.0f", "etiquette": False},
    color_discrete_sequence=[BLEU],
)
fig.update_traces(textposition="outside", textfont_size=12)
fig.update_layout(
    yaxis={"categoryorder": "total descending"},  # la moins chère en haut
    font_size=12,
    height=650,
    margin={"r": 170},
)

st.subheader(f"Les {len(top)} communes les moins chères au m²")
st.caption("Cliquez sur une barre pour voir le détail de la commune, ou choisissez-la plus bas.")
evenement = st.plotly_chart(
    fig,
    on_select="rerun",
    selection_mode="points",
    key="communes",
    alt=(
        f"Barres horizontales des {len(top)} communes les moins chères au m² pour ces critères. "
        f"{titre}."
    ),
)

# Un nouveau clic sur une barre choisit la commune dans la liste déroulante.
# On retient le dernier clic, sinon il écraserait un choix fait ensuite dans la liste.
points = evenement.selection.points
clic = points[0]["y"] if points else None
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

col_evo, col_sections = st.columns(2)

with col_evo:
    evo = evolution_cache(vue_commune, n_min)
    tend = tendance(evo)
    if tend is None:
        st.info(f"Pas assez d'années avec au moins {n_min} ventes pour montrer une évolution.")
    else:
        sens = "en baisse" if tend["variation_pct"] < 0 else "en hausse"
        titre_evo = (
            f"Prix {sens} de {abs(tend['variation_pct']):.0f} % entre {tend['debut']} et "
            f"{tend['fin']} ({nombre(tend['prix_debut'])} → {nombre(tend['prix_fin'])} €/m², "
            f"{nombre(evo['n'].sum())} ventes)"
        )
        fig_evo = px.line(
            evo,
            x="annee",
            y="prix_m2_med",
            markers=True,
            text=[f"{n} ventes" for n in evo["n"]],
            title=titre_evo,
            labels={"annee": "Année", "prix_m2_med": "Prix médian (€/m²)", "n": "Ventes"},
            hover_data={"n": True},
            color_discrete_sequence=[ORANGE],
        )
        fig_evo.update_traces(textposition="top center", textfont_size=12, marker_size=10)
        fig_evo.update_layout(font_size=12, xaxis={"dtick": 1})
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
            hide_index=True,
            column_config={
                "section": "Section",
                "n": "Ventes",
                "prix_m2_med": st.column_config.NumberColumn("Prix médian (€/m²)", format="%.0f"),
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
        hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "Prix (€)": st.column_config.NumberColumn("Prix (€)", format="%.0f"),
            "Prix (€/m²)": st.column_config.NumberColumn("Prix (€/m²)", format="%.0f"),
            "Surface (m²)": st.column_config.NumberColumn("Surface (m²)", format="%.0f"),
            "Pièces": st.column_config.NumberColumn("Pièces", format="%.0f"),
        },
    )

# ---------- Méthode et limites ----------

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
- **Localisation** : la section cadastrale est le niveau le plus fin, pas d'adresse.
"""
    )

st.caption("Source : DGFiP, DVF, Licence Ouverte 2.0.")
