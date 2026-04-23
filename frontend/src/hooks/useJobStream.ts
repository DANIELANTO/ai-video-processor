import { useState, useEffect } from 'react';

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
        if (!jobId) return;

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

            // Verify the connection state. 
            // EventSource.CLOSED = 2 (Permanent close)
            if (eventSource.readyState === EventSource.CLOSED) {
                console.log("SSE connection closed by the server.");
            } else {
                // If the state is 0 (CONNECTING), it is trying to reconnect.
                // To avoid an infinite loop in case of serious errors (e.g. Backend turned off),
                // It manually closes the connection and marks it as FAILED in the UI.
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