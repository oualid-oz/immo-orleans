"""Tests du serveur MCP (serveur_mcp.py) : ses outils donnent les mêmes chiffres que l'application,
refusent les paramètres faux, et le serveur marche vraiment par stdio, comme dans assistant.py."""

import asyncio
import json

import pytest
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver.exceptions import ToolError

from assistant import SERVEUR_MCP
from calculs import comparables, filtrer, par_commune
from modele import predire
from serveur_mcp import CODES_COMMUNES, MODELE, VENTES, serveur_mcp


def outil(nom: str, **arguments) -> dict:
    """Appelle un outil du serveur (dans ce processus) et lit son résultat JSON."""
    resultat = asyncio.run(serveur_mcp.call_tool(nom, arguments))
    return json.loads(resultat.content[0].text)


def test_six_outils_en_lecture_seule():
    outils = asyncio.run(serveur_mcp.list_tools())
    assert {o.name for o in outils} == {
        "chercher_commune",
        "chiffres_cles",
        "communes_les_moins_cheres",
        "detail_commune",
        "estimer_prix",
        "erreur_du_modele",
    }
    assert all(o.annotations.read_only_hint for o in outils)


def test_memes_communes_que_l_application():
    resultat = outil("communes_les_moins_cheres", type="Maison", budget_max=300_000)
    attendu = par_commune(filtrer(VENTES, "Maison", 300_000, 0, (2021, 2025)), 10).head(10)
    assert [c["nom_commune"] for c in resultat["communes"]] == list(attendu["nom_commune"])
    assert [c["n"] for c in resultat["communes"]] == list(attendu["n"])
    assert all(c["n"] >= 10 for c in resultat["communes"])  # jamais de groupe sous n_min


def test_budget_respecte_dans_les_chiffres_cles():
    petit = outil("chiffres_cles", type="Maison", budget_max=100_000)
    tout = outil("chiffres_cles", type="Maison")
    assert petit["nb_ventes"] < tout["nb_ventes"]
    assert petit["prix_median"] <= 100_000


def test_chercher_commune_sans_accent_ni_tiret():
    assert outil("chercher_commune", texte="st jean de la ruelle")["communes"] == [
        "Saint-Jean-de-la-Ruelle"
    ]


def test_estimation_comme_l_onglet_prix():
    resultat = outil(
        "estimer_prix",
        type="Appartement",
        commune="Orléans",
        surface=60,
        pieces=3,
        prix_demande=180_000,
    )
    attendu = predire(MODELE, "Appartement", CODES_COMMUNES["Orléans"], 60, 3, 0)
    assert resultat["estimation"] == round(attendu)
    assert len(resultat["comparables"]) == len(comparables(VENTES, "Orléans", "Appartement", 60))
    assert resultat["verdict"] == "au-dessus du marché"  # +34 %, au-delà de la marge


def test_commune_inconnue_refusee_avec_suggestion():
    with pytest.raises(ToolError, match="Orléans"):
        outil("detail_commune", commune="Orleans", type="Maison")


def test_type_de_bien_invalide_refuse():
    with pytest.raises(ToolError):
        outil("chiffres_cles", type="Château")


def test_le_serveur_marche_par_stdio_comme_dans_l_assistant():
    """Lance vraiment serveur_mcp.py (environ 4 s), comme assistant.py à chaque question."""

    async def scenario():
        async with (
            stdio_client(SERVEUR_MCP) as (lire, ecrire),
            ClientSession(lire, ecrire) as serveur,
        ):
            await serveur.initialize()
            outils = (await serveur.list_tools()).tools
            ok = await serveur.call_tool("chercher_commune", {"texte": "olivet"})
            erreur = await serveur.call_tool("detail_commune", {"commune": "X", "type": "Maison"})
            return outils, ok, erreur

    outils, ok, erreur = asyncio.run(scenario())
    assert len(outils) == 6
    assert json.loads(ok.content[0].text) == {"communes": ["Olivet"]}
    assert erreur.is_error  # côté client, une erreur d'outil arrive comme un résultat, pas un crash
