# chat-report-skeleton-example -- Claude Code plugin skeleton

**Status:** REFERENCE only. Not a production plugin.
**Origin:** Co-committed with `claudecode/PLUGIN-FORMAT-RESEARCH.md` as the B.2 deliverable of the chat-report sibling delegated session.
**Audience:** the optimus M5 (Claude Code Bundle + Installer) implementation, plus anyone learning the Claude Code plugin format.

## What this skeleton is

A minimum-viable Claude Code plugin demonstrating each component type. Every file is intentionally small -- the goal is "this is the SHAPE of every component" rather than "this is a useful plugin."

## File-by-file

| File | What it demonstrates |
|------|---------------------|
| `.claude-plugin/plugin.json` | The required manifest. Minimum fields: `name`. Recommended fields shown: `description`, `version`, `author`, `license`, `keywords`. |
| `commands/example.md` | A slash command (`/example [name]`). Demonstrates the YAML frontmatter (`description`, `argument-hint`, `allowed-tools`) and the prose body as prompt template. |
| `agents/example-reviewer.md` | A subagent definition. Demonstrates `name`, `description` (with `<example>` blocks shaping autonomous-selection), `model: inherit`, `color`, `tools` allowlist. |
| `skills/example-skill/SKILL.md` | A skill. Demonstrates the `skills/<name>/SKILL.md` directory pattern and the frontmatter shape. |
| `hooks/hooks.json` | A SessionStart hook config using `${CLAUDE_PLUGIN_ROOT}` for path portability and a `matcher` regex (`startup\|clear\|compact`). |
| `hooks/example-hook.sh` | The bash shell script the hook invokes. Emits the expected JSON-stdout protocol (`hookSpecificOutput.additionalContext`). |
| `.mcp.json` | An MCP server registration template. The referenced `mcp/example-server.js` file is NOT shipped -- production plugins provide their own server. |
| `README.md` | This file. |

## What this skeleton is NOT

- **Not a production plugin.** The hook does nothing useful; the command is prose-only; the agent's review is intentionally narrow; the MCP server file is absent.
- **Not the optimus Claude Code bundle.** Optimus M5's bundler generates a DIFFERENT plugin tree from optimus's IDE-agnostic `src/{hooks,agents,skills,rules,commands}/` source per AGENTS.md Founding Decision 6. This skeleton is the reference shape M5 produces against; it is not the bundle itself.
- **Not Cursor-compatible.** A multi-IDE plugin (like `superpowers`) would also ship `.cursor-plugin/plugin.json`, `.codex/`, `.opencode/`, `gemini-extension.json`, etc. Adding those is the job of the M4 bundler.

## How to install / try it

> **Status:** registration pattern, not a turnkey recipe. The steps below show every file you need to touch. You will likely also need to restart Claude Code for it to re-read the plugin index. The MCP-server portion will error on load because the skeleton's `.mcp.json` references `${CLAUDE_PLUGIN_ROOT}/mcp/example-server.js` which is intentionally NOT shipped (it's a template -- production plugins provide their own server).

### Step 1 -- Copy the skeleton into the plugins cache

**Windows (PowerShell):**

```powershell
$dest = "$env:USERPROFILE\.claude\plugins\cache\local\chat-report-skeleton-example\0.1.0"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item -Recurse -Force "$PSScriptRoot\*" $dest
```

**macOS / Linux:**

```bash
dest="$HOME/.claude/plugins/cache/local/chat-report-skeleton-example/0.1.0"
mkdir -p "$dest"
cp -r ./* "$dest/"
```

Note: the install path includes a `<marketplace-id>` segment (`local` here, since the skeleton is not published to a marketplace). The activation key in step 3 must match this segment exactly.

### Step 2 -- Register in `installed_plugins.json`

Edit `~/.claude/plugins/installed_plugins.json` (Windows: `%USERPROFILE%\.claude\plugins\installed_plugins.json`). Add this entry to the `plugins` object (alongside whatever other plugins are already registered):

```json
"chat-report-skeleton-example@local": [
  {
    "scope": "user",
    "installPath": "<absolute-path-from-step-1>",
    "version": "0.1.0",
    "installedAt": "2026-05-12T00:00:00.000Z",
    "lastUpdated": "2026-05-12T00:00:00.000Z"
  }
]
```

Replace `<absolute-path-from-step-1>` with the actual path written in step 1 (e.g., `C:\\Users\\me\\.claude\\plugins\\cache\\local\\chat-report-skeleton-example\\0.1.0` -- note the double backslashes for the JSON escape on Windows).

### Step 3 -- Enable in `~/.claude/settings.json`

Edit `~/.claude/settings.json`. Inside the `enabledPlugins` object, add:

```json
"chat-report-skeleton-example@local": true
```

### Step 4 -- Restart Claude Code

Quit and relaunch. On next session start, the SessionStart hook (`hooks/example-hook.sh`) fires and injects `additionalContext` into the session. The `/example` slash command becomes available. The `example-reviewer` agent becomes selectable. The `example-skill` skill is loadable via the Skill tool.

Expect an MCP load error for `example-mcp` -- this is the intentional missing-server gap mentioned above.

### Step 5 -- Uninstall

Reverse: remove the `enabledPlugins` entry (or set to `false`), remove the `installed_plugins.json` entry, delete the install directory. Restart Claude Code.

## Cross-references

- B.2 research report (where the format claims are evidenced): `../M5-plugin-format-research.md`
- B.1 chat-history store discovery (lives in the chat-report repo): <https://github.com/dtwaling/ai-chat-report/blob/master/claudecode/DISCOVERY.md>
- M5 Claude Code bundle (downstream consumer): `../../M5-claude-code-bundle.md`
- M5 task decomposition (skeleton-eligible at milestone-load time): `../../M5-tasks.md`
