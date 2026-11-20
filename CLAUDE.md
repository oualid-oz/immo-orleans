# Immo Orléans : contexte du projet

Course project, CODA Orléans M2-D, "Applications web de données avec Python" (case 5, Immobilier).
Graded by a grid: online URL, interactivity (2 filters + drill-down), business relevance,
accessibility, ML layer with its error metric, code quality, oral defence (every member must be
able to explain any file). Keep code simple and explainable.

## User and decision
- User: a couple looking to buy a home around Orléans.
- Decision: "Choisir dans quelle commune (et quel quartier) chercher, pour notre budget, et savoir
  si un prix demandé est raisonnable."

## Data
`data/immobilier.parquet`: 46,022 single-dwelling sales, Loiret, 2021-2025. Source "DGFiP, DVF"
(Licence Ouverte 2.0, cite it in the app).
Columns: id_mutation, date_mutation, annee, valeur_fonciere, type (Maison/Appartement),
surface_reelle_bati, nombre_pieces_principales, prix_m2, surface_terrain, code_commune,
nom_commune, code_postal, section, longitude, latitude.
Already filtered at source: one dwelling per sale, price 10k-2M €, 9-400 m², 300-8000 €/m².

Data rules:
- medians, never means
- always show the number of sales next to a price, hide groups under `n_min` sales
- section (cadastral) is the finest level, no addresses
- DVF says nothing about condition, floor or DPE: say so in the app

## Stack and rules
- Streamlit + Plotly Express + pandas + scikit-learn. Python 3.12. Use `uv add`, never pip.
- All UI text in French. Code identifiers in French, like the course.
- `calculs.py` = pure pandas functions (no streamlit import). `app.py` = display only.
- Every widget has a `key=`. `@st.cache_data` on loading and aggregates.
- Paths built from `Path(__file__)`, never relative to the working directory.
- Accessibility: Okabe-Ito colours, never colour alone, text >= 12 px, `alt=` on every
  `st.plotly_chart`, chart titles state the finding and its number of sales.
- Secrets only in `.streamlit/secrets.toml` (git-ignored).
- Before finishing a task: `uv run ruff check . && uv run ruff format . && uv run pytest -q`.

## Run
`uv run streamlit run app.py --server.address 127.0.0.1`
