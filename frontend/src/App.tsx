import { useState, useRef, useEffect } from 'react';
import { type SubtitleSegment } from './hooks/useSubtitleEditor';
import { useJobStream } from './hooks/useJobStream';
import { videoApi } from './services/api';
import { SubtitleEditor } from './components/SubtitleEditor';

function App() {
  const [jobId, setJobId] = useState<string | null>(() => localStorage.getItem('activeVideoJobId'));
  const [file, setFile] = useState<File | null>(null);
  const [videoObjectUrl, setVideoObjectUrl] = useState<string | null>(null);
  const [subtitlesToEdit, setSubtitlesToEdit] = useState<SubtitleSegment[] | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Sync jobId to localStorage
  useEffect(() => {
    if (jobId) {
      localStorage.setItem('activeVideoJobId', jobId);
    } else {
      localStorage.removeItem('activeVideoJobId');
    }
  }, [jobId]);

  // Manage video object URL lifecycle
  useEffect(() => {
    if (file) {
      const url = URL.createObjectURL(file);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVideoObjectUrl(url);
      return () => URL.revokeObjectURL(url);
    }
    setVideoObjectUrl(null);
  }, [file]);

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

  const handleReset = () => {
    if (window.confirm('Are you sure you want to start a new video? The current progress will be lost from this view.')) {
      setJobId(null);
      setFile(null);
      setSubtitlesToEdit(null);
    }
  };

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary p-4 md:p-8 font-sans">
      <div className="max-w-6xl mx-auto flex flex-col gap-8">
        
        <header className="flex flex-col items-center justify-center pt-4 pb-2 border-b border-border-subtle">
          <h1 className="text-3xl font-extrabold text-text-primary tracking-tight">AI Video Editor</h1>
          <p className="text-text-secondary mt-1 text-sm">Transcribe, correct and render with the power of Whisper and FFmpeg</p>
        </header>

        <main className="flex-grow flex flex-col items-center justify-center">
          {/* Upload Zone (Visible if no Active Job) */}
          {!jobId && (
            <div className="w-full max-w-2xl bg-bg-surface p-10 rounded-2xl border border-border-subtle shadow-md text-center">
              <input
                type="file"
                accept="video/mp4"
                className="hidden"
                ref={fileInputRef}
                onChange={handleFileChange}
              />
              <div 
                className={`border-2 border-dashed rounded-xl p-12 transition-colors ${file ? 'border-accent-blue bg-bg-elevated' : 'border-border-subtle hover:border-text-muted hover:bg-bg-elevated'}`}
              >
                <div className="flex flex-col items-center justify-center gap-4">
                  <svg xmlns="http://www.w3.org/2000/svg" className={`h-12 w-12 ${file ? 'text-accent-blue' : 'text-text-secondary'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-text-primary font-medium text-lg">
                    {file ? file.name : 'Drag & drop your video here'}
                  </p>
                  {!file && <p className="text-text-secondary text-sm">or click to browse for a .mp4 file</p>}
                  
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="mt-2 bg-bg-elevated border border-border-subtle hover:border-text-secondary text-text-primary font-medium py-2 px-6 rounded-lg transition-colors text-sm"
                  >
                    Browse Files
                  </button>
                </div>
              </div>

              {file && (
                <div className="mt-8">
                  <button
                    onClick={handleUploadStart}
                    className="w-full sm:w-auto bg-accent-blue hover:bg-accent-blue-hover text-white font-bold py-3 px-8 rounded-lg transition-colors shadow-lg shadow-accent-blue/20"
                  >
                    Upload and Transcribe
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Status Zone / Progress Bar */}
          {jobId && (stream.status === 'TRANSCRIBING' || stream.status === 'RENDERING' || stream.status === 'PENDING' || stream.status === 'CONNECTED') && (
            <div className="w-full max-w-xl bg-bg-surface p-8 rounded-2xl border border-border-subtle shadow-md text-center mt-8">
              <div className="flex justify-center mb-6">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-accent-blue"></div>
              </div>
              <h2 className="text-xl font-bold text-text-primary mb-6">
                {(stream.status === 'TRANSCRIBING' || stream.status === 'PENDING' || stream.status === 'CONNECTED') ? 'Analyzing audio with OpenAI...' : 'Generating Final Video with FFmpeg...'}
              </h2>
              <div className="w-full bg-bg-elevated rounded-full h-3 mb-3 overflow-hidden border border-border-subtle">
                <div
                  className="bg-accent-blue h-full rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${stream.progress || 0}%` }}
                ></div>
              </div>
              <p className="text-text-secondary font-mono text-sm">{stream.progress || 0}%</p>
            </div>
          )}

          {/* Edit Zone */}
          {stream.status === 'REVIEW_PENDING' && subtitlesToEdit && (
            <SubtitleEditor 
              initialSubtitles={subtitlesToEdit} 
              onSubmitRender={handleSubmitRender} 
              videoSrc={videoObjectUrl}
            />
          )}

          {/* Completion Zone */}
          {stream.status === 'COMPLETED' && stream.final_url && (
            <div className="w-full max-w-xl bg-bg-surface p-10 rounded-2xl border border-success/30 shadow-[0_0_15px_rgba(63,185,80,0.1)] text-center mt-8">
              <div className="flex justify-center mb-4">
                <svg className="w-16 h-16 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-text-primary mb-6">Process Completed!</h2>
              <a
                href={stream.final_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center bg-success hover:bg-success-hover text-white font-bold py-3 px-8 rounded-lg shadow-lg shadow-success/20 transition-colors"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download Generated Video
              </a>
            </div>
          )}

          {/* Error Zone */}
          {stream.status === 'FAILED' && (
            <div className="w-full max-w-xl bg-bg-surface p-10 rounded-2xl border border-error/30 shadow-[0_0_15px_rgba(248,81,73,0.1)] text-center mt-8">
              <div className="flex justify-center mb-4">
                <svg className="w-16 h-16 text-error" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-text-primary mb-2">Processing Failed</h2>
              <p className="text-text-secondary mb-8">{stream.message || 'An unexpected error occurred during processing.'}</p>
            </div>
          )}
        </main>

        {/* Reset / New Video Button */}
        {jobId && (
          <footer className="mt-8 text-center pb-4">
            <button
              onClick={handleReset}
              className="text-text-muted hover:text-error text-sm font-medium transition-colors flex items-center justify-center mx-auto"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Discard and Start New Video
            </button>
          </footer>
        )}

      </div>
    </div>
  );
}

export default App;