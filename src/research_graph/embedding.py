"""Lazy, CPU-only multilingual E5 adapter; never requires a GitHub/API token."""

import importlib
from collections.abc import Sequence
from typing import Literal, Protocol, cast

MODEL_NAME = "intfloat/multilingual-e5-base"
MODEL_REVISION = "d128750597153bb5987e10b1c3493a34e5a4502a"


class _Array(Protocol):
    def tolist(self) -> list[list[float]]: ...


class _Model(Protocol):
    def encode(
        self,
        sentences: list[str],
        *,
        batch_size: int,
        normalize_embeddings: bool,
        show_progress_bar: bool,
        convert_to_numpy: bool,
    ) -> _Array: ...


class SentenceEncoder:
    """Use the same pinned model for queries and passages, with E5 prefixes."""

    model_name = MODEL_NAME
    revision = MODEL_REVISION

    def __init__(self) -> None:
        try:
            module = importlib.import_module("sentence_transformers")
        except ModuleNotFoundError as error:
            if error.name != "sentence_transformers":
                raise
            raise RuntimeError(
                "Install optional requirements-search.txt; see docs/anime_search.md"
            ) from None
        self._model = cast(
            _Model,
            module.SentenceTransformer(
                self.model_name, revision=self.revision, device="cpu", trust_remote_code=False
            ),
        )

    def encode(
        self, texts: Sequence[str], *, kind: Literal["query", "passage"]
    ) -> list[list[float]]:
        # E5 requires these English prefixes even for Russian-language input.
        sentences = [f"{kind}: {text}" for text in texts]
        return self._model.encode(
            sentences,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).tolist()
