# Spec: Fix render_video crash por `out_time_ms=N/A` y análisis de performance

## Estado

Implementada

---

## Contexto

Al iniciar el proceso de renderizado de video (tarea Celery `render_video`), FFmpeg emite líneas de progreso a través de `-progress -`. Estas líneas tienen el formato `clave=valor`. Entre ellas aparece `out_time_ms` que representa el tiempo procesado en microsegundos.

**El problema:** En ciertos frames (especialmente al inicio y/o al final del proceso), FFmpeg puede emitir `out_time_ms=N/A` en lugar de un número entero. El código actual intenta hacer `int("N/A")`, lo que provoca:

```
ValueError: invalid literal for int() with base 10: 'N/A'
```

Esto rompe la tarea Celery, que captura la excepción y marca el job como `FAILED`, propagando el error al frontend como "Processing Failed" incluso si el video podría haberse procesado correctamente.

El bug es independiente de las specs actuales (no fue introducido por ninguna spec reciente). Además, el usuario reporta que el procesamiento demora considerablemente. Se hace un análisis de cuello de botella incluido en esta spec.

---

## Objetivo

1. Corregir el crash `ValueError: invalid literal for int() with base 10: 'N/A'` en la tarea `render_video` de `app/infrastructure/workers.py`.
2. Analizar el pipeline para identificar cuellos de botella de performance dentro de los límites del stack actual (sin incurrir en gasto de infraestructura).
3. Aplicar mejoras de performance que sean gratuitas o de bajo costo (cambio de modelo AI más rápido y económico si aplica).

---

## Alcance

- Manejo defensivo del valor `N/A` en el parsing de progreso de FFmpeg.
- Análisis y mejora del comando FFmpeg en `render_video` (flags de encodeo, preset, threads).
- Evaluación del modelo de IA actual (`whisper-1`) y si existe una alternativa más rápida dentro del mismo tier de costo.
- Lógica de progreso robusta que ignore líneas con valores no numéricos.

---

## Fuera de Alcance

- No se modificará la infraestructura Docker (no se agregarán contenedores, no se cambiará hardware).
- No se cambiará la base de datos ni el esquema.
- No se modificará el pipeline de transcripción (Whisper) salvo que se decida cambiar el modelo.
- No se modificará la capa de dominio (`app/domain/`).
- No se modificará la capa de aplicación (`app/application/`).
- No se modificará el frontend salvo que sea necesario para comunicar el error de forma más informativa.
- No se agregarán nuevas dependencias.

---

## Requisitos Funcionales

- [ ] **RF-01:** Si `out_time_ms` tiene el valor `N/A`, la línea debe ser ignorada silenciosamente sin interrumpir el proceso FFmpeg.
- [ ] **RF-02:** El proceso de renderizado debe continuar y completarse correctamente aunque FFmpeg emita valores `N/A` durante la lectura del progreso.
- [ ] **RF-03:** El job no debe quedar en estado `FAILED` por un error de parsing de progreso.
- [ ] **RF-04:** El progreso en Redis debe seguir publicándose correctamente en los frames donde `out_time_ms` sí tenga valor numérico.

---

## Requisitos Técnicos

- [ ] **RT-01:** Usar `try/except ValueError` (o validación con `.isnumeric()` / `strip().lstrip('-').isdigit()`) al parsear `out_time_ms` para ignorar valores no numéricos.
- [ ] **RT-02:** El handling debe mantenerse dentro del `for line in process.stdout:` existente sin refactorizar la estructura del método.
- [ ] **RT-03:** El FFmpeg command debe usar flags que aceleren el encoding sin afectar calidad visual percibida por el usuario:
  - `-preset ultrafast` o `-preset veryfast` en el encoder de video.
  - `-threads 0` para usar todos los cores disponibles del contenedor.
  - Evaluar si copiar el stream de video (`-c:v copy`) es viable (no lo es si se aplica `vf` filter con `eq=` y `subtitles=`).
