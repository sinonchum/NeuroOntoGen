from neuro_onto_gen.graph import InMemoryGraphRepository, RepositoryQueryResult


TURTLE = """
@prefix ex: <http://example.org/company/> .

<http://example.org/company/employee/E-001> a ex:Employee ;
    ex:empId "E-001" ;
    ex:hasAccessLevel 3 ;
    ex:operates <http://example.org/company/asset/VPN> .

<http://example.org/company/asset/VPN> a ex:SecureAsset ;
    ex:assetId "VPN" ;
    ex:requiredClearance 2 .
"""


def test_in_memory_graph_repository_loads_turtle_and_runs_select_queries() -> None:
    repository = InMemoryGraphRepository()

    summary = repository.load_turtle(TURTLE, graph_name="company-example")
    result = repository.query(
        """
        PREFIX ex: <http://example.org/company/>
        SELECT ?employee ?asset WHERE {
            ?employee a ex:Employee ;
                      ex:operates ?asset .
        }
        ORDER BY ?employee
        """
    )

    assert summary.graph_name == "company-example"
    assert summary.triple_count == 7
    assert isinstance(result, RepositoryQueryResult)
    assert result.result_type == "select"
    assert result.variables == ("employee", "asset")
    assert result.rows == (
        {
            "employee": "http://example.org/company/employee/E-001",
            "asset": "http://example.org/company/asset/VPN",
        },
    )
    assert repository.triple_count == 7


def test_in_memory_graph_repository_runs_construct_queries_as_turtle() -> None:
    repository = InMemoryGraphRepository().load_turtle(TURTLE)

    result = repository.query(
        """
        PREFIX ex: <http://example.org/company/>
        CONSTRUCT { ?employee ex:canOperate ?asset }
        WHERE { ?employee ex:operates ?asset }
        """
    )

    assert result.result_type == "graph"
    assert result.variables == ()
    assert result.rows == ()
    assert "canOperate" in result.turtle
    assert "employee/E-001" in result.turtle
    assert "asset/VPN" in result.turtle


def test_in_memory_graph_repository_is_local_only_and_exportable() -> None:
    repository = InMemoryGraphRepository().load_turtle(TURTLE)

    assert repository.backend_name == "rdflib-in-memory"
    assert repository.connection_label == "local-in-memory"
    assert repository.is_networked is False

    exported = repository.to_turtle()
    assert "Employee" in exported
    assert "SecureAsset" in exported
