"""Erlaubt `python -m materialswiki` als Kurzform von `python -m materialswiki.cli`."""
from .cli import main

raise SystemExit(main())
