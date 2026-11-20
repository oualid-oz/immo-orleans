# Immo Orléans : où acheter autour d'Orléans avec notre budget ?

**URL** : https://immo-orleans.streamlit.app/

**Pour** : un couple qui cherche à acheter un logement autour d'Orléans. Décision : choisir dans
quelle commune (et quel quartier) chercher pour son budget, et savoir si un prix demandé est
raisonnable.

**Données** : DGFiP, DVF (Demandes de valeurs foncières), Licence Ouverte 2.0. 46 022 ventes
d'un seul logement dans le Loiret, 2021-2025 (`data/immobilier.parquet`). Médianes uniquement,
groupes de moins de 10 ventes masqués. DVF ne renseigne ni l'état, ni l'étage, ni le DPE.

**Framework** : Streamlit + Plotly Express + pandas.

**Couche ML** : TODO (scikit-learn, estimation du prix avec sa métrique d'erreur).

**Assistant de code** : Claude Code (Anthropic), guidé par `CLAUDE.md` et `SPRINTS.md`.

**Depuis la version intermédiaire** : TODO

**Lancer** :

```bash
uv sync
uv run streamlit run app.py --server.address 127.0.0.1
```

Tests et qualité : `uv run ruff check . && uv run ruff format . && uv run pytest -q`
