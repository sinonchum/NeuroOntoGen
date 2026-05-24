"""RDFLib-backed graph repository adapters.

The default repository is deliberately local and in-memory. It provides a safe
smoke-testable connector boundary before wiring production graph databases such
as GraphDB, Fuseki, Neptune, or SPARQL endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rdflib import Graph, URIRef


@dataclass(frozen=True)
class GraphLoadSummary:
    """Summary for a graph load operation."""

    graph_name: str
    triple_count: int
    backend: str


@dataclass(frozen=True)
class RepositoryQueryResult:
    """Normalized graph repository query result."""

    result_type: str
    variables: tuple[str, ...] = ()
    rows: tuple[dict[str, str], ...] = ()
    turtle: str = ""


class GraphRepositoryProtocol(Protocol):
    """Protocol for graph repositories used by NeuroOntoGen."""

    backend_name: str
    connection_label: str
    is_networked: bool

    def load_turtle(self, turtle: str, *, graph_name: str = "default") -> "InMemoryGraphRepository":
        """Load Turtle into the repository and return a fluent repository handle."""
        ...

    def query(self, sparql: str) -> RepositoryQueryResult:
        """Run a SPARQL query and return normalized results."""
        ...

    def to_turtle(self) -> str:
        """Export the repository graph as Turtle."""
        ...


class InMemoryGraphRepository:
    """Local RDFLib graph repository for deterministic smoke tests.

    This class intentionally does not open network connections. It is a connector
    seam and local validation backend, not a production remote graph database
    client.
    """

    backend_name = "rdflib-in-memory"
    connection_label = "local-in-memory"
    is_networked = False

    def __init__(self, graph: Graph | None = None) -> None:
        self._graph = graph or Graph()
        self._graph_name = "default"

    @property
    def graph_name(self) -> str:
        """Return the last graph name used for loading."""
        return self._graph_name

    @property
    def triple_count(self) -> int:
        """Return the current number of triples in the repository."""
        return len(self._graph)

    def load_turtle(self, turtle: str, *, graph_name: str = "default") -> "InMemoryGraphRepository":
        """Load Turtle into the local repository and return this repository.

        Returning ``self`` keeps CLI/examples concise while the ``graph_name`` and
        ``triple_count`` properties expose the load summary.
        """
        self._graph.parse(data=turtle, format="turtle")
        self._graph_name = graph_name
        return self

    def query(self, sparql: str) -> RepositoryQueryResult:
        """Run a SPARQL query against the local graph."""
        result = self._graph.query(sparql)
        result_type = getattr(result, "type", None)
        if result_type == "SELECT":
            variables = tuple(str(variable) for variable in result.vars)
            rows = tuple(
                {
                    variable: _stringify_binding(row[index])
                    for index, variable in enumerate(variables)
                    if row[index] is not None
                }
                for row in result
            )
            return RepositoryQueryResult(result_type="select", variables=variables, rows=rows)
        if result_type == "CONSTRUCT":
            graph = Graph()
            for triple in result:
                graph.add(triple)
            return RepositoryQueryResult(result_type="graph", turtle=graph.serialize(format="turtle"))
        if result_type == "ASK":
            return RepositoryQueryResult(
                result_type="ask",
                variables=("result",),
                rows=({"result": str(bool(result))},),
            )
        raise ValueError(f"Unsupported SPARQL query result type: {result_type}")

    def to_turtle(self) -> str:
        """Export the local graph as Turtle."""
        return self._graph.serialize(format="turtle")


def _stringify_binding(value: object) -> str:
    if isinstance(value, URIRef):
        return str(value)
    return str(value)
