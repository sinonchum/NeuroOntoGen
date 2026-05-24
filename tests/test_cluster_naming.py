from neuro_onto_gen.clustering.discovery import LlmClusterNamer, discover_schema_from_terms


class RecordingProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_llm_cluster_namer_builds_review_safe_prompt_and_sanitizes_pascal_case_label() -> None:
    provider = RecordingProvider("```text\nResearch Actor!!!\n```")
    namer = LlmClusterNamer(provider=provider, ontology_name="NeuroOntology")

    label = namer.name_cluster(
        exemplar="Researcher",
        terms=["Researcher", "Scientist", "Principal Investigator"],
    )

    assert label == "ResearchActor"
    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert "NeuroOntology" in prompt
    assert "Researcher" in prompt
    assert "Scientist" in prompt
    assert "Principal Investigator" in prompt
    assert "Return exactly one PascalCase class label" in prompt
    assert "human ontology review" in prompt


def test_discover_schema_from_terms_uses_injected_cluster_namer_and_marks_draft_review() -> None:
    provider = RecordingProvider("Organization Actor")
    report = discover_schema_from_terms(
        ["Company", "Organization", "Employer"],
        embeddings={
            "Company": [1.0, 0.0],
            "Organization": [0.96, 0.04],
            "Employer": [0.92, 0.08],
        },
        cluster_namer=LlmClusterNamer(provider=provider, ontology_name="CompanyAccess"),
        similarity_threshold=0.85,
    )

    assert report.cluster_count == 1
    cluster = report.clusters[0]
    assert cluster.label == "OrganizationActor"
    assert cluster.exemplar in {"Company", "Organization", "Employer"}
    assert cluster.requires_human_review is True
    assert report.backend == "deterministic-similarity-fallback+llm-cluster-namer"
    assert "LLM-generated cluster labels require human ontology review." in report.warnings

    draft = report.to_linkml_draft(schema_name="company_discovery")
    assert "OrganizationActor" in draft["classes"]
    assert draft["classes"]["OrganizationActor"]["annotations"]["requires_human_review"] == "true"
    assert draft["annotations"]["discovery_backend"].endswith("+llm-cluster-namer")
