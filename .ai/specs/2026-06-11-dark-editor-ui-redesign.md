# Spec: Rediseño UI/UX — Dark Editor Theme + Sincronización Video/Subtítulos

## Estado

Implementada

---

## Contexto

La interfaz actual de **AI Video Editor** es una página blanca/clara básica con estados renderizados secuencialmente en una columna centrada. El componente principal de edición (`SubtitleEditor`) es una tabla HTML plana sin interactividad visual avanzada. Concretamente:

- **Fondo blanco** (`bg-gray-100`) con cards blancas: aspecto genérico de formulario web.
- **Sin preview de video**: durante la revisión de subtítulos, el usuario no puede ver el video que está editando.
- **Sin sincronización**: no hay forma de saber a qué momento del video corresponde cada fila de la tabla.
- **Sin resaltado activo**: no se indica cuál subtítulo está activo en el tiempo actual del video.
- **Scroll de página completa**: cuando hay muchos subtítulos, toda la página hace scroll, no solo la tabla.
- **Botones grandes y desproporcionales** al contenido.
- **Estados inconsistentes visualmente**: upload, progreso, revisión y completado tienen estilos distintos y descoordinados.

Todo esto produce una experiencia que se siente como un prototipo funcional y no como un producto terminado.

---

## Objetivo

Migrar la interfaz completa de la aplicación a un **tema oscuro profesional tipo editor de subtítulos/video**, donde:
1. Todos los estados (upload, progress, review, rendering, completed, error) tengan un aspecto visual coherente y oscuro.
2. La pantalla de revisión de subtítulos sea un **editor dual-panel**: preview del video a la izquierda, listado editable a la derecha.
3. El video y los subtítulos estén **sincronizados en tiempo real**: click en fila → seek en video; reproducción del video → resaltado automático de fila activa.
4. El subtítulo activo se **superponga sobre el video** como overlay mientras se reproduce.

**No se modifica ninguna lógica de backend ni los endpoints de la API.**

---

## Alcance

- Rediseño visual completo de `App.tsx` (todos los estados UI).
- Rediseño completo de `SubtitleEditor.tsx`.
- Creación del nuevo hook `useVideoSync.ts`.
- Actualización de `index.css` / `App.css` con design tokens del tema oscuro.
- Actualización de los archivos de contexto del harness post-implementación.

---

## Fuera de Alcance

- **Ningún cambio en backend**: ni endpoints, ni workers, ni ORM, ni dominio.
- **Sin cambios en `api.ts`**, `useJobStream.ts`, `useSubtitleEditor.ts` (salvo extensión no destructiva).
- **Sin cambios en el flujo de datos**: el estado de la aplicación (`jobId`, `stream.status`, `subtitlesToEdit`) permanece igual en `App.tsx`. Solo cambia el JSX/estilos.
- Sin añadir autenticación, multi-job support ni listado de trabajos.
- Sin añadir tests automatizados en esta iteración (el proyecto no tiene estructura de testing).
- Sin cambios en el esquema de base de datos (`SubtitleSegment` ya tiene `start_time_ms`, `end_time_ms`, `index`, `text`).

---

## Requisitos Funcionales

### RF-01: Tema oscuro en todos los estados
- [ ] Todos los estados de la UI usan la paleta de colores oscura definida en la sección de diseño.
- [ ] No debe quedar ningún `bg-white`, `bg-gray-100` ni `text-gray-900` en el diseño principal.

### RF-02: Estado Upload
- [ ] Pantalla de upload oscura con zona de drag-and-drop (o botón de browse) con borde discontinuo tenue.
- [ ] Nombre del archivo seleccionado visible en el UI antes de subir.
- [ ] Botón "Upload and Transcribe" visible solo cuando hay archivo seleccionado.

### RF-03: Estado Progress (TRANSCRIBING / RENDERING / PENDING / CONNECTED)
- [ ] Panel oscuro con barra de progreso estilizada.
- [ ] Texto descriptivo del estado actual (Analyzing audio / Generating video).
- [ ] Porcentaje visible con fuente monospace.

