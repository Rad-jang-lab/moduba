import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MPLBACKEND", "Agg")

try:
    import matplotlib
    matplotlib.use("Agg", force=True)
except ModuleNotFoundError:
    matplotlib_stub = types.ModuleType("matplotlib")
    pyplot_stub = types.ModuleType("matplotlib.pyplot")
    ticker_stub = types.ModuleType("matplotlib.ticker")

    def _noop(*_args, **_kwargs):
        return None

    class _MaxNLocator:
        def __init__(self, *_args, **_kwargs):
            pass

    pyplot_stub.figure = _noop
    pyplot_stub.plot = _noop
    pyplot_stub.xlabel = _noop
    pyplot_stub.ylabel = _noop
    pyplot_stub.title = _noop
    pyplot_stub.tight_layout = _noop
    pyplot_stub.show = _noop
    pyplot_stub.subplots = lambda *_args, **_kwargs: (None, None)

    ticker_stub.MaxNLocator = _MaxNLocator
    matplotlib_stub.pyplot = pyplot_stub
    matplotlib_stub.ticker = ticker_stub

    sys.modules["matplotlib"] = matplotlib_stub
    sys.modules["matplotlib.pyplot"] = pyplot_stub
    sys.modules["matplotlib.ticker"] = ticker_stub

import pytest
from tkinter import messagebox


@pytest.fixture(autouse=True)
def _suppress_messagebox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(messagebox, "showwarning", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(messagebox, "askokcancel", lambda *args, **kwargs: True)
