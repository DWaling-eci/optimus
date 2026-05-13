# Claude Code Plugin Format -- Research Report

**Status:** B.2 deliverable for the chat-report sibling delegated session.
**Feasibility gate verdict:** **POSITIVE** -- the plugin format is officially documented + empirically confirmed across 10 installed plugins, and every `src/{hooks,agents,skills,rules}/` surface from optimus's AGENTS.md maps cleanly to a Claude Code plugin component.
**Authored:** 2026-05-12
**Claude Code version observed (this session):** `2.1.140`
**Observation method:** invoked the official `plugin-dev:plugin-structure` skill on this machine for the canonical spec (which IS the source -- Anthropic-authored, version-tracked), then cross-verified against 10 real plugins installed in `~/.claude/plugins/cache/claude-plugins-official/` (including `superpowers`, `plugin-dev`, `hookify`, `huggingface-skills`, `agent-sdk-dev`, `mcp-server-dev`, `code-modernization`, `github`, `rust-analyzer-lsp`, `semgrep`).

This report is the chat-report sibling project's load-bearing input for downstream consumers:
- **M5 -- Claude Code Bundle + Installer** (`docs/decomp/M5-tasks.md`, `docs/decomp/M5-claude-code-bundle.md`) explicitly says: "Plugin format research is covered by the chat-report sibling delegated session... M5 consumes the findings; M5 does not duplicate the research." This report IS that handoff.
- **CHARTER Founding Decision 8** (minimum-supported-IDE-version model) consumes the Q5 version pin.
- **AGENTS.md Founding Decision 6** (IDE-agnostic `src/{hooks,agents,skills,rules}/` source surface) consumes the Q7 mapping.

---

## Q4 -- What is the format spec source?

**Spec source: Anthropic-authored, multi-modal.**

1. **In-product source (canonical, version-tracked with Claude Code itself):** the `plugin-dev` plugin (`plugin-dev@claude-plugins-official`), authored by Anthropic (`"author": {"name": "Anthropic", "email": "support@anthropic.com"}` per its `plugin.json`). Specifically the `plugin-dev:plugin-structure` skill, accessible from any Claude Code session via the Skill tool. This skill defines the directory layout, manifest schema, component formats, and `${CLAUDE_PLUGIN_ROOT}` path-portability convention. The skill is the canonical, version-current source -- when the format evolves, this skill is the truth.

2. **Public documentation (the `code.claude.com` documentation site):** verified during B.1 cross-OS research for the `.claude/` directory + env-var pages (`<https://code.claude.com/docs/en/sessions>`, `<https://code.claude.com/docs/en/claude-directory>`, `<https://code.claude.com/docs/en/env-vars>`, `<https://code.claude.com/docs/en/settings>`). The site also carries plugin-specific pages; this report did NOT empirically WebFetch a plugin-specific page, so for any current-version specifics the in-product `plugin-dev:plugin-structure` skill is the canonical source. M5 should cite specific public-docs URLs as it builds against them and verify each page is live at that time.

3. **Empirical reference implementations (10 plugins in `~/.claude/plugins/cache/claude-plugins-official/`):**
   - `plugin-dev` (Anthropic): the format-authoring plugin itself; **reference implementation by definition**
   - `superpowers` (Jesse Vincent / `obra/superpowers`): the most full-featured non-Anthropic plugin observed; ships cross-IDE variants (Claude Code, Cursor, Codex, OpenCode, Gemini) which makes it the reference for the cross-IDE-source pattern optimus M4/M5 also adopt
   - `hookify`, `huggingface-skills`, `mcp-server-dev`, `agent-sdk-dev`, `code-modernization` (Anthropic + community): additional working examples

**Optimus does not need to reverse-engineer.** The format is documented and Anthropic-supported. M5 builds against the spec, not against guesses.

### Q4 verdict: POSITIVE.

Format spec source is in-product (canonical) + documented (citable) + empirically-confirmable (10 working examples). The brief's contingency ("if undocumented, the empirical contract reverse-engineered from existing plugins") is moot.

