"""Serveur MCP d'Immo Orléans : les outils de l'assistant, en lecture seule.

MCP (Model Context Protocol) est un protocole standard pour donner des outils à un modèle d'IA.
Ce serveur expose 6 outils qui appellent les fonctions de calculs.py et modele.py : l'assistant
reformule nos médianes et nos nombres de ventes, il n'invente aucun chiffre.

Il communique par « stdio » (entrée / sortie standard) : un client le lance comme un programme.
- l'onglet « Assistant » de app.py le lance à chaque question (voir assistant.py) ;
- Claude Code peut aussi l'utiliser :
  claude mcp add immo-orleans -- uv run --project <chemin> python <chemin>/serveur_mcp.py

Lancé seul (python serveur_mcp.py), il attend des messages MCP sur son entrée standard.
"""

import json
import re
import unicodedata
from typing import Annotated, Literal

import joblib
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from calculs import (
    charger,
    comparables,
    evolution,
    filtrer,
    indicateurs,
    par_commune,
    par_section,
    surface_pour_budget,
    tendance,
)
from modele import FICHIER_METRIQUES, FICHIER_MODELE, predire

# Chargés une fois, au lancement du serveur.
VENTES = charger()
MODELE = joblib.load(FICHIER_MODELE)
METRIQUES = json.loads(FICHIER_METRIQUES.read_text(encoding="utf-8"))
CODES_COMMUNES = dict(zip(VENTES["nom_commune"], VENTES["code_commune"]))
N_MIN = 10  # règle du site : pas de médiane sur moins de 10 ventes

serveur_mcp = MCPServer(
    name="Immo Orléans",
    instructions=(
        "Ventes immobilières DVF du Loiret, 2021-2025 (DGFiP, Licence Ouverte 2.0) : médianes, "
        "nombre de ventes, évolution des prix, estimation d'un prix demandé. Vérifier l'orthographe "
        "d'une commune avec chercher_commune avant les autres outils."
    ),
)
LECTURE_SEULE = ToolAnnotations(read_only_hint=True, open_world_hint=False)

TypeBien = Literal["Maison", "Appartement"]
Budget = Annotated[int | None, Field(ge=10_000, le=2_000_000, description="Budget maximum (€)")]
SurfaceMin = Annotated[int | None, Field(ge=0, le=400, description="Surface habitable minimum")]
Annee = Annotated[int | None, Field(ge=2021, le=2025)]
NomCommune = Annotated[str, Field(min_length=1, max_length=80, description="Orthographe exacte")]


# ---------- Aides ----------


def en_json(objet):
    """Tableaux pandas et nombres numpy -> types Python simples (dates en texte AAAA-MM-JJ)."""
    if hasattr(objet, "to_dict"):
        nombres = objet.select_dtypes("number").columns  # on n'arrondit pas les dates
        objet = objet.round(dict.fromkeys(nombres, 1)).to_dict(orient="records")
    texte = json.dumps(objet, default=lambda x: x.item() if hasattr(x, "item") else str(x)[:10])
    return json.loads(texte)


def vue_filtree(type, budget_max, surface_min, annee_min, annee_max):
    """Paramètres d'un outil -> ventes filtrées. Sans budget précisé : pas de limite."""
    debut, fin = annee_min or 2021, annee_max or 2025
    annees = (min(debut, fin), max(debut, fin))
    return filtrer(VENTES, type, budget_max or 2_000_000, surface_min or 0, annees)


