# Agent Instructions — AI Video Processor

> **This file contains mandatory instructions for any AI agent, LLM, or IDE assistant working on this project.**  
> These rules are non-negotiable. Ignoring them is a failed execution.

---

## Step 1 — Read Context Before Doing Anything

Before modifying any code, always read the following files in order:

1. `.ai/context/project-context.md` — What the project is, how to run it, env vars.
2. `.ai/context/architecture-design.md` — DDD layers, data flow, endpoints, risks.
3. `.ai/context/file-map.md` — Where every file lives and what it is responsible for.
4. `.ai/context/development-guidelines.md` — Code conventions, naming, how to add features.
5. `.ai/context/decisions.md` — Why key decisions were made (ADR log).

Do not skip this step. Do not assume you already know the project.

---

## Step 2 — Check for an Existing Spec

Before implementing a new feature, significant change, **or bug fix**:

1. Look in `.ai/specs/` for a spec related to the requested change.
2. If a spec exists: read it completely. It is the source of truth for the 
   implementation. Validate the guidelines with `.ai/specs/README.md`.
3. If no spec exists: **create one** using `.ai/specs/spec-template.md` before 
   writing any code, and follow the guidelines in `.ai/specs/README.md`.

**For bugs and fixes specifically**, follow the triage rules in 
`.ai/specs/README.md` under "Manejo de Bugs y Fixes" to decide whether to 
update an existing spec or create a new one. Either way, a spec must exist 
before touching code.

**Only trivial changes** (typos, minor wording, small cosmetic adjustments) 
may skip the spec requirement. Fixing a runtime error, a logic bug, or a 
broken behavior is NOT trivial.

---

## Step 3 — Follow the Spec During Implementation

- Implement only what the spec describes. Do not add scope creep.
- If you discover the spec is incomplete or incorrect mid-implementation:
  1. Stop.
  2. Update the spec.
  3. Resume implementation.
- The spec is the contract. The conversation or user prompt is context, not the spec.

---

## Step 4 — Follow DDD Layer Order

When making backend changes, always follow this order:

1. **Domain** (`app/domain/`) — entities, enums, business rules
2. **Application** (`app/application/`) — interfaces (ports), use cases
3. **Infrastructure** (`app/infrastructure/`) — adapters, workers, repositories
4. **Presentation** (`app/presentation/`) — routes, DTOs, dependency injection

Never import inner layers from outer layers in reverse (e.g., importing infrastructure from domain). This is an architectural violation.

---

## Step 5 — Update the Harness After Implementation

After implementing a significant change, update the relevant context files:

| Changed | Update |
|---|---|
| New files created or deleted | `.ai/context/file-map.md` |
| Architecture or layers changed | `.ai/context/architecture-design.md` |
| Technical decision made | `.ai/context/decisions.md` |
| Tech stack, setup, or commands changed | `.ai/context/project-context.md` |
| New conventions introduced | `.ai/context/development-guidelines.md` |

Mark the implemented spec as `Implementada` and add implementation notes.

---

## Step 6 — What to Log After a Change

Every significant change must leave a clear record answering:

1. **What was changed?** (specific files, functions, classes)
2. **Why was it changed?** (business reason or technical motivation)
3. **What files were affected?** (list them)
4. **What is the impact on future changes?** (risks, constraints, next steps)

---

## Mandatory Rules

- **Do not assume critical information.** If something is unclear, mark it as `Pendiente de confirmar` and ask.
- **Do not hardcode secrets, credentials, or environment-specific values.** Use `os.getenv()`.
- **Do not import infrastructure from domain or application layers.** Dependency direction is strictly inward.
- **Do not add business logic to `app/presentation/main.py`.** Routes orchestrate; use cases decide.
- **Always clean up temp files** in workers using `finally` blocks.
- **Do not break interface contracts.** If you change an ABC, update all its implementing adapters.
- **Do not modify the database schema** without recording the change in `decisions.md`.
- **Do not delete or overwrite `.ai/` files** without good reason. They are the project's memory.
- **Keep context files accurate.** Stale documentation is worse than no documentation.

---

## Context Update Triggers

The `.ai/context/` files must be updated in any of these situations:

- A new feature is added.
- A feature is removed.
- An important dependency changes.
- The architecture changes.
- The data flow changes.
- The folder structure changes.
- A module is renamed.
- New patterns or conventions are introduced.
- A significant technical decision is taken.
- A spec is implemented that changes the expected system behavior.
- A direct user prompt introduces information relevant to future agents.

---

## Quick Reference

| I need to... | Go to... |
|---|---|
| Understand the project | `.ai/context/project-context.md` |
| Understand the architecture | `.ai/context/architecture-design.md` |
| Find a file | `.ai/context/file-map.md` |
| Know the code conventions | `.ai/context/development-guidelines.md` |
| Understand why something was built that way | `.ai/context/decisions.md` |
| Start a new feature | `.ai/specs/spec-template.md` |
| See existing specs | `.ai/specs/` |
