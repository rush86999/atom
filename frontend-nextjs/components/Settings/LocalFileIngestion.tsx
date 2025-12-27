'use client';

import React, { useState, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';

interface IngestedFile {
    file_path: string;
    file_name: string;
    extension: string;
    file_size: number;
    content: string | null;
    needs_ocr: boolean;
    ingested_at: string;
}

export default function LocalFileIngestion() {
    const [files, setFiles] = useState<IngestedFile[]>([]);
    const [loading, setLoading] = useState(false);
    const [isTauri, setIsTauri] = useState(false);
    const [processingOCR, setProcessingOCR] = useState<string | null>(null);

    React.useEffect(() => {
        // @ts-ignore
        setIsTauri(typeof window !== 'undefined' && window.__TAURI__);
    }, []);

    const handleSelectFiles = async () => {
        if (!isTauri) return;

        try {
            // Open file dialog
            const result = await invoke<{ success: boolean; path?: string }>('open_file_dialog', {
                filters: [
                    ['All Documents', ['pdf', 'docx', 'txt', 'md', 'csv', 'json', 'png', 'jpg', 'jpeg']],
                    ['Text', ['txt', 'md', 'json', 'csv']],
                    ['Documents', ['pdf', 'docx']],
                    ['Images', ['png', 'jpg', 'jpeg', 'tiff']],
                ],
            });

            if (result.success && result.path) {
                await ingestFile(result.path);
            }
        } catch (error) {
            console.error('File selection failed:', error);
        }
    };

    const handleSelectFolder = async () => {
        if (!isTauri) return;

        try {
            const result = await invoke<{ success: boolean; path?: string }>('open_folder_dialog', {});

            if (result.success && result.path) {
                setLoading(true);
                // List directory and ingest all supported files
                const dirResult = await invoke<{ success: boolean; entries?: Array<{ path: string; is_directory: boolean; extension: string }> }>(
                    'list_directory',
                    { path: result.path }
                );

                if (dirResult.success && dirResult.entries) {
                    const supportedExts = ['pdf', 'docx', 'txt', 'md', 'csv', 'json', 'png', 'jpg', 'jpeg'];
                    const filesToIngest = dirResult.entries.filter(
                        e => !e.is_directory && supportedExts.includes(e.extension.toLowerCase())
                    );

                    for (const file of filesToIngest.slice(0, 20)) { // Limit to 20 files
                        await ingestFile(file.path);
                    }
                }
                setLoading(false);
            }
        } catch (error) {
            console.error('Folder selection failed:', error);
            setLoading(false);
        }
    };

    const ingestFile = async (filePath: string) => {
        try {
            const result = await invoke<IngestedFile>('atom_invoke_command', {
                command: 'ingest_local_file',
                params: { file_path: filePath },
            });

            if (result.file_path) {
                setFiles(prev => [...prev, result]);
            }
        } catch (error) {
            console.error('File ingestion failed:', error);
        }
    };

    const handleOCR = async (file: IngestedFile) => {
        setProcessingOCR(file.file_path);

        try {
            const result = await invoke<{ success: boolean; text?: string }>(
                'atom_invoke_command',
                {
                    command: 'process_local_ocr',
                    params: { file_path: file.file_path },
                }
            );

            if (result.success && result.text) {
                // Update file with OCR content
                setFiles(prev => prev.map(f =>
                    f.file_path === file.file_path
                        ? { ...f, content: result.text || null, needs_ocr: false }
                        : f
                ));
            }
        } catch (error) {
            console.error('OCR failed:', error);
        } finally {
            setProcessingOCR(null);
        }
    };

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    if (!isTauri) {
        return (
            <div className="p-6 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <h3 className="text-lg font-semibold mb-2">📁 Local File Ingestion</h3>
                <p className="text-gray-600 dark:text-gray-400">
                    Local file ingestion is only available in the Atom desktop app.
                </p>
            </div>
        );
    }

    return (
        <div className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span>📁</span> Local File Ingestion
            </h3>

            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Ingest local documents into Atom's memory for offline access and search.
            </p>

            {/* Action Buttons */}
            <div className="flex gap-3 mb-6">
                <button
                    onClick={handleSelectFiles}
                    disabled={loading}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
                >
                    <span>📄</span> Select File
                </button>
                <button
                    onClick={handleSelectFolder}
                    disabled={loading}
                    className="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
                >
                    <span>📂</span> Select Folder
                </button>
            </div>

            {loading && (
                <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400 mb-4">
                    <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
                    <span>Processing files...</span>
                </div>
            )}

            {/* Ingested Files */}
            {files.length > 0 && (
                <div>
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                        Ingested Files ({files.length})
                    </h4>
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                        {files.map((file, index) => (
                            <div
                                key={file.file_path + index}
                                className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2 min-w-0">
                                        <span className="text-lg">
                                            {['pdf'].includes(file.extension) ? '📕' :
                                                ['docx', 'doc'].includes(file.extension) ? '📘' :
                                                    ['png', 'jpg', 'jpeg'].includes(file.extension) ? '🖼️' :
                                                        ['txt', 'md'].includes(file.extension) ? '📝' : '📄'}
                                        </span>
                                        <div className="min-w-0">
                                            <p className="font-medium truncate">{file.file_name}</p>
                                            <p className="text-xs text-gray-500">
                                                {file.extension.toUpperCase()} • {formatFileSize(file.file_size)}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {file.needs_ocr && (
                                            <button
                                                onClick={() => handleOCR(file)}
                                                disabled={processingOCR === file.file_path}
                                                className="px-2 py-1 text-xs bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 rounded hover:bg-yellow-200 disabled:opacity-50"
                                            >
                                                {processingOCR === file.file_path ? '⏳' : '🔍 OCR'}
                                            </button>
                                        )}
                                        {file.content && (
                                            <span className="px-2 py-1 text-xs bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 rounded">
                                                ✓ Ready
                                            </span>
                                        )}
                                    </div>
                                </div>
                                {file.content && (
                                    <p className="mt-2 text-xs text-gray-600 dark:text-gray-400 line-clamp-2">
                                        {file.content.substring(0, 150)}...
                                    </p>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {files.length === 0 && !loading && (
                <div className="text-center py-8 text-gray-500">
                    <span className="text-3xl block mb-2">📂</span>
                    <p>No files ingested yet</p>
                    <p className="text-sm">Select a file or folder to get started</p>
                </div>
            )}
        </div>
    );
}