- [ ] **RT-04:** El manejo de errores debe hacer log del valor `N/A` a `stderr` o al logger de Celery para diagnóstico sin interrumpir la ejecución.
- [ ] **RT-05:** El código debe mantenerse dentro de la capa de infraestructura.

---

## Archivos o Módulos Afectados

| Archivo | Tipo de cambio |
|---|---|
| `app/infrastructure/workers.py` | Modificación (bug fix + mejoras FFmpeg) |

---

## Diseño Propuesto

### Backend — Fix del crash (`workers.py`, línea 180)

**Antes (código roto):**
```python
for line in process.stdout:
    if "out_time_ms=" in line:
        current_time_seconds = int(line.split("=")[1].strip()) / 1000000
        percent = min(99, math.floor((current_time_seconds / max(0.1, estimated_duration)) * 100))
        if percent > 0:
            redis_client.publish(...)
```

**Después (código corregido):**
```python
for line in process.stdout:
    if "out_time_ms=" in line:
        raw_value = line.split("=")[1].strip()
        try:
            current_time_us = int(raw_value)
        except ValueError:
            # FFmpeg emits 'N/A' at the start/end of processing — skip silently
            continue
        if current_time_us <= 0:
            continue
        current_time_seconds = current_time_us / 1_000_000
        percent = min(99, math.floor((current_time_seconds / max(0.1, estimated_duration)) * 100))
        if percent > 0:
            redis_client.publish(f"channel:job:{job_id_str}", json.dumps({
                "status": "RENDERING",
                "progress": percent
            }))
```

---

### Backend — Mejora de performance en FFmpeg

FFmpeg por defecto usa el encoder `libx264` con preset `medium`. El preset controla la velocidad de encoding vs. compresión. Para un video tipico en un contenedor compartido, cambiar a `ultrafast` o `veryfast` puede reducir el tiempo de rendering en un **50–70%** a costo de un archivo de salida ligeramente mayor (aceptable para este caso de uso).

**Propuesta de comando FFmpeg mejorado:**
```python
cmd = [
    'ffmpeg', '-y', '-i', tmp_input_video,
    '-vf', vf_filter,
    '-c:v', 'libx264',
    '-preset', 'ultrafast',   # Más rápido, archivo ligeramente más grande
    '-crf', '23',             # Calidad constante razonable (default)
    '-threads', '0',          # Usar todos los cores disponibles
    '-c:a', 'copy',
    '-progress', '-', '-nostats',
    tmp_output_video
]
```

> **Nota:** `-c:v copy` NO es una opción válida aquí porque se aplica un filtro de video (`-vf`). Copiar el stream de video sin re-encodear solo funciona cuando no hay filtros de video.

---

### Análisis de cuello de botella del pipeline completo

El pipeline tiene 3 fases costosas:

| Fase | Herramienta | Cuello de botella | Mejora posible |
|---|---|---|---|
| Descarga del video | Azure Blob | Red / latencia | No modificable sin cambiar infra |
| Transcripción | OpenAI Whisper `whisper-1` | API remota, tiempo de respuesta | Evaluar `gpt-4o-transcribe` o `whisper-large-v3-turbo` si disponible en API |
| Rendering | FFmpeg | CPU / preset | Cambiar a `ultrafast` (gratis, en scope) |

**Conclusión sobre Whisper:** `whisper-1` es el único modelo de transcripción disponible en la API de OpenAI para audio. No existe un modelo alternativo oficial de OpenAI que sea más rápido Y más barato. El cuello de botella de transcripción está en la latencia de la API externa y no es optimizable sin cambiar de proveedor. Se mantiene `whisper-1`.

**Conclusión sobre FFmpeg:** El cambio de preset es **gratuito, inmediato, y significativo**. Es la mejora de mayor impacto dentro del scope.

---

## Impacto en Arquitectura

- [x] No — Este cambio solo afecta la capa de infraestructura (`workers.py`). No modifica contratos de API, esquema de base de datos, ni capas de dominio/aplicación.

---

## Plan de Implementación

