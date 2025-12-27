
import express, { Request, Response } from 'express';
import cors from 'cors';
import { Piece } from '@activepieces/pieces-framework';
import { exec } from 'child_process';
import util from 'util';

const execAsync = util.promisify(exec);
const app = express();
const PORT = process.env.PORT || 3003;

app.use(express.json());
app.use(cors());

// In-memory piece registry
const pieces: Record<string, Piece> = {};

// Helper to load pieces (placeholder for now, will implement dynamic loading next)
const loadPiece = async (pieceName: string) => {
    // Logic to require() the piece if installed
    try {
        // This assumes the piece is already installed in node_modules
        // We need to find the main entry point. 
        // For standard activepieces, it's usually exported as `piece` if we import the package.
        // real dynamic loading will be more complex.
        return null;
    } catch (e) {
        return null;
    }
}

app.get('/health', (req: Request, res: Response) => {
    res.json({ status: 'ok', pieces_loaded: Object.keys(pieces).length });
});

// Endpoint to list available pieces (metadata only)
app.get('/pieces', (req: Request, res: Response) => {
    const metadata = Object.entries(pieces).map(([name, p]) => {
        // Handle newer pieces-framework structure where these are methods
        const actions = typeof p.actions === 'function' ? p.actions() : (p as any).actions || {};
        const triggers = typeof p.triggers === 'function' ? p.triggers() : (p as any).triggers || {};

        return {
            name: name,
            displayName: p.displayName,
            logoUrl: p.logoUrl,
            version: (p as any).version || '0.0.0',
            authors: p.authors,
            actions: Object.keys(actions),
            triggers: Object.keys(triggers),
        };
    });
    res.json(metadata);
});

// Endpoint to get full details for a specific piece
app.get('/pieces/:name', (req: Request, res: Response) => {
    const piece = pieces[req.params.name];
    if (!piece) {
        return res.status(404).json({ error: 'Piece not found' });
    }

    const actions = typeof piece.actions === 'function' ? piece.actions() : (piece as any).actions || {};
    const triggers = typeof piece.triggers === 'function' ? piece.triggers() : (piece as any).triggers || {};

    res.json({
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

        // Try to load if not in memory
        if (!pieces[pieceName]) {
            // For now, just error. We will add dynamic install later.
            // pieces[pieceName] = await loadPiece(pieceName);
        }

        const piece = pieces[pieceName];
        if (!piece) {
            return res.status(404).json({ error: `Piece ${pieceName} not found` });
        }

        const actions = typeof piece.actions === 'function' ? piece.actions() : (piece as any).actions || {};
        const action = actions[actionName];

        if (!action) {
            return res.status(404).json({ error: `Action ${actionName} not found in piece ${pieceName}` });
        }

        // Execute the action
        const context = {
            propsValue: props,
            auth: auth,
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
            project: {} as any,
            flow: {} as any
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
        await execAsync(`npm install ${packageName}`);

        // Dynamically require it
        // Note: This is simplified. In prod we might need to restart or use a sophisticated loader.
        // For this hybrid architecture, simply having it in node_modules might be enough if we dynamic import on demand.

        try {
            // Clean cache to allow re-import
            const resolved = require.resolve(packageName);
            delete require.cache[resolved];

            const module = require(packageName);
            // ActivePieces packages usually export `piece` property? Or the default export is the piece?
            // We need to inspect a real package to be sure.
            const piece = module.piece || module.default;

            if (piece) {
                pieces[packageName] = piece;
                res.json({ success: true, message: `Installed and loaded ${packageName}` });
            } else {
                res.json({ success: false, error: 'Package installed but no piece export found' });
            }
        } catch (importErr: any) {
            res.status(500).json({ success: false, error: `Import failed: ${importErr.message}` });
        }

    } catch (e: any) {
        res.status(500).json({ success: false, error: e.message });
    }
});

app.listen(PORT, () => {
    console.log(`Atom Piece Engine running on port ${PORT}`);
});
