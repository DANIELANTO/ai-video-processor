import { useState, useEffect } from 'react';
import { videoApi } from '../services/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface JobStreamData {
    status: 'PENDING' | 'TRANSCRIBING' | 'REVIEW_PENDING' | 'RENDERING' | 'COMPLETED' | 'FAILED' | 'CONNECTED';
    progress: number;
    message?: string;
    final_url?: string;
}

export const useJobStream = (jobId: string | null) => {
    const [streamData, setStreamData] = useState<JobStreamData>({ status: 'PENDING', progress: 0 });

    useEffect(() => {
        if (!jobId) {
            setStreamData({ status: 'PENDING', progress: 0 });
            return;
        }

        // Fetch initial state to synchronize UI immediately on reload
        videoApi.getJobDetails(jobId)
            .then(data => {
                setStreamData(prev => ({
                    ...prev,
                    status: data.status,
                    final_url: data.final_url,
                }));
            })
            .catch(err => {
                console.error("Error fetching initial job status:", err);
            });

        // Endpoint connection to FastAPI SSE
        const eventSource = new EventSource(`${API_BASE_URL}/jobs/${jobId}/stream`);

        eventSource.onmessage = (event) => {
            const data: JobStreamData = JSON.parse(event.data);

            setStreamData(prev => ({
                ...prev,
                ...data
            }));

            // Close the connection if it reaches a terminal state
            if (data.status === 'COMPLETED' || data.status === 'FAILED') {
                eventSource.close();
            }
        };

        eventSource.onerror = (err) => {
            console.error("Error detected in SSE connection:", err);

            if (eventSource.readyState === EventSource.CLOSED) {
                console.log("SSE connection closed by the server.");
            } else {
                console.warn("Forcing SSE close to avoid infinite retries.");
                eventSource.close();
                setStreamData(prev => ({
                    ...prev,
                    status: 'FAILED',
                    message: 'Network error: Could not maintain connection with the server.'
                }));
            }
        };

        // Cleanup on component unmount
        return () => {
            eventSource.close();
        };
    }, [jobId]);

    return streamData;
};