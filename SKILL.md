# AI-Controlled Widget Skill

## Overview

This skill enables an outer Claude agent to share control of an interactive widget with the user. The user interacts with the widget directly, and when they want AI help, they click "Send to Claude" which relays the widget's state to the chat. The agent modifies the state and renders an updated widget.

**Key insight**: The widget template lives on GitHub and is fetched via CDN. The agent only emits a tiny loader (~20 lines) with the updated state JSON. This scales to arbitrarily large widgets without burning context.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  GitHub repo (eigensignalclaude/widget-templates)       │
│  └── my_widget.html  (template with BAKED_STATE)        │
└──────────────────────┬──────────────────────────────────┘
                       │ cached via jsdelivr CDN
                       ▼
┌─────────────────────────────────────────────────────────┐
│  show_widget loader (~20 lines)                         │
│  1. Defines INJECTED_STATE = { ... }                    │
│  2. Fetches template from CDN                           │
│  3. Replaces BAKED_STATE region via regex                │
│  4. Injects HTML + re-executes scripts                  │
│  5. sendPrompt() available for user→agent communication │
└──────────────────────┬──────────────────────────────────┘
                       │ user clicks "Send to Claude"
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Outer Claude agent                                     │
│  1. Reads state JSON from chat message                  │
│  2. Modifies state as needed                            │
│  3. Renders new loader with updated INJECTED_STATE      │
└─────────────────────────────────────────────────────────┘
```

## Step 1: Create the Widget Template

Create an HTML file with a clearly marked `BAKED_STATE` region. This is the only part that changes between renders.

```html
<div id="app">
  <!-- Your widget UI here -->
  <button onclick="doSendToClaude()">Send to Claude ↗</button>
</div>

<script>
// __BAKED_STATE_START__
var BAKED_STATE = {"key": "default_value"};
// __BAKED_STATE_END__

var state = JSON.parse(JSON.stringify(BAKED_STATE));

function render() {
  // Update DOM from state
}

function readInputs() {
  // Sync DOM inputs back into state
}

function doSendToClaude() {
  readInputs();
  var msg = document.getElementById('claude-msg').value.trim();
  var payload = '[Widget State]:\n```json\n'
    + JSON.stringify(state, null, 2)
    + '\n```\n\n'
    + (msg ? 'User: ' + msg : 'User: (just sending current state)');
  if (typeof sendPrompt === 'function') {
    sendPrompt(payload);
  } else {
    alert('sendPrompt not available in this context.');
  }
}

render();
</script>
```

### Rules for the template:

- Use `var` (not `const`/`let`) for BAKED_STATE — the regex replacement must work reliably.
- The `// __BAKED_STATE_START__` and `// __BAKED_STATE_END__` markers must appear exactly as shown, on their own lines. Do not move or reformat them.
- BAKED_STATE must be valid JSON assigned on a single conceptual statement (the inject script writes it as formatted JSON, which is fine).
- The template must be self-contained HTML (no JSX, no imports). It runs inside the Visualizer's iframe sandbox.
- Use Visualizer CSS variables for theming (`var(--color-text-primary)`, `var(--color-background-primary)`, etc.) so the widget looks native in both light and dark mode.
- `sendPrompt(text)` is a global function available in the Visualizer context. It sends a message to the chat as if the user typed it.
- Do NOT use `localStorage`, `sessionStorage`, or any browser storage APIs — they are blocked in the sandbox.
- External scripts can only be loaded from: `cdnjs.cloudflare.com`, `esm.sh`, `cdn.jsdelivr.net`, `unpkg.com`.

## Step 2: Push Template to GitHub

Upload the template to the `eigensignalclaude/widget-templates` repo using the GitHub Contents API:

```bash
TOKEN="<github_pat>"
REPO="eigensignalclaude/widget-templates"
FILE="my_widget.html"

CONTENT=$(base64 -w0 "$FILE")
curl -s -X PUT "https://api.github.com/repos/$REPO/contents/$FILE" \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Add $FILE\",\"content\":\"$CONTENT\"}"
```

To update an existing file, you must include the `sha` of the current version:

```bash
SHA=$(curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/$REPO/contents/$FILE" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['sha'])")

CONTENT=$(base64 -w0 "$FILE")
curl -s -X PUT "https://api.github.com/repos/$REPO/contents/$FILE" \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Update $FILE\",\"content\":\"$CONTENT\",\"sha\":\"$SHA\"}"
```

The GitHub PAT should be uploaded by the user as a file — do not ask them to paste it in chat. The token needs **Contents: Read and write** permission on the repo.

