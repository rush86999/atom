// Canvas Type Registry
// Centralizes all canvas types and their configurations

import { ComponentType } from 'react';
import {
    Terminal,
    Globe,
    Monitor,
    Box,
    Grid3x3,
    Mail,
    FileText,
    Table2
} from 'lucide-react';

// Lazy load canvas components
const TerminalCanvas = dynamic(() => import('@/components/canvas/TerminalCanvas').then(m => m.TerminalCanvas));
const BrowserCanvas = dynamic(() => import('@/components/canvas/BrowserCanvas').then(m => m.BrowserCanvas));
const DesktopCanvas = dynamic(() => import('@/components/canvas/DesktopCanvas').then(m => m.DesktopCanvas));
const AppCanvas = dynamic(() => import('@/components/canvas/AppCanvas').then(m => m.AppCanvas));
const IntegrationCanvas = dynamic(() => import('@/components/canvas/IntegrationCanvas').then(m => m.IntegrationCanvas));
const EmailCanvas = dynamic(() => import('@/components/canvas/EmailCanvas').then(m => m.EmailCanvas));
const DocumentCanvas = dynamic(() => import('@/components/canvas/DocumentCanvas').then(m => m.DocumentCanvas));
const SpreadsheetCanvas = dynamic(() => import('@/components/canvas/SpreadsheetCanvas').then(m => m.SpreadsheetCanvas));

import dynamic from 'next/dynamic';

export type CanvasCategory = 'execution' | 'content' | 'integration';

export interface CanvasType {
    id: string;
    name: string;
    description: string;
    icon: ComponentType<{ className?: string }>;
    component: ComponentType<any>;
    category: CanvasCategory;
    requiresAuth?: boolean;
    requiresDesktop?: boolean;  // Only available in Tauri app
    supportsGuidance?: boolean;  // Real-time agent guidance
}

export const CANVAS_TYPES: Record<string, CanvasType> = {
    // Execution Canvases (Agent-controlled environments)
    terminal: {
        id: 'terminal',
        name: 'Terminal',
        description: 'Command-line interface with real-time execution',
        icon: Terminal,
        component: TerminalCanvas,
        category: 'execution',
        supportsGuidance: true
    },
    browser: {
        id: 'browser',
        name: 'Browser',
        description: 'Web automation and monitoring',
        icon: Globe,
        component: BrowserCanvas,
        category: 'execution',
        supportsGuidance: true
    },
    desktop: {
        id: 'desktop',
        name: 'Desktop',
        description: 'Remote desktop control',
        icon: Monitor,
        component: DesktopCanvas,
        category: 'execution',
        requiresDesktop: true,
        supportsGuidance: true
    },
    app: {
        id: 'app',
        name: 'App',
        description: 'Generic application embedding',
        icon: Box,
        component: AppCanvas,
        category: 'execution',
        supportsGuidance: true
    },

    // Integration Canvases
    integrations: {
        id: 'integrations',
        name: 'Integrations',
        description: 'Visual integration management',
        icon: Grid3x3,
        component: IntegrationCanvas,
        category: 'integration',
        supportsGuidance: true
    },

    // Content Canvases
    email: {
        id: 'email',
        name: 'Email',
        description: 'Email composer with AI assistance',
        icon: Mail,
        component: EmailCanvas,
        category: 'content',
        supportsGuidance: false
    },
    document: {
        id: 'document',
        name: 'Document',
        description: 'Document editor with AI',
        icon: FileText,
        component: DocumentCanvas,
        category: 'content',
        supportsGuidance: false
    },
    spreadsheet: {
        id: 'spreadsheet',
        name: 'Spreadsheet',
        description: 'Spreadsheet with formulas and AI',
        icon: Table2,
        component: SpreadsheetCanvas,
        category: 'content',
        supportsGuidance: false
    }
};

// Helper functions
export function getCanvasType(id: string): CanvasType | undefined {
    return CANVAS_TYPES[id];
}

export function getCanvasByCategory(category: CanvasCategory): CanvasType[] {
    return Object.values(CANVAS_TYPES).filter(t => t.category === category);
}

export function getAvailableCanvasTypes(isDesktop: boolean = false): CanvasType[] {
    return Object.values(CANVAS_TYPES).filter(
        type => !type.requiresDesktop || isDesktop
    );
}

export function getGuidanceEnabledCanvases(): CanvasType[] {
    return Object.values(CANVAS_TYPES).filter(t => t.supportsGuidance);
}

// Check if running in Tauri desktop app
export function isDesktopApp(): boolean {
    return typeof window !== 'undefined' && '__TAURI__' in window;
}