---

## Q5 -- Which Claude Code version is the format pinned against?

**Headline answer: Claude Code provides NO format version-pin mechanism. Plugins are version-implicit. M5 must enforce a minimum-IDE-version floor externally.**

Specifically:
- The `.claude-plugin/plugin.json` manifest has NO `claude_code_min_version` or equivalent compatibility field. Real plugins (`superpowers/5.1.0`, `plugin-dev/unknown`, etc.) ship zero version-compatibility metadata.
- `installed_plugins.json` records the plugin's own `version` and `installedAt` timestamp but does NOT record the Claude Code version it was installed against.
- Activation in `~/.claude/settings.json`'s `enabledPlugins` is a simple boolean -- no compatibility negotiation.

The compatibility model is implicit: if Claude Code's plugin loader can parse the manifest and load the components, the plugin works. There is no handshake, no version-skew check, no compatibility manifest field.

**Empirically observed format version on this machine: `2.1.140`.** Components verified at this version:

- `.claude-plugin/plugin.json` manifest schema (`name` required; `description`, `version`, `author`, `homepage`, `repository`, `license`, `keywords` optional).
- `hooks/hooks.json` with the `hooks.<EventName>[].matcher` + `hooks.<EventName>[].hooks[]` shape (verified byte-for-byte against `superpowers/5.1.0/hooks/hooks.json`).
- Agent `.md` files with YAML frontmatter (`name`, `description`, `model`, `color`, `tools`).
- Command `.md` files with YAML frontmatter (`description`, `argument-hint`, `allowed-tools`).
- Skill directories with `SKILL.md` containing YAML frontmatter (`name`, `description`, `version`).
- `${CLAUDE_PLUGIN_ROOT}` env-var pattern.

