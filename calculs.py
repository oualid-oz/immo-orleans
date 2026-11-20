"""Calculs purs (pandas uniquement, pas de streamlit) pour l'application Immo Orléans."""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data" / "immobilier.parquet"


def charger() -> pd.DataFrame:
    """Charge les ventes DVF du Loiret (2021-2025)."""
    return pd.read_parquet(DATA)


def par_commune(df: pd.DataFrame, n_min: int = 10) -> pd.DataFrame:
    """Médianes par commune, en gardant les communes avec au moins n_min ventes.

    Colonnes : nom_commune, n, prix_m2_med, prix_med. Triées de la moins chère à la plus chère.
    """
    resultat = (
        df.groupby("nom_commune")
        .agg(
            n=("prix_m2", "size"),
            prix_m2_med=("prix_m2", "median"),
            prix_med=("valeur_fonciere", "median"),
        )
        .reset_index()
    )
    resultat = resultat[resultat["n"] >= n_min]
    return resultat.sort_values("prix_m2_med").reset_index(drop=True)
