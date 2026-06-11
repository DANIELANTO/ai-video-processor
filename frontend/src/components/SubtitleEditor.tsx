import { memo, useRef, useEffect } from 'react';
import { useSubtitleEditor, type SubtitleSegment } from '../hooks/useSubtitleEditor';
import { useVideoSync } from '../hooks/useVideoSync';
import { formatTime } from '../utils/subtitle.utils';

interface SubtitleEditorProps {
    initialSubtitles: SubtitleSegment[];
    onSubmitRender: (correctedSubtitles: SubtitleSegment[]) => void;
    videoSrc: string | null;
}

// Interface for subtitle row
interface SubtitleRowProps {
    index: number;
    formattedStart: string;
    formattedEnd: string;
    text: string;
    isActive: boolean;
    onTextChange: (index: number, newText: string) => void;
    onClick: () => void;
}

const SubtitleRow = memo(function SubtitleRow({
    index, formattedStart, formattedEnd, text, isActive, onTextChange, onClick
}: SubtitleRowProps) {
    const rowRef = useRef<HTMLTableRowElement>(null);

    // Auto-scroll logic
    useEffect(() => {
        if (isActive && rowRef.current) {
            rowRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }, [isActive]);

    return (
        <tr 
            ref={rowRef}
            onClick={onClick}
            className={`cursor-pointer transition-colors border-b border-border-subtle group ${isActive ? 'bg-accent-blue/10 border-l-2 border-l-accent-amber' : 'hover:bg-bg-elevated border-l-2 border-l-transparent'}`}
        >
            <td className={`px-3 py-3 text-xs ${isActive ? 'text-accent-amber font-bold' : 'text-text-muted'}`}>{index}</td>
            <td className="px-2 py-3 text-xs text-text-secondary font-mono">{formattedStart}</td>
            <td className="px-2 py-3 text-xs text-text-secondary font-mono">{formattedEnd}</td>
            <td className="px-4 py-3">
                <textarea
                    value={text}
                    onChange={(e) => onTextChange(index, e.target.value)}
                    onClick={(e) => e.stopPropagation()} // Prevent triggering row click when typing
                    aria-label={`Editar texto del subtítulo ${index}`}
                    className={`w-full h-16 px-3 py-2 border rounded-md focus:outline-none focus:ring-1 focus:ring-accent-blue transition-colors text-sm resize-none ${isActive ? 'bg-bg-elevated border-accent-blue text-text-primary' : 'bg-bg-primary border-border-subtle text-text-primary group-hover:bg-bg-surface'}`}
                />
            </td>
        </tr>
    );
});

export function SubtitleEditor({ initialSubtitles, onSubmitRender, videoSrc }: SubtitleEditorProps) {
    const { subtitlesList, handleTextChange } = useSubtitleEditor(initialSubtitles);
    const videoRef = useRef<HTMLVideoElement>(null);
    const { activeIndex, activeText, seekTo } = useVideoSync(videoRef, subtitlesList);

    return (
        <div className="w-full">
            <div className="flex flex-col lg:flex-row gap-6">
                
                {/* Left Panel: Video Preview */}
                <div className="lg:w-1/2 xl:w-3/5 flex flex-col gap-4">
                    <div className="bg-bg-surface rounded-xl border border-border-subtle overflow-hidden relative shadow-md">
                        {videoSrc ? (
                            <div className="relative w-full aspect-video bg-black">
                                <video 
                                    ref={videoRef}
                                    src={videoSrc} 
                                    controls 
                                    className="w-full h-full object-contain"
                                    preload="metadata"
                                />
                                {/* Subtitle Overlay */}
                                {activeText && (
                                    <div className="absolute bottom-16 left-0 right-0 flex justify-center px-8 pointer-events-none">
                                        <span className="bg-black/60 text-white font-medium text-lg md:text-xl text-center px-4 py-1 rounded shadow-lg backdrop-blur-sm tracking-wide" style={{ textShadow: '1px 1px 2px black, 0 0 1em black' }}>
                                            {activeText}
                                        </span>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="w-full aspect-video bg-bg-elevated flex flex-col items-center justify-center text-text-muted">
                                <svg className="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                                <span>Video preview not available</span>
                                <span className="text-xs mt-1">Please re-upload the video</span>
                            </div>
                        )}
                        <div className="p-4 border-t border-border-subtle flex justify-between items-center bg-bg-surface">
                            <h3 className="text-sm font-semibold text-text-primary">Preview</h3>
                            {activeIndex !== null && (
                                <span className="text-xs bg-bg-elevated px-2 py-1 rounded text-accent-amber border border-border-subtle">
                                    Editing Subtitle #{activeIndex}
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right Panel: Subtitle List */}
                <div className="lg:w-1/2 xl:w-2/5 flex flex-col bg-bg-surface rounded-xl border border-border-subtle shadow-md overflow-hidden" style={{ maxHeight: '600px' }}>
                    <div className="p-4 border-b border-border-subtle flex justify-between items-center shrink-0 bg-bg-elevated">
                        <h3 className="text-sm font-semibold text-text-primary flex items-center">
                            <svg className="w-4 h-4 mr-2 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
                            Transcript Editor
                        </h3>
                        <span className="text-xs text-text-secondary font-mono bg-bg-primary px-2 py-1 rounded border border-border-subtle">
                            {subtitlesList.length} rows
                        </span>
                    </div>

                    <div className="overflow-y-auto flex-grow bg-bg-surface custom-scrollbar">
                        <table className="w-full text-left border-collapse">
                            <thead className="sticky top-0 bg-bg-surface z-10 shadow-sm border-b border-border-subtle">
                                <tr>
                                    <th className="px-3 py-2 text-xs font-medium text-text-secondary uppercase tracking-wider w-10">#</th>
                                    <th className="px-2 py-2 text-xs font-medium text-text-secondary uppercase tracking-wider w-16">Start</th>
                                    <th className="px-2 py-2 text-xs font-medium text-text-secondary uppercase tracking-wider w-16">End</th>
                                    <th className="px-4 py-2 text-xs font-medium text-text-secondary uppercase tracking-wider">Text</th>
                                </tr>
                            </thead>
                            <tbody>
                                {subtitlesList.map((sub) => (
                                    <SubtitleRow
                                        key={sub.id}
                                        index={sub.index}
                                        formattedStart={formatTime(sub.start_time_ms)}
                                        formattedEnd={formatTime(sub.end_time_ms)}
                                        text={sub.text}
                                        isActive={sub.index === activeIndex}
                                        onTextChange={handleTextChange}
                                        onClick={() => seekTo(sub.start_time_ms)}
                                    />
                                ))}
                            </tbody>
                        </table>
                    </div>
                    
                    <div className="p-4 border-t border-border-subtle shrink-0 bg-bg-elevated">
                        <button
                            onClick={() => onSubmitRender(subtitlesList)}
                            className="w-full bg-accent-blue hover:bg-accent-blue-hover text-white font-medium py-3 px-4 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-accent-blue/50 flex justify-center items-center shadow-md shadow-accent-blue/10 text-sm"
                        >
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"></path></svg>
                            Confirm Corrections & Render
                        </button>
                    </div>
                </div>
            </div>
            
            <style>{`
                .custom-scrollbar::-webkit-scrollbar { width: 6px; }
                .custom-scrollbar::-webkit-scrollbar-track { background: var(--color-bg-surface); }
                .custom-scrollbar::-webkit-scrollbar-thumb { background-color: var(--color-border-subtle); border-radius: 20px; }
            `}</style>
        </div>
    );
}