### RF-04: Estado Review — Layout Dual-Panel
- [ ] Panel izquierdo: preview del video con overlay del subtítulo activo.
- [ ] Panel derecho: listado/tabla editable de subtítulos con scroll interno independiente.
- [ ] Los dos paneles son visibles simultáneamente en resoluciones ≥ 1280px (desktop).
- [ ] En pantallas < 1024px, el video va arriba y la tabla debajo (layout vertical).
- [ ] El área total de la pantalla de revisión no produce scroll de página, solo scroll interno en la tabla.

### RF-05: Preview de Video con Subtítulo Overlay
- [ ] El `<video>` element carga el archivo seleccionado localmente (object URL) usando el `File` original.
- [ ] Sobre el video se muestra el texto del subtítulo activo en el tiempo actual (overlay posicionado en la parte inferior del video).
- [ ] Controles nativos del navegador (`controls`) habilitados.
- [ ] El video no hace autoplay al cargar la pantalla de revisión.

### RF-06: Sincronización Video → Subtítulo (auto-highlight)
- [ ] Mientras el video se reproduce, la fila del subtítulo correspondiente al `currentTime` del video se resalta automáticamente.
- [ ] La lista hace auto-scroll para mantener la fila activa visible.

### RF-07: Sincronización Subtítulo → Video (seek on click)
- [ ] Al hacer click en una fila de subtítulo, el video hace seek al `start_time_ms` de ese subtítulo (convertido a segundos).
- [ ] La fila seleccionada se resalta visualmente (color de acento activo).

### RF-08: Edición en tiempo real
- [ ] Al editar el texto de una fila en la tabla, el overlay del video se actualiza inmediatamente sin recargar ni renderizar nada.

### RF-09: Estado Completed
- [ ] Pantalla de éxito oscura con icono visual, mensaje de éxito y botón de descarga.
- [ ] Opción "Start New Video" claramente visible.

### RF-10: Estado Error (FAILED)
- [ ] Panel oscuro con mensaje de error visible y opción de iniciar nuevo video.

### RF-11: Botón "Discard and Start New Video"
- [ ] Visible en todos los estados donde hay un job activo.
- [ ] Proporcional al nuevo diseño (no gigante).

---

## Requisitos Técnicos

### RT-01: Stack sin cambios
- [ ] React 19, TypeScript, Vite, TailwindCSS v4. No se añaden nuevas librerías de UI externa.

### RT-02: Nuevo hook `useVideoSync`
- [ ] Acepta: ref del elemento `<video>`, lista de `SubtitleSegment[]`.
- [ ] Retorna: `activeIndex` (índice del subtítulo activo o `null`), `activeText` (texto activo o `''`), `seekTo(startTimeMs: number)`.
- [ ] Usa `timeupdate` event del video para actualizar `activeIndex` en tiempo real.
- [ ] No depende de ninguna librería externa.

### RT-03: Object URL del archivo local
- [ ] En `App.tsx`, se crea un `objectURL` del `File` original con `URL.createObjectURL(file)`.
- [ ] El URL se revoca en cleanup para evitar memory leaks.
- [ ] Este URL se pasa a `SubtitleEditor` como prop `videoSrc`.

### RT-04: Auto-scroll a fila activa
- [ ] Usar `useEffect` + `ref` sobre la fila activa y llamar `scrollIntoView({ behavior: 'smooth', block: 'nearest' })`.

### RT-05: TailwindCSS v4 — Design Tokens
- [ ] Definir variables CSS custom en `index.css` (bajo `:root` o `@theme`).
- [ ] Los colores del tema se usan consistentemente en todos los componentes.

### RT-06: No romper contratos existentes
- [ ] `SubtitleEditor` sigue aceptando `initialSubtitles` y `onSubmitRender` con las mismas firmas.
- [ ] `useSubtitleEditor` no se modifica.

---

## Archivos o Módulos Afectados

| Archivo | Tipo de cambio |
|---|---|
| `frontend/src/App.tsx` | Modificación mayor — JSX, layout, object URL, paso de props al editor |
| `frontend/src/components/SubtitleEditor.tsx` | Modificación mayor — layout dual-panel, video, overlay, sincronización |
| `frontend/src/hooks/useVideoSync.ts` | **Creación nueva** — lógica de sincronización video/subtítulos |
| `frontend/src/index.css` | Modificación — design tokens oscuros, reset global |
| `frontend/src/App.css` | Modificación menor o consolidación en index.css |
| `.ai/context/file-map.md` | Actualizar — nuevo hook `useVideoSync.ts` |
| `.ai/context/development-guidelines.md` | Actualizar — patrón de video sync |
| `.ai/context/decisions.md` | Agregar DEC-0013 — Object URL para preview local |

