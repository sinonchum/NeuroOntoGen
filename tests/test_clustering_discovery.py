from neuro_onto_gen.clustering.discovery import discover_schema_from_terms, extract_terms


def test_discovers_non_empty_clusters_with_auto_count_from_injected_embeddings() -> None:
    terms = [
        "Company",
        "Organization",
        "Employer",
        "Person",
        "Researcher",
        "Employee",
    ]
    embeddings = {
        "Company": [1.0, 0.0],
        "Organization": [0.96, 0.04],
        "Employer": [0.92, 0.08],
        "Person": [0.0, 1.0],
        "Researcher": [0.03, 0.97],
        "Employee": [0.08, 0.92],
    }

    report = discover_schema_from_terms(terms, embeddings=embeddings, similarity_threshold=0.85)

    assert report.term_count == 6
    assert report.cluster_count == 2
    assert len(report.clusters) == 2
    assert all(cluster.members for cluster in report.clusters)
    assert {member.term for cluster in report.clusters for member in cluster.members} == set(terms)
    assert all(cluster.requires_human_review for cluster in report.clusters)
    assert report.backend in {"sklearn-affinity-propagation", "deterministic-similarity-fallback"}


def test_generates_human_reviewable_linkml_schema_draft_from_clusters() -> None:
    report = discover_schema_from_terms(
        ["Company", "Organization", "Person", "Researcher"],
        embeddings={
            "Company": [1.0, 0.0],
            "Organization": [0.95, 0.05],
            "Person": [0.0, 1.0],
            "Researcher": [0.02, 0.98],
        },
        similarity_threshold=0.85,
    )

    draft = report.to_linkml_draft(schema_name="company_discovery")

    assert draft["name"] == "company_discovery"
    assert draft["annotations"]["generation_status"] == "schema_discovery_draft_requires_human_review"
    assert len(draft["classes"]) == 2
    class_descriptions = "\n".join(cls["description"] for cls in draft["classes"].values())
    assert "Discovered from candidate terms" in class_descriptions
    assert "Company" in class_descriptions
    assert "Person" in class_descriptions


def test_extract_terms_normalizes_repeated_candidate_terms_without_spacy_dependency() -> None:
    terms = extract_terms(
        [
            "Acme Robotics employs a research scientist.",
            "The research scientist designs autonomous robot controllers for Acme Robotics.",
        ],
        min_frequency=2,
    )

    assert "Acme Robotics" in terms
    assert "research scientist" in terms
    assert len(terms) == len(set(terms))