**Implication for optimus M5 (per CHARTER Founding Decision 8):** since Claude Code does NOT enforce minimum-IDE-version itself, the optimus M5 installer MUST enforce it externally -- before installing the bundle, probe the running Claude Code version (via `claude --version` or equivalent) and refuse the install if below the optimus-declared floor. The floor itself (M5's choice) should be a specific 2.1.x patch covering the event surfaces optimus's hooks rely on. For this report's reference skeleton, we tested against 2.1.140; that's the empirically-confirmed floor for the skeleton's components.

**Format stability across recent Claude Code versions:** the B.1 cross-version probe (sessions on 2.1.140 and 2.1.128) showed additive-only schema evolution in the chat-history JSONL store. The plugin format is NOT directly tested for cross-version stability in this report -- a 2.1.128-installed plugin loading on a 2.1.140 host would be the direct test, but I have no orthogonal version pair on the machine. The B.1 evidence is suggestive (additive evolution discipline applied to one Claude Code subsystem likely applies to others), not proof.

### Q5 verdict: POSITIVE.

The question is now sharply answered (no version-pin mechanism; M5 enforces externally). The cross-version-stability sub-question is correctly characterized as inferred-not-proven; this is a risk for M5's installer to budget for, not a gate-blocker for B.2.

---

## Q6 -- Plugin install location per supported OS?

**Per-OS root directory:**

| OS | Plugin root | Empirical status |
|----|-------------|------------------|
| Windows | `%USERPROFILE%\.claude\plugins\` | Verified on this machine |
| macOS | `~/.claude/plugins/` | Inferred from POSIX convention + the `plugin-dev:plugin-structure` skill's `~/.claude/` references; NOT empirically tested on a macOS host |
| Linux | `~/.claude/plugins/` | Same as macOS -- inferred, not empirically tested |

**Override:** `CLAUDE_CONFIG_DIR` env var. If set, `~/.claude/` is replaced by `${CLAUDE_CONFIG_DIR}/` (per the public-docs B.1 lookup at `<https://code.claude.com/docs/en/env-vars>`; not independently probed in this report by setting + verifying). M5's installer MUST honor this; the bundle's install probe MUST NOT hardcode `~/.claude/`.

**Plugin root structure (empirically verified on Windows):**

```
~/.claude/plugins/
  installed_plugins.json     -- index of installed plugins (schema below)
  known_marketplaces.json    -- registered marketplaces
  blocklist.json             -- plugin blocklist (Anthropic-managed?)
  install-counts-cache.json  -- usage stats cache
  marketplaces/
    <marketplace-id>/        -- per-marketplace cached manifest
  cache/
    <marketplace-id>/
      <plugin-name>/
        <version>/           -- the actual plugin source tree lives here
          .claude-plugin/plugin.json
          commands/...
          agents/...
          skills/...
          hooks/hooks.json
          .mcp.json
          .in_use/<pid>      -- per-process liveness pin
  data/
    ...                      -- runtime data
```

**Install path resolution (from `installed_plugins.json`):**

```json
{
  "version": 2,
  "plugins": {
    "<plugin-name>@<marketplace-id>": [
      {
        "scope": "user",
        "installPath": "<absolute-path-to-plugin-version-dir>",
        "version": "1.0.0" | "unknown",
        "installedAt": "<ISO 8601>",
        "lastUpdated": "<ISO 8601>",
        "gitCommitSha": "<sha>"
      }
    ]
  }
}
```

The plugins array allows multiple installs of the same plugin (different versions or different scopes -- empirically all observed entries are `scope: "user"`, but the schema clearly supports per-project scopes too).

**Activation (in `~/.claude/settings.json`):**

```json
{
  "enabledPlugins": {
    "superpowers@claude-plugins-official": true,
    "plugin-dev@claude-plugins-official": true,
    ...
  }
}
```

Activation key format: `<plugin-name>@<marketplace-id>`. Same key as `installed_plugins.json`. Disabling without uninstall: set to `false` or remove the key.

**Per-process liveness pins (`.in_use/<pid>`):** each plugin's install dir contains `.in_use/<pid>` empty files keyed by Claude Code OS process IDs currently using the plugin. Matches the PID pattern observed in B.1 at `~/.claude/sessions/<pid>.json`. The chat-report tool doesn't need this; M5's installer probably doesn't either, except to know whether a plugin can be safely uninstalled without disrupting a running session.

### Q6 verdict: POSITIVE.

Install location is stable, well-documented, env-var-overridable, and structurally identical across OSes.

---

## Q7 -- Event/hook/tool surfaces + mapping to optimus's IDE-agnostic source

Claude Code plugins expose **five distinct component types**. Each maps to one of optimus's IDE-agnostic source directories from AGENTS.md / Founding Decision 6, with one source-side gap that optimus M5 must resolve.

### 7.1 Slash commands (`commands/`)

**Plugin layout:** `commands/<name>.md`, one Markdown file per command, kebab-case filename. Auto-discovered.

**File format (empirical example from `plugin-dev/commands/create-plugin.md`):**

```markdown
---
description: Guided end-to-end plugin creation workflow with component design, implementation, and validation
argument-hint: Optional plugin description
allowed-tools:
  ["Read", "Write", "Grep", "Glob", "Bash", "TodoWrite", "AskUserQuestion", "Skill", "Task"]
---

# Command body in Markdown -- becomes the slash-command's prompt template.
# Use $ARGUMENTS as placeholder for user-supplied args.
```

**Optimus source mapping:** **NO direct optimus source surface today**. AGENTS.md Founding Decision 6 names `src/{hooks,agents,skills,rules}/` -- slash commands aren't enumerated. **Action for M5:** add `src/commands/` to the IDE-agnostic surface; bundler emits `commands/<name>.md` for the Claude Code bundle. Cursor's equivalent (slash-command surface) lives elsewhere and is the Cursor bundler's concern.

### 7.2 Subagents (`agents/`)

**Plugin layout:** `agents/<agent-id>.md`, one Markdown file per agent. Auto-discovered.

**File format (empirical example from `plugin-dev/agents/plugin-validator.md`):**

```markdown
---
name: plugin-validator
description: |
  Use this agent when the user asks to "validate my plugin", "check plugin structure", ...
  <example>
  Context: User finished creating a new plugin
  user: "I've created my first plugin with commands and hooks"
  assistant: "I'll use the plugin-validator agent to check the plugin."
  </example>
  ...
model: inherit
color: yellow
tools: ["Read", "Grep", "Glob", "Bash"]
---

You are an expert plugin validator specializing in ...
```

**Frontmatter fields:** `name` (required), `description` (required; the description shapes when Claude Code autonomously selects the agent), `model` (`inherit` or explicit ID), `color` (UI hint), `tools` (allowlist).

**Optimus source mapping:** `src/agents/` (AGENTS.md FD6). 1:1 file shape. The Claude Code bundler copies `src/agents/<name>.md` -> `<bundle>/agents/<name>.md` verbatim (with possible IDE-specific frontmatter transformation; the Cursor bundler may need to remap `model: inherit` / `color`).

### 7.3 Skills (`skills/`)

**Plugin layout:** `skills/<skill-name>/SKILL.md`, one subdirectory per skill, each containing a `SKILL.md` plus optional supporting files (scripts, references, examples).

**File format (`SKILL.md` frontmatter):**

```markdown
---
name: skill-name
description: When to use this skill -- triggers + scenarios
version: 1.0.0
---

Skill body in Markdown. Loaded into context when the Skill tool invokes this skill by name.
```

**Skills as autonomous activation surface:** unlike commands (user-triggered) and agents (Claude-Code-selected with description-based heuristics), skills are loaded on-demand via the Skill tool. They become the agent's working knowledge.

**Optimus source mapping:** `src/skills/` (AGENTS.md FD6). 1:1 shape. The Claude Code bundler copies `src/skills/<name>/` -> `<bundle>/skills/<name>/` verbatim. Supporting-file subdirectories (scripts/, references/, examples/) are preserved.

### 7.4 Hooks (`hooks/hooks.json`)

**Plugin layout:** `hooks/hooks.json` + supporting scripts (typically `hooks/<script-name>` or `hooks/scripts/<name>.sh`). NOT auto-discovered as `.md`; the JSON config IS the authoritative registration.

**File format (real example from `superpowers/5.1.0/hooks/hooks.json`):**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" session-start",
            "async": false
          }
        ]
      }
    ]
  }
}
```

**Event surface (full enumeration per the spec):** `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `SessionStart`, `SessionEnd`, `UserPromptSubmit`, `PreCompact`, `Notification`.

