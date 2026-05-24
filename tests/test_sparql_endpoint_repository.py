import pytest

from neuro_onto_gen.graph import HttpResponse, SPARQLEndpointRepository
from neuro_onto_gen.graph.repository import InMemoryGraphRepository


class RecordingHttpClient:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        *,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append(
            {
                "url": url,
                "body": body.decode("utf-8"),
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


def test_sparql_endpoint_repository_does_not_call_network_until_query() -> None:
    http_client = RecordingHttpClient(HttpResponse(status_code=200, text='{"boolean": true}'))

    repository = SPARQLEndpointRepository(
        endpoint_url="https://graph.example/sparql",
        http_client=http_client,
    )

    assert repository.backend_name == "sparql-endpoint"
    assert repository.connection_label == "https://graph.example/sparql"
    assert repository.is_networked is True
    assert http_client.calls == []


def test_sparql_endpoint_repository_normalizes_select_json_results() -> None:
    http_client = RecordingHttpClient(
        HttpResponse(
            status_code=200,
            text='''{
              "head": {"vars": ["employee", "level"]},
              "results": {
                "bindings": [
                  {
                    "employee": {"type": "uri", "value": "http://example.org/company/employee/E-001"},
                    "level": {"type": "literal", "value": "3"}
                  }
                ]
              }
            }''',
            headers={"content-type": "application/sparql-results+json"},
        )
    )
    repository = SPARQLEndpointRepository(
        endpoint_url="https://graph.example/sparql",
        http_client=http_client,
        timeout_seconds=3.5,
    )

    result = repository.query("SELECT ?employee ?level WHERE { ?employee ?p ?level }")

    assert result.result_type == "select"
    assert result.variables == ("employee", "level")
    assert result.rows == (
        {
            "employee": "http://example.org/company/employee/E-001",
            "level": "3",
        },
    )
    assert http_client.calls == [
        {
            "url": "https://graph.example/sparql",
            "body": "SELECT ?employee ?level WHERE { ?employee ?p ?level }",
            "headers": {
                "accept": "application/sparql-results+json",
                "content-type": "application/sparql-query; charset=utf-8",
            },
            "timeout_seconds": 3.5,
        }
    ]


def test_sparql_endpoint_repository_returns_construct_turtle() -> None:
    http_client = RecordingHttpClient(
        HttpResponse(
            status_code=200,
            text="@prefix ex: <http://example.org/company/> .\nex:a ex:b ex:c .\n",
            headers={"content-type": "text/turtle"},
        )
    )
    repository = SPARQLEndpointRepository(
        endpoint_url="https://graph.example/sparql",
        http_client=http_client,
    )

    result = repository.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")

    assert result.result_type == "graph"
    assert result.turtle.startswith("@prefix ex:")
    assert http_client.calls[0]["headers"]["accept"] == "text/turtle, application/n-triples;q=0.9"


def test_sparql_endpoint_repository_normalizes_ask_false_results() -> None:
    http_client = RecordingHttpClient(HttpResponse(status_code=200, text='{"boolean": false}'))
    repository = SPARQLEndpointRepository(
        endpoint_url="https://graph.example/sparql",
        http_client=http_client,
    )

    result = repository.query("ASK WHERE { <urn:missing> ?p ?o }")

    assert result.result_type == "ask"
    assert result.rows == ({"result": "False"},)


def test_sparql_endpoint_repository_rejects_load_turtle_without_update_endpoint() -> None:
    repository = SPARQLEndpointRepository(endpoint_url="https://graph.example/sparql")

    with pytest.raises(NotImplementedError, match="read/query-only"):
        repository.load_turtle("@prefix ex: <http://example.org/> .")


def test_in_memory_graph_repository_normalizes_ask_false_results() -> None:
    repository = InMemoryGraphRepository()

    result = repository.query("ASK WHERE { <urn:missing> ?p ?o }")

    assert result.result_type == "ask"
    assert result.rows == ({"result": "False"},)
