#!/usr/bin/env bash
# Minimal reference SessionStart hook for the chat-report plugin skeleton.
#
# Receives the event subtype as $1 (e.g. "session-start").
# Emits a JSON payload to stdout that Claude Code consumes per the hooks
# protocol: hookSpecificOutput.additionalContext is injected into the
# session's context window.
#
# This script is invoked via `bash "${CLAUDE_PLUGIN_ROOT}/hooks/example-hook.sh"
# session-start` per hooks.json. On Windows, bash is provided by Git for
# Windows (the standard install ships with the Bash shell). On POSIX systems
# bash is universally available.

cat <<EOF
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "chat-report-skeleton-example loaded (subtype: $1)"}}
EOF
