"""
Orchestration LangGraph — S3 InvoiceAgent.

Graphe :
  parse ──(échec, attempt < max)──> parse   (retry)
  parse ──(succès)──> validate ──> END
  parse ──(échec, attempt >= max)──> END   (fail)

Réconciliation volontairement absente à ce stade (cf. décision S3 : pas de
source de référence — bons de commande / paiements — disponible pour l'instant).
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.parse_agent import parse_node, route_after_parse
from app.agents.state import InvoiceGraphState
from app.agents.validation_agent import validation_node


def build_invoice_graph():
    graph = StateGraph(InvoiceGraphState)
    graph.add_node("parse", parse_node)
    graph.add_node("validate", validation_node)

    graph.set_entry_point("parse")
    graph.add_conditional_edges(
        "parse",
        route_after_parse,
        {"retry": "parse", "validate": "validate", "fail": END},
    )
    graph.add_edge("validate", END)

    return graph.compile()


_compiled_graph = None


def get_invoice_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_invoice_graph()
    return _compiled_graph


def run_invoice_pipeline(file_bytes: bytes, mime_type: str, max_attempts: int = 2) -> InvoiceGraphState:
    """Exécute le pipeline complet (Agent Parse + Agent Validation) sur une facture."""
    graph = get_invoice_graph()
    initial_state: InvoiceGraphState = {
        "file_bytes": file_bytes,
        "mime_type": mime_type,
        "attempt": 0,
        "max_attempts": max_attempts,
    }
    return graph.invoke(initial_state)
