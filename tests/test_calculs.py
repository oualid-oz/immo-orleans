import pandas as pd

from calculs import par_commune


def test_par_commune_filtre_et_trie():
    df = pd.DataFrame(
        {
            "nom_commune": ["A", "A", "A", "B", "B", "B", "C"],
            "prix_m2": [3000, 2000, 1000, 500, 600, 700, 100],
            "valeur_fonciere": [300_000, 200_000, 100_000, 50_000, 60_000, 70_000, 10_000],
        }
    )
    res = par_commune(df, n_min=3)
    assert list(res["nom_commune"]) == ["B", "A"]  # C masquée (1 vente), B moins chère
    assert list(res.columns) == ["nom_commune", "n", "prix_m2_med", "prix_med"]
    assert res.loc[1, "prix_m2_med"] == 2000  # médiane, pas moyenne
    assert res.loc[0, "n"] == 3
