import { useState, useRef, useEffect } from 'react';
import { type SubtitleSegment } from './hooks/useSubtitleEditor';
import { useJobStream } from './hooks/useJobStream';
import { videoApi } from './services/api';
import { SubtitleEditor } from './components/SubtitleEditor';

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [subtitlesToEdit, setSubtitlesToEdit] = useState<SubtitleSegment[] | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Custom hook for Server-Sent Events
  const stream = useJobStream(jobId);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadStart = async () => {
    if (!file) return;

    try {
      // 1. Request upload URL from FastAPI
      const { job_id, upload_url } = await videoApi.requestUpload(file.name);
      setJobId(job_id); // This automatically triggers the useJobStream hook

      // 2. Upload directly to Azure Blob Storage
      await videoApi.uploadToAzure(upload_url, file);

      // 3. Confirm to FastAPI to trigger the Celery Worker
      await videoApi.confirmUpload(job_id);

    } catch (error) {
      console.error(error);
      alert('There was an error in the upload process');
    }
  };

  // Effect to load subtitles when status changes to REVIEW_PENDING
  useEffect(() => {
    if (stream.status === 'REVIEW_PENDING' && !subtitlesToEdit && jobId) {
      videoApi.getJobDetails(jobId).then((data) => {
        setSubtitlesToEdit(data.subtitles);
      }).catch(console.error);
    }
  }, [stream.status, subtitlesToEdit, jobId]);

  const handleSubmitRender = async (corrected: SubtitleSegment[]) => {
    if (!jobId) return;
    try {
      await videoApi.submitRender(jobId, corrected);
      setSubtitlesToEdit(null); // Hide editor while rendering
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-8 font-sans">
      <div className="max-w-4xl mx-auto">
        <header className="mb-8 text-center">
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">AI Video Editor</h1>
          <p className="text-gray-500 mt-2">Transcribe, correct and render with the power of Whisper and FFmpeg</p>
        </header>

        {/* Upload Zone (Visible if no Active Job) */}
        {!jobId && (
          <div className="bg-white p-10 rounded-2xl shadow-sm border border-gray-200 text-center">
            <input
              type="file"
              accept="video/mp4"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileChange}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="bg-gray-100 hover:bg-gray-200 text-gray-800 font-semibold py-4 px-6 rounded-lg transition-colors"
            >
              {file ? `Selected: ${file.name}` : 'Browse for Video File'}
            </button>

            {file && (
              <button
                onClick={handleUploadStart}
                className="ml-4 bg-green-600 hover:bg-green-700 text-white font-bold py-4 px-8 rounded-lg transition-colors shadow-md"
              >
                Upload and Transcribe
              </button>
            )}
          </div>
        )}

        {/* Status Zone / Progress Bar */}
        {jobId && (stream.status === 'TRANSCRIBING' || stream.status === 'RENDERING' || stream.status === 'PENDING' || stream.status === 'CONNECTED') && (
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-200 text-center mt-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4">
              {(stream.status === 'TRANSCRIBING' || stream.status === 'PENDING' || stream.status === 'CONNECTED') ? 'Analyzing audio with OpenAI...' : 'Generating Final Video with FFmpeg...'}
            </h2>
            <div className="w-full bg-gray-200 rounded-full h-4 mb-4 overflow-hidden">
              <div
                className="bg-blue-600 h-4 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${stream.progress || 0}%` }}
              ></div>
            </div>
            <p className="text-gray-500 font-mono">{stream.progress || 0}%</p>
          </div>
        )}

        {/* Edit Zone */}
        {stream.status === 'REVIEW_PENDING' && subtitlesToEdit && (
          <SubtitleEditor initialSubtitles={subtitlesToEdit} onSubmitRender={handleSubmitRender} />
        )}

        {/* Completion Zone */}
        {stream.status === 'COMPLETED' && stream.final_url && (
          <div className="bg-green-50 p-10 rounded-2xl shadow-sm border border-green-200 text-center mt-6">
            <h2 className="text-2xl font-bold text-green-800 mb-4">Process Completed!</h2>
            <a
              href={stream.final_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-8 rounded-lg shadow-md transition-colors"
            >
              Download Generated Video
            </a>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;