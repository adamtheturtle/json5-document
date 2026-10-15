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

    """Parse JSON5 while preserving source comments."""

    import json5_document

    source = "// heading\n{count: 2,}"
    document = json5_document.parse(source=source)
    assert document.value == {"count": 2}
    assert document.comments[0].text == "// heading"
    assert document.to_source() == source

Use ``loads(source=...)`` when only Python values are needed.
See the `documentation <https://adamtheturtle.github.io/json5-document/>`_ for the full API and parsing policies.
