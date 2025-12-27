'use client';

import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';

interface OCRStatus {
    python_available: boolean;
    tesseract_available: boolean;
    surya_available: boolean;
    recommended: string;
    any_available: boolean;
}

interface InstallGuide {
    tesseract: {
        description: string;
        install: { macos: string; windows: string; linux: string };
    };
    surya: {
        description: string;
        install: { all: string };
        note: string;
    };
}

export default function LocalOCRSettings() {
    const [ocrStatus, setOcrStatus] = useState<OCRStatus | null>(null);
    const [installGuide, setInstallGuide] = useState<InstallGuide | null>(null);
    const [loading, setLoading] = useState(true);
    const [testFile, setTestFile] = useState<string>('');
    const [testResult, setTestResult] = useState<string>('');
    const [testing, setTesting] = useState(false);
    const [isTauri, setIsTauri] = useState(false);

    useEffect(() => {
        // Check if running in Tauri
        const checkTauri = async () => {
            try {
                // @ts-ignore
                if (typeof window !== 'undefined' && window.__TAURI__) {
                    setIsTauri(true);
                    await loadOCRStatus();
                }
            } catch {
                setIsTauri(false);
            }
            setLoading(false);
        };
        checkTauri();
    }, []);

    const loadOCRStatus = async () => {
        try {
            const status = await invoke<OCRStatus>('atom_invoke_command', {
                command: 'check_ocr_availability',
                params: {},
            });
            setOcrStatus(status);

            const guide = await invoke<InstallGuide>('atom_invoke_command', {
                command: 'get_ocr_installation_guide',
                params: {},
            });
            setInstallGuide(guide);
        } catch (error) {
            console.error('Failed to load OCR status:', error);
        }
    };

    const handleSelectFile = async () => {
        try {
            const result = await invoke<{ success: boolean; path?: string }>('open_file_dialog', {
                filters: [
                    ['Documents', ['pdf', 'png', 'jpg', 'jpeg', 'tiff']],
                    ['Images', ['png', 'jpg', 'jpeg', 'tiff']],
                    ['PDF', ['pdf']],
                ],
            });
            if (result.success && result.path) {
                setTestFile(result.path);
            }
        } catch (error) {
            console.error('File selection failed:', error);
        }
    };

    const handleTestOCR = async () => {
        if (!testFile) return;

        setTesting(true);
        setTestResult('');

        try {
            const result = await invoke<{ success: boolean; text?: string; error?: string }>(
                'atom_invoke_command',
                {
                    command: 'process_local_ocr',
                    params: { file_path: testFile },
                }
            );

            if (result.success && result.text) {
                setTestResult(result.text.substring(0, 500) + (result.text.length > 500 ? '...' : ''));
            } else {
                setTestResult(`Error: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            setTestResult(`Error: ${error}`);
        } finally {
            setTesting(false);
        }
    };

    if (!isTauri) {
        return (
            <div className="p-6 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <h3 className="text-lg font-semibold mb-2">Local OCR</h3>
                <p className="text-gray-600 dark:text-gray-400">
                    Local OCR is only available in the Atom desktop app.
                    <a href="/download" className="text-blue-500 ml-1">Download</a>
                </p>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="p-6 bg-gray-50 dark:bg-gray-800 rounded-lg animate-pulse">
                <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3"></div>
            </div>
        );
    }

    return (
        <div className="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <span>🔍</span> Local OCR Settings
            </h3>

            {/* OCR Engine Status */}
            <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                    Available OCR Engines
                </h4>
                <div className="space-y-2">
                    <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded">
                        <div>
                            <span className="font-medium">Tesseract</span>
                            <span className="text-sm text-gray-500 ml-2">Fast, lightweight (~50MB)</span>
                        </div>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${ocrStatus?.tesseract_available
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                            }`}>
                            {ocrStatus?.tesseract_available ? '✓ Installed' : '✗ Not Found'}
                        </span>
                    </div>

                    <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded">
                        <div>
                            <span className="font-medium">Surya</span>
                            <span className="text-sm text-gray-500 ml-2">High accuracy, 90+ languages</span>
                        </div>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${ocrStatus?.surya_available
                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                            }`}>
                            {ocrStatus?.surya_available ? '✓ Installed' : 'Not Installed'}
                        </span>
                    </div>
                </div>

                {ocrStatus?.recommended && ocrStatus.recommended !== 'none' && (
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                        Recommended: <strong>{ocrStatus.recommended}</strong>
                    </p>
                )}
            </div>

            {/* Installation Guide */}
            {!ocrStatus?.any_available && installGuide && (
                <div className="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                    <h4 className="text-sm font-medium text-yellow-800 dark:text-yellow-200 mb-2">
                        Install an OCR Engine
                    </h4>
                    <div className="text-sm text-yellow-700 dark:text-yellow-300 space-y-2">
                        <p><strong>Tesseract (Quick):</strong></p>
                        <code className="block bg-yellow-100 dark:bg-yellow-900 p-2 rounded text-xs">
                            {installGuide.tesseract.install.macos}
                        </code>
                        <p className="mt-2"><strong>Surya (Best Quality):</strong></p>
                        <code className="block bg-yellow-100 dark:bg-yellow-900 p-2 rounded text-xs">
                            {installGuide.surya.install.all}
                        </code>
                    </div>
                </div>
            )}

            {/* Test OCR */}
            {ocrStatus?.any_available && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                        Test OCR
                    </h4>
                    <div className="flex gap-2 mb-3">
                        <button
                            onClick={handleSelectFile}
                            className="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded text-sm"
                        >
                            Select File
                        </button>
                        {testFile && (
                            <span className="text-sm text-gray-500 self-center truncate max-w-[200px]">
                                {testFile.split('/').pop()}
                            </span>
                        )}
                    </div>

                    {testFile && (
                        <button
                            onClick={handleTestOCR}
                            disabled={testing}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm disabled:opacity-50"
                        >
                            {testing ? 'Processing...' : 'Run OCR'}
                        </button>
                    )}

                    {testResult && (
                        <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-700 rounded">
                            <p className="text-sm font-medium mb-1">Result:</p>
                            <pre className="text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
                                {testResult}
                            </pre>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
