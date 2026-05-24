from neuro_onto_gen.clustering.discovery import (
    AffinityPropagationClusterer,
    SentenceTransformerEmbeddingProvider,
    SpaCyTermExtractor,
    discover_schema_from_terms,
    discover_schema_from_texts,
)


class FakeSpan:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeDoc:
    def __init__(self, chunks: list[str]) -> None:
        self.noun_chunks = [FakeSpan(chunk) for chunk in chunks]


class FakeNlp:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, text: str) -> FakeDoc:
        self.calls.append(text)
        if "first" in text:
            return FakeDoc(["secure asset", "access policy"])
        return FakeDoc(["secure asset", "employee record"])


class FakeSentenceTransformer:
    def __init__(self) -> None:
        self.encoded_batches: list[list[str]] = []

    def encode(self, terms: list[str], normalize_embeddings: bool = True) -> list[list[float]]:
        self.encoded_batches.append(list(terms))
        assert normalize_embeddings is True
        return [[1.0, 0.0] if "asset" in term.lower() else [0.0, 1.0] for term in terms]


class FakeAffinityPropagation:
    def __init__(self, *, affinity: str, random_state: int | None = None, preference: float | None = None) -> None:
        self.affinity = affinity
        self.random_state = random_state
        self.preference = preference
        self.labels_: list[int] = []

    def fit(self, matrix: list[list[float]]) -> "FakeAffinityPropagation":
        assert self.affinity == "precomputed"
        self.labels_ = [index // 2 for index in range(len(matrix))]
        return self


def test_spacy_term_extractor_uses_injected_noun_chunk_pipeline_without_model_download() -> None:
    fake_nlp = FakeNlp()
    extractor = SpaCyTermExtractor(nlp=fake_nlp)

    terms = extractor.extract_terms(["first text", "second text"], min_frequency=2)

    assert terms == ["secure asset"]
    assert fake_nlp.calls == ["first text", "second text"]


def test_sentence_transformer_embedding_provider_uses_injected_model_normalized_encode() -> None:
    model = FakeSentenceTransformer()
    provider = SentenceTransformerEmbeddingProvider(model=model)

    embeddings = provider.embed_terms(["secure asset", "access policy"])

    assert embeddings == {"secure asset": (1.0, 0.0), "access policy": (0.0, 1.0)}
    assert model.encoded_batches == [["secure asset", "access policy"]]


def test_affinity_propagation_clusterer_is_lazy_and_produces_backend_report() -> None:
    clusterer = AffinityPropagationClusterer(affinity_propagation_cls=FakeAffinityPropagation)
    embeddings = {
        "secure asset": [1.0, 0.0],
        "digital asset": [0.95, 0.05],
        "employee": [0.0, 1.0],
        "contractor": [0.05, 0.95],
    }

    report = discover_schema_from_terms(
        embeddings.keys(),
        embeddings=embeddings,
        clusterer=clusterer,
    )

    assert report.backend == "sklearn-affinity-propagation"
    assert report.cluster_count == 2
    assert {member.term for cluster in report.clusters for member in cluster.members} == set(embeddings)
    assert all(cluster.requires_human_review for cluster in report.clusters)


def test_discover_schema_from_texts_accepts_production_extractor_and_embedding_provider() -> None:
    report = discover_schema_from_texts(
        ["first text", "second text"],
        term_extractor=SpaCyTermExtractor(nlp=FakeNlp()),
        embedding_provider=SentenceTransformerEmbeddingProvider(model=FakeSentenceTransformer()),
        clusterer=AffinityPropagationClusterer(affinity_propagation_cls=FakeAffinityPropagation),
    )

    assert report.backend == "sklearn-affinity-propagation"
    assert report.term_count == 3
    assert report.to_linkml_draft("company_discovery")["annotations"]["generation_status"] == (
        "schema_discovery_draft_requires_human_review"
    )
