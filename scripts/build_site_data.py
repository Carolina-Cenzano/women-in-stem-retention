"""Wraps the analysis output into the JS file the dashboard loads.

The dashboard reads its data from a plain script file rather than fetch(), so it
works when opened straight from disk as well as when served over the web. Run
this after re-running prepare_data.py.
"""

import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main():
    src = os.path.join(ROOT, "output", "stem_aggregates.json")
    dest = os.path.join(ROOT, "data.js")
    with open(src) as f:
        payload = json.load(f)
    with open(dest, "w") as f:
        f.write("const STEM_DATA = ")
        json.dump(payload, f, separators=(",", ":"))
        f.write(";\n")
    print("wrote", dest)


if __name__ == "__main__":
    main()