**Per-hook config:** `matcher` is a regex matched against the event subtype (e.g., `SessionStart` has subtypes `startup`, `clear`, `compact`). `hooks[]` is an ordered list of handlers, each with `type: "command"` (currently the only documented type) + `command` (the shell command) + `async`/`timeout` (lifecycle controls).

**`${CLAUDE_PLUGIN_ROOT}` is the portable path token.** Resolved by Claude Code to the plugin's install path at hook execution time. NEVER hardcode an absolute path.

**Optimus source mapping:** `src/hooks/` (AGENTS.md FD6). The optimus source format is **IDE-agnostic Node.js ESM** (per AGENTS.md: "v2 authors hooks in `src/hooks/` ... as IDE-agnostic Node.js ESM"). The Claude Code bundler must **transform** `src/hooks/<name>.mjs` -> generated `hooks/hooks.json` + bundled `hooks/<name>` shell shim. Format transformation responsibility lives in the bundler, NOT the source.

**Cross-IDE pattern observed in `superpowers/5.1.0`:** ships both `hooks/hooks.json` (Claude Code) AND `hooks/hooks-cursor.json` (Cursor format). Optimus's bundler should produce the appropriate per-IDE JSON from one Node-ESM source -- which is exactly the AGENTS.md TR-17 contract.

### 7.5 MCP servers (`.mcp.json`)

**Plugin layout:** `.mcp.json` at plugin root (NOT `mcp/.mcp.json` -- the dot-prefix dotfile lives at the top level).

**File format:**

