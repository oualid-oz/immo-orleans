"""Chargement du modèle de prix (entraîné par scripts/train.py) et prédiction."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

RACINE = Path(__file__).parent
FICHIER_MODELE = RACINE / "modele.joblib"
FICHIER_METRIQUES = RACINE / "metriques.json"


@st.cache_resource
def charger_modele():
    """Le modèle est chargé une seule fois et partagé entre les visiteurs."""
    return joblib.load(FICHIER_MODELE)


@st.cache_data
def charger_metriques() -> dict:
    """Erreurs mesurées en validation croisée pour le modèle et la référence."""
    return json.loads(FICHIER_METRIQUES.read_text())


def predire(
    modele,
    type_bien: str,
    code_commune: str,
    surface: float,
    pieces: int,
    terrain: float,
    annee: int = 2025,
) -> float:
    """Prix estimé en € (le modèle prédit le log du prix, on repasse à l'échelle réelle)."""
    ligne = pd.DataFrame(
        [
            {
                "type": type_bien,
                "code_commune": code_commune,
                "surface_reelle_bati": surface,
                "nombre_pieces_principales": pieces,
                "surface_terrain": terrain,
                "annee": annee,
            }
        ]
    )
    return float(np.exp(modele.predict(ligne)[0]))
