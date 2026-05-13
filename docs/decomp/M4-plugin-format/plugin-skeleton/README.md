# cursor-plugin-skeleton-example -- Cursor plugin skeleton

**Status:** REFERENCE only. Not a production plugin.
**Origin:** Co-committed with `M4-plugin-format-research.md` as the M4 prerequisite plugin-format research deliverable. Cursor analog of `docs/decomp/M5-plugin-format/plugin-skeleton/`.
**Audience:** the optimus M4 (Cursor Bundle + Installer) implementation, plus anyone learning the Cursor plugin format.

## What this skeleton is

A minimum-viable Cursor plugin demonstrating each component type. Every file is intentionally small -- the goal is "this is the SHAPE of every component" rather than "this is a useful plugin."

## File-by-file

| File | What it demonstrates |
|------|---------------------|
| `.cursor-plugin/plugin.json` | The required manifest. Minimum field: `name`. Recommended fields shown: `displayName`, `description`, `version`, `author`, `license`, `keywords`. **CRITICAL:** the four explicit surface-pointer fields (`skills`, `agents`, `commands`, `hooks`) -- Cursor does NOT auto-discover; the manifest MUST point at the directories. |
| `commands/example.md` | A slash command (`/example [name]`). Demonstrates the YAML frontmatter (`description`) and the prose body as prompt template with `$ARGUMENTS` placeholder. |
| `agents/example-reviewer.md` | A subagent definition. Demonstrates the Cursor-specific minimal frontmatter (`name`, `description` only) -- NO `model`, `color`, or `tools` fields (those are Claude-Code-only). |
| `skills/example-skill/SKILL.md` | A skill with **explicit `disable-model-invocation: false`** to demonstrate the auto-invocation pattern (Cursor's default is `true`). |
| `hooks/hooks-cursor.json` | A `sessionStart` hook config. Demonstrates `version: 1` schema root, camelCase event names, flat hook config (no `matcher.hooks[]` nesting like Claude Code), `failClosed` field. Uses relative path (no `${CLAUDE_PLUGIN_ROOT}` analog in Cursor). |
| `hooks/example-hook.sh` | The bash shell script the hook invokes. Emits the expected JSON-stdout protocol (`hookSpecificOutput.additionalContext`) -- convergent with Claude Code's hook protocol on this point. |
| `cursor-rules-templates/example-rule.mdc` | A rule template demonstrating the Cursor `.mdc` format with `description`, `globs`, `alwaysApply` frontmatter. Shipped in the plugin but installer-copied into project-scope `.cursor/rules/`. |
| `README.md` | This file. |

## What this skeleton is NOT

- **Not a production plugin.** The hook does nothing useful; the command is prose-only; the subagent's review is intentionally narrow; the rule is reference-only; no MCP server is shipped at plugin scope.
- **Not the optimus Cursor bundle.** M4's bundler generates a DIFFERENT plugin tree from optimus's IDE-agnostic `src/{hooks,agents,skills,rules,commands}/` source per AGENTS.md Founding Decision 6. This skeleton is the reference shape M4 produces against; it is not the bundle itself.
- **Not Claude-Code-compatible.** A multi-IDE plugin (like `superpowers/b7a8f76`) would also ship `.claude-plugin/plugin.json`, `.codex/`, `.opencode/`, `gemini-extension.json`, etc., AND a parallel `hooks/hooks.json` with PascalCase events. Adding those is the job of the M5 bundler.
- **Not a VS Code extension.** Cursor extensions live at `~/.cursor/extensions/` and use the VS Code extension format. Cursor plugins live at `~/.cursor/plugins/` (a separate surface) and use this format. M4's installer must NOT install into `~/.cursor/extensions/`.

## How to install / try it

> **Status:** registration pattern, not a turnkey recipe. The steps below show the files you need to touch. You will likely also need to restart Cursor for it to re-read the plugin cache. Cursor does NOT have an `installed_plugins.json` analog or an `enabledPlugins` settings.json block -- discovery is scan-based via the `.cache-complete` marker at each `<install-dir>/` root.

### Step 1 -- Copy the skeleton into the Cursor plugins cache

The Cursor install path pattern is `~/.cursor/plugins/cache/<marketplace-id>/<plugin-name>/<commit-sha-or-version>/`. For local/non-marketplace installs, use a marketplace ID like `local` or `optimus-bundles`.

**Windows (PowerShell):**

```powershell
$dest = "$env:USERPROFILE\.cursor\plugins\cache\local\cursor-plugin-skeleton-example\0.1.0"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item -Recurse -Force "$PSScriptRoot\*" $dest
New-Item -ItemType File -Path "$dest\.cache-complete" -Force | Out-Null
```

**macOS / Linux:**

```bash
dest="$HOME/.cursor/plugins/cache/local/cursor-plugin-skeleton-example/0.1.0"
mkdir -p "$dest"
cp -r ./* "$dest/"
touch "$dest/.cache-complete"
```

Note: the `.cache-complete` marker file (zero bytes) signals to Cursor that the install succeeded. Without it, Cursor may skip the plugin during scan.

### Step 2 -- (Cursor does NOT have a separate registration step)

Unlike Claude Code's `installed_plugins.json` + `enabledPlugins` ceremony, Cursor discovers plugins by scanning `~/.cursor/plugins/cache/` directly. Once the `.cache-complete` marker exists, the plugin is discoverable on next Cursor restart.

### Step 3 -- Restart Cursor

Quit and relaunch. On next session start, the `sessionStart` hook (`hooks/example-hook.sh`) fires and injects `additionalContext` into the session. The `/example` slash command becomes available. The `example-reviewer` subagent becomes selectable. The `example-skill` skill is loadable.

The bundled `cursor-rules-templates/example-rule.mdc` is NOT auto-loaded -- rules require step 4.

### Step 4 -- (Optional) Install the rule template into a project

Cursor rules only load from project-scope `<project>/.cursor/rules/`. To activate the example rule for a specific project:

**Windows (PowerShell):**

```powershell
$src = "$env:USERPROFILE\.cursor\plugins\cache\local\cursor-plugin-skeleton-example\0.1.0\cursor-rules-templates\example-rule.mdc"
$dest = "<project-root>\.cursor\rules\example-rule.mdc"
New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
Copy-Item -Force $src $dest
```

**macOS / Linux:**

```bash
src="$HOME/.cursor/plugins/cache/local/cursor-plugin-skeleton-example/0.1.0/cursor-rules-templates/example-rule.mdc"
dest="<project-root>/.cursor/rules/example-rule.mdc"
mkdir -p "$(dirname "$dest")"
cp "$src" "$dest"
```

This is the manual analog of the M4 host-side installer's `optimus init <project>` step.

### Step 5 -- (Optional) Demonstrate user-scope MCP merge

The skeleton does NOT ship a plugin-scope `.mcp.json` (plugin-scope MCP registration in Cursor is TBD per the research report's risk #2). Production optimus M4 installer will instead merge into `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "optimus": {
      "command": "<absolute-path-to-optimus-CLI-shim>",
      "args": ["mcp"]
    }
  }
}
```

Merge logic: if `~/.cursor/mcp.json` already exists, parse it, add the `optimus` key under `mcpServers`, write back. If `~/.cursor/mcp.json` doesn't exist, create it with the above content. Last-writer-wins on key collisions -- warn the user on `optimus` collision.

### Step 6 -- Uninstall

Reverse: delete the install directory (`~/.cursor/plugins/cache/local/cursor-plugin-skeleton-example/0.1.0/`). Optional: remove the rule from each project's `.cursor/rules/example-rule.mdc`. Optional: remove the `optimus` entry from `~/.cursor/mcp.json`. Restart Cursor.

## Cross-references

- M4 plugin-format research (the canonical decision record for the claims here): `../M4-plugin-format-research.md`
- M5 plugin-format research (Claude Code analog): `../../M5-plugin-format/M5-plugin-format-research.md`
- M5 plugin skeleton (Claude Code analog for direct comparison): `../../M5-plugin-format/plugin-skeleton/`
- M4 Cursor bundle (downstream consumer): `../../M4-cursor-bundle.md`
- M4 task decomposition (skeleton-eligible at milestone-load time): `../../M4-tasks.md`