```json
{
  "mcpServers": {
    "<server-id>": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/servers/server.js"],
      "env": {
        "API_KEY": "${API_KEY}"
      }
    }
  }
}
```

**Server keys** are the registration IDs. When a registered MCP server exposes a tool, the tool appears in Claude Code's available-tools surface as `mcp__<server-id>__<tool-name>` (verified empirically in B.1 against the deferred-tools listing showing entries like `mcp__claude_ai_Cloudflare_Developer_Platform__d1_database_query`).

**Manifest dual-form (inline vs separate file).** MCP server registration can live in EITHER:
- A separate `.mcp.json` at plugin root (the form the skeleton uses, the form documented in the `plugin-dev:plugin-structure` skill), OR
- An inline `mcpServers` block inside `.claude-plugin/plugin.json` itself (per the manifest schema reference, the `mcpServers` field is one of the recognized `plugin.json` keys).

Both forms are valid; the separate-file form is preferred for plugins shipping multiple MCP servers or wanting to keep the manifest lean. The skeleton demonstrates the separate-file form. M5's bundler can choose either form; the optimus container's MCP registration is likely simple enough that inline-in-`plugin.json` works fine.

**Optimus source mapping:** the optimus container is itself an MCP server. The bundle's `.mcp.json` registers the container per `docs/decisions/transport-and-discovery.md`. There is no `src/mcp/` source surface today; the container is its own first-class artifact. **Action for M5:** the Claude Code bundle ships a `.mcp.json` whose `command` invokes the optimus host-side CLI shim (`optimus`), which in turn dispatches to the singleton container. The CLI shim's path is host-installer-determined; the `.mcp.json` `command` must be patch-able at install time, not bake-time. **This is a CLI-shim coordination point, not a bundler-source concern.**

### 7.6 Rules surface

**Plugin layout (empirical, not officially-documented):** plugins ship `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` at plugin root as IDE-specific session-level instructions (observed in `superpowers/5.1.0` and others). The Claude Code session sometimes auto-includes plugin-shipped `CLAUDE.md` content depending on configuration.

