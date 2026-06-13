# Local Embedding Setup with fastembed

When FreeLLM API doesn't have embedding endpoints (pitfall #13), add a
local CPU embedding provider using `fastembed` (Qdrant, ONNX Runtime).

## Pattern: Add local embedding to any OpenAI-protocol project

### 1. Install

```bash
pip install fastembed
# Or with uv: uv add fastembed
```

### 2. Implement the EmbeddingProvider protocol

```python
"""Local embedding via fastembed — async wrapper around sync ONNX."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import numpy as np
from fastembed import TextEmbedding


class EmbeddingError(Exception):
    """Raised on any provider-side embedding failure."""


class FastEmbedProvider:
    """Local CPU embedding via fastembed / ONNX Runtime.

    Args:
        model: HuggingFace model name
            (e.g. "BAAI/bge-small-en-v1.5" → 384 dim).
        dim: Target vector dimension; longer vectors truncated here.
        batch_size: How many texts per ONNX batch.
    """

    def __init__(
        self,
        *,
        model: str = "BAAI/bge-small-en-v1.5",
        dim: int = 384,
        batch_size: int = 32,
    ) -> None:
        self.dim = dim
        self._batch_size = batch_size
        self._lock = asyncio.Lock()  # ONNX is not thread-safe
        self._model = TextEmbedding(model_name=model, max_length=512)

    async def embed(self, text: str) -> list[float]:
        vectors = await self._embed_async([text])
        return vectors[0]

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._embed_async(texts)

    async def _embed_async(self, texts: Sequence[str]) -> list[list[float]]:
        async with self._lock:
            try:
                embeddings = list(
                    self._model.embed(list(texts), batch_size=self._batch_size)
                )
            except Exception as exc:
                raise EmbeddingError(str(exc)) from exc
        vectors = []
        for emb in embeddings:
            arr: np.ndarray = emb
            if arr.shape[0] > self.dim:
                arr = arr[: self.dim]
            vectors.append(arr.tolist())
        return vectors
```

### 3. Auto-detect in factory (api_key → remote, None → local)

```python
from .fastembed_provider import FastEmbedProvider
from .openai_provider import OpenAIEmbeddingProvider

def build_embedding_provider(settings) -> EmbeddingProvider:
    # Local path — no api_key needed
    if settings.api_key is None:
        model_name = settings.model or "BAAI/bge-small-en-v1.5"
        return FastEmbedProvider(
            model=model_name,
            dim=dim,
            batch_size=settings.batch_size,
        )

    # Remote path — requires model + base_url
    return OpenAIEmbeddingProvider(
        model=settings.model,
        api_key=settings.api_key.get_secret_value(),
        base_url=settings.base_url,
        dim=dim,
        ...
    )
```

## Identity/no-op reranker (keep pipelines alive)

When you don't have a real reranker, create a no-op that passes docs
through at score 1.0:

```python
class IdentityRerankProvider:
    async def rerank(self, query, documents, *, instruction=None):
        if not documents:
            return []
        return [RerankResult(index=i, score=1.0) for i in range(len(documents))]
```

Add to factory with early return so no model/base_url is required:

```python
if settings.provider == "identity":
    return IdentityRerankProvider()
```

Config setting: ``[rerank] provider = "identity"`` (default).

## Supported fastembed models

| Model | Dim | Size | Notes |
|-------|-----|------|-------|
| `BAAI/bge-small-en-v1.5` | 384 | ~33 MB | Fast, good quality |
| `BAAI/bge-base-en-v1.5` | 768 | ~100 MB | Better quality |
| `BAAI/bge-large-en-v1.5` | 1024 | ~330 MB | Best quality |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | ~80 MB | Popular, tiny |
| `sentence-transformers/all-mpnet-base-v2` | 768 | ~420 MB | Strong all-round |
| `intfloat/multilingual-e5-small` | 384 | ~100 MB | Multilingual |
| `intfloat/multilingual-e5-base` | 768 | ~260 MB | Multilingual better |
| `intfloat/multilingual-e5-large` | 1024 | ~780 MB | Multilingual best |

Models auto-download to ``~/.cache/huggingface/hub/`` on first use
(~100 MB for bge-small).

## Config layering (TOML → .env)

Put local-first defaults in user TOML, and let `.env` override only
when a remote endpoint is actually intended:

```toml
# ~/.everos/config.toml — local defaults
[embedding]
model    = "BAAI/bge-small-en-v1.5"
# api_key unset → fastembed

[rerank]
provider = "identity"
```

Priority: ``init_args > env vars > .env > user_toml > default_toml``.
Since `.env` has **higher** priority than user TOML, comment out
embedding env vars in `.env` when you want local mode:

```bash
# .env — comment out embedding to let user_toml take effect
# EVEROS_EMBEDDING__MODEL=...
# EVEROS_EMBEDDING__API_KEY=...
```
