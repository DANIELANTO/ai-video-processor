# Spec: UI/UX Redesign — Dark Editor Theme + Video/Subtitle Synchronization

## Status

Implemented

---

## Context

The current **AI Video Editor** interface is a basic light/white page with states rendered sequentially in a centered column. The main editing component (`SubtitleEditor`) is a flat HTML table without advanced visual interactivity. Specifically:

- **White background** (`bg-gray-100`) with white cards: generic web form appearance.
- **No video preview**: during subtitle review, the user cannot see the video they are editing.
- **No synchronization**: there is no way to know which point in the video each row of the table corresponds to.
- **No active highlight**: there is no indication of which subtitle is active at the current video time.
- **Full-page scroll**: when there are many subtitles, the entire page scrolls, not just the table.
- **Large buttons** disproportionate to the content.
- **Visually inconsistent states**: upload, progress, review, and completed have different, uncoordinated styles.

All of this produces an experience that feels like a functional prototype rather than a finished product.

---

## Objective

Migrate the entire application interface to a **professional dark theme typical of subtitle/video editors**, where:
1. All states (upload, progress, review, rendering, completed, error) have a coherent and professional dark visual appearance.
2. The subtitle review screen is a **dual-panel editor**: video preview on the left, editable list on the right.
3. The video and subtitles are **synchronized in real time**: clicking a row performs a seek in the video; playing the video automatically highlights the active row.
4. The active subtitle is **overlaid on the video** as an overlay during playback.

**No backend logic or API endpoints are modified.**

---

## Scope

- Complete visual redesign of `App.tsx` (all UI states).
- Complete redesign of `SubtitleEditor.tsx`.
- Creation of the new `useVideoSync.ts` hook.
- Update of `index.css` / `App.css` with dark theme design tokens.
- Update of harness context files post-implementation.

---

## Out of Scope

- **No backend changes**: no endpoints, workers, ORM, or domain changes.
- **No changes to `api.ts`**, `useJobStream.ts`, or `useSubtitleEditor.ts` (except for non-destructive extensions).
- **No changes to data flow**: the application state (`jobId`, `stream.status`, `subtitlesToEdit`) remains the same in `App.tsx`. Only the JSX/styles change.
- No addition of authentication, multi-job support, or job lists.
- No addition of automated tests in this iteration (the project does not have a testing structure).
- No changes to the database schema (`SubtitleSegment` already has `start_time_ms`, `end_time_ms`, `index`, `text`).

---

## Functional Requirements

### RF-01: Dark theme across all states
- [ ] All UI states use the dark color palette defined in the design section.
- [ ] No `bg-white`, `bg-gray-100`, or `text-gray-900` should remain in the main design.

### RF-02: Upload State
- [ ] Dark upload screen with a styled drag-and-drop area (or browse button) with a subtle dashed border.
- [ ] Selected file name visible in the UI before uploading.
- [ ] "Upload and Transcribe" button visible only when a file is selected.

### RF-03: Progress State (TRANSCRIBING / RENDERING / PENDING / CONNECTED)
- [ ] Dark panel with a styled progress bar.
- [ ] Descriptive text of the current state (e.g., "Analyzing audio" / "Generating video").
- [ ] Percentage visible with a monospace font.

### RF-04: Review State — Dual-Panel Layout
- [ ] Left panel: video preview with active subtitle overlay.
- [ ] Right panel: editable list/table of subtitles with independent internal scroll.
- [ ] Both panels are visible simultaneously on resolutions ≥ 1280px (desktop).
- [ ] On screens < 1024px, the video goes on top and the table below (vertical layout).
- [ ] The total area of the review screen does not produce page scroll; only internal scroll in the table.

### RF-05: Video Preview with Subtitle Overlay
- [ ] The `<video>` element loads the locally selected file (object URL) using the original `File`.
- [ ] The text of the active subtitle at the current time is shown as an overlay on the video (positioned at the bottom of the video).
- [ ] Native browser controls (`controls`) enabled.
- [ ] Video does not autoplay when loading the review screen.

