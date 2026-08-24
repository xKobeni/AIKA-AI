"""Shared compatibility checks for PostgreSQL pgvector embeddings."""

SCHEMA_EMBEDDING_DIMENSION = 768


class EmbeddingCompatibilityError(ValueError):
    """Base error for embeddings that cannot safely reach pgvector."""


class EmbeddingConfigurationError(EmbeddingCompatibilityError):
    """Raised when startup configuration disagrees with the DB schema contract."""


class EmbeddingDimensionError(EmbeddingCompatibilityError):
    """Raised when a generated or repository-bound vector has the wrong size."""

    def __init__(self, name, expected, actual):
        self.name = name
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"{name} must contain exactly {expected} values; found {actual}."
        )


def validate_configured_embedding_dimension(
    configured_dimension,
    schema_dimension=SCHEMA_EMBEDDING_DIMENSION,
):
    """Validate the startup setting against the versioned schema contract."""
    if isinstance(configured_dimension, bool):
        raise EmbeddingConfigurationError(
            "EMBEDDING_DIMENSION must be a positive integer."
        )
    try:
        dimension = int(configured_dimension)
    except (TypeError, ValueError) as exc:
        raise EmbeddingConfigurationError(
            "EMBEDDING_DIMENSION must be a positive integer."
        ) from exc

    if dimension <= 0:
        raise EmbeddingConfigurationError(
            "EMBEDDING_DIMENSION must be a positive integer."
        )
    if dimension != schema_dimension:
        raise EmbeddingConfigurationError(
            f"Configured embedding dimension {dimension} does not match the "
            f"PostgreSQL vector schema dimension {schema_dimension}. Changing "
            "embedding dimensions requires a database migration and an AIKA restart."
        )
    return dimension


def validate_embedding_vector(
    embedding,
    expected_dimension=SCHEMA_EMBEDDING_DIMENSION,
    *,
    name="embedding",
    allow_none=False,
):
    """Reject incompatible vectors before a PostgreSQL operation can begin."""
    if embedding is None:
        if allow_none:
            return None
        raise EmbeddingDimensionError(name, expected_dimension, 0)

    if isinstance(embedding, (str, bytes, bytearray)):
        raise EmbeddingDimensionError(name, expected_dimension, "non-vector")
    try:
        actual = len(embedding)
    except TypeError as exc:
        raise EmbeddingDimensionError(
            name, expected_dimension, "non-vector"
        ) from exc

    if actual != expected_dimension:
        raise EmbeddingDimensionError(name, expected_dimension, actual)
    return embedding
