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


def _nombre(x: float) -> str:
    """1234.5 -> '1 235' (séparateur de milliers à la française)."""
    return f"{x:,.0f}".replace(",", " ")


def carte_communes(vue: pd.DataFrame, n_min: int = 10) -> pd.DataFrame:
    """Une ligne par commune pour la carte : médianes, position et tranche de prix.

    Position = médiane des coordonnées des ventes (pas d'adresse, seulement la commune).
    Tranche = quart de la distribution des prix médians au m² (4 classes, avec leurs bornes),
    pour que la légende se lise en texte et pas seulement en couleur.
    """
    communes = par_commune(vue, n_min)
    positions = vue.groupby("nom_commune")[["latitude", "longitude"]].median().reset_index()
    return _avec_tranches(communes.merge(positions, on="nom_commune"), "toutes les communes")


def _avec_tranches(groupes: pd.DataFrame, libelle_unique: str) -> pd.DataFrame:
    """Ajoute la colonne tranche : quart des prix médians au m², avec ses bornes en texte
    (« 787 à 1 393 €/m² »). Moins de 4 prix différents : une seule tranche."""
    groupes = groupes.copy()
    if groupes["prix_m2_med"].nunique() < 4:
        groupes["tranche"] = libelle_unique
        return groupes
    classes, bornes = pd.qcut(groupes["prix_m2_med"], 4, retbins=True, duplicates="drop")
    noms = [f"{_nombre(bornes[i])} à {_nombre(bornes[i + 1])} €/m²" for i in range(len(bornes) - 1)]
    groupes["tranche"] = [noms[code] for code in classes.cat.codes]
    return groupes


def carte_sections(vue: pd.DataFrame, commune: str, n_min: int = 10) -> pd.DataFrame:
    """Une ligne par section cadastrale de la commune, pour la carte : médianes, position, tranche.

    Mêmes sections que par_section (au moins n_min ventes), de la moins chère à la plus chère.
    Position = médiane des coordonnées des ventes de la section (jamais une vente seule).
    """
    sections = par_section(vue, commune, n_min)
    dans_commune = vue[vue["nom_commune"] == commune]
    positions = dans_commune.groupby("section")[["latitude", "longitude"]].median().reset_index()
    resultat = sections.merge(positions, on="section").dropna(subset=["latitude", "longitude"])
    return _avec_tranches(resultat.reset_index(drop=True), "toutes les sections")


VENTES_MIN_POSITION = 5  # une section de moins de 5 ventes n'est pas placée sur la carte


def carte_comparables(
    df: pd.DataFrame, commune: str, proches: pd.DataFrame, prix_demande: float
) -> pd.DataFrame:
    """Les ventes comparables (résultat de comparables()) regroupées par section, pour la carte.

    On ne place jamais une vente seule (ce serait presque une adresse) : chaque cercle est une
    section, à la position médiane de TOUTES ses ventes, et seulement si elle en compte au moins
    VENTES_MIN_POSITION. Colonnes : section, n (comparables), prix_med (leur prix médian),
    latitude, longitude, position_prix (moins cher que le prix demandé ou non).
    """
    dans_commune = df[df["nom_commune"] == commune]
    nb_ventes = dans_commune.groupby("section").size()
    positions = dans_commune.groupby("section")[["latitude", "longitude"]].median()
    positions = positions[nb_ventes >= VENTES_MIN_POSITION].reset_index()
    groupes = (
        proches.groupby("Section")
        .agg(n=("Prix (€)", "size"), prix_med=("Prix (€)", "median"))
        .reset_index()
        .rename(columns={"Section": "section"})
    )
    resultat = groupes.merge(positions, on="section").dropna(subset=["latitude", "longitude"])
    resultat["position_prix"] = [
        "moins cher que le prix demandé" if p < prix_demande else "au prix demandé ou plus cher"
        for p in resultat["prix_med"]
    ]
    return resultat.sort_values("prix_med").reset_index(drop=True)


def surface_pour_budget(communes: pd.DataFrame, budget: float) -> pd.DataFrame:
    """Ajoute surface_budget : les m² que le budget achète au prix médian au m² de chaque commune."""
    return communes.assign(surface_budget=budget / communes["prix_m2_med"])
