"""Cold-start schema discovery from candidate domain terms.

This module intentionally produces *draft* schema suggestions only.  Clustering can
surface candidate TBox classes, but the output must be reviewed by a human domain
expert before it is promoted into a production ontology.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, Sequence

NumberVector = Sequence[float]
EmbeddingMap = Mapping[str, NumberVector]


class TermExtractorProtocol(Protocol):
    """Protocol for candidate-term extractors."""

    backend_name: str

    def extract_terms(self, texts: Iterable[str], *, min_frequency: int = 1) -> list[str]:
        """Return normalized candidate schema terms from source texts."""
        ...


class EmbeddingProviderProtocol(Protocol):
    """Protocol for term embedding providers."""

    backend_name: str

    def embed_terms(self, terms: Sequence[str]) -> EmbeddingMap:
        """Return embeddings keyed by term."""
        ...


class ClustererProtocol(Protocol):
    """Protocol for clustering terms from a precomputed embedding map."""

    backend_name: str

    def cluster(self, terms: Sequence[str], vectors: Mapping[str, tuple[float, ...]]) -> dict[str, int]:
        """Return cluster labels keyed by term."""
        ...


class CompletionProviderProtocol(Protocol):
    """Protocol for provider clients that can complete naming prompts."""

    def complete(self, prompt: str) -> str:
        """Return a model completion for a prompt."""
        ...


class ClusterNamerProtocol(Protocol):
    """Protocol for optional production cluster-label generators."""

    backend_name: str

    def name_cluster(self, *, exemplar: str, terms: Sequence[str]) -> str:
        """Return a human-readable class label for a discovered cluster."""
        ...


@dataclass(frozen=True)
class ClusterMember:
    """A candidate term assigned to a discovered cluster."""

    term: str
    similarity_to_exemplar: float

    def to_json_dict(self) -> dict[str, object]:
        return {
            "term": self.term,
            "similarity_to_exemplar": round(self.similarity_to_exemplar, 6),
        }


@dataclass(frozen=True)
class DiscoveredCluster:
    """Human-reviewable cluster of candidate terms."""

    label: str
    exemplar: str
    members: tuple[ClusterMember, ...]
    requires_human_review: bool = True

    def to_json_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "exemplar": self.exemplar,
            "requires_human_review": self.requires_human_review,
            "members": [member.to_json_dict() for member in self.members],
        }


@dataclass(frozen=True)
class SchemaDiscoveryReport:
    """Result of clustering candidate terms into draft schema concepts."""

    clusters: tuple[DiscoveredCluster, ...]
    term_count: int
    backend: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def cluster_count(self) -> int:
        return len(self.clusters)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "term_count": self.term_count,
            "cluster_count": self.cluster_count,
            "backend": self.backend,
            "warnings": list(self.warnings),
            "clusters": [cluster.to_json_dict() for cluster in self.clusters],
        }

    def to_linkml_draft(self, schema_name: str = "discovered_schema") -> dict[str, object]:
        """Render a minimal LinkML-compatible draft from discovered clusters."""
        classes: dict[str, dict[str, object]] = {}
        for cluster in self.clusters:
            class_name = _to_pascal_case(cluster.label)
            member_terms = ", ".join(member.term for member in cluster.members)
            classes[class_name] = {
                "description": (
                    "Discovered from candidate terms; requires human ontology review. "
                    f"Terms: {member_terms}."
                ),
                "annotations": {
                    "cluster_exemplar": cluster.exemplar,
                    "requires_human_review": "true",
                    "source_terms": member_terms,
                },
            }

        return {
            "id": f"https://example.org/{_to_snake_case(schema_name)}",
            "name": schema_name,
            "prefixes": {schema_name: f"https://example.org/{_to_snake_case(schema_name)}/"},
            "default_prefix": schema_name,
            "annotations": {
                "generation_status": "schema_discovery_draft_requires_human_review",
                "discovery_backend": self.backend,
            },
            "classes": classes,
        }


_SIMPLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def extract_terms(texts: Iterable[str], *, min_frequency: int = 1) -> list[str]:
    """Extract lightweight candidate terms without requiring SpaCy.

    The optional production path can swap in ``SpaCyTermExtractor``, but the base
    SDK keeps a deterministic regex fallback so cloning the repository does not
    require heavyweight model downloads.
    """
    return _extract_terms_with_fallback(texts, min_frequency=min_frequency)


@dataclass(frozen=True)
class SpaCyTermExtractor:
    """Production noun-chunk candidate extractor with lazy SpaCy loading.

    Tests can inject a tiny ``nlp`` callable to avoid model downloads. Production
    callers can pass ``model_name`` and install the ``clustering`` extra.
    """

    model_name: str = "en_core_web_sm"
    nlp: Any | None = None
    backend_name: str = "spacy-noun-chunks"

    def extract_terms(self, texts: Iterable[str], *, min_frequency: int = 1) -> list[str]:
        nlp = self.nlp if self.nlp is not None else self._load_spacy_model()
        counts: Counter[str] = Counter()
        display: dict[str, str] = {}
        for text in texts:
            doc = nlp(text)
            for chunk in getattr(doc, "noun_chunks", []):
                normalized = _normalize_term(str(chunk.text))
                if not normalized or normalized in _SIMPLE_STOPWORDS:
                    continue
                counts[normalized.lower()] += 1
                display.setdefault(normalized.lower(), normalized)
        return [display[key] for key, count in counts.items() if count >= min_frequency]

    def _load_spacy_model(self) -> Any:
        try:
            import spacy  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise RuntimeError("SpaCy is not installed. Install with: pip install -e '.[clustering]'") from exc
        try:
            return spacy.load(self.model_name)
        except OSError as exc:
            raise RuntimeError(
                f"SpaCy model {self.model_name!r} is not installed. "
                f"Run: python -m spacy download {self.model_name}"
            ) from exc


@dataclass(frozen=True)
class SentenceTransformerEmbeddingProvider:
    """Production term embedding provider with lazy sentence-transformers loading."""

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    model: Any | None = None
    backend_name: str = "sentence-transformers"

    def embed_terms(self, terms: Sequence[str]) -> EmbeddingMap:
        model = self.model if self.model is not None else self._load_model()
        ordered_terms = list(terms)
        encoded = model.encode(ordered_terms, normalize_embeddings=True)
        return {
            term: tuple(float(value) for value in vector)
            for term, vector in zip(ordered_terms, encoded)
        }

    def _load_model(self) -> Any:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Install with: pip install -e '.[clustering]'"
            ) from exc
        return SentenceTransformer(self.model_name)


@dataclass(frozen=True)
class AffinityPropagationClusterer:
    """Cluster embeddings with scikit-learn AffinityPropagation.

    The adapter uses a precomputed cosine similarity matrix and lazy imports so
    the base package remains lightweight.
    """

    preference: float | None = None
    random_state: int | None = 0
    affinity_propagation_cls: Any | None = None
    backend_name: str = "sklearn-affinity-propagation"

    def cluster(self, terms: Sequence[str], vectors: Mapping[str, tuple[float, ...]]) -> dict[str, int]:
        if not terms:
            return {}
        affinity_propagation_cls = (
            self.affinity_propagation_cls
            if self.affinity_propagation_cls is not None
            else self._load_affinity_propagation_cls()
        )
        matrix = [[_cosine(vectors[left], vectors[right]) for right in terms] for left in terms]
        model = affinity_propagation_cls(
            affinity="precomputed",
            random_state=self.random_state,
            preference=self.preference,
        )
        fitted = model.fit(matrix)
        labels = list(getattr(fitted, "labels_"))
        return {term: int(label) for term, label in zip(terms, labels)}

    def _load_affinity_propagation_cls(self) -> Any:
        try:
            from sklearn.cluster import AffinityPropagation  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise RuntimeError("scikit-learn is not installed. Install with: pip install -e '.[clustering]'") from exc
        return AffinityPropagation


@dataclass(frozen=True)
class LlmClusterNamer:
    """Production cluster namer backed by an LLM completion provider.

    The returned label is still a draft ontology class name and must be reviewed
    by a human domain expert before promotion into a canonical TBox.
    """

    provider: CompletionProviderProtocol
    ontology_name: str = "DiscoveredOntology"
    backend_name: str = "llm-cluster-namer"

    def name_cluster(self, *, exemplar: str, terms: Sequence[str]) -> str:
        prompt = self._build_prompt(exemplar=exemplar, terms=terms)
        return _sanitize_class_label(self.provider.complete(prompt), fallback=exemplar)

    def _build_prompt(self, *, exemplar: str, terms: Sequence[str]) -> str:
        numbered_terms = "\n".join(f"{index}. {term}" for index, term in enumerate(terms, start=1))
        return (
            "# NeuroOntoGen Cluster Naming Prompt\n"
            f"Ontology: {self.ontology_name}\n"
            f"Cluster exemplar: {exemplar}\n\n"
            "## Candidate terms\n"
            f"{numbered_terms}\n\n"
            "## Task\n"
            "Return exactly one PascalCase class label for this draft ontology cluster. "
            "The label must be concise, domain-neutral, and suitable for human ontology review. "
            "Do not include Markdown, quotes, explanations, properties, or unrelated entities.\n\n"
            "## Output Contract\n"
            "Return exactly one PascalCase class label."
        )


@dataclass(frozen=True)
class _FallbackTermExtractor:
    backend_name: str = "regex-fallback"

    def extract_terms(self, texts: Iterable[str], *, min_frequency: int = 1) -> list[str]:
        return _extract_terms_with_fallback(texts, min_frequency=min_frequency)


def _extract_terms_with_fallback(texts: Iterable[str], *, min_frequency: int = 1) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for text in texts:
        candidates = _candidate_phrases(text)
        for candidate in candidates:
            normalized = _normalize_term(candidate)
            if not normalized or normalized in _SIMPLE_STOPWORDS:
                continue
            counts[normalized.lower()] += 1
            display.setdefault(normalized.lower(), normalized)

    return [display[key] for key, count in counts.items() if count >= min_frequency]


def discover_schema_from_texts(
    texts: Iterable[str],
    *,
    embeddings: EmbeddingMap | None = None,
    embedding_provider: EmbeddingProviderProtocol | None = None,
    term_extractor: TermExtractorProtocol | None = None,
    clusterer: ClustererProtocol | None = None,
    cluster_namer: ClusterNamerProtocol | None = None,
    min_frequency: int = 1,
    similarity_threshold: float = 0.78,
) -> SchemaDiscoveryReport:
    """Extract terms from text and cluster them into schema-discovery suggestions."""
    extractor = term_extractor or _FallbackTermExtractor()
    terms = extractor.extract_terms(texts, min_frequency=min_frequency)
    return discover_schema_from_terms(
        terms,
        embeddings=embeddings,
        embedding_provider=embedding_provider,
        clusterer=clusterer,
        cluster_namer=cluster_namer,
        similarity_threshold=similarity_threshold,
    )


def discover_schema_from_terms(
    terms: Iterable[str],
    *,
    embeddings: EmbeddingMap | None = None,
    embedding_provider: EmbeddingProviderProtocol | None = None,
    clusterer: ClustererProtocol | None = None,
    cluster_namer: ClusterNamerProtocol | None = None,
    similarity_threshold: float = 0.78,
) -> SchemaDiscoveryReport:
    """Cluster candidate terms and return a human-reviewable schema draft report.

    The production path can combine ``SentenceTransformerEmbeddingProvider`` with
    ``AffinityPropagationClusterer`` and an optional ``LlmClusterNamer``. The
    default path remains deterministic and dependency-light for CI/reviewer
    smoke tests.
    """
    if embeddings is not None and embedding_provider is not None:
        raise ValueError("Pass either embeddings or embedding_provider, not both.")

    unique_terms = _dedupe_terms(terms)
    if not unique_terms:
        return SchemaDiscoveryReport(
            clusters=(),
            term_count=0,
            backend="deterministic-similarity-fallback",
            warnings=("No candidate terms were provided.",),
        )

    vector_map = _vectors_for_terms(unique_terms, embeddings, embedding_provider)
    if clusterer is None:
        labels = _cluster_by_similarity(unique_terms, vector_map, similarity_threshold)
        backend = "deterministic-similarity-fallback"
    else:
        labels = clusterer.cluster(unique_terms, vector_map)
        backend = clusterer.backend_name
    clusters = _build_clusters(unique_terms, labels, vector_map, cluster_namer)
    warnings = ["Generated clusters are schema-discovery suggestions only and require human review."]
    if cluster_namer is not None:
        backend = f"{backend}+{cluster_namer.backend_name}"
        warnings.append("LLM-generated cluster labels require human ontology review.")
    return SchemaDiscoveryReport(
        clusters=tuple(clusters),
        term_count=len(unique_terms),
        backend=backend,
        warnings=tuple(warnings),
    )


def _candidate_phrases(text: str) -> list[str]:
    capitalized = re.findall(r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*\b", text)
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b", text)
    lower_ngrams: list[str] = []
    for size in (2, 3):
        for index in range(0, max(len(tokens) - size + 1, 0)):
            window = tokens[index : index + size]
            if any(token[0].isupper() for token in window):
                continue
            lower_ngrams.append(" ".join(window))
    return [*capitalized, *lower_ngrams, *tokens]


def _normalize_term(term: str) -> str:
    cleaned = re.sub(r"\s+", " ", term.strip(" .,:;()[]{}\n\t"))
    words = [word for word in cleaned.split(" ") if word.lower() not in _SIMPLE_STOPWORDS]
    if not words:
        return ""
    return " ".join(words)


def _dedupe_terms(terms: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        normalized = _normalize_term(term)
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            unique.append(normalized)
    return unique


def _vectors_for_terms(
    terms: Sequence[str],
    embeddings: EmbeddingMap | None,
    embedding_provider: EmbeddingProviderProtocol | None,
) -> dict[str, tuple[float, ...]]:
    if embeddings is not None:
        missing = [term for term in terms if term not in embeddings]
        if missing:
            raise ValueError(f"Missing embeddings for terms: {', '.join(missing)}")
        return {term: tuple(float(value) for value in embeddings[term]) for term in terms}
    if embedding_provider is not None:
        provided = embedding_provider.embed_terms(terms)
        missing = [term for term in terms if term not in provided]
        if missing:
            raise ValueError(f"Embedding provider missed terms: {', '.join(missing)}")
        return {term: tuple(float(value) for value in provided[term]) for term in terms}
    return {term: _char_ngram_vector(term) for term in terms}


def _cluster_by_similarity(
    terms: Sequence[str],
    vectors: Mapping[str, tuple[float, ...]],
    threshold: float,
) -> dict[str, int]:
    parent = {term: term for term in terms}

    def find(term: str) -> str:
        while parent[term] != term:
            parent[term] = parent[parent[term]]
            term = parent[term]
        return term

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for index, left in enumerate(terms):
        for right in terms[index + 1 :]:
            if _cosine(vectors[left], vectors[right]) >= threshold:
                union(left, right)

    root_to_label: dict[str, int] = {}
    labels: dict[str, int] = {}
    for term in terms:
        root = find(term)
        root_to_label.setdefault(root, len(root_to_label))
        labels[term] = root_to_label[root]
    return labels


def _build_clusters(
    terms: Sequence[str],
    labels: Mapping[str, int],
    vectors: Mapping[str, tuple[float, ...]],
    cluster_namer: ClusterNamerProtocol | None = None,
) -> list[DiscoveredCluster]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for term in terms:
        grouped[labels[term]].append(term)

    clusters: list[DiscoveredCluster] = []
    for label_id in sorted(grouped):
        cluster_terms = grouped[label_id]
        exemplar = _choose_exemplar(cluster_terms, vectors)
        members = tuple(
            ClusterMember(term=term, similarity_to_exemplar=_cosine(vectors[term], vectors[exemplar]))
            for term in sorted(cluster_terms, key=str.lower)
        )
        label = (
            cluster_namer.name_cluster(exemplar=exemplar, terms=[member.term for member in members])
            if cluster_namer is not None
            else _to_pascal_case(exemplar)
        )
        clusters.append(
            DiscoveredCluster(
                label=label,
                exemplar=exemplar,
                members=members,
            )
        )
    return sorted(clusters, key=lambda cluster: cluster.label)


def _choose_exemplar(terms: Sequence[str], vectors: Mapping[str, tuple[float, ...]]) -> str:
    def score(term: str) -> tuple[float, int, str]:
        similarities = [_cosine(vectors[term], vectors[other]) for other in terms]
        return (sum(similarities) / len(similarities), -len(term), term.lower())

    return max(terms, key=score)


def _char_ngram_vector(term: str) -> tuple[float, ...]:
    text = f"  {term.lower()}  "
    grams = Counter(text[index : index + 3] for index in range(max(len(text) - 2, 1)))
    ordered = sorted(grams)
    # Hash into a small deterministic vector to avoid a variable-size sparse dependency.
    buckets = [0.0] * 64
    for gram in ordered:
        buckets[sum(ord(ch) for ch in gram) % len(buckets)] += float(grams[gram])
    return tuple(buckets)


def _cosine(left: NumberVector, right: NumberVector) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding vectors must have the same dimensionality.")
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _sanitize_class_label(label: str, *, fallback: str) -> str:
    stripped = label.strip()
    fence_match = re.fullmatch(r"```(?:text)?\s*\n(?P<body>.*?)\n?```", stripped, flags=re.DOTALL)
    if fence_match is not None:
        stripped = fence_match.group("body").strip()
    first_line = stripped.splitlines()[0] if stripped.splitlines() else ""
    sanitized = _to_pascal_case(first_line)
    return sanitized or _to_pascal_case(fallback)


def _to_pascal_case(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    return "".join(word[:1].upper() + word[1:] for word in words) or "DiscoveredClass"


def _to_snake_case(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value.lower())
    return "_".join(words) or "discovered_schema"
