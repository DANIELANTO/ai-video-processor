import { type SubtitleSegment } from '../hooks/useSubtitleEditor';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

export const videoApi = {
    // 1. Request upload URL from FastAPI
    requestUpload: async (filename: string) => {
        const response = await fetch(`${API_BASE_URL}/jobs/upload`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        if (!response.ok) throw new Error('Error al solicitar upload');
        return response.json(); // { job_id, upload_url, status }
    },

    // 2. Upload binary file directly to Azure Blob Storage
    uploadToAzure: async (uploadUrl: string, file: File) => {
        // In Azure, it is often necessary to send the header 'x-ms-blob-type': 'BlockBlob'
        const response = await fetch(uploadUrl, {
            method: 'PUT',
            headers: {
                'x-ms-blob-type': 'BlockBlob',
                'Content-Type': file.type || 'video/mp4'
            },
            body: file
        });
        if (!response.ok) throw new Error('Error subiendo a Azure');
        return true;
    },

    // 3. Notify backend that Azure already has the file
    confirmUpload: async (jobId: string) => {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/confirm-upload`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Error confirmando upload');
        return response.json();
    },

    // 4. Get job details with extracted subtitles from DB
    getJobDetails: async (jobId: string) => {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
        if (!response.ok) throw new Error('Error obteniendo detalles del trabajo');
        return response.json();
    },

    // 5. Send corrections for rendering
    submitRender: async (jobId: string, correctedSubtitles: SubtitleSegment[]) => {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/render`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ corrected_subtitles: correctedSubtitles })
        });
        if (!response.ok) throw new Error('Error al iniciar renderizado');
        return response.json();
    }
};