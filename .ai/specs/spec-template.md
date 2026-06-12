# Spec: [Feature or change name]

## Status

Proposal | In progress | Implemented | Cancelled

---

## Context

Explain why this change is needed. What problem does it solve? What limitation of the current system motivates this spec?

---

## Objective

Clearly describe what is to be achieved. One or two concrete sentences.

---

## Scope

What is included in the change:
- ...
- ...

---

## Out of Scope

What MUST NOT be modified or touched during this implementation:
- ...
- ...

---

## Functional Requirements

- [ ] Functional requirement 1
- [ ] Functional requirement 2
- [ ] Functional requirement 3

---

## Technical Requirements

- [ ] Technical requirement 1 (e.g., must implement interface X)
- [ ] Technical requirement 2 (e.g., must work in Docker)
- [ ] Technical requirement 3 (e.g., must not modify the domain layer)

---

## Affected Files or Modules

List the files, folders, or modules that will likely be created or modified:

| File | Change Type |
|---|---|
| `app/domain/entities.py` | Modification |
| `app/application/interfaces.py` | Modification |
| `app/application/use_cases/process_video.py` | Modification |
| `app/infrastructure/workers.py` | Modification |
| `app/presentation/main.py` | Modification |
| `frontend/src/services/api.ts` | Modification |

---

## Proposed Design

Explain the proposed solution at a technical level. It can include pseudocode, diagrams, implementation decisions, or descriptions of changes in each layer.

### Backend

...

### Frontend

...

---

## Architectural Impact

Does this change affect the architecture of the project?

- [ ] Yes
- [ ] No

If it affects the architecture, the following files must be updated after implementation:
- `.ai/context/architecture-design.md`
- `.ai/context/file-map.md`
- `.ai/context/decisions.md`
- `.ai/context/project-context.md` (if applicable)

---

## Implementation Plan

1. Step 1: ...
2. Step 2: ...
3. Step 3: ...
4. Step 4: ...
5. Step 5: Mark spec as Implemented and update context files.

---

## Acceptance Criteria

- [ ] Criterion 1: ...
- [ ] Criterion 2: ...
- [ ] Criterion 3: ...

---

## Suggested Tests

Describe how to validate that the change works correctly:

- **Manual:** ...
- **Automated (if applicable):** ...
- **Edge cases:** ...

---

## Risks

| Risk | Probability | Mitigation |
|---|---|---|
| ... | High / Medium / Low | ... |

---

## Notes for Future Agents

Include any information that might be useful for another LLM or developer who takes on this spec or works on a related feature.

- ...
- ...

---

## Implementation Notes

_(To be filled out after implementation)_

**Implementation date:** YYYY-MM-DD  
**Changes made:**  
- ...

**Context files updated:**
- [ ] `.ai/context/file-map.md`
- [ ] `.ai/context/architecture-design.md`
- [ ] `.ai/context/decisions.md`
- [ ] `.ai/context/project-context.md`
- [ ] `.ai/context/development-guidelines.md`
