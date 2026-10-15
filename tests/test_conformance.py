"""Exercise the upstream JSON5 grammar corpus through the public API."""

from pathlib import Path

import pytest

from json5_document import JSON5DecodeError, parse

_CASES = sorted(
    path
    for path in (Path(__file__).parent / "conformance").rglob(pattern="*")
    if path.suffix in {".json", ".json5", ".js", ".txt"}
    and path.name != "UPSTREAM.txt"
)


@pytest.mark.parametrize(argnames="path", argvalues=_CASES, ids=str)
def test_conformance(path: Path) -> None:
    """Accept valid syntax and reject malformed syntax or duplicate
    keys.
    """
    source = path.read_bytes().decode(encoding="utf-8")
    if path.suffix in {".js", ".txt"} or path.name == "duplicate-keys.json":
        with pytest.raises(expected_exception=JSON5DecodeError):
            _ = parse(source=source)
        return
    document = parse(source=source)
    assert document.to_source() == source
    assert "".join(token.text for token in document.tokens) == source
    assert all(
        source[token.start : token.end] == token.text
        for token in document.tokens
    )
