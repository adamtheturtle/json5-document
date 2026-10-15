json5-document
==============

A typed JSON5 parser that preserves comments, tokens, and source spans.
It requires Python 3.12 or newer and has no runtime dependencies.

Installation
------------

.. code-block:: console

    pip install json5-document

Usage
-----

.. code-block:: python

    """Inspect parsed JSON5 values and their source comments."""

    import json5_document

    source = "// heading\n{count: 2, /* explanation */ items: [1, 2,],}"
    document = json5_document.parse(source=source)
    assert document.value == {"count": 2, "items": [1, 2]}
    assert document.to_source() == source
    assert [comment.text for comment in document.comments] == [
        "// heading",
        "/* explanation */",
    ]
    assert document.root.keys[0].value == "count"
    assert [child.value for child in document.root.children] == [
        2,
        [1, 2],
    ]

Use ``loads(source=...)`` when only Python values are needed.
Use ``tokenize(source=...)`` to inspect every token, including whitespace.
Token and node spans use half-open Unicode character offsets into the original source.

Parsing contract
----------------

The parser supports JSON5 1.0 syntax, including Unicode identifiers and whitespace, hexadecimal numbers, single-quoted strings, line continuations, trailing commas, and both comment forms.
Line comments end at CR, LF, U+2028, or U+2029.
Unescaped U+2028 and U+2029 inside strings are accepted.

Duplicate object keys are rejected, including equivalent escaped spellings.
Finite numeric literals that overflow or underflow binary64 are rejected.
Explicit ``Infinity`` and ``NaN`` are accepted.
Negative zero is preserved, including the integer spelling ``-0``.
UTF-16 surrogate pairs are combined; lone surrogates are retained for callers to apply their own Unicode policy.
Integers are arbitrary precision within the interpreter's decimal digit limit.
The nesting limit is 512 collections, enforced without recursive parsing.

``JSON5DecodeError`` provides ``reason``, ``msg``, ``doc``, ``pos``, ``lineno``, and ``colno``.
Positions refer to the original input, with one-based lines and columns and zero-based offsets.
Every JSON5 line terminator is recognized when reporting positions.

The document is a source snapshot.
``to_source()`` returns the original text; changing a returned Python collection does not edit that text.
Source editing and JSONC validation are outside this library's API.

Development
-----------

See `CONTRIBUTING.rst <CONTRIBUTING.rst>`_ for quality checks and the test corpus.
The project uses the MIT license.