### RF-06: Video → Subtitle Synchronization (auto-highlight)
- [ ] While the video is playing, the subtitle row corresponding to the video's `currentTime` is automatically highlighted.
- [ ] The list auto-scrolls to keep the active row visible.

### RF-07: Subtitle → Video Synchronization (seek on click)
- [ ] Clicking a subtitle row seeks the video to the `start_time_ms` of that subtitle (converted to seconds).
- [ ] The selected row is visually highlighted (active accent color).

### RF-08: Real-time Editing
- [ ] Editing the text of a row in the table updates the video overlay immediately without reloading or rendering anything.

### RF-09: Completed State
- [ ] Dark success screen with a visual icon, success message, and download button.
- [ ] "Start New Video" option clearly visible.

### RF-10: Error State (FAILED)
- [ ] Dark panel showing the error message and an option to start a new video.

### RF-11: "Discard and Start New Video" Button
- [ ] Visible in all states where there is an active job.
- [ ] Proportional to the new design (not giant).

---

## Technical Requirements

### RT-01: Stack without changes
- [ ] React 19, TypeScript, Vite, TailwindCSS v4. No external UI library is added.

### RT-02: New `useVideoSync` hook
- [ ] Accepts: `<video>` element ref, list of `SubtitleSegment[]`.
- [ ] Returns: `activeIndex` (index of active subtitle or `null`), `activeText` (active text or `''`), `seekTo(startTimeMs: number)`.
- [ ] Uses the video's `timeupdate` event to update `activeIndex` in real time.
- [ ] Does not depend on any external library.

### RT-03: Local File Object URL
- [ ] In `App.tsx`, an `objectURL` of the original `File` is created with `URL.createObjectURL(file)`.
- [ ] The URL is revoked in cleanup to avoid memory leaks.
- [ ] This URL is passed to `SubtitleEditor` as the `videoSrc` prop.

### RT-04: Auto-scroll to active row
- [ ] Use `useEffect` + `ref` on the active row and call `scrollIntoView({ behavior: 'smooth', block: 'nearest' })`.

### RT-05: TailwindCSS v4 — Design Tokens
- [ ] Define custom CSS variables in `index.css` (under `:root` or `@theme`).
- [ ] Theme colors are used consistently across all components.

### RT-06: Do not break existing contracts
- [ ] `SubtitleEditor` continues to accept `initialSubtitles` and `onSubmitRender` with the same signatures.
- [ ] `useSubtitleEditor` is not modified.

---

## Affected Files or Modules

| File | Change Type |
|---|---|
| `frontend/src/App.tsx` | Major modification — JSX, layout, object URL, passing props to editor |
| `frontend/src/components/SubtitleEditor.tsx` | Major modification — dual-panel layout, video, overlay, synchronization |
| `frontend/src/hooks/useVideoSync.ts` | **New file** — video/subtitle synchronization logic |
| `frontend/src/index.css` | Modification — dark design tokens, global reset |
| `frontend/src/App.css` | Minor modification or consolidation into index.css |
| `.ai/context/file-map.md` | Update — new hook `useVideoSync.ts` |
| `.ai/context/development-guidelines.md` | Update — video sync pattern |
| `.ai/context/decisions.md` | Add DEC-0013 — Object URL for local preview |

---

## Proposed Design

### Color Palette (Design Tokens)

```css
/* index.css */
:root {
  --bg-primary:     #0d1117;   /* Main background — near-black blue */
  --bg-surface:     #161b22;   /* Panels/cards */
  --bg-elevated:    #21262d;   /* Hover, inputs */
  --border-subtle:  #30363d;   /* Subtle borders */
  --text-primary:   #e6edf3;   /* Primary text */
  --text-secondary: #8b949e;   /* Secondary text */
  --text-muted:     #484f58;   /* Dimmed text */
  --accent-blue:    #1f6feb;   /* Action accent */
  --accent-amber:   #e3b341;   /* Active subtitle */
  --success:        #3fb950;   /* Completed state */
  --error:          #f85149;   /* Error state */
}
```

### Review State Layout (Dual-Panel)