**Optimus source mapping:** `src/rules/` (AGENTS.md FD6). The Claude Code surface is conditional: rules can ship as (a) inline content auto-included via plugin-shipped `CLAUDE.md`, (b) loaded on-demand via a slash-command (e.g., `/optimus-rules`), or (c) a session-start hook that injects via `additionalContext`. The bundler picks one or more of these channels per rule. **Action for M5:** confirm with the plugin-dev:hook-development skill (or empirical probe) the most-reliable channel for the rule types optimus ships; likely option (c) via a SessionStart hook injecting `additionalContext` (the pattern observed in B.1's record dumps).

### Surface-to-source mapping summary

| Optimus source dir | Claude Code plugin component | Bundler transformation |
|--------------------|-----------------------------|--------------------------|
| `src/agents/` | `agents/<name>.md` | 1:1 copy (possible YAML-field remap) |
| `src/skills/` | `skills/<name>/SKILL.md` + supporting files | 1:1 copy |
| `src/hooks/` | `hooks/hooks.json` + supporting scripts | Node ESM -> JSON + shim generation |
| `src/rules/` | `CLAUDE.md` snippet OR `commands/<rule>.md` slash-command OR SessionStart hook with `additionalContext` | Channel selection per rule |
| (no source today) | `commands/<name>.md` slash commands | M5 should add `src/commands/` to the source surface |
| (no source today) | `.mcp.json` MCP server registration | Bundler-templates, install-time-patched for CLI shim path |

### Q7 verdict: POSITIVE with one source-surface gap.

All Claude Code surfaces map cleanly except: (a) `src/commands/` doesn't exist in optimus's source today -- AGENTS.md FD6 should be augmented; (b) the rules surface needs M5 to pick a channel. Neither blocks plugin format research; both are M5 source-surface design questions.

---

## The `plugin-skeleton/` deliverable

A minimal working Claude Code plugin demonstrating each component type lives in the sibling directory `plugin-skeleton/` (i.e. `docs/decomp/M5-plugin-format/plugin-skeleton/` from the optimus repo root). It is reference-only for M5; it is NOT the optimus bundle. M5's bundler produces a different (optimus-specific) plugin tree from optimus's `src/{hooks,agents,skills,rules,commands}/` source. The skeleton's purpose is to give M5 a verified template -- "this is what a minimal valid Claude Code plugin looks like, file by file."

The skeleton contains:
- `.claude-plugin/plugin.json` (manifest, minimal required fields)
- `commands/example.md` (a `/example` slash command)
- `agents/example-reviewer.md` (a subagent definition)
- `skills/example-skill/SKILL.md` (a skill)
- `hooks/hooks.json` (a SessionStart hook using `${CLAUDE_PLUGIN_ROOT}`)
- `hooks/example-hook.sh` (a bash hook shim emitting `hookSpecificOutput.additionalContext`)
- `.mcp.json` (an MCP server registration template, env-var-substituted; referenced server file NOT shipped -- this is reference-shape only)
- `README.md` documenting the skeleton + install steps

**Cross-platform hook portability note.** The skeleton's hook shim uses bash directly (`bash "${CLAUDE_PLUGIN_ROOT}/hooks/example-hook.sh"`), which works on POSIX and on Windows machines with Git for Windows bash on PATH. This is the simpler-but-not-fully-portable pattern. The production-grade alternative -- used by `superpowers/5.1.0/hooks/run-hook.cmd` -- is a polyglot `.cmd` launcher that probes for bash in standard install locations on Windows, then dispatches to the actual hook script. **Recommendation for M5:** adopt the polyglot launcher pattern from `superpowers/5.1.0/hooks/run-hook.cmd` rather than the skeleton's simpler approach. The skeleton's purpose is to demonstrate format shape, not production-grade portability.

See `plugin-skeleton/README.md` (sibling directory) for usage, install steps, and what each file demonstrates.

---

## Risks and unknowns (NOT gate-negative; flagged for M5 planning)

1. **Plugin-format breaking changes within 2.1.x.** Empirically tested at 2.1.140 only; B.1 cross-version-stability evidence for the chat-history JSONL store extrapolates here, but is not a direct test. **M5 mitigation:** snapshot a plugin built today and verify it loads cleanly on the highest-available Claude Code version at M5 build time; add a CI fixture covering the load.

2. **`additionalContext` injection mechanism for rules.** Empirically observed in B.1 record dumps (the session's SessionStart hook injects an `additionalContext` block via the `superpowers:using-superpowers` skill content -- this is the mechanism plugin authors use for "things the session must know at startup"). Plug optimus's `src/rules/` content here. Empirically verified pattern; design choice for M5.

3. **Cross-IDE manifest co-existence in one source repo.** `superpowers/5.1.0` ships `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex/INSTALL.md`, `.opencode/plugins/superpowers.js`, `gemini-extension.json` IN THE SAME source tree. Optimus's M4 + M5 bundlers can adopt this same pattern (one optimus source repo, per-IDE bundle directories). The chat-report toolkit's `cursor/` + `claudecode/` layout (this very repo) is a small-scale instance of the same pattern.

4. **MCP server install-time patching for the CLI shim path.** The `.mcp.json` `command` must reference `optimus` (CLI shim) at a path that varies by OS install location. M5's installer must rewrite this at install time. Pattern: ship a templated `.mcp.json.template` and substitute on install. Documented as the right pattern in `plugin-dev:mcp-integration` skill.

5. **Plugin `version` field optionality.** `plugin-dev/plugin.json` omits `version` entirely (resulting in `"version": "unknown"` in `installed_plugins.json`). For optimus, the bundle version MUST be present (per CHARTER FD8's `bundle_format_version` requirement). **Action for M5:** make `version` mandatory in the optimus bundle.

---

## Cross-references

- Mission brief (canonical): `../delegated-sessions/chat-report-mission-brief.md`
- M5 consumers: sibling `../M5-tasks.md` and `../M5-claude-code-bundle.md`
- CHARTER FD8 (minimum-supported-IDE-version model): `../../../CHARTER.md`
- AGENTS.md FD6 IDE-agnostic source surface: `../../../AGENTS.md`
- B.1 discovery report (lives in the chat-report repo, the consumer of B.1's deliverable): <https://github.com/dtwaling/ai-chat-report/blob/master/claudecode/DISCOVERY.md>

---

## Gate decision

**Gate 2 verdict: POSITIVE** (after revision).

**Verdict trajectory per brief section 7.2 (cold-reviewer pass):**

- Initial self-verdict on first draft: POSITIVE.
- Cold-reviewer (fresh worktree-isolated subagent) verdict: **PARTIAL**, with 4 must-fix items blocking PR:
  1. The report referenced `hooks/example-hook.cmd` while the skeleton shipped `hooks/example-hook.sh`. Internal-inconsistency.
  2. Q5 wording buried the actual answer ("no version-pin mechanism exists in Claude Code") under a caveat about cross-version stability.
  3. Skeleton README install instructions were incomplete -- a reader following them would not get a working plugin (missing `installed_plugins.json` registration snippet, vague `enabledPlugins` step).
  4. Skeleton's hook uses bash directly, which requires Git-for-Windows bash on PATH on Windows -- inferior to the polyglot `run-hook.cmd` pattern from `superpowers/5.1.0`. Either adopt the polyglot pattern or explicitly recommend M5 use it.
  Plus 3 minor flags: unverified plugins-specific docs URL claim, macOS/Linux paths inferred-not-verified, MCP manifest dual-form (inline `mcpServers` in `plugin.json` vs separate `.mcp.json`) not addressed.
- Revision pass: all 4 must-fix + the 3 minor flags addressed in this report and `plugin-skeleton/README.md`. Specifically:
  1. Report's "skeleton contains" section corrected to `example-hook.sh`; cross-platform-portability note added pointing M5 at the polyglot pattern.
  2. Q5 rewritten to lead with the headline answer; the cross-version inference is now framed as a separate, downstream risk.
  3. README's "How to install / try it" section rewritten with explicit `installed_plugins.json` registration JSON snippet, `~/.claude/settings.json` activation snippet, restart step, and uninstall instructions.
  4. Skeleton retains the simpler bash-direct pattern but the report + skeleton README now explicitly recommend M5 adopt the polyglot `run-hook.cmd` pattern from `superpowers/5.1.0`. Rationale: a reference skeleton is a teaching artifact for the format; portability hardening is M5's concern, not the skeleton's.
  Minor flags: public docs URL claim softened (no longer asserts a specific plugins-page exists at code.claude.com); macOS/Linux paths in Q6 now labeled "Inferred, not empirically tested"; `CLAUDE_CONFIG_DIR` is similarly labeled; MCP manifest dual-form (inline vs separate file) is now documented in Q7.5.

Cold-reviewer pass and revision documented to make the verdict trajectory auditable.

**Delivery note (location correction).** Per PM ruling 2026-05-12 during the B.2 commit attempt, the brief's specified output path (`ai-chat-report/claudecode/PLUGIN-FORMAT-RESEARCH.md` and sibling `plugin-skeleton/`) was a research-co-location convenience that conflated "session that does the work" with "repo that owns the output." This deliverable's actual consumer is optimus M5; the output lives in the optimus repo at `docs/decomp/M5-plugin-format/`. The "PR 3" item in the brief's section 6.3 PR cadence is therefore not an ai-chat-report PR; it is a direct-trunk commit in optimus (per pre-init pattern). B.3 (Claude Code chat-report variant build) is unblocked once this commit lands AND PR 2 (`DISCOVERY.md`, already merged) is in `dtwaling/ai-chat-report:master`.

**Optimus commit message (direct to trunk per pre-init pattern):** `docs(decomp): M5 plugin format research + reference skeleton (B.2 deliverable from chat-report sibling delegated session)`
