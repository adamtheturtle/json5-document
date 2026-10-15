"""Typed JSON5 parsing with comments and original source spans."""

from json5_document._lexer import tokenize
from json5_document._model import (
    Document,
    ErrorKind,
    JSON5DecodeError,
    Node,
    Token,
    TokenKind,
)
from json5_document._parser import loads, parse
from json5_document.types import Scalar, Value

__all__ = [
    "Document",
    "ErrorKind",
    "JSON5DecodeError",
    "Node",
    "Scalar",
    "Token",
    "TokenKind",
    "Value",
    "loads",
    "parse",
    "tokenize",
]