```
Desktop (≥1024px):
┌───────────────────────────────────────────────────────────────┐
│  Header: "AI Video Editor"                    [Discard ×]     │
├────────────────────────┬──────────────────────────────────────┤
│  VIDEO PREVIEW         │  SUBTITLE EDITOR                     │
│  ┌──────────────────┐  │  ┌────────────────────────────────┐  │
│  │                  │  │  │ #  │ Start  │ End    │ Text    │  │
│  │  [video player]  │  │  ├────────────────────────────────┤  │
│  │                  │  │  │ 1  │ 00:01  │ 00:03  │ [edit] │  │
│  │──────────────────│  │  │ 2  │ 00:04  │ 00:07  │ [edit] │← active (amber)
│  │  "subtitle text" │  │  │ 3  │ 00:08  │ 00:11  │ [edit] │  │
│  │                  │  │  │ ...                            │  │
│  └──────────────────┘  │  └────────────────────────────────┘  │
│  [▶ 00:04 / 01:22]     │  [Confirm & Render Video →]          │
└────────────────────────┴──────────────────────────────────────┘

Mobile (<1024px): video on top, table below (vertical layout).
```

### Hook `useVideoSync` — Complete Signature

```typescript
// frontend/src/hooks/useVideoSync.ts
import { useState, useEffect, useCallback } from 'react';
import type { SubtitleSegment } from './useSubtitleEditor';

interface UseVideoSyncResult {
  activeIndex: number | null;
  activeText: string;
  seekTo: (startTimeMs: number) => void;
}

export function useVideoSync(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  subtitles: SubtitleSegment[]
): UseVideoSyncResult {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const currentMs = video.currentTime * 1000;
      const active = subtitles.find(
        s => currentMs >= s.start_time_ms && currentMs < s.end_time_ms
      );
      setActiveIndex(prev => {
        const next = active?.index ?? null;
        return prev === next ? prev : next; // avoid unnecessary re-renders
      });
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    return () => video.removeEventListener('timeupdate', handleTimeUpdate);
  }, [videoRef, subtitles]);

  const seekTo = useCallback((startTimeMs: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = startTimeMs / 1000;
    }
  }, [videoRef]);

  const activeText = subtitles.find(s => s.index === activeIndex)?.text ?? '';

  return { activeIndex, activeText, seekTo };
}
```

---

## Implementation Plan

**Step 1 — Design Tokens and App.tsx shell**
- Define theme CSS variables in `index.css`.
- Redesign global layout (header, container, footer with "Discard").
- Apply dark theme to Upload and Progress states.
- Verify visually in the browser.

**Step 2 — Hook `useVideoSync`**
- Create `frontend/src/hooks/useVideoSync.ts`.
- Implement `timeupdate` + `seekTo` + `activeIndex` logic.

**Step 3 — Object URL in `App.tsx`**
- Add `videoObjectUrl` state.
- Create/revoke object URL on file selection / reset.
- Pass `videoSrc` to `SubtitleEditor`.

**Step 4 — Redesign `SubtitleEditor.tsx` — Dual-Panel Layout**
- Implement two-column layout.
- Left panel: `<video>` element.
- Right panel: table with internal scroll, dark styles.

**Step 5 — Synchronization Integration**
- Instantiate `useVideoSync` in `SubtitleEditor`.
- Connect `seekTo` to row click.
- Highlight active row based on `activeIndex`.
- Implement auto-scroll to active row.
- Implement subtitle overlay on the video.

**Step 6 — Remaining states and polish**
- Redesign Completed and Error states.
- Adjust proportions, spacing, and micro-details.

**Step 7 — Update harness**
- Update `file-map.md`, `decisions.md`, `development-guidelines.md`.
- Mark spec as `Implemented`.

---

## Acceptance Criteria

