#!/usr/bin/env bash
# Minimal reference sessionStart hook for the Cursor plugin skeleton.
#
# Receives the event subtype as $1 (e.g. "session-start").
# Emits a JSON payload to stdout that Cursor consumes per the hooks protocol:
# hookSpecificOutput.additionalContext is injected into the session's context
# window. (Cursor's hook protocol is convergent with Claude Code's here; both
# IDEs accept this JSON shape from a command-type hook on stdout.)
#
# This script is invoked via `bash "./hooks/example-hook.sh" session-start` per
# hooks-cursor.json. The relative path is resolved against the plugin install
# root by Cursor (NOT the project root) for plugin-level hooks. Cursor does NOT
# provide a ${CLAUDE_PLUGIN_ROOT} env-var analog; relative-to-plugin-root is
# the contract.
#
# On Windows, bash is provided by Git for Windows (the standard install ships
# with the Bash shell). On POSIX systems bash is universally available.
#
# For production-grade portability, prefer the polyglot run-hook.cmd launcher
# pattern used by superpowers/b7a8f76/hooks/run-hook.cmd (probes for bash in
# multiple Windows install locations before dispatching). This skeleton uses
# the simpler bash-direct pattern to keep the format demonstration uncluttered.

cat <<EOF
{"hookSpecificOutput": {"hookEventName": "sessionStart", "additionalContext": "cursor-plugin-skeleton-example loaded (subtype: $1)"}}
EOF
