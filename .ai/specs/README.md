# Specs — AI Video Processor

> This folder contains all technical specifications for features, changes, refactors, and significant decisions in the AI Video Processor project.

---

## What Is a Spec?

A spec (specification) is a structured document that describes **what** is going to be built or changed, **why**, **how**, and **what constraints** apply — **before or during implementation**.

A spec is not a design document for humans only. It is the **primary contract** between the developer/agent implementing a feature and the rest of the system. It must be complete enough that another agent or developer could pick it up and implement it correctly.

---

## When to Create a Spec

Create a spec for:

- **New features** — any new functionality visible to the end user or API consumer.
- **Significant refactors** — changes that restructure modules, move files, or alter responsibilities.
- **Breaking changes** — changes that affect the API contract, database schema, or domain model.
- **Architectural decisions** — introducing a new pattern, dependency, or structural approach.
- **Bug fixes with complex causes** — where the fix requires understanding the system deeply.

You do **not** need a spec for:
- Trivial typo or text corrections.
- Small cosmetic UI adjustments.
- Adding a comment or updating documentation only.

---

## How to Name a Spec

Use this convention:

```
YYYY-MM-DD-feature-or-change-name.md
```

Use lowercase, hyphen-separated words. Be descriptive but concise.

**Examples:**
```
2026-06-11-add-job-listing-endpoint.md
2026-06-11-alembic-migrations-setup.md
2026-06-12-separate-transcription-rendering-queues.md
2026-06-15-user-authentication-jwt.md
2026-06-20-refactor-workers-dependency-injection.md
```

---

## How to Use a Spec to Implement Changes

1. **Create the spec** using `.ai/specs/spec-template.md` as a base.
2. **Fill in all sections** relevant to the change. Mark unknown sections as `Pending confirmation`.
3. **Implement following the spec**. The spec is the source of truth — not the chat conversation.
4. **If the spec is found to be incomplete** during implementation, update the spec first, then continue.
5. **After implementation**, mark the spec's status as `Implemented` and add a brief implementation note.

---

## How to Update the Project Context After Implementation

After a spec is implemented, update whichever of these files are affected:

| File | When to update |
|---|---|
| `.ai/context/file-map.md` | New files added, files renamed/deleted |
| `.ai/context/architecture-design.md` | Structural or architectural changes |
| `.ai/context/decisions.md` | New technical decision recorded |
| `.ai/context/project-context.md` | Tech stack, commands, or setup changed |
| `.ai/context/development-guidelines.md` | New conventions or patterns introduced |

---

## Spec Lifecycle

```
Proposal → In progress → Implemented
                       → Cancelled
```

- **Proposal:** The spec is written but not yet being implemented.
- **In progress:** Implementation has started.
- **Implemented:** The feature/change is complete and context files have been updated.
- **Cancelled:** The spec was abandoned. Keep the file with a note explaining why.

## Handling Bugs and Fixes

Not all bugs require a new spec.

### Update an existing spec when:

- The bug was introduced by that same spec.
- The bug is a direct consequence of a recent feature.
- The fix is part of the same functional objective.
- The change does not represent a new initiative.

### Create a new spec when:

- The bug is independent of current specs.
- The bug requires architectural changes.
- The bug affects multiple modules with no direct relation to the original spec.
- The fix requires its own technical strategy.
- The bug represents an independent work initiative.

### General rule

If the fix answers the question:

"Is this still part of the same objective?"

Then update the existing spec.

If it answers:

"Does this deserve its own planning, analysis, and acceptance criteria?"

Then create a new spec.