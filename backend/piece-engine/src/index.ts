
import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import { Piece } from '@activepieces/pieces-framework';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const app = express();
const PORT = process.env.PORT || 3003;

// ============================================================================
// SECURITY: Authentication Middleware
// ============================================================================

const PIECE_ENGINE_API_KEY = process.env.PIECE_ENGINE_API_KEY || '';
const REQUIRE_AUTH = process.env.REQUIRE_AUTH === 'true' || PIECE_ENGINE_API_KEY.length > 0;

/**
 * Authentication middleware for management endpoints.
 * Validates API key via X-API-Key header or Authorization: Bearer <key>
 */
function authenticateRequest(req: Request, res: Response, next: NextFunction): void {
    // Skip authentication if not explicitly enabled
    if (!REQUIRE_AUTH) {
        next();
        return;
    }

    // Try X-API-Key header first
    const apiKey = req.headers['x-api-key'] as string;

    // Try Authorization header (Bearer token)
    const authHeader = req.headers['authorization'] as string;
    const bearerToken = authHeader?.startsWith('Bearer ') ? authHeader.substring(7) : null;

    const token = apiKey || bearerToken;

    if (!token) {
        res.status(401).json({
            success: false,
            error: 'Authentication required. Provide X-API-Key header or Authorization: Bearer <key>.'
        });
        return;
    }

    if (token !== PIECE_ENGINE_API_KEY) {
        res.status(403).json({
            success: false,
            error: 'Invalid API key'
        });
        return;
    }

    next();
}

// NPM package name validation (RFC compliance)
// Based on: https://github.com/npm/validate-npm-package-name
const VALID_PACKAGE_NAME_REGEX = /^(?:@([a-z0-9-~][a-z0-9-._~]*)\/)?([a-z0-9-~][a-z0-9-._~]*)$/;

/**
 * Validates an npm package name against RFC standards to prevent command injection.
 * @param packageName - The package name to validate
 * @returns True if the package name is valid, false otherwise
 */
function isValidPackageName(packageName: string): boolean {
    if (!packageName || typeof packageName !== 'string') {
        return false;
    }

    // Check length (npm limits to 214 chars)
    if (packageName.length > 214) {
        return false;
    }

    // Validate against RFC-compliant regex
    return VALID_PACKAGE_NAME_REGEX.test(packageName);
}

/**
 * Safely installs an npm package using spawn (no shell interpretation).
 * @param packageName - The validated package name to install
 * @returns Promise that resolves when installation completes
 */
function safeNpmInstall(packageName: string): Promise<void> {
    return new Promise((resolve, reject) => {
        // Use spawn with argument array to prevent shell injection
        const process = spawn('npm', ['install', packageName, '--save'], {
            stdio: 'inherit',
            shell: false // Critical: Disable shell to prevent command injection
        });

        process.on('close', (code) => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`npm install exited with code ${code}`));
            }
        });

        process.on('error', (err) => {
            reject(new Error(`Failed to spawn npm process: ${err.message}`));
        });
    });
}

app.use(express.json());
app.use(cors());

// In-memory piece registry
const pieces: Record<string, any> = {};

// Helper to load a piece safely
const loadPiece = async (pieceName: string): Promise<Piece | null> => {
    try {
        console.log(`Attempting to load piece: ${pieceName}`);

        // SECURITY: Validate package name before any operations
        if (!isValidPackageName(pieceName)) {
            console.error(`Invalid package name: ${pieceName}`);
            return null;
        }

        // Try to import directly
        let module;
        try {
            module = await import(pieceName);
        } catch (importErr) {
            console.log(`Module ${pieceName} not found. Attempting dynamic install...`);
            // Use safe installation method with spawn instead of exec
            await safeNpmInstall(pieceName);
            module = await import(pieceName);
        }

        const piece = module.piece || module.default?.piece || module.default;

        if (piece && typeof piece === 'object' && piece.displayName) {
            pieces[pieceName] = piece;
            return piece;
        }
        console.warn(`Module ${pieceName} loaded but no Piece export found.`);
        return null;
    } catch (e: any) {
        console.error(`Failed to load/install piece ${pieceName}:`, e.message);
        return null;
    }
};

