"""Tests de la boucle de l'assistant (assistant.py) sans appeler Groq : un faux serveur local
répond comme l'API de Groq (format OpenAI, en streaming). On vérifie que l'assistant recolle un
appel d'outil arrivé en morceaux, l'exécute sur le vrai serveur MCP, renvoie le résultat au
modèle, puis affiche sa réponse finale ; et qu'une clé refusée donne un message clair."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

import assistant

QUESTION = [{"role": "user", "content": "Comment s'écrit olivet ?"}]


def morceau(delta: dict, fin: str | None = None) -> bytes:
    """Un morceau de réponse en streaming, au format OpenAI (Server-Sent Events)."""
    donnees = {
        "id": "test",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "faux-modele",
        "choices": [{"index": 0, "delta": delta, "finish_reason": fin}],
    }
    return f"data: {json.dumps(donnees)}\n\n".encode()


class FauxGroq(BaseHTTPRequestHandler):
    # Partagés entre les requêtes (un nouvel objet par requête) : variables de classe.
    requetes: ClassVar[list[dict]] = []  # ce que l'assistant a envoyé, pour les vérifications
    statut = 200

    def do_POST(self):
        corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FauxGroq.requetes.append(corps)
        if FauxGroq.statut != 200:
            self.send_response(FauxGroq.statut)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": {"message": "cle invalide"}}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        resultats = [m for m in corps["messages"] if m["role"] == "tool"]
        if not resultats:
            # 1er tour : le modèle demande l'outil chercher_commune, arguments en deux morceaux.
            appel = {"index": 0, "id": "appel1", "type": "function"}
            self.wfile.write(
                morceau(
                    {
                        "tool_calls": [
                            {**appel, "function": {"name": "chercher_commune", "arguments": ""}}
                        ]
                    }
                )
            )
            self.wfile.write(
                morceau({"tool_calls": [{"index": 0, "function": {"arguments": '{"texte": '}}]})
            )
            self.wfile.write(
                morceau({"tool_calls": [{"index": 0, "function": {"arguments": '"olivet"}'}}]})
            )
            self.wfile.write(morceau({}, "tool_calls"))
        else:
            # 2e tour : réponse finale qui reprend le résultat de l'outil.
            communes = json.loads(resultats[-1]["content"])["communes"]
            self.wfile.write(morceau({"content": "La commune s'écrit "}))
            self.wfile.write(morceau({"content": communes[0] + "."}, "stop"))
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):  # pas de journal dans la sortie des tests
        pass


@pytest.fixture
def faux_groq(monkeypatch):
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), FauxGroq)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    monkeypatch.setattr(assistant, "URL_GROQ", f"http://127.0.0.1:{serveur.server_port}")
    FauxGroq.requetes, FauxGroq.statut = [], 200
    yield FauxGroq
    serveur.shutdown()


def test_appel_d_outil_en_morceaux_execute_sur_le_serveur_mcp(faux_groq):
    reponse = "".join(assistant.reponse_en_flux(QUESTION, "cle-test", "faux-modele"))
    assert reponse == "La commune s'écrit Olivet."

    premiere, seconde = faux_groq.requetes
    assert premiere["messages"][0]["role"] == "system"
    assert len(premiere["tools"]) == 6  # les outils du serveur MCP, au format « function »
    # 2e requête : la demande d'outil recollée, puis le résultat du vrai serveur MCP.
    demande = seconde["messages"][-2]["tool_calls"][0]["function"]
    assert demande == {"name": "chercher_commune", "arguments": '{"texte": "olivet"}'}
    assert json.loads(seconde["messages"][-1]["content"]) == {"communes": ["Olivet"]}


def test_cle_refusee_message_clair(faux_groq):
    faux_groq.statut = 401
    reponse = "".join(assistant.reponse_en_flux(QUESTION, "mauvaise-cle", "faux-modele"))
    assert "GROQ_API_KEY" in reponse
