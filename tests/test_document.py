"""Document semantics, source metadata, and parser regressions."""

import copy
import json
import math

import pytest
from hypothesis import given, strategies

from json5_document import (
    Document,
    ErrorKind,
    JSON5DecodeError,
    TokenKind,
    Value,
    loads,
    parse,
    tokenize,
)


@pytest.mark.parametrize(
    argnames="ending", argvalues=["\n", "\r", "\r\n", "\u2028", "\u2029"]
)
def test_comment_terminators(ending: str) -> None:
    """A following value cannot be swallowed into a line comment."""
    source = "// heading" + ending + "[1, // note" + ending + "2\n]"
    document = parse(source=source)
    assert document.value == [1, 2]
    assert [token.text for token in document.comments] == [
        "// heading",
        "// note",
    ]
    assert document.to_source() == source


@pytest.mark.parametrize(
    argnames="space",
    argvalues=["\u1680", "\u2000", "\u2003", "\u202f", "\u205f", "\u3000"],
)
def test_unicode_whitespace(space: str) -> None:
    """All Unicode Space Separator characters are legal whitespace."""
    assert loads(source="[1," + space + "2]") == [1, 2]


def test_source_spans_and_comments() -> None:
    """Nested nodes, member names, and comment tokens reference source."""
    source = '/* lead */ {a: [1, /* item */ 2], "b": {}} // tail'
    document = parse(source=source)
    assert isinstance(document, Document)
    assert document.value == {"a": [1, 2], "b": {}}
    assert (
        source[document.root.start : document.root.end]
        == '{a: [1, /* item */ 2], "b": {}}'
    )
    assert [key.value for key in document.root.keys] == ["a", "b"]
    assert [token.text for token in document.root.commas] == [","]
    array = document.root.children[0]
    assert source[array.start : array.end] == "[1, /* item */ 2]"
    assert [child.value for child in array.children] == [1, 2]
    assert [comment.kind for comment in document.comments] == [
        TokenKind.COMMENT
    ] * 3
    assert "".join(token.text for token in tokenize(source=source)) == source


@pytest.mark.parametrize(
    argnames="source", argvalues=["-0", "-0.0", "-0e10", "-.0"]
)
def test_negative_zero(source: str) -> None:
    """Negative zero retains its sign regardless of numeric spelling."""
    value = loads(source=source)
    assert isinstance(value, float)
    assert value == 0
    assert math.copysign(1.0, value) == -1


@pytest.mark.parametrize(
    argnames=("source", "expected"),
    argvalues=[
        ("+0xff", 255),
        ("-0Xff", -255),
        (".5", 0.5),
        ("1.e2", 100.0),
        ("0e9999", 0.0),
    ],
)
def test_numbers(source: str, expected: Value) -> None:
    """JSON5 hexadecimal and decimal spellings decode accurately."""
    assert loads(source=source) == expected


@pytest.mark.parametrize(argnames="source", argvalues=["NaN", "+NaN", "-NaN"])
def test_nan(source: str) -> None:
    """All explicitly signed NaN spellings are accepted."""
    value = loads(source=source)
    assert isinstance(value, float)
    assert math.isnan(value)


@pytest.mark.parametrize(
    argnames=("source", "expected"),
    argvalues=[
        ("Infinity", math.inf),
        ("+Infinity", math.inf),
        ("-Infinity", -math.inf),
    ],
)
def test_infinity(source: str, expected: float) -> None:
    """Only explicit infinity may yield infinite numeric values."""
    assert loads(source=source) == expected


@pytest.mark.parametrize(
    argnames="source", argvalues=["1e400", "-1e400", "1e-4000"]
)
def test_float_range(source: str) -> None:
    """Finite literals cannot silently overflow or underflow."""
    with pytest.raises(expected_exception=JSON5DecodeError) as caught:
        _ = loads(source=source)
    assert caught.value.reason == ErrorKind.NUMBER_RANGE


@pytest.mark.parametrize(
    argnames="source",
    argvalues=[
        "{a:1,a:2}",
        '{a:1,"\\u0061":2}',
        '{"😀":1,"\\ud83d\\ude00":2}',
        "{nested:{a:1,a:2}}",
    ],
)
def test_duplicate_keys(source: str) -> None:
    """Equivalent decoded keys are rejected before data is overwritten."""
    with pytest.raises(expected_exception=JSON5DecodeError) as caught:
        _ = loads(source=source)
    assert caught.value.reason == ErrorKind.DUPLICATE_KEY


@pytest.mark.parametrize(argnames="quote", argvalues=['"', "'"])
def test_raw_unicode_string_separators(quote: str) -> None:
    """Unicode line and paragraph separators are valid inside strings."""
    assert loads(source=quote + "a\u2028b\u2029c" + quote) == "a\u2028b\u2029c"


@pytest.mark.parametrize(
    argnames="ending", argvalues=["\n", "\r", "\r\n", "\u2028", "\u2029"]
)
def test_string_continuation(ending: str) -> None:
    """An escaped line terminator disappears from a string value."""
    assert loads(source='"a\\' + ending + 'b"') == "ab"


def test_string_escapes_and_surrogates() -> None:
    """JSON5 escape forms and UTF-16 surrogate pairs decode correctly."""
    assert (
        loads(source=r'"\b\f\n\r\t\v\0\x41\u0042\q\"\\"')
        == '\b\f\n\r\t\v\0ABq"\\'
    )
    assert loads(source=r'"\uD83D\uDE00"') == "😀"
    assert loads(source=r'"\uD800"') == "\ud800"


