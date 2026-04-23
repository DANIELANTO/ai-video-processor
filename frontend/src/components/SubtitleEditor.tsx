import { memo } from 'react';
import { useSubtitleEditor, type SubtitleSegment } from '../hooks/useSubtitleEditor';
import { formatTime, calculateDuration } from '../utils/subtitle.utils';

interface SubtitleEditorProps {
    initialSubtitles: SubtitleSegment[];
    onSubmitRender: (correctedSubtitles: SubtitleSegment[]) => void;
}

// Interface for subtitle row
interface SubtitleRowProps {
    index: number;
    formattedStart: string;
    formattedEnd: string;
    formattedDuration: string;
    text: string;
    onTextChange: (index: number, newText: string) => void;
}

const SubtitleRow = memo(function SubtitleRow({
    index, formattedStart, formattedEnd, formattedDuration, text, onTextChange
}: SubtitleRowProps) {
    return (
        <tr className="hover:bg-gray-50 transition-colors">
            <td className="px-4 py-3 text-sm text-gray-500">{index}</td>
            <td className="px-4 py-3 text-sm text-gray-500 font-mono">{formattedStart}</td>
            <td className="px-4 py-3 text-sm text-gray-500 font-mono">{formattedEnd}</td>
            <td className="px-4 py-3 text-sm text-gray-500 font-mono text-xs">{formattedDuration}</td>
            <td className="px-4 py-3">
                <input
                    type="text"
                    value={text}
                    onChange={(e) => onTextChange(index, e.target.value)}
                    aria-label={`Editar texto del subtítulo ${index}`}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-700 transition-colors"
                />
            </td>
        </tr>
    );
});

export function SubtitleEditor({ initialSubtitles, onSubmitRender }: SubtitleEditorProps) {
    const { subtitlesList, handleTextChange } = useSubtitleEditor(initialSubtitles);

    return (
        <div className="max-w-5xl mx-auto mt-8 p-6 bg-white rounded-xl shadow-lg border border-gray-100">
            <h3 className="text-2xl font-bold text-gray-800 mb-6 border-b pb-4">Subtitle Review</h3>

            <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr>
                            <th className="px-4 py-3 bg-gray-50 border-b-2 border-gray-200 text-sm font-semibold text-gray-600 tracking-wider">#</th>
                            <th className="px-4 py-3 bg-gray-50 border-b-2 border-gray-200 text-sm font-semibold text-gray-600 tracking-wider">Inicio</th>
                            <th className="px-4 py-3 bg-gray-50 border-b-2 border-gray-200 text-sm font-semibold text-gray-600 tracking-wider">Fin</th>
                            <th className="px-4 py-3 bg-gray-50 border-b-2 border-gray-200 text-sm font-semibold text-gray-600 tracking-wider">Duración</th>
                            <th className="px-4 py-3 bg-gray-50 border-b-2 border-gray-200 text-sm font-semibold text-gray-600 tracking-wider w-1/2">Texto Editable</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                        {subtitlesList.map((sub) => (
                            <SubtitleRow
                                key={sub.id}
                                index={sub.index}
                                formattedStart={formatTime(sub.start_time_ms)}
                                formattedEnd={formatTime(sub.end_time_ms)}
                                formattedDuration={formatTime(calculateDuration(sub.start_time_ms, sub.end_time_ms))}
                                text={sub.text}
                                onTextChange={handleTextChange}
                            />
                        ))}
                    </tbody>
                </table>
            </div>

            <button
                onClick={() => onSubmitRender(subtitlesList)}
                className="mt-8 w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 flex justify-center shadow-md"
            >
                Confirm Corrections and Render Video
            </button>
        </div>
    );
}