---

## Diseño Propuesto

### Paleta de Colores (Design Tokens)

```css
/* index.css */
:root {
  --bg-primary:     #0d1117;   /* Fondo principal — casi negro azulado */
  --bg-surface:     #161b22;   /* Paneles/cards */
  --bg-elevated:    #21262d;   /* Hover, inputs */
  --border-subtle:  #30363d;   /* Bordes sutiles */
  --text-primary:   #e6edf3;   /* Texto principal */
  --text-secondary: #8b949e;   /* Texto secundario */
  --text-muted:     #484f58;   /* Texto tenue */
  --accent-blue:    #1f6feb;   /* Acento acciones */
  --accent-amber:   #e3b341;   /* Subtítulo activo */
  --success:        #3fb950;   /* Estado completado */
  --error:          #f85149;   /* Estado error */
}
```

### Layout de Estado Review (Dual-Panel)

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
│  │──────────────────│  │  │ 2  │ 00:04  │ 00:07  │ [edit] │← activo (amber)
│  │  "subtitle text" │  │  │ 3  │ 00:08  │ 00:11  │ [edit] │  │
│  └──────────────────┘  │  │ ...                            │  │
│  [▶ 00:04 / 01:22]     │  └────────────────────────────────┘  │
│                        │  [Confirm & Render Video →]          │
└────────────────────────┴──────────────────────────────────────┘