def normaliser(texte: str) -> str:
    """'Saint-Jean-de-la-Ruelle' et 'st jean de la ruelle' doivent se retrouver."""
    sans_accents = unicodedata.normalize("NFD", texte)
    t = "".join(c for c in sans_accents if not unicodedata.combining(c)).lower()
    t = re.sub(r"\bst\b", "saint", t)
    t = re.sub(r"\bste\b", "sainte", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def communes_proches(texte: str) -> list[str]:
    cherche = normaliser(texte)
    return [c for c in sorted(CODES_COMMUNES) if cherche in normaliser(c)][:10]


def commune_connue(commune: str) -> None:
    """Une commune inconnue renvoie une erreur lisible par le modèle, avec des suggestions."""
    if commune not in CODES_COMMUNES:
        raise ToolError(
            f"Commune inconnue : « {commune} ». Communes proches : {communes_proches(commune)}"
        )


# ---------- Les 6 outils ----------


@serveur_mcp.tool(annotations=LECTURE_SEULE)
def chercher_commune(
    texte: Annotated[str, Field(min_length=2, max_length=80, description="Nom ou début de nom")],
) -> dict:
    """Trouve l'orthographe exacte d'une commune du Loiret présente dans les données (accents et
    tirets compris). À appeler avant les autres outils dès qu'un nom de commune vient de
    l'utilisateur."""
    trouvees = communes_proches(texte)
    if not trouvees:
        raise ToolError(f"Aucune commune ne correspond à « {texte} » dans les ventes du Loiret.")
    return {"communes": trouvees}


@serveur_mcp.tool(annotations=LECTURE_SEULE)
def chiffres_cles(
    type: TypeBien,
    budget_max: Budget = None,
    surface_min: SurfaceMin = None,
    annee_min: Annee = None,
    annee_max: Annee = None,
) -> dict:
    """Pour un type de bien et des filtres, sur tout le Loiret : nombre de ventes, prix médian au
    m², prix médian, prix médian au m² par année, et sa variation depuis 2022."""
    vue = vue_filtree(type, budget_max, surface_min, annee_min, annee_max)
    par_annee = evolution(vue, N_MIN)
    return en_json(
        indicateurs(vue) | {"par_annee": en_json(par_annee), "tendance": tendance(par_annee)}
    )


@serveur_mcp.tool(annotations=LECTURE_SEULE)
def communes_les_moins_cheres(
    type: TypeBien,
    budget_max: Budget = None,
    surface_min: SurfaceMin = None,
    annee_min: Annee = None,
    annee_max: Annee = None,
    limite: Annotated[int, Field(ge=1, le=50, description="Nombre de communes")] = 10,
) -> dict:
    """Communes classées de la moins chère à la plus chère au m² (médianes, avec leur nombre de
    ventes, et la surface que le budget permet d'acheter). Communes de moins de 10 ventes
    exclues."""
    vue = vue_filtree(type, budget_max, surface_min, annee_min, annee_max)
    communes = surface_pour_budget(par_commune(vue, N_MIN), budget_max or 2_000_000)
    return {
        "nb_ventes": len(vue),
        "nb_communes": len(communes),
        "communes": en_json(communes.head(limite)),
    }


@serveur_mcp.tool(annotations=LECTURE_SEULE)
def detail_commune(
    commune: NomCommune,
    type: TypeBien,
    budget_max: Budget = None,
    surface_min: SurfaceMin = None,
    annee_min: Annee = None,
    annee_max: Annee = None,
) -> dict:
    """Pour une commune (orthographe exacte, voir chercher_commune) : prix médian au m² par année
    avec la variation depuis 2022, et les sections cadastrales (quartiers) de la moins chère à la
    plus chère, chacune avec son nombre de ventes."""
    commune_connue(commune)
    vue = vue_filtree(type, budget_max, surface_min, annee_min, annee_max)
    evo = evolution(vue[vue["nom_commune"] == commune], N_MIN)
    sections = par_section(vue, commune, N_MIN)
    return {
        "commune": commune,
        "nb_ventes": int((vue["nom_commune"] == commune).sum()),
        "evolution": en_json(evo),
        "tendance": en_json(tendance(evo)),
        "nb_sections": len(sections),
        "sections": en_json(sections.head(15)),
    }


@serveur_mcp.tool(annotations=LECTURE_SEULE)
def estimer_prix(
    type: TypeBien,
    commune: NomCommune,
    surface: Annotated[float, Field(ge=9, le=400, description="Surface habitable (m²)")],
    pieces: Annotated[int, Field(ge=0, le=30, description="Pièces principales")],
    prix_demande: Annotated[int, Field(ge=10_000, le=2_000_000, description="Prix demandé (€)")],
    terrain: Annotated[float, Field(ge=0, le=100_000, description="Terrain (m²), 0 si aucun")] = 0,
) -> dict:
    """Estime le prix d'un logement avec le modèle du site et le compare au prix demandé :
    estimation, écart en %, marge d'erreur habituelle du modèle, verdict, 10 ventes comparables
    (même commune, même type, surface à ± 20 %)."""
    commune_connue(commune)
    estimation = predire(MODELE, type, CODES_COMMUNES[commune], surface, pieces, terrain)
    ecart = 100 * (prix_demande / estimation - 1)
    marge = METRIQUES["modele"]["erreur_mediane_pct"]
    # Mêmes seuils que l'onglet « Ce prix est-il raisonnable ? » de app.py.
    if abs(ecart) <= marge:
        verdict = "dans l'erreur habituelle du modèle"
    elif ecart > 0:
        verdict = "au-dessus du marché"
    else:
        verdict = "en dessous du marché"
    return {
        "estimation": round(estimation),
        "prix_demande": prix_demande,
        "ecart_pct": round(ecart, 1),
        "marge_pct": round(marge, 1),
        "verdict": verdict,
        "comparables": en_json(comparables(VENTES, commune, type, surface)),
    }


@serveur_mcp.tool(annotations=LECTURE_SEULE)
def erreur_du_modele() -> dict:
    """Erreurs du modèle de prix mesurées en validation croisée 5 plis (erreur médiane en €,
    MAPE), comparées à la référence (prix médian au m² de la commune × surface)."""
    return METRIQUES


if __name__ == "__main__":
    serveur_mcp.run()  # transport stdio par défaut
