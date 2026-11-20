"""Entraîne le modèle de prix et mesure son erreur. À lancer une fois : uv run python scripts/train.py

Écrit modele.joblib et metriques.json à la racine du projet. L'application ne fait que les lire.
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from calculs import charger  # après sys.path.insert : calculs.py est à la racine

CATEGORIES = ["type", "code_commune"]
NUMERIQUES = ["surface_reelle_bati", "nombre_pieces_principales", "surface_terrain", "annee"]
VARIABLES = CATEGORIES + NUMERIQUES


def preparer(df: pd.DataFrame) -> pd.DataFrame:
    """Les colonnes utilisées par le modèle, terrain manquant = 0."""
    x = df[VARIABLES].copy()
    x["surface_terrain"] = x["surface_terrain"].fillna(0)
    return x


def creer_modele() -> Pipeline:
    """Encodage one-hot des catégories, puis gradient boosting sur des arbres."""
    encodage = ColumnTransformer(
        [("categories", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORIES)],
        remainder="passthrough",
    )
    return Pipeline(
        [("encodage", encodage), ("regression", HistGradientBoostingRegressor(random_state=42))]
    )


def reference(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Méthode simple : médiane €/m² de la commune et du type (sur le train) × surface.

    Si la paire commune + type n'existe pas dans le train, on prend la médiane du type.
    """
    par_groupe = train.groupby(["code_commune", "type"])["prix_m2"].median()
    par_type = train.groupby("type")["prix_m2"].median()
    cles = pd.MultiIndex.from_frame(test[["code_commune", "type"]])
    prix_m2 = par_groupe.reindex(cles).to_numpy()
    secours = test["type"].map(par_type).to_numpy()
    prix_m2 = np.where(np.isnan(prix_m2), secours, prix_m2)
    return prix_m2 * test["surface_reelle_bati"].to_numpy()


def erreurs(vrai: np.ndarray, predit: np.ndarray) -> dict:
    """Erreurs sur l'échelle réelle des prix (en €), pas sur le logarithme."""
    ecart = np.abs(predit - vrai)
    return {
        "mae": float(ecart.mean()),
        "erreur_mediane": float(np.median(ecart)),
        "mape": float(100 * (ecart / vrai).mean()),
        "erreur_mediane_pct": float(100 * np.median(ecart / vrai)),
    }


def main():
    df = charger().reset_index(drop=True)
    x = preparer(df)
    y = np.log(df["valeur_fonciere"])  # cible en log : les écarts de prix sont relatifs

    pred_modele = np.zeros(len(df))
    pred_reference = np.zeros(len(df))
    plis = KFold(n_splits=5, shuffle=True, random_state=42)
    for i, (idx_train, idx_test) in enumerate(plis.split(x), start=1):
        modele = creer_modele().fit(x.iloc[idx_train], y.iloc[idx_train])
        pred_modele[idx_test] = np.exp(modele.predict(x.iloc[idx_test]))
        pred_reference[idx_test] = reference(df.iloc[idx_train], df.iloc[idx_test])
        print(f"pli {i}/5 terminé")

    vrai = df["valeur_fonciere"].to_numpy()
    metriques = {
        "nb_ventes": len(df),
        "validation": "validation croisée 5 plis (KFold, shuffle, random_state=42)",
        "modele": erreurs(vrai, pred_modele),
        "reference": erreurs(vrai, pred_reference),
    }

    # Modèle final : entraîné sur toutes les ventes.
    joblib.dump(creer_modele().fit(x, y), RACINE / "modele.joblib")
    (RACINE / "metriques.json").write_text(json.dumps(metriques, indent=2, ensure_ascii=False))
    print(json.dumps(metriques, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
