# Immo Orléans : où acheter autour d'Orléans avec notre budget ?

**URL** : https://immo-orleans.streamlit.app/

**Pour** : un couple qui cherche à acheter un logement autour d'Orléans. Décision : choisir dans
quelle commune (et quel quartier) chercher pour son budget, et savoir si un prix demandé est
raisonnable.

**Données** : DGFiP, DVF (Demandes de valeurs foncières), Licence Ouverte 2.0. 46 022 ventes
d'un seul logement dans le Loiret, 2021-2025 (`data/immobilier.parquet`). Filtré à la source :
une habitation par vente, prix 10 k€ - 2 M€, 9-400 m², 300-8 000 €/m². Médianes uniquement,
nombre de ventes affiché à côté de chaque prix, groupes sous le seuil `n_min` (10 par défaut)
masqués. La section cadastrale est le niveau le plus fin (pas d'adresse). DVF ne renseigne ni
l'état, ni l'étage, ni le DPE.

**Framework** : Streamlit + Plotly Express + pandas + scikit-learn, Python 3.12, géré avec `uv`.
Deux onglets :

- *Où chercher ?* : filtres (type, budget, surface, années, ventes minimum), 3 indicateurs,
  puis exploration en 3 niveaux : communes (clic sur une barre ou liste) → évolution par année
  et sections de la commune → ventes individuelles d'une section.
- *Ce prix est-il raisonnable ?* : on décrit un bien et son prix demandé ; l'application donne
  l'estimation du modèle, l'écart en %, et les 10 ventes comparables les plus proches.

**Couche ML** : `scripts/train.py` (lancé une fois, pas par l'application) entraîne un
`HistGradientBoostingRegressor` (one-hot sur le type et la commune) qui prédit le log du prix
à partir du type, de la commune, de la surface, des pièces, du terrain et de l'année. Il
produit `modele.joblib` et `metriques.json`. Erreurs mesurées en validation croisée 5 plis, sur
l'échelle réelle des prix, comparées à une référence simple (médiane €/m² de la commune et du
type sur les plis d'entraînement × surface) :

| | Erreur médiane | MAE | MAPE |
|---|---|---|---|
| Modèle | 27 233 € | 40 690 € | 27,7 % |
| Référence | 29 197 € | 43 560 € | 30,6 % |

Le modèle fait un peu mieux que la référence, mais l'erreur reste importante : DVF ne connaît
ni l'état, ni l'étage, ni le DPE. L'application le dit et affiche les ventes comparables pour
que l'utilisateur juge lui-même.

**Assistant de code** : Claude Code (Anthropic), guidé par `CLAUDE.md` et `SPRINTS.md`. Chaque
fichier a été relu et peut être expliqué par chaque membre du groupe.

**Depuis la version intermédiaire** :

- couche ML : modèle de prix, métriques en validation croisée contre une référence
  (`scripts/train.py`, `modele.py`, `metriques.json`) ;
- nouvel onglet « Ce prix est-il raisonnable ? » (formulaire, estimation, écart, comparables) ;
- `calculs.comparables()` : même commune, même type, surface à ± 20 % ;
- tests sur les vraies données qui prouvent que les filtres fonctionnent (budget respecté,
  Maison ≠ Appartement, jamais de groupe sous `n_min`) et que le modèle bat la référence ;
- « Méthode et limites » et la source restent visibles même quand les filtres ne donnent
  aucune vente ;
- retours de la revue de 11 h 55 : TODO ;
- accessibilité : la courbe d'évolution passe de l'orange Okabe-Ito (#E69F00, contraste 2,2:1
  sur blanc, sous le minimum de 3:1) au vermillon #D55E00 (3,9:1 sur fond clair, 4,9:1 sur
  fond sombre) ; tailles de texte des graphiques fixées explicitement à 12 px minimum (axes,
  étiquettes, survol) ; titres sur deux lignes pour ne pas être coupés sur téléphone ; texte
  `alt=` sur les 3 tableaux en plus des 2 graphiques ; « Prix stables » au lieu de « en baisse
  de 0 % » quand la variation est inférieure à 1 % ;
- téléphone : indication que les filtres sont dans le panneau latéral (replié sur mobile) ;
  formulaire réordonné pour décrire le bien avant de saisir le prix demandé ;
- audit d'accessibilité de l'autre groupe : TODO ;
- vérifié depuis un clone propre (`uv sync` puis `streamlit run` lancé depuis un autre
  dossier) : aucun chemin ne dépend du dossier courant.

**Lancer** :

```bash
uv sync
uv run streamlit run app.py --server.address 127.0.0.1
```

Réentraîner le modèle (environ 1 minute) : `uv run python scripts/train.py`

Tests et qualité : `uv run ruff check . && uv run ruff format . && uv run pytest -q`
