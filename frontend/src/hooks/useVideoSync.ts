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
                return prev === next ? prev : next;
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
