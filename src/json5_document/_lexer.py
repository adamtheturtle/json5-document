"""JSON5 lexical grammar with original source spans."""

import math
import re
import unicodedata
from collections.abc import Iterator

from json5_document._model import (
    ErrorKind,
    JSON5DecodeError,
    Token,
    TokenKind,
)

_LINE_ENDINGS = "\r\n\u2028\u2029"
_WHITE_SPACE = "\t\v\f \ufeff" + _LINE_ENDINGS
_NUMBER = re.compile(
    pattern=r"[+-]?(?:Infinity|NaN|0[xX][0-9a-fA-F]+|"
    r"(?:(?:0|[1-9][0-9]*)(?:\.[0-9]*)?|\.[0-9]+)"
    r"(?:[eE][+-]?[0-9]+)?)"
)
_ESCAPES = {
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
    "0": "\0",
}


def _error(*, source: str, position: int, message: str) -> JSON5DecodeError:
    """Build a position-bearing lexical error."""
    return JSON5DecodeError(
        message=message,
        source=source,
        position=position,
        reason=ErrorKind.SYNTAX,
    )


def _hex_escape(*, source: str, index: int, width: int) -> str:
    """Decode the exact required number of hexadecimal digits."""
    digits = source[index : index + width]
    if len(digits) != width or any(
        char not in "0123456789abcdefABCDEF" for char in digits
    ):
        raise _error(
            source=source, position=index, message="Invalid hexadecimal escape"
        )
    return chr(int(digits, base=16))


def _string(*, source: str, start: int) -> tuple[int, str]:
    """Read a quoted string and decode JSON5 escape sequences."""
    quote = source[start]
    index = start + 1
    characters: list[str] = []
    while index < len(source):
        char = source[index]
        index += 1
        if char == quote:
            decoded = "".join(characters)
            # Combine well-formed surrogate pairs while retaining lone ones.
            return index, decoded.encode(
                encoding="utf-16", errors="surrogatepass"
            ).decode(encoding="utf-16", errors="surrogatepass")
        if char in "\r\n":
            raise _error(
                source=source,
                position=index - 1,
                message="Unescaped line terminator in string",
            )
        if char != "\\":
            characters.append(char)
            continue
        if index == len(source):
            break
        char = source[index]
        index += 1
        if char in _LINE_ENDINGS:
            if char == "\r" and source[index : index + 1] == "\n":
                index += 1
        elif char in "xu":
            width = 2 if char == "x" else 4
            characters.append(
                _hex_escape(source=source, index=index, width=width)
            )
            index += width
        elif char in "123456789" or (
            char == "0" and source[index : index + 1] in tuple("0123456789")
        ):
            raise _error(
                source=source,
                position=index - 1,
                message="Decimal digits cannot be escaped",
            )
        else:
            characters.append(_ESCAPES.get(char, char))
    raise _error(source=source, position=start, message="Unterminated string")


def _identifier_character(*, char: str, first: bool) -> bool:
    """Apply ECMAScript identifier Unicode category rules."""
    categories = {"Lu", "Ll", "Lt", "Lm", "Lo", "Nl"}
    if not first:
        categories |= {"Mn", "Mc", "Nd", "Pc"}
    return (
        char in "$_"
        or unicodedata.category(char) in categories
        or (not first and char in "\u200c\u200d")
    )


def _identifier(*, source: str, start: int) -> tuple[int, str]:
    """Read an IdentifierName, validating escaped characters too."""
    index = start
    characters: list[str] = []
    while index < len(source):
        char = source[index]
        end = index + 1
        if char == "\\":
            if source[index + 1 : index + 2] != "u":
                raise _error(
                    source=source,
                    position=index,
                    message="Identifiers only allow Unicode escapes",
                )
            char = _hex_escape(source=source, index=index + 2, width=4)
            end = index + 6
            if not _identifier_character(
                char=char, first=not bool(characters)
            ):
                raise _error(
                    source=source,
                    position=index,
                    message="Invalid escaped identifier character",
                )
        elif not _identifier_character(char=char, first=not bool(characters)):
            break
        characters.append(char)
        index = end
    if not bool(characters):
        raise _error(
            source=source, position=start, message="Unexpected character"
        )
    return index, "".join(characters)


def _number_value(*, source: str, start: int, raw: str) -> int | float:
    """Decode a number while rejecting finite overflow and underflow."""
    unsigned = raw.lstrip("+-")
    if unsigned == "NaN":
        return math.nan
    if unsigned == "Infinity":
        return -math.inf if raw.startswith("-") else math.inf
    try:
        if unsigned.startswith(("0x", "0X")):
            integer = int(raw, base=16)
            _ = str(object=integer)
            return integer
        if raw == "-0":
            return -0.0
        if not any(char in raw for char in ".eE"):
            return int(raw, base=10)
        value = float(raw)
    except ValueError as exc:
        raise JSON5DecodeError(
            source=source,
            position=start,
            reason=ErrorKind.INTEGER_DIGITS,
            message="Integer exceeds the interpreter's supported digit limit",
        ) from exc
    significant = (
        unsigned.lower().split(sep="e")[0].replace(".", "").strip("0")
    )
    if math.isinf(value) or (value == 0 and bool(significant)):
        raise JSON5DecodeError(
            source=source,
            position=start,
            reason=ErrorKind.NUMBER_RANGE,
            message="Finite numeric token is outside binary64 range",
        )
    return value


def _whitespace_end(*, source: str, index: int) -> int:
    """Find the end of consecutive JSON5 whitespace."""
    index += 1
    while index < len(source) and (
        source[index] in _WHITE_SPACE
        or unicodedata.category(source[index]) == "Zs"
    ):
        index += 1
    return index


def _block_comment_end(*, source: str, index: int) -> int:
    """Find a block comment's terminator or report its original start."""
    close = source.find("*/", index + 2)
    if close == -1:
        raise _error(
            source=source, position=index, message="Unterminated block comment"
        )
    return close + 2


def tokenize(*, source: str) -> Iterator[Token]:
    """
    Yield every source token, including comments and whitespace.

    Lexical validity is checked; use ``parse`` to validate the complete
    document grammar.
    """
    index = 0
    while index < len(source):
        start = index
        char = source[index]
        value: str | int | float | bool | None = None
        if char in _WHITE_SPACE or unicodedata.category(char) == "Zs":
            kind = TokenKind.WHITESPACE
            index = _whitespace_end(source=source, index=index)
        elif source.startswith("//", index):
            kind = TokenKind.COMMENT
            index += 2
            while index < len(source) and source[index] not in _LINE_ENDINGS:
                index += 1
        elif source.startswith("/*", index):
            kind = TokenKind.COMMENT
            index = _block_comment_end(source=source, index=index)
        elif char in "{}[]:,":
            kind = TokenKind.PUNCTUATION
            index += 1
        elif char in "\"'":
            kind = TokenKind.STRING
            index, value = _string(source=source, start=start)
        elif char in "+-.0123456789":
            kind = TokenKind.NUMBER
            match = _NUMBER.match(string=source, pos=index)
            if match is None:
                raise _error(
                    source=source, position=start, message="Invalid number"
                )
            index = match.end()
            value = _number_value(
                source=source, start=start, raw=match.group()
            )
        else:
            kind = TokenKind.IDENTIFIER
            index, value = _identifier(source=source, start=start)
        yield Token(
            kind=kind,
            text=source[start:index],
            start=start,
            end=index,
            value=value,
        )