- [ ] **CA-01:** The app has no white backgrounds as the main theme. All states are dark.
- [ ] **CA-02:** The upload state shows a dark, styled selection zone.
- [ ] **CA-03:** The progress state shows a dark progress bar with the correct %.
- [ ] **CA-04:** The review state shows the video on the left and the table on the right in desktop.
- [ ] **CA-05:** The video loads and plays the locally selected file.
- [ ] **CA-06:** The active subtitle is overlaid on the video as an overlay.
- [ ] **CA-07:** Row click → video seeks to `start_time_ms` of that subtitle.
- [ ] **CA-08:** Playing the video → active row changes automatically with auto-scroll.
- [ ] **CA-09:** Editing text → video overlay updates in real time.
- [ ] **CA-10:** "Confirm & Render" button triggers the render with corrections.
- [ ] **CA-11:** Completed state shows download button and start new video option.
- [ ] **CA-12:** Error state shows message and start new video option.
- [ ] **CA-13:** Subtitle table has internal scroll; the page does NOT scroll with many subtitles.
- [ ] **CA-14:** On screens < 1024px, video and table stack vertically.
- [ ] **CA-15:** Existing `SubtitleEditor` contracts (`initialSubtitles`, `onSubmitRender`) do not change.
- [ ] **CA-16:** Complete flow upload → transcribe → review → render → download works.

---

## Suggested Tests

- **Manual — Complete Flow:** Select MP4 → upload → transcribe → edit → render → download.
- **Manual — Sync:** Play video in review → verify active row changes. Click row → verify seek.
- **Manual — Overlay:** Play → verify text on video. Edit text → verify overlay updates.
- **Manual — Responsive:** Reduce window to < 1024px → verify vertical layout.
- **Edge Case:** Subtitle with empty text → overlay shows nothing.
- **Edge Case:** Video paused between subtitles → no overlay.
- **Edge Case:** List of 50+ subtitles → internal scroll, no page scroll.
- **Edge Case:** Reload page in `REVIEW_PENDING` state → subtitles load from API but video does not show (documented limitation).

---

## Risks

| Risk | Probability | Mitigation |
|---|---|---|
| Original `File` not available if user reloads page in `REVIEW_PENDING` | High | Documented limitation. Table works without video. Render is unaffected (Azure has the video). |
| Memory leak due to not revoking the object URL | Medium | Revoke in `handleReset` and in `App.tsx` `useEffect` cleanup. |
| TailwindCSS v4 — compatibility with custom CSS variables | Low | TailwindCSS v4 supports `@theme`. If issues occur, use standard `:root` CSS. |
| Frequent `timeupdate` → too many re-renders | Low | Update `activeIndex` only when the active subtitle changes (previous comparison check). |
| Overlay covers video controls | Low | Position overlay with `bottom: 48px` to avoid covering the native control bar. |
| Codec not supported by browser | Low | Only accept `video/mp4` (`accept="video/mp4"` on input). MP4/H.264 is universal. |

---

## Notes for Future Agents

- The original user `File` lives in `App.tsx` as `const [file, setFile]`. For preview, it is converted to an ObjectURL and passed to `SubtitleEditor` as the `videoSrc` prop. **It cannot be recovered if the page is reloaded** (browser limitation).
- `SubtitleSegment.start_time_ms` and `end_time_ms` are in **milliseconds**. `HTMLVideoElement.currentTime` is in **seconds**. Conversion: `video.currentTime * 1000` and `start_time_ms / 1000`.
- TailwindCSS v4 uses `@import "tailwindcss"` in `index.css`. Check if the project uses `@theme {}` or `:root {}` before implementing tokens.
- `useVideoSync` is **complementary** to `useSubtitleEditor`, it does not replace it. Both are used together in `SubtitleEditor`.
- For auto-scroll, use a callback ref or an object ref on the active `<tr>` and call `scrollIntoView` in a `useEffect([activeIndex])`.

---

## Implementation Notes

**Implementation date:** 2026-06-11  
**Changes made:**  
- Implemented the new dark design across the entire UI (`index.css`, `App.tsx`).
- Refactored `SubtitleEditor.tsx` to a dual-panel layout with video preview.
- Created `useVideoSync.ts` hook to allow jumping to different video sections on subtitle row click.

**Context files updated:**
- [x] `.ai/context/file-map.md`
- [ ] `.ai/context/architecture-design.md`
- [x] `.ai/context/decisions.md`
- [ ] `.ai/context/project-context.md`
- [x] `.ai/context/development-guidelines.md`
