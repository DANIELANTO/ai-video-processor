# Spec: Fix Critical Infrastructure Boot Errors

**Fecha:** 2026-06-11  
**Autor:** AI Agent  
**Estado:** Implementada  
**Tipo:** Bug fix (multi-module)

---

## 1. Contexto y Problema

Al levantar el stack con `docker compose up --build`, se detectan cuatro errores que impiden que los servicios arranquen correctamente. Durante la implementación surgieron dos bugs adicionales no previstos (Error 5 y Error 6).

### Error 1 — API no puede resolver el host "db" (DNS / timing)
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError)
could not translate host name "db" to address: Temporary failure in name resolution
```
**Causa raíz:** `database.py` llama a `_create_engine_with_retry()` en tiempo de importación del módulo. Cuando `main.py` es importado por Uvicorn, el módulo `database.py` se ejecuta inmediatamente. En ese instante, la red interna de Docker puede no estar lista aún. El `depends_on: condition: service_healthy` no garantiza que el DNS interno de Docker esté propagado en el momento exacto del primer import de Python.

**Fix:** Refactorizar `database.py` a lazy initialization (`engine = None`, `SessionLocal = None`). Nueva función `init_db()` hace la conexión real. `main.py` llama a `init_db()` dentro de un FastAPI lifespan handler, que corre después de que Uvicorn está corriendo y la red Docker está garantizada. (Ver DEC-0011 en `decisions.md`.)

---

### Error 2 — `redis.asyncio` no encontrado
```
Cannot find module 'redis.asyncio'
```
**Causa raíz:** Imagen Docker cacheada con versión anterior de `redis`. La librería `redis==7.4.0` en `requirements.txt` SÍ incluye `redis.asyncio`.

**Fix:** Rebuild limpio con `--no-cache`. No se requieren cambios de código.

---

### Error 3 — Frontend recibe 404 en `POST /api/v1/jobs/upload`
```
:8000/api/v1/jobs/upload:1 Failed to load resource: 404
```
**Causa raíz:** Consecuencia en cascada del Error 1. La API nunca levantaba. La ruta existe y es correcta.

**Fix:** Resuelto al resolver Error 1. No se requieren cambios de frontend.

---

### Error 4 — Celery SecurityWarning (root user)
```
SecurityWarning: You're running the worker with superuser privileges
```
**Causa raíz:** El Dockerfile no crea un usuario no-root.

**Fix:** `C_FORCE_ROOT=1` en el servicio `worker_whisper` de `docker-compose.yml`. Deuda técnica: crear usuario no-root en Dockerfile en una spec futura.

---

### Error 5 — Conflicto de puerto 8000 (descubierto durante implementación)
```
Bind for 0.0.0.0:8000 failed: port is already allocated
```
**Causa raíz:** El contenedor `nodepay-ai-service-1` (otro proyecto del mismo entorno) ocupa el puerto 8000 en el host.

**Fix:** Cambiar el mapeo de puerto host de `8000:8000` a `8001:8000` en `docker-compose.yml`. Actualizar `VITE_API_BASE_URL` en `frontend/.env` a `localhost:8001`. Actualizar fallbacks hardcodeados en `api.ts` y `useJobStream.ts`.

---

### Error 6 — Worker falla con `TypeError: 'NoneType' object is not callable` (descubierto post-implementación)
```
TypeError: 'NoneType' object is not callable
  File "/workspace/app/infrastructure/workers.py", line 55, in transcribe_audio
    db = SessionLocal()
```
**Causa raíz:** El refactor de lazy initialization dejó `SessionLocal = None` a nivel de módulo. El worker de Celery corre en su **propio proceso separado**, importa `database.py` directamente y **nunca pasa por el lifespan de FastAPI**, por lo que `init_db()` jamás se ejecuta en el proceso del worker. Cuando la tarea intenta llamar `SessionLocal()`, falla porque sigue siendo `None`.

**Fix:** Llamar a `init_db()` explícitamente en `workers.py` a nivel de módulo (después de los imports). El contenedor `worker_whisper` ya depende de `db: condition: service_healthy`, así que el DB está garantizado cuando el worker arranca.

---

## 2. Archivos Afectados

| Archivo | Cambio |
|---|---|
| `app/infrastructure/database.py` | Lazy init: `engine = None`, `SessionLocal = None`, nueva función `init_db()` |
| `app/presentation/main.py` | FastAPI lifespan handler que llama `init_db()` + `create_all()` |
| `app/infrastructure/workers.py` | Llamada explícita a `init_db()` a nivel de módulo |
| `docker-compose.yml` | Puerto `8001:8000`, `C_FORCE_ROOT=1`, `restart: on-failure`, `REDIS_URL` en api |
| `frontend/.env` | `VITE_API_BASE_URL` → `localhost:8001` |
| `frontend/src/services/api.ts` | Fallback hardcodeado `8000→8001` |
| `frontend/src/hooks/useJobStream.ts` | Fallback hardcodeado `8000→8001` |

---

## 3. Criterios de Aceptación

- [x] `docker compose up` levanta todos los servicios sin errores fatales.
- [x] La API responde en `http://localhost:8001/docs`.
- [x] `POST /api/v1/jobs/upload` devuelve 201.
- [ ] El worker de Celery completa `transcribe_audio` sin `TypeError`.
- [x] El warning de Celery SecurityWarning no detiene el worker.
- [x] `redis.asyncio` se importa correctamente.
- [ ] La UI avanza del estado "Analyzing audio" al estado de revisión de subtítulos.

---

## 4. Prueba de Azure (Manual)

Una vez que los servicios estén corriendo:
1. Llamar a `POST /api/v1/jobs/upload` con `{"filename": "test.mp4"}`.
2. Verificar que la respuesta incluye un `upload_url` con dominio `*.blob.core.windows.net`.
3. Confirmar que el contenedor de Azure (`AZURE_CONTAINER_NAME`) recibe el blob.
4. Confirmar que `transcribe_audio` completa y la UI muestra el editor de subtítulos.

---

## 6. Notas de Implementación

- **DEC-0011** registrado en `decisions.md` documenta la decisión de lazy init.
- El puerto del host para la API es ahora `8001` (cambio permanente mientras `nodepay-ai-service` coexista en el mismo entorno).
- El worker necesita llamar `init_db()` independientemente porque corre en un proceso separado al de FastAPI.
- `project-context.md` actualizado: puerto de la API, nuevo puerto mapeado.