The file is then available at:
```
https://cdn.jsdelivr.net/gh/eigensignalclaude/widget-templates@main/my_widget.html
```

Note: jsdelivr caches aggressively. Template changes may take a few minutes to propagate. This is fine because the template rarely changes — state injection happens client-side in the loader.

## Step 3: Render the Loader

When the agent needs to display the widget (initial render or state update), use `show_widget` with this loader pattern:

```javascript
// The only part that changes per render:
var INJECTED_STATE = {"key": "new_value", ...};

var logEl = document.getElementById('loader-log');
logEl.textContent = 'Loading...';

fetch('https://cdn.jsdelivr.net/gh/eigensignalclaude/widget-templates@main/my_widget.html')
  .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
  .then(function(html) {
    var stateJson = JSON.stringify(INJECTED_STATE);
    html = html.replace(
      /\/\/ __BAKED_STATE_START__[\s\S]*?\/\/ __BAKED_STATE_END__/,
      '// __BAKED_STATE_START__\nvar BAKED_STATE = ' + stateJson + ';\n// __BAKED_STATE_END__'
    );
    var container = document.getElementById('widget-container');
    container.innerHTML = html;
    container.querySelectorAll('script').forEach(function(old) {
      var ns = document.createElement('script');
      ns.textContent = old.textContent;
      old.parentNode.replaceChild(ns, old);
    });
    logEl.style.display = 'none';
  })
  .catch(function(e) { logEl.textContent = 'Load failed: ' + e.message; });
```

Wrap this in a minimal HTML shell for `show_widget`:

```html
<div id="loader-log" style="font-family: var(--font-mono); font-size: 11px; color: var(--color-text-tertiary); padding: 1rem 0;"></div>
<div id="widget-container"></div>
<script>
// ... loader code above ...
</script>
```

The loader is ~20 lines. Only `INJECTED_STATE` changes between renders. The full widget template is fetched from CDN cache.

## Step 4: Handle Incoming State

When the user clicks "Send to Claude", a message appears in chat like:

```
[Widget State]:
\```json
{
  "a": "6",
  "b": "7",
  "operator": "*",
  "result": 42,
  "history": [...]
}
\```

User: Make the result odd.
```

The agent should:
1. Parse the state JSON from the message
2. Read the user's request
3. Modify the state as needed
4. Render a new loader with the updated `INJECTED_STATE`

## inject_state.py (for file artifact workflow)

For large apps that don't fit in the Visualizer, there is also a file-based workflow using `inject_state.py`. This script replaces the BAKED_STATE region in any file (HTML or JSX) with new JSON:

```bash
python inject_state.py template.html --json '{"key": "value"}' --out output.html
python inject_state.py template.html state.json                # modifies in-place
python inject_state.py template.html --json '...' --stdout     # prints to stdout
```

The file artifact workflow trades `sendPrompt` (user must copy-paste state) for zero context burn on arbitrarily large apps.

## Known Limitations

- **jsdelivr caching**: Template updates take minutes to propagate. Only update templates for structural changes, not state changes (state injection is client-side).
- **sendPrompt only works in Visualizer**: `show_widget` has the parent-frame channel connected. File artifacts (`present_files`) do not — `window.claude.sendConversationMessage` exists but its internal channel is null.
- **Sandbox CSP**: External fetches only work from `cdnjs.cloudflare.com`, `esm.sh`, `cdn.jsdelivr.net`, `unpkg.com`. All other origins are blocked.
- **No localStorage/sessionStorage**: Blocked in the sandbox. Use React state or JS variables for in-session data.
- **XMLHttpRequest is CORS-blocked**: Only `fetch` works in the sandbox.
- **Proxy hangs**: The artifact API proxy (`api.anthropic.com` from inside artifacts) occasionally hangs indefinitely. This does not affect the CDN loader pattern since it doesn't make API calls from inside the widget.
- **Script re-execution after innerHTML**: Scripts inserted via `innerHTML` don't auto-execute. The loader must clone each `<script>` element into a new one to trigger execution.

## Choosing the Right Pattern

| Factor | CDN Loader (Visualizer) | File Artifact |
|---|---|---|
| `sendPrompt` works | Yes | No (user copy-pastes) |
| Context burn per turn | ~20 lines + state JSON | Zero (just present_files) |
| Widget size limit | Unlimited (CDN-hosted) | Unlimited (file-based) |
| Requires GitHub | Yes | No |
| Best for | Interactive AI-controlled apps | Very large apps, or when GitHub unavailable |

## Reference Implementation

- Template: `eigensignalclaude/widget-templates/calculator_widget.html`
- Inject script: `eigensignalclaude/widget-templates/inject_state.py`
