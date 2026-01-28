import { useState, useCallback } from 'react';
import apiClient from '@/lib/api';

export function useFileUpload() {
    const [isUploading, setIsUploading] = useState(false);
    const [progress, setProgress] = useState(0);

    const uploadFile = useCallback(async (file: File) => {
        setIsUploading(true);
        setProgress(0);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await apiClient.post('/api/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                onUploadProgress: (progressEvent: any) => {
                    const percentCompleted = Math.round(
                        (progressEvent.loaded * 100) / (progressEvent.total || 1)
                    );
                    setProgress(percentCompleted);
                },
            } as any);

            return response.data;
        } catch (error) {
            console.error('File upload failed:', error);
            throw error;
        } finally {
            setIsUploading(false);
        }
    }, []);

    return {
        uploadFile,
        isUploading,
        progress,
    };
}

export default useFileUpload;