Mobile (<1024px): video arriba, tabla debajo (layout vertical).
```

### Hook `useVideoSync` — Firma Completa

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
        return prev === next ? prev : next; // evitar re-renders innecesarios
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

## Plan de Implementación

**Paso 1 — Design Tokens y App.tsx shell**
- Definir variables CSS del tema en `index.css`.
- Rediseñar layout global (header, contenedor, footer con "Discard").
- Aplicar tema oscuro a estados de Upload y Progress.
- Verificar visualmente en browser.

**Paso 2 — Hook `useVideoSync`**
- Crear `frontend/src/hooks/useVideoSync.ts`.
- Implementar lógica `timeupdate` + `seekTo` + `activeIndex`.

**Paso 3 — Object URL en `App.tsx`**
- Añadir estado `videoObjectUrl`.
- Crear/revocar object URL al seleccionar archivo / resetear.
- Pasar `videoSrc` a `SubtitleEditor`.

**Paso 4 — Rediseño `SubtitleEditor.tsx` — Layout Dual-Panel**
- Implementar layout dos columnas.
- Panel izquierdo: `<video>` element.
- Panel derecho: tabla con scroll interno, estilos oscuros.

**Paso 5 — Integración de Sincronización**
- Instanciar `useVideoSync` en `SubtitleEditor`.
- Conectar `seekTo` al click en fila.
- Resaltar fila activa por `activeIndex`.
- Implementar auto-scroll a fila activa.
- Implementar overlay del subtítulo sobre el video.

**Paso 6 — Estados restantes y polish**
- Rediseñar estados Completed y Error.
- Ajustar proporciones, espaciado y micro-detalles.

**Paso 7 — Actualizar harness**
- Actualizar `file-map.md`, `decisions.md`, `development-guidelines.md`.
- Marcar spec como `Implementada`.

---

## Criterios de Aceptación

- [ ] **CA-01:** La app no tiene fondos blancos como tema principal. Todos los estados son oscuros.
- [ ] **CA-02:** El estado de upload muestra zona de selección estilizada oscura.
- [ ] **CA-03:** El estado de progreso muestra barra de progreso oscura con % correcto.
- [ ] **CA-04:** El estado de revisión muestra video a la izquierda y tabla a la derecha en desktop.
- [ ] **CA-05:** El video carga y reproduce el archivo seleccionado localmente.
- [ ] **CA-06:** El subtítulo activo se superpone sobre el video como overlay.
- [ ] **CA-07:** Click en fila → video hace seek al `start_time_ms` de ese subtítulo.
- [ ] **CA-08:** Reproducción del video → fila activa cambia automáticamente con auto-scroll.
- [ ] **CA-09:** Edición del texto → overlay del video se actualiza en tiempo real.
- [ ] **CA-10:** Botón "Confirm & Render" dispara el render con las correcciones.
- [ ] **CA-11:** Estado completed muestra botón de descarga y opción de nuevo video.
- [ ] **CA-12:** Estado error muestra mensaje y opción de nuevo video.
- [ ] **CA-13:** Tabla de subtítulos tiene scroll interno; la página NO scrollea con muchos subtítulos.
- [ ] **CA-14:** En pantallas < 1024px, video y tabla se apilan verticalmente.
- [ ] **CA-15:** Los contratos de `SubtitleEditor` (`initialSubtitles`, `onSubmitRender`) no cambian.
- [ ] **CA-16:** El flujo completo upload → transcribe → review → render → download funciona.

---

## Pruebas Sugeridas

- **Manual — Flujo completo:** Seleccionar MP4 → upload → transcribir → editar → render → descargar.
- **Manual — Sincronización:** Reproducir video en review → verificar que la fila activa cambia. Click en fila → verificar seek.
- **Manual — Overlay:** Reproducir → verificar texto sobre video. Editar texto → verificar actualización del overlay.
- **Manual — Responsive:** Reducir ventana a < 1024px → verificar layout vertical.
- **Caso borde:** Subtítulo con texto vacío → overlay no muestra nada.
- **Caso borde:** Video en pausa entre subtítulos → sin overlay.
- **Caso borde:** Lista de 50+ subtítulos → scroll interno, no scroll de página.
- **Caso borde:** Recargar página en estado `REVIEW_PENDING` → subtítulos cargan desde API pero el video no se muestra (limitación documentada).

---

## Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| `File` original no disponible si el usuario recarga la página en `REVIEW_PENDING` | Alta | Limitación documentada. La tabla funciona sin video. El render no se ve afectado (Azure tiene el video). |
| Memory leak por no revocar el object URL | Media | Revocar en `handleReset` y en cleanup del `useEffect` en `App.tsx`. |
| TailwindCSS v4 — compatibilidad con variables CSS custom | Baja | TailwindCSS v4 soporta `@theme`. Si hay problemas, usar `:root` CSS estándar. |
| `timeupdate` frecuente → demasiados re-renders | Baja | Actualizar `activeIndex` solo cuando cambia el subtítulo activo (comparación previa). |
| Overlay cubre controles del video | Baja | Posicionar overlay con `bottom: 48px` para no tapar la barra de controles nativa. |
| Codec no soportado por browser | Baja | Solo se acepta `video/mp4` (`accept="video/mp4"` en el input). MP4/H.264 es universal. |

---

## Notas para Futuros Agentes

- El `File` original del usuario vive en `App.tsx` como `const [file, setFile]`. Para el preview se convierte a ObjectURL y se pasa a `SubtitleEditor` como prop `videoSrc`. **No se puede recuperar si la página se recarga** (limitación del browser).
- `SubtitleSegment.start_time_ms` y `end_time_ms` están en **milisegundos**. `HTMLVideoElement.currentTime` está en **segundos**. Conversión: `video.currentTime * 1000` y `start_time_ms / 1000`.
- TailwindCSS v4 usa `@import "tailwindcss"` en `index.css`. Verificar si el proyecto usa `@theme {}` o `:root {}` antes de implementar tokens.
- `useVideoSync` es **complementario** a `useSubtitleEditor`, no lo reemplaza. Ambos se usan juntos en `SubtitleEditor`.
- Para el auto-scroll, usar un `ref` de callback o un `ref` de objeto sobre el `<tr>` activo y llamar `scrollIntoView` en un `useEffect([activeIndex])`.

---

## Notas de Implementación

_(Llenar después de implementar)_

**Fecha de implementación:** 2026-06-11  
**Cambios realizados:**  
- Implementado el nuevo diseño oscuro en toda la UI (`index.css`, `App.tsx`).
- Refactorizado `SubtitleEditor.tsx` a un layout de doble panel con previsualización del video.
- Creado `useVideoSync.ts` que permite saltar a las diferentes secciones del video al seleccionar un subtítulo.

**Archivos de contexto actualizados:**
- [x] `.ai/context/file-map.md`
- [ ] `.ai/context/architecture-design.md`
- [x] `.ai/context/decisions.md`
- [ ] `.ai/context/project-context.md`
- [x] `.ai/context/development-guidelines.md`
