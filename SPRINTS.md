# Les 4 sprints : un prompt par sprint

The context (user, decision, data, rules) is in `CLAUDE.md`, which the assistant reads on its own.
Paste one sprint at a time. Don't start the next one until the "Done when" list is all ticked.

---

## Sprint 1 · 45 min · Une première page en ligne

```text
Sprint 1. Read CLAUDE.md first.
Goal: a minimal app deployed online before the break.

1. Create calculs.py with:
   - DATA = Path(__file__).parent / "data" / "immobilier.parquet"
   - charger() -> DataFrame (read_parquet)
   - par_commune(df, n_min=10) -> DataFrame: nom_commune, n (number of sales),
     prix_m2_med, prix_med; keep n >= n_min; sorted by prix_m2_med ascending
2. Create app.py:
   - @st.cache_data wrapper around charger()
   - st.title("Où acheter autour d'Orléans avec notre budget ?")
   - one filter in the sidebar: type (radio Maison / Appartement, key="type")
   - one horizontal bar chart (plotly express): 20 cheapest communes by median €/m²,
     n in the bar label, title stating the finding, e.g.
     "<commune> : <x> €/m² médian sur <n> ventes, la moins chère"
   - st.caption with the source "DGFiP, DVF, Licence Ouverte 2.0"
3. README.md with the course template (URL, Pour, Données, Framework, Couche ML,
   Assistant de code, Depuis la version intermédiaire, Lancer); URL left as TODO.
4. Run ruff, then start the app locally to check that it works.
Explain each file in 3 lines at the end.
```

Then do these yourself:
- create the GitHub repo (public, or private if your teacher allows it), `git add . && git commit -m "sprint 1" && git push`
- share.streamlit.io → Create app → your repo, branch `main`, file `app.py`, Python 3.12 → Deploy
- put the URL in the README, then commit and push

**Done when:** the URL works on a phone · the filter changes the chart · the URL is in the README.

---

## Sprint 2 · 40 min · Un parcours complet pour midi

```text
Sprint 2. Read CLAUDE.md, calculs.py and app.py first.
Goal: filters, metrics and the 3-level drill-down, ready for the 11:55 demo.

calculs.py, add pure functions:
- filtrer(df, type, budget_max, surface_min, annees) -> DataFrame
- indicateurs(vue) -> dict(nb_ventes, prix_m2_median, prix_median)
- par_section(vue, commune, n_min) -> DataFrame (section, n, prix_m2_med, prix_med)
- evolution(vue) -> DataFrame (annee, n, prix_m2_med)

app.py:
- sidebar filters, each with key=: type, budget max (€ slider), surface min (m²),
  années (range 2021-2025), n_min (min sales per group, default 10).
  ALL metrics and charts use the filtered view.
  Empty view -> st.warning("...") + st.stop().
- 3 st.metric at the top: ventes correspondantes, prix médian au m², prix médian
- main chart (communes): st.plotly_chart(fig, on_select="rerun", key="communes",
  alt="<one sentence with the finding>"). A clicked bar selects the commune.
  Also a selectbox "Commune" (key="commune") as fallback, because Plotly selection is lost
  when the figure changes.
- level 2, selected commune: evolution chart by year (title says whether prices went down
  after 2022, with n) + sections table (median €/m², n)
- level 3: selectbox for a section -> st.dataframe of its individual sales
  (date, type, surface, pièces, prix, prix_m2)
- st.expander("Méthode et limites"): filters applied at source, medians, n_min,
  DVF says nothing about condition/floor/DPE, source + licence
- cache the aggregates with @st.cache_data
Run ruff, start locally, check that every filter changes every chart.
```

Then: `git push` before the end of the sprint, because the demo uses the online version.

**Done when:** 3 metrics · ≥ 2 filters acting on everything · commune → section → sales works · titles state findings with n · pushed.

**At the 11:55 demo:** write down the feedback you get. You show what you fixed at the defence, and it counts for 4 points.

---

## Sprint 3 · 50 min · Le modèle, le test, le README

```text
Sprint 3. Read CLAUDE.md, calculs.py and app.py first.
Goal: ML layer with its error metric, one meaningful test, review feedback applied.

1. scripts/train.py (run once, not by the app):
   - features: type, surface_reelle_bati, nombre_pieces_principales, surface_terrain
     (fill NaN with 0), code_commune, annee; target log(valeur_fonciere)
   - sklearn Pipeline: OneHotEncoder(handle_unknown="ignore") on type and code_commune
     + HistGradientBoostingRegressor
   - 5-fold cross-validation; MAE (€) and MAPE (%) on the real price scale
   - baseline: median €/m² of the commune (and type) × surface, same folds
   - save modele.joblib and metriques.json at the project root
2. modele.py: charger_modele() with @st.cache_resource, predire(...) -> price in €
3. app.py: new tab "Ce prix est-il raisonnable ?":
   st.form with type, commune, surface, pièces, terrain, prix demandé ->
   estimated price, gap in % vs the asking price, the 10 closest comparable sales
   (same commune, same type, surface ±20 %) via calculs.comparables(...),
   and a caption: "Modèle : erreur médiane X € (MAPE Y %) contre Z € pour la référence".
4. tests/test_calculs.py: tests that prove the filters WORK, not just "> 0":
   Maison and Appartement give different medians; every sale left after the budget filter
   is <= budget; par_commune never returns n < n_min.
5. Apply these review feedback points: <PASTE THE 11:55 FEEDBACK HERE>
6. README: fill every section, including "Depuis la version intermédiaire".
Run ruff check, ruff format, pytest. Commit modele.joblib + metriques.json.
```

If `modele.joblib` is over ~50 MB, ask the assistant to reduce `max_iter` or the number of features.

**Done when:** the form works · MAE shown next to the baseline · `pytest` green · `ruff` clean · README complete · pushed.

---

## Sprint 4 · 35 min · Vérifier la version en ligne avant 15h50

```text
Sprint 4. Read CLAUDE.md and app.py first.
Goal: polish only, no new features.
1. Accessibility check of every chart: Okabe-Ito colours, nothing carried by colour alone,
   text >= 12 px, alt= on every st.plotly_chart, every title states the finding + n.
2. Mobile order: on a phone the columns stack in code order. Make sure the metrics and the
   main chart come before the details.
3. Apply these accessibility-audit points from the other group: <PASTE HERE>
4. Make sure no path depends on the working directory and that the app starts from a clean
   clone (uv sync, then streamlit run).
5. ruff + pytest, then update the README "Depuis la version intermédiaire".
List what you changed so I can mention it at the defence.
```

Then do these yourself:
- push, open the URL on a phone and click through the whole path
- open the URL again a few minutes before your defence so the app is awake
- **no push after 15:50**

**Defence (5 + 3 min, live app, no slides):** user + decision in one sentence → demo starting from their question → what changed since midday → the model and its limit → why Streamlit, in two sentences.
