#!/usr/bin/env python3
"""Execute notebooks from a fresh kernel, the way a learner would.

Usage:
    python tools/run_notebooks.py [--save] [--allow-errors] nb1.ipynb nb2.ipynb ...

--save          write the fresh outputs back into the notebook (only if it passed)
--allow-errors  keep going after an error (for exercise notebooks, whose blanks fail)

During the run only, input() is replaced by a fake keyboard that answers
12, 7, 0, 1, 2, 3, 4, 5, 6, 8, 9 in turn (and echoes "prompt + answer"), so notebooks
that ask the user for values do not block. Plotly figures are saved as JSON. The
injected setup cell is removed before saving, and outputs containing email
addresses are never saved (privacy). Exit code 1 if any notebook fails.

Needs: nbclient, nbformat, ipykernel (pip install nbclient nbformat ipykernel).
"""
import json
import re
import sys
import time

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

SETUP = nbformat.v4.new_code_cell(
    "import builtins, itertools\n"
    "_sb_answers = itertools.cycle(['12', '7', '0', '1', '2', '3', '4', '5', '6', '8', '9'])\n"
    "def _sb_input(prompt=''):\n"
    "    v = next(_sb_answers); print(f'{prompt}{v}'); return v\n"
    "builtins.input = _sb_input\n"
    "input = _sb_input\n"
    "try:\n"
    "    import plotly.io as _pio; _pio.renderers.default = 'plotly_mimetype'\n"
    "except ImportError:\n"
    "    pass\n"
    "import matplotlib; matplotlib.use('module://matplotlib_inline.backend_inline')\n")


# Outputs that contain email addresses are never saved (privacy): the code stays, the output is cleared.
EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@(?!example\.com)[A-Za-z0-9.-]+\.[a-z]{2,}")
# Lines that only describe the machine that ran the notebook (XGBoost looking for a GPU...)
NOISE = re.compile(r"nvidia-smi: not found")


def run(path, save, allow):
    nb = nbformat.read(path, as_version=4)
    nb.cells.insert(0, SETUP)
    client = NotebookClient(nb, timeout=300, kernel_name="python3", allow_errors=allow,
                            resources={"metadata": {"path": path.rsplit("/", 1)[0] if "/" in path else "."}})
    ok = True
    try:
        client.execute()
        errors = [(i - 1, o.get("ename"), o.get("evalue", "")[:120])
                  for i, c in enumerate(nb.cells) if c.cell_type == "code"
                  for o in c.get("outputs", []) if o.get("output_type") == "error"]
        status = "OK" if not errors else f"{len(errors)} errors: {errors[:3]}"
        ok = not errors or allow
    except CellExecutionError as e:
        status = "FAIL: " + str(e).strip().splitlines()[-1][:200]
        ok = False
    nb.cells.pop(0)
    for c in nb.cells:
        if c.cell_type == "code":
            c.execution_count = None
            for o in c.get("outputs", []):
                if "execution_count" in o:
                    o["execution_count"] = None
                if o.get("output_type") == "stream":  # noise from the machine that ran the notebook
                    o["text"] = "".join(l for l in o["text"].splitlines(True) if not NOISE.search(l))
            c.outputs = [o for o in c.get("outputs", []) if o.get("output_type") != "stream" or o["text"]]
    if save and ok and status == "OK":
        cleared = 0
        for c in nb.cells:
            if c.cell_type == "code" and any(EMAIL.search(json.dumps(o)) for o in c.get("outputs", [])):
                c.outputs = []
                cleared += 1
        if cleared:
            status += f" (outputs with email addresses not saved: {cleared} cells)"
        nbformat.write(nb, path)
    return ok, status


def main():
    args = sys.argv[1:]
    save, allow = "--save" in args, "--allow-errors" in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        sys.exit(__doc__)
    failed = 0
    for p in paths:
        t = time.time()
        ok, status = run(p, save, allow)
        failed += not ok
        print(f"{time.time() - t:5.1f}s  {status[:150]:150}  {p}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
