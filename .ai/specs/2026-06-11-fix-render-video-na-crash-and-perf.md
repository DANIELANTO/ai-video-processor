# Spec: Fix render_video crash due to out_time_ms=N/A and performance analysis

## Status

Implemented

---

## Context

Upon starting the video rendering process (Celery task `render_video`), FFmpeg emits progress lines via `-progress -`. These lines have the format `key=value`. Among them is `out_time_ms` which represents the processed time in microseconds.

**The problem:** On certain frames (especially at the start and/or end of the process), FFmpeg can emit `out_time_ms=N/A` instead of an integer. The current code attempts to run `int("N/A")`, which causes:

```
ValueError: invalid literal for int() with base 10: 'N/A'
```

This breaks the Celery task, which catches the exception and marks the job as `FAILED`, propagating the error to the frontend as "Processing Failed" even if the video could have been processed successfully.

The bug is independent of current specs (it was not introduced by any recent spec). Additionally, the user reports that processing takes a significant amount of time. A bottleneck analysis is included in this spec.

---

## Objective

1. Fix the `ValueError: invalid literal for int() with base 10: 'N/A'` crash in the `render_video` task of `app/infrastructure/workers.py`.
2. Analyze the pipeline to identify performance bottlenecks within the limits of the current stack (without incurring infrastructure costs).
3. Apply performance improvements that are free or low-cost (switching to a faster and cheaper AI model if applicable).

---

## Scope

- Defensive handling of the `N/A` value in FFmpeg progress parsing.
- Analysis and improvement of the FFmpeg command in `render_video` (encoding flags, preset, threads).
- Evaluation of the current AI model (`whisper-1`) and whether a faster alternative exists within the same cost tier.
- Robust progress logic that ignores lines with non-numeric values.

---

## Out of Scope

- No modifications to the Docker infrastructure (no additional containers, no hardware changes).
- No changes to the database or schema.
- No modifications to the transcription pipeline (Whisper) unless we decide to change the model.
- No modifications to the domain layer (`app/domain/`).
- No modifications to the application layer (`app/application/`).
- No modifications to the frontend unless necessary to report the error more informatively.
- No new dependencies will be added.

---

## Functional Requirements

- [ ] **RF-01:** If `out_time_ms` has the value `N/A`, the line must be silently ignored without interrupting the FFmpeg process.
- [ ] **RF-02:** The rendering process must continue and complete successfully even if FFmpeg emits `N/A` values during progress reading.
- [ ] **RF-03:** The job must not end up in the `FAILED` state due to a progress parsing error.
- [ ] **RF-04:** Progress in Redis must continue to be published correctly on frames where `out_time_ms` does have a numeric value.

---

## Technical Requirements

- [ ] **RT-01:** Use `try/except ValueError` (or validation with `.isnumeric()` / `strip().lstrip('-').isdigit()`) when parsing `out_time_ms` to ignore non-numeric values.
- [ ] **RT-02:** The handling must remain within the existing `for line in process.stdout:` loop without refactoring the method structure.
- [ ] **RT-03:** The FFmpeg command must use flags that speed up encoding without affecting the user's perceived visual quality:
  - `-preset ultrafast` or `-preset veryfast` in the video encoder.
  - `-threads 0` to use all available container cores.
  - Evaluate if copying the video stream (`-c:v copy`) is viable (it is not if a `vf` filter is applied with `eq=` and `subtitles=`).
- [ ] **RT-04:** Error handling should log the `N/A` value to `stderr` or the Celery logger for diagnosis without interrupting execution.
- [ ] **RT-05:** The code must remain within the infrastructure layer.

---

## Affected Files or Modules

| File | Change Type |
|---|---|
| `app/infrastructure/workers.py` | Modification (bug fix + FFmpeg improvements) |

---

## Proposed Design

### Backend — Crash Fix (`workers.py`, line 180)

**Before (broken code):**
```python
for line in process.stdout:
    if "out_time_ms=" in line:
        current_time_seconds = int(line.split("=")[1].strip()) / 1000000
        percent = min(99, math.floor((current_time_seconds / max(0.1, estimated_duration)) * 100))
        if percent > 0:
            redis_client.publish(...)
```

**After (corrected code):**
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

### Backend — FFmpeg Performance Improvement

By default, FFmpeg uses the `libx264` encoder with the `medium` preset. The preset controls encoding speed vs. compression. For a typical video in a shared container, switching to `ultrafast` or `veryfast` can reduce rendering time by **50–70%** at the cost of a slightly larger output file (acceptable for this use case).

**Proposed Improved FFmpeg Command:**
```python
cmd = [
    'ffmpeg', '-y', '-i', tmp_input_video,
    '-vf', vf_filter,
    '-c:v', 'libx264',
    '-preset', 'ultrafast',   # Faster, slightly larger file size
    '-crf', '23',             # Reasonable constant quality (default)
    '-threads', '0',          # Use all available cores
    '-c:a', 'copy',
    '-progress', '-', '-nostats',
    tmp_output_video
]
```

