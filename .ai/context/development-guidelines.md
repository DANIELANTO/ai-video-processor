# Development Guidelines — AI Video Processor

> **For AI Agents:** Read this file before writing any code.  
> Last updated: 2026-06-11

---

## ⚠️ Mandatory Spec Rule

**Before implementing any new feature or significant change, a spec must exist in `.ai/specs/`.**

If no spec exists:
1. Create one using `.ai/specs/spec-template.md`.
2. Fill in: context, objective, scope, requirements, affected files, implementation plan.
3. Only then proceed with implementation.
4. If the spec turns out incomplete mid-implementation, **update the spec first**.

---

## 1. Code Conventions

### Python (Backend)

- **Python 3.11** (per Dockerfile)
- **Type hints:** Mandatory on all function signatures.
- **Pydantic v2:** Use `model_dump()` (not `dict()`), `model_validate()` (not `parse_obj()`).
- **Enums:** Use `str, Enum` pattern for serialization compatibility.
- **Imports order:** stdlib → third-party → internal. Always use full module paths.
- **Error handling:**
  - Use cases: raise `ValueError` for business errors.
  - Presentation: convert to `HTTPException`.
  - Workers: catch all → mark job `FAILED` → re-raise.
- No `print()` statements in production code.

### TypeScript/React (Frontend)

- **Functional components only.** Named exports for components (except root `App`).
- **Hooks:** Must start with `use`. Place in `src/hooks/`.
- **API calls:** All HTTP logic in `src/services/api.ts`. Components never call `fetch` directly.
- **Styling:** TailwindCSS v4 utility classes in JSX. No inline `style` except for truly dynamic values.
- No `console.log` in production code.

---

## 2. Naming Conventions

### Python

| Item | Convention | Example |
|---|---|---|
| Classes | PascalCase | `MediaJob`, `PostgresMediaJobRepository` |
| Functions/methods | snake_case | `execute()`, `get_by_id()` |
| Variables | snake_case | `job_id`, `tmp_video_path` |
| Constants | UPPER_SNAKE_CASE | `REDIS_URL` |
| Interfaces (ABCs) | `I` + PascalCase | `IMediaJobRepository` |
| Adapters | Descriptive + `Adapter` suffix | `AzureBlobStorageAdapter` |
| Use Cases | Descriptive + `UseCase` suffix | `ProcessUploadedVideoUseCase` |

### TypeScript

| Item | Convention | Example |
|---|---|---|
| Components | PascalCase | `SubtitleEditor` |
| Hooks | `use` + camelCase | `useJobStream` |
| Types/Interfaces | PascalCase | `SubtitleSegment` |
| Files (components) | PascalCase | `SubtitleEditor.tsx` |
| Files (other) | camelCase | `useJobStream.ts`, `api.ts` |

---

## 3. How to Add a New Feature

1. **Write the spec** → `.ai/specs/YYYY-MM-DD-feature-name.md`
2. **Identify affected files** via `.ai/context/file-map.md`
3. **Backend changes** — follow DDD layer order:
   1. Domain entities (`app/domain/entities.py`)
   2. Interfaces/ports (`app/application/interfaces.py`)
   3. Use cases (`app/application/use_cases/`)
   4. Infrastructure adapters (`app/infrastructure/`)
   5. Presentation / routes (`app/presentation/main.py`)
4. **Frontend changes:**
   1. API client (`src/services/api.ts`)
   2. Hooks (`src/hooks/`)
   3. Components (`src/components/`)
   4. Root `App.tsx` (only if state machine changes)
5. **Update harness files** (see Section 12)
6. **Mark spec as Implemented**

---

## 4. How to Modify Existing Code

- Never break the interface contract. Changing an ABC method requires updating all adapters.
- Never import infrastructure from domain or application layers.
- Never add business logic to `main.py` (routing + DI only).
- Always clean up temp files in workers using `finally` blocks.
- When modifying domain entities, check all serialization points (repository, workers).

---

## 5. How to Add a New Endpoint

1. Define a Pydantic request DTO in `main.py` (if body needed).
2. Add a dependency provider function (`get_*`) if new infrastructure is needed.
3. Add the route function. Never put business logic in the route.
4. Map exceptions: `ValueError` → 404, `Exception` → 500.
5. Document the endpoint in `architecture-design.md`.

---

## 6. How to Add a New Background Task

1. Add interface method to `app/application/interfaces.py`.
2. Implement in `app/infrastructure/queue.py`.
3. Create Celery task in `app/infrastructure/workers.py` with `@celery_app.task(name=...)`.
4. Follow pattern: load job → publish start event → do work → publish progress → save → publish completion.
5. Wrap in `try/except/finally`. Always clean up temp files.

---

## 7. Error Handling Strategy

| Layer | Strategy |
|---|---|
| Domain | Pydantic `@model_validator` → raises `ValueError` |
| Use Cases | Raise `ValueError` for business violations |
| Infrastructure | Propagate exceptions upward |
| Presentation | `ValueError` → HTTP 404 / `Exception` → HTTP 500 |
| Workers | Catch all → mark job `FAILED` → publish `FAILED` event → re-raise |

---

## 8. Configuration Management

- All secrets in `.env` (never hardcoded).
- Values read via `os.getenv("VAR", "default")`.
- When adding a new env variable, update:
  - `.env`
  - `docker-compose.yml`
  - `.ai/context/project-context.md` (env vars table)

---

## 9. Database Schema Changes

> ⚠️ No migrations — `Base.metadata.create_all()` is used.

Steps for adding a column:
1. Add column to `MediaJobModel` in `infrastructure/database.py`.
2. Update `save()` and `get_by_id()` in `infrastructure/repositories.py`.
3. Update domain entity if it needs to carry the field.
4. Manually apply `ALTER TABLE` or recreate the table in dev.
5. Record in `decisions.md`.

> 💡 Alembic migration setup is recommended — see `decisions.md`.

---

## 10. Frontend API Changes

When backend response shape changes:
1. Update TypeScript types in `src/services/api.ts`.
2. Check all consuming hooks and components.
3. Run `npm run build` to catch type errors.

---

## 11. How to Document Changes

After completing a significant change:
1. Mark the spec as `Implementada` with notes.
2. Update `decisions.md` if a technical decision was made.
3. Update `architecture-design.md` if structural changes occurred.
4. Update `file-map.md` if files were added, removed, or renamed.
5. Update `project-context.md` if setup, stack, or commands changed.

---

## 12. Keeping the Harness Up to Date

Update the relevant `.ai/context/` files when:

| Trigger | Files to update |
|---|---|
| New feature added | `file-map.md`, `architecture-design.md`, spec marked Implemented |
| Feature removed | `file-map.md`, `architecture-design.md`, `project-context.md` |
| Dependency added/changed | `project-context.md`, `decisions.md` |
| Architecture changes | `architecture-design.md`, `file-map.md`, `decisions.md` |
| Data flow changes | `architecture-design.md` |
| Folder structure changes | `file-map.md` |
| Module renamed | `file-map.md`, `architecture-design.md` |
| New convention introduced | `development-guidelines.md` |
| Critical technical decision | `decisions.md` |
| Main execution flow changes | `architecture-design.md`, `project-context.md` |
| Spec implemented changing behavior | All relevant context files |
| Direct user prompt with key project info | Whichever context file is relevant |
