"""Calculs purs (pandas uniquement, pas de streamlit) pour l'application Immo Orléans."""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data" / "immobilier.parquet"


def charger() -> pd.DataFrame:
    """Charge les ventes DVF du Loiret (2021-2025)."""
    return pd.read_parquet(DATA)


def filtrer(
    df: pd.DataFrame,
    type_bien: str,
    budget_max: float,
    surface_min: float,
    annees: tuple[int, int],
) -> pd.DataFrame:
    """Garde les ventes du type choisi, dans le budget, assez grandes et dans les années choisies."""
    debut, fin = annees
    garder = (
        (df["type"] == type_bien)
        & (df["valeur_fonciere"] <= budget_max)
        & (df["surface_reelle_bati"] >= surface_min)
        & (df["annee"].between(debut, fin))
    )
    return df[garder]


def indicateurs(vue: pd.DataFrame) -> dict:
    """Nombre de ventes, prix médian au m² et prix médian de la vue."""
    return {
        "nb_ventes": len(vue),
        "prix_m2_median": vue["prix_m2"].median(),
        "prix_median": vue["valeur_fonciere"].median(),
    }


def _medianes(vue: pd.DataFrame, colonne: str, n_min: int) -> pd.DataFrame:
    """Nombre de ventes et médianes par valeur de `colonne`, groupes de moins de n_min masqués."""
    resultat = (
        vue.groupby(colonne)
        .agg(
            n=("prix_m2", "size"),
            prix_m2_med=("prix_m2", "median"),
            prix_med=("valeur_fonciere", "median"),
        )
        .reset_index()
    )
    resultat = resultat[resultat["n"] >= n_min]
    return resultat.sort_values("prix_m2_med").reset_index(drop=True)


def par_commune(vue: pd.DataFrame, n_min: int = 10) -> pd.DataFrame:
    """Médianes par commune (nom_commune, n, prix_m2_med, prix_med), de la moins chère à la plus chère."""
    return _medianes(vue, "nom_commune", n_min)


def par_section(vue: pd.DataFrame, commune: str, n_min: int = 10) -> pd.DataFrame:
    """Médianes par section cadastrale d'une commune (section, n, prix_m2_med, prix_med)."""
    return _medianes(vue[vue["nom_commune"] == commune], "section", n_min)


def evolution(vue: pd.DataFrame, n_min: int = 10) -> pd.DataFrame:
    """Prix médian au m² par année (annee, n, prix_m2_med), années de moins de n_min ventes masquées."""
    resultat = (
        vue.groupby("annee")
        .agg(n=("prix_m2", "size"), prix_m2_med=("prix_m2", "median"))
        .reset_index()
    )
    return resultat[resultat["n"] >= n_min].reset_index(drop=True)


def tendance(evo: pd.DataFrame, annee_ref: int = 2022) -> dict | None:
    """Variation du prix médian au m² entre annee_ref (ou la 1re année dispo) et la dernière année.

    Renvoie None s'il y a moins de deux années à comparer.
    """
    if len(evo) < 2:
        return None
    debut = annee_ref if annee_ref in set(evo["annee"].iloc[:-1]) else evo["annee"].iloc[0]
    ligne_debut = evo[evo["annee"] == debut].iloc[0]
    ligne_fin = evo.iloc[-1]
    return {
        "debut": int(debut),
        "fin": int(ligne_fin["annee"]),
        "prix_debut": ligne_debut["prix_m2_med"],
        "prix_fin": ligne_fin["prix_m2_med"],
        "variation_pct": 100 * (ligne_fin["prix_m2_med"] / ligne_debut["prix_m2_med"] - 1),
    }


def ventes_section(vue: pd.DataFrame, commune: str, section: str) -> pd.DataFrame:
    """Ventes individuelles d'une section, les plus récentes d'abord, colonnes en français."""
    ventes = vue[(vue["nom_commune"] == commune) & (vue["section"] == section)]
    colonnes = {
        "date_mutation": "Date",
        "type": "Type",
        "surface_reelle_bati": "Surface (m²)",
        "nombre_pieces_principales": "Pièces",
        "valeur_fonciere": "Prix (€)",
        "prix_m2": "Prix (€/m²)",
    }
    return (
        ventes.sort_values("date_mutation", ascending=False)[list(colonnes)]
        .rename(columns=colonnes)
        .reset_index(drop=True)
    )


def comparables(
    df: pd.DataFrame, commune: str, type_bien: str, surface: float, n: int = 10
) -> pd.DataFrame:
    """Les n ventes les plus proches : même commune, même type, surface à ±20 %.

    Triées par écart de surface (la plus proche d'abord), puis de la plus récente à la plus ancienne.
    """
    proches = df[
        (df["nom_commune"] == commune)
        & (df["type"] == type_bien)
        & (df["surface_reelle_bati"].between(0.8 * surface, 1.2 * surface))
    ]
    proches = proches.assign(ecart_surface=(proches["surface_reelle_bati"] - surface).abs())
    proches = proches.sort_values(["ecart_surface", "date_mutation"], ascending=[True, False])
    colonnes = {
        "date_mutation": "Date",
        "section": "Section",
        "surface_reelle_bati": "Surface (m²)",
        "nombre_pieces_principales": "Pièces",
        "surface_terrain": "Terrain (m²)",
        "valeur_fonciere": "Prix (€)",
        "prix_m2": "Prix (€/m²)",
    }
    return proches.head(n)[list(colonnes)].rename(columns=colonnes).reset_index(drop=True)
