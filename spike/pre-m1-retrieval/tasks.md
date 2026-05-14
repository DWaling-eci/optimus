# Retrieval Test Tasks

Control prompts for testing repository retrieval over the MarkSystems superrepo.

## Task 1: Navigational
Prompt:
Where is the Kotlin REST provider for the `ms-core-api` House endpoint, and what nearby files define its request parameters, response contract, repository, and integration tests?

Success criteria:
- Answer names exact file paths for the House REST provider, params/request extraction, response contract, repository/service layer, and integration test.
- Answer distinguishes production files from test files.
- Answer gives enough local context to navigate directly to the implementation without broad searching.

## Task 2: Subsystem Comprehension
Prompt:
Explain how `ms-core-api` loads runtime configuration for local development and deployment. Include the role of `config/`, `config/custom/`, `config-builder/`, and `ms-core-api-lab/`.

Success criteria:
- Answer identifies the main config files/templates and explains how generated config differs from checked-in runtime config.
- Answer explains local lab startup path and how it supplies config to the service.
- Answer calls out environment/custom overrides and deployment-related config flow.
- Answer cites concrete files or directories for each part of the explanation.

## Task 3: Cross-Module Trace
Prompt:
How does a request flow from the HTTP API layer to the data layer for the `ms-option-api` Option Pricing endpoint? Trace the route/provider, service interface or provider, repository, params/request extraction, response contract, and any shared `ms-core` types or helpers involved.

Success criteria:
- Answer traces the endpoint in order from HTTP route to request parsing, service call, repository query, record/model mapping, and response contract.
- Answer names exact classes/files for each hop in `ms-option-api`.
- Answer identifies any reused `ms-core` abstractions, value types, request helpers, repository helpers, or response envelope patterns involved.
- Answer notes auth or tenant/company/development scoping if present in the request flow.

## Task 4: Pattern Find
Prompt:
Find all places in `ms-event-source` and `ms-event-store` where publishing, ingesting, or write-back logic retries or recovers after failure. For each place, identify the service/class, triggering failure condition, retry or recovery strategy, and logging behavior.

Success criteria:
- Answer includes a repo-wide search strategy or evidence that both `ms-event-source` and `ms-event-store` were checked.
- Answer lists every retry/recovery location found, with file path, class/function, and failure condition.
- Answer explains retry count/backoff/requeue/skip/dead-letter/manual recovery behavior where applicable.
- Answer explicitly states when no retry behavior exists for a relevant publishing, ingesting, or write-back path instead of leaving it ambiguous.
