"""Build compiled LangGraph from registry + constants (thin wiring layer)."""

from __future__ import annotations

import warnings

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

# LangGraph serde pulls `Reviver()` without `allowed_objects`; LangChain warns until upstream passes it explicitly.
warnings.filterwarnings(
    "ignore",
    category=LangChainPendingDeprecationWarning,
    message="The default value of `allowed_objects` will change",
)

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from black_company.constants import SPECIALIST_NODES, NodeId
from black_company.nodes import SPECIALIST_FUNCS, pm_orchestrate
from black_company.routing import route_from_pm
from black_company.state import TeamState

if set(SPECIALIST_FUNCS) != set(SPECIALIST_NODES):
    missing = set(SPECIALIST_NODES) - set(SPECIALIST_FUNCS)
    extra = set(SPECIALIST_FUNCS) - set(SPECIALIST_NODES)
    raise RuntimeError(f"SPECIALIST_FUNCS out of sync with SPECIALIST_NODES: missing={missing!r} extra={extra!r}")


def build_graph(*, with_checkpointer: bool = True):
    """Compiled graph: specialists always return to `pm`. Checkpointer for interrupt/resume."""
    g = StateGraph(TeamState)

    g.add_node(NodeId.PM, pm_orchestrate)
    for node_id in SPECIALIST_NODES:
        g.add_node(node_id, SPECIALIST_FUNCS[node_id])

    g.add_edge(START, NodeId.PM)
    path_map = {name: name for name in SPECIALIST_NODES}
    path_map[END] = END
    g.add_conditional_edges(NodeId.PM, route_from_pm, path_map)

    for node_id in SPECIALIST_NODES:
        g.add_edge(node_id, NodeId.PM)

    checkpointer = MemorySaver() if with_checkpointer else None
    return g.compile(checkpointer=checkpointer)