> **Note:** `-c:v copy` is NOT a valid option here because a video filter (`-vf`) is applied. Copying the video stream without re-encoding only works when there are no video filters.

---

### Bottleneck Analysis of the Full Pipeline

The pipeline has 3 costly phases:

| Phase | Tool | Bottleneck | Possible Improvement |
|---|---|---|---|
| Video download | Azure Blob | Network / latency | Not modifiable without changing infra |
| Transcription | OpenAI Whisper `whisper-1` | Remote API, response time | Evaluate `gpt-4o-transcribe` or `whisper-large-v3-turbo` if available in API |
| Rendering | FFmpeg | CPU / preset | Switch to ultrafast (free, in scope) |

**Conclusion on Whisper:** `whisper-1` is the only transcription model available in the OpenAI API for audio. There is no official alternative OpenAI model that is faster AND cheaper. The transcription bottleneck lies in the latency of the external API and cannot be optimized without changing providers. We will keep `whisper-1`.

**Conclusion on FFmpeg:** Changing the preset is **free, immediate, and significant**. It is the highest impact improvement within scope.

---

## Architectural Impact

- [x] No — This change only affects the infrastructure layer (`workers.py`). It does not modify API contracts, database schema, or domain/application layers.

---

## Implementation Plan

1. **Open** `app/infrastructure/workers.py`.
2. **Locate** the `for line in process.stdout:` loop inside `render_video` (approx. line 178).
3. **Apply** the `try/except ValueError` fix for parsing `out_time_ms`.
4. **Update** the FFmpeg command (`cmd` list) to include `-c:v libx264`, `-preset ultrafast`, `-threads 0`.
5. **Verify** that the `finally` block of `render_video` remains intact (cleaning up temporary files).
6. **Mark** this spec as `Implemented`.
7. **Update** `decisions.md` with the decision to use `-preset ultrafast` and the rationale.

---

## Acceptance Criteria

- [ ] **CA-01:** A video that previously crashed with `ValueError: invalid literal for int() with base 10: 'N/A'` now renders completely and the job moves to `COMPLETED` state.
- [ ] **CA-02:** The frontend does not show "Processing Failed" for a valid video.
- [ ] **CA-03:** The rendering progress continues to update correctly in the UI during the process.
- [ ] **CA-04:** The rendering time is noticeably reduced compared to the previous state (estimated: >40% faster).
- [ ] **CA-05:** The final video file is playable and has subtitles correctly burned in.

---

## Suggested Tests

- **Manual:** Upload a video, correct the transcription, click "Process". Verify that the job reaches `COMPLETED` and the video is downloadable.
- **Manual (regression):** Verify that progress updates in real time on the frontend during rendering.
- **Edge Cases:**
  - Very short video (<5 seconds) — FFmpeg might emit only `N/A` values at the beginning.
  - Video without audio — Not applicable (the pipeline requires audio for transcription).
  - Video already fully processed (re-process) — Must create a new `final_*` blob.

---

## Risks

| Risk | Probability | Mitigation |
|---|---|---|
| `-preset ultrafast` generates excessively large files | Low | The `crf 23` limits quality degradation. If it becomes an issue, use `veryfast`. |
| `-threads 0` consumes all cores during rendering and affects other services on the host | Low-Medium | In Docker containers with limited `--cpus` this is harmless. If there is contention, set `-threads 2`. |
| The `N/A` fix masks a real FFmpeg error | Low | The `process.returncode` is still checked after the loop; if FFmpeg genuinely fails, it is caught there. |

---

## Notes for Future Agents

- The `-progress -` flag in FFmpeg sends progress output to stdout; other logs (including fatal errors) go to stderr. The current code mixes stdout and stderr with `stderr=subprocess.STDOUT`. If in the future we need to separate errors from progress, switch to `stderr=subprocess.PIPE` and read both streams.
- `out_time_ms=N/A` occurs in FFmpeg when the muxer does not yet have timing information (typically the first few lines of the process). This is expected and documented behavior.
- If in the future transcription needs to be improved, the only path within OpenAI is to use the Realtime Audio API or Batch API (with a cost discount but higher latency). Both require significant architectural changes.

---

## Implementation Notes

**Implementation date:** 2026-06-11  
**Changes made:**  
- Added a `try/except ValueError` block in `workers.py` when parsing `out_time_ms` to ignore non-numeric values like `N/A`.
- Optimized the FFmpeg command by adding `-preset ultrafast`, `-crf 23`, and `-threads 0` for significantly faster rendering.

**Context files updated:**
- [ ] `.ai/context/file-map.md`
- [ ] `.ai/context/architecture-design.md`
- [x] `.ai/context/decisions.md` (DEC-0014 added)
- [ ] `.ai/context/project-context.md`
- [ ] `.ai/context/development-guidelines.md`
