"""RDFLib-backed graph repository adapters.

The default repository is deliberately local and in-memory. It provides a safe
smoke-testable connector boundary before wiring production graph databases such
as GraphDB, Fuseki, Neptune, or SPARQL endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Protocol
from urllib import request

from rdflib import Graph, URIRef


@dataclass(frozen=True)
class HttpResponse:
    """Minimal HTTP response used by SPARQL endpoint adapters."""

    status_code: int
    text: str
    headers: dict[str, str] = field(default_factory=dict)


class SparqlHttpClientProtocol(Protocol):
    """Protocol for injectable SPARQL HTTP clients."""

    def post(
        self,
        url: str,
        *,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        """POST a SPARQL query to an endpoint."""
        ...


class UrllibSparqlHttpClient:
    """Standard-library HTTP client for SPARQL endpoints."""

    def post(
        self,
        url: str,
        *,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
            return HttpResponse(
                status_code=response.status,
                text=raw,
                headers=dict(response.headers.items()),
            )


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


class SPARQLEndpointRepository:
    """Remote SPARQL endpoint query adapter.

    Construction is side-effect free; network I/O occurs only when ``query`` is
    called. Turtle loading is intentionally not implemented until an explicit
    update endpoint contract is added.
    """

    backend_name = "sparql-endpoint"
    is_networked = True

    def __init__(
        self,
        *,
        endpoint_url: str,
        http_client: SparqlHttpClientProtocol | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.connection_label = endpoint_url
        self._http_client = http_client or UrllibSparqlHttpClient()
        self._timeout_seconds = timeout_seconds

    @property
    def triple_count(self) -> None:
        """Remote endpoints do not expose a local triple count."""
        return None

    def load_turtle(self, turtle: str, *, graph_name: str = "default") -> "SPARQLEndpointRepository":
        """Reject local Turtle loading for the read/query-only endpoint adapter."""
        raise NotImplementedError(
            "SPARQLEndpointRepository is read/query-only; add an explicit update endpoint "
            "before loading Turtle into a remote graph."
        )

    def query(self, sparql: str) -> RepositoryQueryResult:
        """Run a SPARQL query through the remote endpoint."""
        query_type = _query_type(sparql)
        response = self._http_client.post(
            self.endpoint_url,
            body=sparql.encode("utf-8"),
            headers={
                "accept": _accept_header(query_type),
                "content-type": "application/sparql-query; charset=utf-8",
            },
            timeout_seconds=self._timeout_seconds,
        )
        if response.status_code >= 400:
            raise ValueError(f"SPARQL endpoint returned HTTP {response.status_code}: {response.text}")
        if query_type == "select":
            return _parse_sparql_json_select(response.text)
        if query_type == "ask":
            return _parse_sparql_json_ask(response.text)
        if query_type in {"construct", "describe"}:
            return RepositoryQueryResult(result_type="graph", turtle=response.text)
        raise ValueError(f"Unsupported SPARQL query type: {query_type}")

    def to_turtle(self) -> str:
        """Remote endpoints cannot be exported without an explicit CONSTRUCT query."""
        raise NotImplementedError("Use a CONSTRUCT query to export remote graph data.")


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
                rows=({"result": str(bool(result.askAnswer))},),
            )
        raise ValueError(f"Unsupported SPARQL query result type: {result_type}")

    def to_turtle(self) -> str:
        """Export the local graph as Turtle."""
        return self._graph.serialize(format="turtle")


def _query_type(sparql: str) -> str:
    stripped_lines = [line.strip() for line in sparql.strip().splitlines() if line.strip()]
    non_prefix_lines = [
        line
        for line in stripped_lines
        if not line.upper().startswith(("PREFIX ", "BASE "))
    ]
    if not non_prefix_lines:
        raise ValueError("SPARQL query is empty or contains only prefixes.")
    first_token = non_prefix_lines[0].split(maxsplit=1)[0].lower()
    return first_token


def _accept_header(query_type: str) -> str:
    if query_type in {"select", "ask"}:
        return "application/sparql-results+json"
    if query_type in {"construct", "describe"}:
        return "text/turtle, application/n-triples;q=0.9"
    return "application/sparql-results+json, text/turtle;q=0.9"


def _parse_sparql_json_select(text: str) -> RepositoryQueryResult:
    payload = json.loads(text)
    variables = tuple(payload.get("head", {}).get("vars", ()))
    rows = tuple(
        {
            variable: binding[variable]["value"]
            for variable in variables
            if variable in binding
        }
        for binding in payload.get("results", {}).get("bindings", [])
    )
    return RepositoryQueryResult(result_type="select", variables=variables, rows=rows)


def _parse_sparql_json_ask(text: str) -> RepositoryQueryResult:
    payload = json.loads(text)
    return RepositoryQueryResult(
        result_type="ask",
        variables=("result",),
        rows=({"result": str(bool(payload.get("boolean")))},),
    )


def _stringify_binding(value: object) -> str:
    if isinstance(value, URIRef):
        return str(value)
    return str(value)
