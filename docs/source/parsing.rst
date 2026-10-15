Parsing contract
================

The parser supports JSON5 1.0 syntax, including Unicode identifiers and whitespace, hexadecimal numbers, single-quoted strings, line continuations, trailing commas, and both comment forms.
Line comments end at CR, LF, U+2028, or U+2029.
Unescaped U+2028 and U+2029 inside strings are accepted.

Duplicate object keys are rejected, including equivalent escaped spellings.
Finite numeric literals that overflow or underflow binary64 are rejected.
Explicit ``Infinity`` and ``NaN`` are accepted.
Negative zero is preserved, including hexadecimal spellings.
UTF-16 surrogate pairs are combined; lone surrogates are retained for callers to apply their own Unicode policy.
Integers are arbitrary precision within the interpreter's decimal digit limit.
The nesting limit is 512 collections, enforced without recursive parsing.

Use ``tokenize(source=...)`` to inspect every token, including whitespace.
Token and node spans use half-open Unicode character offsets into the original source.

``JSON5DecodeError`` provides ``reason``, ``msg``, ``doc``, ``pos``, ``lineno``, and ``colno``.
Positions refer to the original input, with one-based lines and columns and zero-based offsets.
Every JSON5 line terminator is recognized when reporting positions.

The document is a source snapshot.
``to_source()`` returns the original text; changing a returned Python collection does not edit that text.
Source editing and JSONC validation are outside this library's API.
