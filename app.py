"""Application Streamlit : affichage uniquement, les calculs sont dans calculs.py."""

import plotly.express as px
import streamlit as st

from calculs import charger, par_commune

BLEU_OKABE_ITO = "#0072B2"
NB_COMMUNES = 20


def nombre(x: float) -> str:
    """Formate un nombre à la française : 1 234."""
    return f"{x:,.0f}".replace(",", " ")


@st.cache_data
def charger_donnees():
    return charger()


@st.cache_data
def communes(type_bien: str):
    df = charger_donnees()
    return par_commune(df[df["type"] == type_bien])


st.set_page_config(page_title="Immo Orléans", layout="wide")
st.title("Où acheter autour d'Orléans avec notre budget ?")

type_bien = st.sidebar.radio("Type de bien", ["Maison", "Appartement"], key="type")

top = communes(type_bien).head(NB_COMMUNES)

if top.empty:
    st.warning("Pas assez de ventes pour afficher des communes.")
else:
    moins_chere = top.iloc[0]
    titre = (
        f"{moins_chere['nom_commune']} : {nombre(moins_chere['prix_m2_med'])} €/m² médian "
        f"sur {moins_chere['n']} ventes, la moins chère"
    )

    etiquettes = [
        f"{nombre(prix)} €/m² ({n} ventes)" for prix, n in zip(top["prix_m2_med"], top["n"])
    ]
    top = top.assign(etiquette=etiquettes)
    fig = px.bar(
        top,
        x="prix_m2_med",
        y="nom_commune",
        orientation="h",
        text="etiquette",
        title=titre,
        labels={"prix_m2_med": "Prix médian (€/m²)", "nom_commune": "Commune", "n": "Ventes"},
        hover_data={"n": True, "prix_med": ":,.0f", "etiquette": False},
        color_discrete_sequence=[BLEU_OKABE_ITO],
    )
    fig.update_traces(textposition="outside", textfont_size=12)
    fig.update_layout(
        yaxis={"categoryorder": "total descending"},  # la moins chère en haut
        font_size=12,
        height=650,
        margin={"r": 160},
    )
    st.plotly_chart(
        fig,
        key="graphique_communes",
        alt=(
            f"Barres horizontales : les {len(top)} communes du Loiret où le prix médian "
            f"au m² des {type_bien.lower()}s est le plus bas. {titre}."
        ),
    )

st.caption(
    "Source : DGFiP, DVF (Demandes de valeurs foncières), Licence Ouverte 2.0. "
    "Ventes 2021-2025, Loiret. Communes avec moins de 10 ventes masquées. "
    "DVF ne dit rien de l'état du bien, de l'étage ni du DPE."
)
