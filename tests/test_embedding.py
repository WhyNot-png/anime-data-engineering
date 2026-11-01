"""Verify E5 formatting and CPU configuration without downloading weights."""

import importlib
from types import ModuleType

import pytest

from research_graph import embedding


def test_encoder_configuration_and_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    options: dict[str, object] = {}

    class Array:
        def tolist(self) -> list[list[float]]:
            return [[1.0, 0.0]]

    class Model:
        def encode(self, sentences: list[str], **kwargs: object) -> Array:
            assert kwargs["normalize_embeddings"] is True
            calls.append(sentences)
            return Array()

    def factory(name: str, **kwargs: object) -> Model:
        options.update(kwargs)
        options["name"] = name
        return Model()

    module = ModuleType("fake_sentence_transformers")
    monkeypatch.setattr(module, "SentenceTransformer", factory, raising=False)
    monkeypatch.setattr(importlib, "import_module", lambda _: module)
    encoder = embedding.SentenceEncoder()
    assert encoder.encode(["тетрадь"], kind="query") == [[1.0, 0.0]]
    encoder.encode(["A plot"], kind="passage")
    assert calls == [["query: тетрадь"], ["passage: A plot"]]
    assert options["revision"] == embedding.MODEL_REVISION
    assert options["device"] == "cpu"
    assert options["trust_remote_code"] is False


def test_missing_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> ModuleType:
        raise ModuleNotFoundError(name=name)

    monkeypatch.setattr(importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="requirements-search"):
        embedding.SentenceEncoder()


def test_unrelated_import_failure_is_not_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> ModuleType:
        raise ModuleNotFoundError(name="another_dependency")

    monkeypatch.setattr(importlib, "import_module", missing)
    with pytest.raises(ModuleNotFoundError):
        embedding.SentenceEncoder()
