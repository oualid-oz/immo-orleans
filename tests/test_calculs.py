import json
from pathlib import Path

import pandas as pd
import pytest

from calculs import (
    VENTES_MIN_POSITION,
    carte_communes,
    carte_comparables,
    carte_sections,
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


def petit_jeu():
    """7 ventes : A (3 ventes), B (3 ventes), C (1 vente)."""
    return pd.DataFrame(
        {
            "nom_commune": ["A", "A", "A", "B", "B", "B", "C"],
            "section": ["AB", "AB", "AC", "ZA", "ZA", "ZA", "AA"],
            "type": ["Maison"] * 6 + ["Appartement"],
            "annee": [2021, 2022, 2025, 2022, 2022, 2025, 2023],
            "date_mutation": pd.to_datetime(
                [
                    "2021-03-01",
                    "2022-05-01",
                    "2025-01-01",
                    "2022-01-01",
                    "2022-06-01",
                    "2025-02-01",
                    "2023-01-01",
                ]
            ),
            "surface_reelle_bati": [100, 100, 100, 100, 100, 100, 100],
            "nombre_pieces_principales": [4, 4, 4, 3, 3, 3, 2],
            "prix_m2": [3000, 2000, 1000, 500, 600, 700, 100],
            "valeur_fonciere": [300_000, 200_000, 100_000, 50_000, 60_000, 70_000, 10_000],
        }
    )


def test_par_commune_filtre_et_trie():
    res = par_commune(petit_jeu(), n_min=3)
    assert list(res["nom_commune"]) == ["B", "A"]  # C masquée (1 vente), B moins chère
    assert list(res.columns) == ["nom_commune", "n", "prix_m2_med", "prix_med"]
    assert res.loc[1, "prix_m2_med"] == 2000  # médiane, pas moyenne
    assert res.loc[0, "n"] == 3


def test_filtrer():
    df = petit_jeu()
    assert len(filtrer(df, "Maison", 2_000_000, 0, (2021, 2025))) == 6
    assert len(filtrer(df, "Maison", 100_000, 0, (2021, 2025))) == 4  # budget
    assert len(filtrer(df, "Maison", 2_000_000, 0, (2022, 2022))) == 3  # années
    assert filtrer(df, "Maison", 2_000_000, 150, (2021, 2025)).empty  # surface


def test_indicateurs():
    ind = indicateurs(petit_jeu())
    assert ind == {"nb_ventes": 7, "prix_m2_median": 700, "prix_median": 70_000}


def test_par_section_ne_garde_que_la_commune():
    res = par_section(petit_jeu(), "A", n_min=2)
    assert list(res["section"]) == ["AB"]  # AC n'a qu'une vente
    assert res.loc[0, "n"] == 2


def test_evolution_et_tendance():
    evo = evolution(petit_jeu(), n_min=2)
    assert list(evo["annee"]) == [2022, 2025]  # 2021 et 2023 : une seule vente
    t = tendance(evo)
    assert t["debut"] == 2022 and t["fin"] == 2025
    assert round(t["variation_pct"]) == round(100 * (850 / 600 - 1))


def test_tendance_sans_assez_d_annees():
    assert tendance(evolution(petit_jeu(), n_min=10)) is None


def test_ventes_section_plus_recentes_d_abord():
    ventes = ventes_section(petit_jeu(), "A", "AB")
    assert len(ventes) == 2
    assert ventes.loc[0, "Date"] == pd.Timestamp("2022-05-01")


# ---------- Sur les vraies données : les filtres font vraiment leur travail ----------


@pytest.fixture(scope="module")
def ventes():
    return charger()


def test_maison_et_appartement_ont_des_medianes_differentes(ventes):
    tout = (2021, 2025)
    maisons = indicateurs(filtrer(ventes, "Maison", 2_000_000, 0, tout))
    apparts = indicateurs(filtrer(ventes, "Appartement", 2_000_000, 0, tout))
    assert maisons["prix_m2_median"] != apparts["prix_m2_median"]
    assert maisons["prix_median"] != apparts["prix_median"]
    # chaque vue ne contient que son type
    assert set(filtrer(ventes, "Maison", 2_000_000, 0, tout)["type"]) == {"Maison"}


@pytest.mark.parametrize("budget", [80_000, 150_000, 300_000])
def test_budget_respecte(ventes, budget):
    vue = filtrer(ventes, "Maison", budget, 0, (2021, 2025))
    assert not vue.empty
    assert (vue["valeur_fonciere"] <= budget).all()
    # et le filtre enlève bien quelque chose : des maisons au-dessus du budget existent
    assert len(vue) < (ventes["type"] == "Maison").sum()


def test_surface_et_annees_respectees(ventes):
    vue = filtrer(ventes, "Appartement", 2_000_000, 60, (2023, 2024))
    assert (vue["surface_reelle_bati"] >= 60).all()
    assert set(vue["annee"]) == {2023, 2024}


@pytest.mark.parametrize("n_min", [1, 10, 50])
def test_par_commune_jamais_sous_n_min(ventes, n_min):
    res = par_commune(ventes, n_min)
    assert (res["n"] >= n_min).all()
    assert res["prix_m2_med"].is_monotonic_increasing


def test_comparables(ventes):
    res = comparables(ventes, "Orléans", "Appartement", 60)
    assert len(res) == 10
    assert res["Surface (m²)"].between(48, 72).all()
    ecarts = (res["Surface (m²)"] - 60).abs()
    assert ecarts.is_monotonic_increasing  # les plus proches d'abord


def test_le_modele_bat_la_reference():
    metriques = json.loads((Path(__file__).parent.parent / "metriques.json").read_text())
    assert metriques["modele"]["erreur_mediane"] < metriques["reference"]["erreur_mediane"]
    assert metriques["modele"]["mape"] < metriques["reference"]["mape"]


def test_surface_pour_budget():
    communes = par_commune(petit_jeu(), n_min=3)  # B : 600 €/m², A : 2000 €/m²
    res = surface_pour_budget(communes, 300_000)
    assert list(res["surface_budget"]) == [500, 150]


def test_carte_communes(ventes):
    vue = filtrer(ventes, "Maison", 300_000, 0, (2021, 2025))
    carte = carte_communes(vue, n_min=10)
    assert (carte["n"] >= 10).all()
    assert len(carte) == len(par_commune(vue, 10))  # aucune commune perdue
    # toutes les positions sont dans le Loiret (pas de commune placée ailleurs)
    assert carte["latitude"].between(47.4, 48.4).all()
    assert carte["longitude"].between(1.4, 3.2).all()
    # 4 tranches de taille égale, la moins chère d'abord
    assert carte["tranche"].nunique() == 4
    assert carte["tranche"].iloc[0] != carte["tranche"].iloc[-1]
    assert carte["tranche"].value_counts().max() - carte["tranche"].value_counts().min() <= 1


def test_carte_sections_memes_sections_que_le_tableau(ventes):
    vue = filtrer(ventes, "Maison", 300_000, 0, (2021, 2025))
    carte = carte_sections(vue, "Orléans", n_min=10)
    tableau = par_section(vue, "Orléans", n_min=10)
    assert list(carte["section"]) == list(
        tableau["section"]
    )  # même ordre, du moins cher au plus cher
    assert (carte["n"] >= 10).all()
    # positions dans Orléans, pas ailleurs dans le Loiret
    assert carte["latitude"].between(47.8, 47.95).all()
    assert carte["longitude"].between(1.8, 2.0).all()
    assert carte["tranche"].nunique() == 4


def test_carte_comparables_jamais_une_position_de_vente_seule(ventes):
    proches = comparables(ventes, "Orléans", "Appartement", 60)
    carte = carte_comparables(ventes, "Orléans", proches, 180_000)
    nb_par_section = ventes[ventes["nom_commune"] == "Orléans"].groupby("section").size()
    # chaque cercle = une section qui a assez de ventes pour que sa position ne trahisse personne
    assert (nb_par_section[carte["section"]] >= VENTES_MIN_POSITION).all()
    assert carte["n"].sum() <= len(proches)
    # couleur cohérente avec le prix demandé
    moins_chers = carte[carte["prix_med"] < 180_000]
    assert (moins_chers["position_prix"] == "moins cher que le prix demandé").all()
