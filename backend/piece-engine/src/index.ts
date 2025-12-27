
import express, { Request, Response } from 'express';
import cors from 'cors';
import { Piece } from '@activepieces/pieces-framework';
import { exec } from 'child_process';
import util from 'util';
import fs from 'fs';
import path from 'path';

const execAsync = util.promisify(exec);
const app = express();
const PORT = process.env.PORT || 3003;

app.use(express.json());
app.use(cors());

// In-memory piece registry
const pieces: Record<string, any> = {};

// Helper to load a piece safely
const loadPiece = async (pieceName: string): Promise<Piece | null> => {
    try {
        console.log(`Attempting to load piece: ${pieceName}`);

        // ActivePieces packages usually export as `piece`
        // We use dynamic import for ESM/TS compatibility
        const module = await import(pieceName);
        const piece = module.piece || module.default?.piece || module.default;

        if (piece && typeof piece === 'object' && piece.displayName) {
            pieces[pieceName] = piece;
            return piece;
        }
        console.warn(`Module ${pieceName} loaded but no Piece export found.`);
        return null;
    } catch (e: any) {
        console.error(`Failed to load piece ${pieceName}:`, e.message);
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
app.get('/pieces/:name', async (req: Request, res: Response) => {
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
app.post('/execute/action', async (req: Request, res: Response) => {
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
app.post('/sys/install', async (req: Request, res: Response) => {
    const { packageName } = req.body;
    try {
        console.log(`Installing ${packageName}...`);
        // Use --no-save to avoid modifying package.json dynamically if preferred, 
        // but here we might want to keep it.
        await execAsync(`npm install ${packageName} --save`);

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

