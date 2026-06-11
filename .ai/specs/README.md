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
2. **Fill in all sections** relevant to the change. Mark unknown sections as `Pendiente de confirmar`.
3. **Implement following the spec**. The spec is the source of truth — not the chat conversation.
4. **If the spec is found to be incomplete** during implementation, update the spec first, then continue.
5. **After implementation**, mark the spec's status as `Implementada` and add a brief implementation note.

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
Propuesta → En progreso → Implementada
                       → Cancelada
```

- **Propuesta:** The spec is written but not yet being implemented.
- **En progreso:** Implementation has started.
- **Implementada:** The feature/change is complete and context files have been updated.
- **Cancelada:** The spec was abandoned. Keep the file with a note explaining why.

## Manejo de Bugs y Fixes

No todos los bugs requieren una nueva spec.

### Actualizar una spec existente cuando:

- El bug fue introducido por esa misma spec.
- El bug es consecuencia directa de una feature reciente.
- El fix forma parte del mismo objetivo funcional.
- El cambio no representa una nueva iniciativa.

### Crear una nueva spec cuando:

- El bug es independiente de las specs actuales.
- El bug requiere cambios arquitectónicos.
- El bug afecta múltiples módulos sin relación directa con la spec original.
- El fix requiere una estrategia técnica propia.
- El bug representa una iniciativa de trabajo independiente.

### Regla general

Si el fix responde a la pregunta:

"¿Esto sigue siendo parte del mismo objetivo?"

Entonces actualizar la spec existente.

Si responde a:

"¿Esto merece su propia planificación, análisis y criterios de aceptación?"

Entonces crear una nueva spec.