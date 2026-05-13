# Git, PR, and Issue Conventions

**Status:** Founding pass. Single-page reference for commit messages, PR descriptions, issue bodies, and the initial label set. Adjust as the project evolves; record additions inline below.

## Commit messages

- **Conventional-commits prefix.** One-line summary in the form `<type>: <subject>` where `<type>` is one of `chore`, `feat`, `docs`, `ci`, `fix`, `refactor`, `test`. (M0-tasks.md already uses this shape; this doc just makes it explicit.)
- **Subject line:** present tense, lowercase, <=72 chars. Example: `feat: add optimus_doctor parent-mount precondition check`.
- **Optional body:** blank line after subject, then wrap at 72 chars. Use the body for the "why" -- what changed should be obvious from the diff.
- **Co-author attribution:** not required for single-author commits. For multi-author work, add `Co-authored-by: Name <email>` trailers per GitHub conventions.

## PR descriptions

PR bodies live as drafts under `body-files/` (gitignored; per AGENTS.md) and are passed via `gh pr create --body-file <body-files/...>`. Required sections:

- **What changed** -- 1-3 bullets, the diff in plain language.
- **Why** -- 1-2 sentences, the motivation. Link the requirement, decision record, or issue this resolves.
- **Test plan** -- bulleted checklist of how reviewers can verify (manual steps, CI jobs that must be green, eval-corpus results to inspect).
- **Risk / rollback** -- one line. What's the blast radius if this is wrong, and how do we back it out?

Keep PRs scoped tight enough that the body fits on one screen. Large PRs without a clear "what changed" + "test plan" get bounced back.

## Issue bodies

- **Body-files pattern (mandatory).** Issue bodies are authored as markdown at `docs/issues/<slug>.md` and filed via `gh issue create --body-file docs/issues/<slug>.md --title "<title>" --label <labels>`. No inline `--body "..."` strings.
- **Slug convention:** `<short-topic>.md` (e.g., `chunk-5-review-findings.md`, `optimus-doctor-parent-mount-precondition.md`). Match the issue title's nut.
- **Body shape:** start with a one-paragraph problem statement, follow with bullets covering scope, acceptance criteria, and any cross-references to TRs / EURs / decision records.
- **Lifecycle:** the body file stays in `docs/issues/` after filing; it is the canonical source. Update the file + edit the issue body if the scope shifts.

## Labels (initial set)

Apply at least one type label plus any applicable scope labels:

- `bug` -- something is broken or behaves contrary to spec.
- `feature` -- new capability or requirement landing.
- `docs` -- documentation-only change (this conventions doc itself qualifies).
- `chore` -- maintenance, refactoring, dependency bumps, repo hygiene.
- `security` -- vulnerability, hardening, or trust-model concern.
- `pre-kickoff` -- work that lands before M0 (e.g., chat-report sibling deliverables).
- `milestone:M<n>` -- scope label tying the issue to a milestone (M0 through M6).
- `blocked` -- waiting on external input, upstream fix, or another issue.

**Adding new labels:** any contributor may propose; record the addition in this doc (append the new label + one-line purpose to the list above) as part of the PR that introduces it. Labels not documented here are non-canonical.

## Cross-reference

- `AGENTS.md` (Conventions section) -- links here for the full spec.
- `docs/decomp/M0-tasks.md` -- already references conventional-commits prefixes in commit-shape examples.
