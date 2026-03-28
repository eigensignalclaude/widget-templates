#!/usr/bin/env python3
"""
inject_state.py — Inject JSON state into a file's BAKED_STATE region.

Works with both JSX (const BAKED_STATE) and HTML/JS (var BAKED_STATE).
Auto-detects the declaration keyword from the existing file content.

Usage:
    python inject_state.py <template_file> --json '{"a": "7", ...}'
    python inject_state.py <template_file> <json_file>
    python inject_state.py <template_file> --json '...' --out <output_file>
    python inject_state.py <template_file> --json '...' --stdout

If --out is given, writes to that path instead of modifying in-place.
If --stdout is given, prints the result to stdout (for piping to show_widget).
"""

import sys
import json
import re
import argparse

START_MARKER = "// __BAKED_STATE_START__"
END_MARKER = "// __BAKED_STATE_END__"


def inject_state(content: str, state: dict) -> str:
    """Replace BAKED_STATE in content string. Returns updated content."""
    # Auto-detect: var or const?
    keyword = "var"
    if "const BAKED_STATE" in content:
        keyword = "const"

    state_json = json.dumps(state, indent=2)
    replacement = (
        f"{START_MARKER}\n"
        f"{keyword} BAKED_STATE = {state_json};\n"
        f"{END_MARKER}"
    )

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )

    if not pattern.search(content):
        print(f"ERROR: markers not found in content", file=sys.stderr)
        sys.exit(1)

    return pattern.sub(replacement, content)


def main():
    parser = argparse.ArgumentParser(description="Inject state into BAKED_STATE region")
    parser.add_argument("template", help="Template file path")
    parser.add_argument("json_source", nargs="?", help="JSON file path (or use --json)")
    parser.add_argument("--json", dest="json_str", help="Inline JSON string")
    parser.add_argument("--out", help="Output file path (default: modify in-place)")
    parser.add_argument("--stdout", action="store_true", help="Print result to stdout")
    args = parser.parse_args()

    # Read template
    with open(args.template, "r") as f:
        content = f.read()

    # Read state
    if args.json_str:
        state = json.loads(args.json_str)
    elif args.json_source:
        with open(args.json_source, "r") as f:
            state = json.load(f)
    else:
        print("ERROR: provide a JSON file or --json", file=sys.stderr)
        sys.exit(1)

    # Inject
    updated = inject_state(content, state)

    # Output
    if args.stdout:
        print(updated, end="")
    elif args.out:
        with open(args.out, "w") as f:
            f.write(updated)
        print(f"OK: wrote to {args.out}", file=sys.stderr)
    else:
        with open(args.template, "w") as f:
            f.write(updated)
        print(f"OK: updated {args.template} in-place", file=sys.stderr)


if __name__ == "__main__":
    main()