def test_identifier_categories() -> None:
    """Identifiers include Unicode categories and escaped characters."""
    assert loads(
        source=(
            r"{\u0061: 1, café: 2, $: 3, _: 4, á: 5, "
            "a\u200c: 6, a\u200d: 7, Infinityfoo: 8, NaN: 9, true: 10}"
        )
    ) == {
        "a": 1,
        "café": 2,
        "$": 3,
        "_": 4,
        "á": 5,
        "a‌": 6,
        "a‍": 7,
        "Infinityfoo": 8,
        "NaN": 9,
        "true": 10,
    }


@pytest.mark.parametrize(
    argnames="source",
    argvalues=[
        "",
        "// comment",
        "/*comment*/",
        "[",
        "{a",
        "{a:",
        "[1",
        "{a:1 b:2}",
        "{a 1}",
        "{1:2}",
        "[,]",
        "[1,,2]",
        "1 2",
        "undefined",
        r"\u0074rue",
        "1/2",
        "+",
        ".",
        "01",
        "0x",
        "[\u0661]",
        "'unterminated",
        '"bad\nline"',
        '"bad\rline"',
        '"\\',
        r'"\1"',
        r'"\01"',
        r'"\xG0"',
        r'"\u123"',
        r"{\x61:1}",
        r"{\u0031:1}",
        "/* unterminated",
    ],
)
def test_malformed_input(source: str) -> None:
    """Invalid syntax raises a structured source error."""
    with pytest.raises(expected_exception=JSON5DecodeError) as caught:
        _ = parse(source=source)
    error = caught.value
    assert error.reason == ErrorKind.SYNTAX
    assert error.doc == source
    assert error.pos >= 0
    assert error.lineno >= 1
    assert error.colno >= 1
    assert "line" in str(object=error)


@pytest.mark.parametrize(
    argnames="ending", argvalues=["\n", "\r", "\r\n", "\u2028", "\u2029"]
)
def test_error_locations(ending: str) -> None:
    """Coordinates reference the unchanged input and every line terminator."""
    source = "/* heading */" + ending + "{a: 1, !}"
    with pytest.raises(expected_exception=JSON5DecodeError) as caught:
        _ = parse(source=source)
    assert caught.value.pos == source.index("!")
    assert (caught.value.lineno, caught.value.colno) == (2, 8)


def test_nesting_limit() -> None:
    """The explicit nesting limit is independent of recursive parser calls."""
    assert len(parse(source="[" * 512 + "0" + "]" * 512).root.children) == 1
    with pytest.raises(expected_exception=JSON5DecodeError) as caught:
        _ = parse(source="[" * 513 + "0" + "]" * 513)
    assert caught.value.reason == ErrorKind.DEPTH


@pytest.mark.parametrize(
    argnames="source",
    argvalues=["1" * 5000, "0x" + "f" * 5000],
    ids=["decimal", "hex"],
)
def test_integer_digit_limit(source: str) -> None:
    """Interpreter integer limits produce source-bearing typed errors."""
    with pytest.raises(expected_exception=JSON5DecodeError) as caught:
        _ = loads(source=source)
    assert caught.value.reason == ErrorKind.INTEGER_DIGITS


_JSON_SCALARS = (
    strategies.none()
    | strategies.booleans()
    | strategies.integers(min_value=-(2**63), max_value=2**63)
    | strategies.floats(allow_nan=False, allow_infinity=False)
    | strategies.text(
        alphabet=strategies.characters(exclude_categories=["Cs"])
    )
)
_JSON_VALUES = strategies.recursive(
    base=_JSON_SCALARS,
    extend=lambda children: (
        strategies.lists(elements=children, max_size=5)
        | strategies.dictionaries(
            keys=strategies.text(max_size=12), values=children, max_size=5
        )
    ),
    max_leaves=20,
)


@given(value=_JSON_VALUES)
def test_json_superset(value: Value) -> None:
    """Generated JSON values decode identically through the JSON5 API."""
    source = json.dumps(obj=value)
    actual = loads(source=source)
    assert actual == value


def test_exception_copy() -> None:
    """Exceptions retain structured details across serialization
    boundaries.
    """
    with pytest.raises(expected_exception=JSON5DecodeError) as caught:
        _ = loads(source="/* heading */\r{a: !}")
    original = caught.value
    restored = copy.deepcopy(x=original)
    assert restored is not original
    assert (restored.msg, restored.doc, restored.pos, restored.reason) == (
        original.msg,
        original.doc,
        original.pos,
        original.reason,
    )
    assert str(object=restored) == str(object=original)


@given(value=_JSON_VALUES)
def test_comments_and_trailing_commas(value: Value) -> None:
    """Generated JSON5 extensions preserve values and comment source."""
    tokens = list(tokenize(source=json.dumps(obj=value)))
    spellings: list[str] = []
    previous = ""
    for token in tokens:
        if token.kind == TokenKind.WHITESPACE:
            continue
        if token.text in {"}", "]"} and previous not in {"{", "["}:
            spellings.append(",")
        spellings.append(token.text)
        previous = token.text
    source = "/* heading */" + "// note\u2028".join(spellings) + "/* tail */"
    document = parse(source=source)
    assert document.value == value
    assert document.to_source() == source
    assert document.comments[0].text == "/* heading */"
    assert document.comments[-1].text == "/* tail */"
