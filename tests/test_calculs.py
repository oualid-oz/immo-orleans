import pandas as pd

from calculs import (
    evolution,
    filtrer,
    indicateurs,
    par_commune,
    par_section,
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
