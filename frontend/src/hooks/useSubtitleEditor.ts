import { useState, useCallback, useMemo } from 'react';

export interface SubtitleSegment {
    id?: string;
    index: number;
    start_time_ms: number;
    end_time_ms: number;
    text: string;
}

export const useSubtitleEditor = (initialSubtitles: SubtitleSegment[]) => {
    // 1. Lazy initialization
    const [subtitlesMap, setSubtitlesMap] = useState<Record<number, SubtitleSegment>>(() => {
        const map: Record<number, SubtitleSegment> = {};
        initialSubtitles.forEach(sub => {
            map[sub.index] = { ...sub, id: sub.id || crypto.randomUUID() };
        });
        return map;
    });

    // 2. Handle text changes
    const handleTextChange = useCallback((index: number, newText: string) => {
        if (newText.length > 200) return;

        setSubtitlesMap(prev => ({
            ...prev,
            [index]: { ...prev[index], text: newText }
        }));
    }, []);

    // 3. Memoized list
    const subtitlesList = useMemo(() => {
        return Object.values(subtitlesMap).sort((a, b) => a.index - b.index);
    }, [subtitlesMap]);

    return { subtitlesList, handleTextChange };
};