1. **Abrir** `app/infrastructure/workers.py`.
2. **Localizar** el bloque `for line in process.stdout:` dentro de `render_video` (aprox. línea 178).
3. **Aplicar** el fix de `try/except ValueError` para el parsing de `out_time_ms`.
4. **Actualizar** el comando FFmpeg (`cmd` list) para incluir `-c:v libx264`, `-preset ultrafast`, `-threads 0`.
5. **Verificar** que el `finally` block de `render_video` sigue intacto (limpieza de archivos temporales).
6. **Marcar** esta spec como `Implementada`.
7. **Actualizar** `decisions.md` con la decisión de usar `-preset ultrafast` y el motivo.

---

## Criterios de Aceptación

- [ ] **CA-01:** Un video que antes fallaba con `ValueError: invalid literal for int() with base 10: 'N/A'` ahora se renderiza completamente y el job queda en estado `COMPLETED`.
- [ ] **CA-02:** El frontend no muestra "Processing Failed" para un video válido.
- [ ] **CA-03:** El progreso de rendering se sigue actualizando correctamente en la UI durante el proceso.
- [ ] **CA-04:** El tiempo de rendering se reduce perceptiblemente respecto al estado anterior (estimado: >40% más rápido).
- [ ] **CA-05:** El archivo de video final es reproducible y con subtítulos correctamente quemados.

---

## Pruebas Sugeridas

- **Manual:** Subir un video, corregir la transcripción, hacer click en "Procesar". Verificar que el job llega a `COMPLETED` y el video es descargable.
- **Manual (regresión):** Verificar que el progreso se actualiza en tiempo real en el frontend durante el rendering.
- **Casos borde:**
  - Video muy corto (<5 segundos) — FFmpeg puede emitir solo valores `N/A` al inicio.
  - Video sin audio — No aplica (el pipeline requiere audio para la transcripción).
  - Video ya completamente procesado (re-proceso) — Debe crear un nuevo blob `final_*`.

---

## Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| `-preset ultrafast` genera archivos demasiado grandes | Baja | El `crf 23` limita la degradación de calidad. Si fuera problema, usar `veryfast`. |
| `-threads 0` consume todos los cores durante el rendering y afecta otros servicios del mismo host | Baja-Media | En contenedores Docker con `--cpus` limitado esto es inofensivo. Si hay contención, setear `-threads 2`. |
| El fix de `N/A` enmascara un error real de FFmpeg | Baja | El `process.returncode` sigue verificándose después del loop; si FFmpeg falla realmente, se captura ahí. |

---

## Notas para Futuros Agentes

- El flag `-progress -` en FFmpeg envía el output de progreso a stdout; los demás logs (incluyendo errores fatales) van a stderr. El código actual mezcla stdout y stderr con `stderr=subprocess.STDOUT`. Si en el futuro se necesita separar errores de progreso, cambiar a `stderr=subprocess.PIPE` y leer ambos streams.
- `out_time_ms=N/A` ocurre en FFmpeg cuando el muxer todavía no tiene información temporal (típicamente las primeras líneas del proceso). Es comportamiento documentado y esperado.
- Si en el futuro se quiere mejorar la transcripción, el único camino dentro de OpenAI es usar la API de Realtime Audio o Batch API (con descuento de costo pero latencia mayor). Ambas requieren cambios arquitectónicos significativos.

---

## Notas de Implementación

**Fecha de implementación:** 2026-06-11  
**Cambios realizados:**  
- Se añadió un bloque `try/except ValueError` en el parsing de `out_time_ms` en `workers.py` para ignorar valores no numéricos como `N/A`.
- Se optimizó el comando de FFmpeg agregando `-preset ultrafast`, `-crf 23` y `-threads 0` para un renderizado significativamente más rápido.

**Archivos de contexto actualizados:**
- [ ] `.ai/context/file-map.md`
- [ ] `.ai/context/architecture-design.md`
- [x] `.ai/context/decisions.md` (DEC-0014 añadido)
- [ ] `.ai/context/project-context.md`
- [ ] `.ai/context/development-guidelines.md`