// Bootstrap: Load all pieces defined in package.json
const bootstrap = async () => {
    try {
        const packageJsonPath = path.join(process.cwd(), 'package.json');
        const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
        const deps = packageJson.dependencies || {};

        const pieceNames = Object.keys(deps).filter(d => d.startsWith('@activepieces/piece-'));

        console.log(`Found ${pieceNames.length} pieces to bootstrap...`);

        for (const name of pieceNames) {
            await loadPiece(name);
        }

        console.log(`Bootstrap complete. ${Object.keys(pieces).length} pieces ready.`);
    } catch (err) {
        console.error('Bootstrap failed:', err);
    }
};

app.get('/health', (req: Request, res: Response) => {
    res.json({
        status: 'ok',
        pieces_loaded: Object.keys(pieces).length,
        loaded_names: Object.keys(pieces)
    });
});

// Endpoint to list available pieces (metadata only)
app.get('/pieces', (req: Request, res: Response) => {
    const metadata = Object.entries(pieces).map(([name, p]) => {
        const actions = typeof p.actions === 'function' ? p.actions() : (p as any).actions || {};
        const triggers = typeof p.triggers === 'function' ? p.triggers() : (p as any).triggers || {};

        return {
            name: name,
            displayName: p.displayName,
            logoUrl: p.logoUrl,
            version: (p as any).version || '0.0.0',
            actions: Object.keys(actions),
            triggers: Object.keys(triggers),
        };
    });
    res.json(metadata);
});

// Endpoint to get full details for a specific piece
// SECURITY: Require authentication for dynamic piece loading (can trigger npm install)
app.get('/pieces/:name', authenticateRequest, async (req: Request, res: Response) => {
    const name = encodeURIComponent(req.params.name);
    // Explicitly allow dots and slashes in piece names if they aren't caught by express router correctly
    // but usually @activepieces/piece-foo works as req.params.name

    let piece = pieces[req.params.name];
    if (!piece) {
        piece = await loadPiece(req.params.name) || null;
    }

    if (!piece) {
        return res.status(404).json({ error: 'Piece not found' });
    }

    const actions = typeof piece.actions === 'function' ? piece.actions() : (piece as any).actions || {};
    const triggers = typeof piece.triggers === 'function' ? piece.triggers() : (piece as any).triggers || {};

    res.json({
        name: req.params.name,
        displayName: piece.displayName,
        logoUrl: piece.logoUrl,
        authors: piece.authors,
        actions: actions,
        triggers: triggers,
        auth: piece.auth
    });
});

// Endpoint to execute an action
// SECURITY: Require authentication for action execution
app.post('/execute/action', authenticateRequest, async (req: Request, res: Response) => {
    try {
        const { pieceName, actionName, props, auth } = req.body;

        let piece = pieces[pieceName];
        if (!piece) {
            piece = await loadPiece(pieceName) || null;
        }

        if (!piece) {
            return res.status(404).json({ error: `Piece ${pieceName} not found` });
        }

        const actions = typeof piece.actions === 'function' ? piece.actions() : (piece as any).actions || {};
        const action = actions[actionName];

        if (!action) {
            return res.status(404).json({ error: `Action ${actionName} not found in piece ${pieceName}` });
        }

        // Context Preparation
        const context = {
            propsValue: props || {},
            auth: auth || {},
            store: {
                put: async () => { },
                get: async () => null,
                delete: async () => { },
            } as any,
            webhookUrl: '',
            files: {
                write: async () => '',
            } as any,
            serverUrl: '',
            project: { id: 'atom-project' } as any,
            flow: { id: 'atom-flow' } as any
        };

        const result = await action.run(context);
        res.json({ success: true, output: result });
    } catch (error: any) {
        console.error('Execution error:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Management: Install a piece
// SECURITY: Require authentication for package installation
app.post('/sys/install', authenticateRequest, async (req: Request, res: Response) => {
    const { packageName } = req.body;

    // SECURITY: Validate package name before installation
    if (!packageName || !isValidPackageName(packageName)) {
        return res.status(400).json({
            success: false,
            error: 'Invalid package name. Package names must follow npm naming conventions.'
        });
    }

    try {
        console.log(`Installing ${packageName}...`);
        // Use safe installation method with spawn instead of exec
        await safeNpmInstall(packageName);

        const piece = await loadPiece(packageName);
        if (piece) {
            res.json({ success: true, message: `Installed and loaded ${packageName}` });
        } else {
            res.json({ success: false, error: 'Package installed but no piece export found' });
        }
    } catch (e: any) {
        res.status(500).json({ success: false, error: e.message });
    }
});

app.listen(PORT, async () => {
    console.log(`Atom Piece Engine running on port ${PORT}`);
    await bootstrap();
});

