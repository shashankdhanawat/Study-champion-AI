import faiss
import numpy as np


# all-MiniLM-L6-v2 creates 384-dimensional embeddings.
index = faiss.IndexFlatL2(384)


def add_embeddings(embeddings):
    """Add valid document embeddings to the FAISS index."""

    if embeddings is None:
        return False

    embeddings = np.asarray(embeddings, dtype=np.float32)

    if embeddings.size == 0:
        return False

    # A single embedding may arrive as shape (384,).
    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    if embeddings.ndim != 2 or embeddings.shape[1] != index.d:
        raise ValueError(
            f"Expected embeddings with shape (n, {index.d}), "
            f"but received {embeddings.shape}."
        )

    index.add(embeddings)
    return True


def get_relevant_chunks(chunks, indices):
    """Convert FAISS search indices to valid document chunks safely."""

    if not chunks or indices is None:
        return []

    indices = np.asarray(indices)

    # Handles [], array([]), and malformed search results.
    if indices.size == 0:
        return []

    # FAISS normally returns shape (1, top_k). Flatten also handles lists.
    results = []

    for raw_index in indices.reshape(-1):
        try:
            chunk_index = int(raw_index)
        except (TypeError, ValueError):
            continue

        # FAISS uses -1 when there is no valid result.
        if 0 <= chunk_index < len(chunks):
            results.append(chunks[chunk_index])

    return results