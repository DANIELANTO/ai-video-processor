# Spec: [Nombre de la feature o cambio]

## Estado

Propuesta | En progreso | Implementada | Cancelada

---

## Contexto

Explica por qué se necesita este cambio. ¿Qué problema resuelve? ¿Qué limitación del sistema actual motiva esta spec?

---

## Objetivo

Describe claramente qué se quiere lograr. Una o dos frases concretas.

---

## Alcance

Qué entra en el cambio:
- ...
- ...

---

## Fuera de Alcance

Qué NO debe modificarse ni tocarse durante esta implementación:
- ...
- ...

---

## Requisitos Funcionales

- [ ] Requisito funcional 1
- [ ] Requisito funcional 2
- [ ] Requisito funcional 3

---

## Requisitos Técnicos

- [ ] Requisito técnico 1 (e.g., debe implementar la interfaz X)
- [ ] Requisito técnico 2 (e.g., debe funcionar en Docker)
- [ ] Requisito técnico 3 (e.g., no debe modificar la capa de dominio)

---

## Archivos o Módulos Afectados

Lista los archivos, carpetas o módulos que probablemente serán creados o modificados:

| Archivo | Tipo de cambio |
|---|---|
| `app/domain/entities.py` | Modificación |
| `app/application/interfaces.py` | Modificación |
| `app/application/use_cases/process_video.py` | Modificación |
| `app/infrastructure/workers.py` | Modificación |
| `app/presentation/main.py` | Modificación |
| `frontend/src/services/api.ts` | Modificación |

---

## Diseño Propuesto

Explica la solución propuesta a nivel técnico. Puede incluir pseudocódigo, diagramas, decisiones de implementación, o descripción de los cambios en cada capa.

### Backend

...

### Frontend

...

---

## Impacto en Arquitectura

¿Este cambio afecta la arquitectura del proyecto?

- [ ] Sí
- [ ] No

Si afecta la arquitectura, los siguientes archivos deben actualizarse después de implementar:
- `.ai/context/architecture-design.md`
- `.ai/context/file-map.md`
- `.ai/context/decisions.md`
- `.ai/context/project-context.md` (si aplica)

---

## Plan de Implementación

1. Paso 1: ...
2. Paso 2: ...
3. Paso 3: ...
4. Paso 4: ...
5. Paso 5: Marcar spec como Implementada y actualizar archivos de contexto.

---

## Criterios de Aceptación

- [ ] Criterio 1: ...
- [ ] Criterio 2: ...
- [ ] Criterio 3: ...

---

## Pruebas Sugeridas

Describe cómo validar que el cambio funciona correctamente:

- **Manual:** ...
- **Automatizado (si aplica):** ...
- **Casos borde:** ...

---

## Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| ... | Alta / Media / Baja | ... |

---

## Notas para Futuros Agentes

Incluye cualquier información que pueda ser útil para otro LLM o desarrollador que retome esta spec o trabaje en una feature relacionada.

- ...
- ...

---

## Notas de Implementación

_(Llenar después de implementar)_

**Fecha de implementación:** YYYY-MM-DD  
**Cambios realizados:**  
- ...

**Archivos de contexto actualizados:**
- [ ] `.ai/context/file-map.md`
- [ ] `.ai/context/architecture-design.md`
- [ ] `.ai/context/decisions.md`
- [ ] `.ai/context/project-context.md`
- [ ] `.ai/context/development-guidelines.md`
