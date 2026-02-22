import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

const DATA_FILE = path.join(process.cwd(), 'data', 'projects.json');

function ensureDataDir() {
    const dir = path.join(process.cwd(), 'data');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function loadProjects(): any[] {
    ensureDataDir();
    if (!fs.existsSync(DATA_FILE)) return [];
    try {
        return JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
    } catch {
        return [];
    }
}

function saveProjects(projects: any[]) {
    ensureDataDir();
    fs.writeFileSync(DATA_FILE, JSON.stringify(projects, null, 2));
}

export default function handler(req: NextApiRequest, res: NextApiResponse) {
    const { id } = req.query;
    let projects = loadProjects();
    const index = projects.findIndex((p: any) => p.id === id);

    if (req.method === 'PUT') {
        if (index === -1) return res.status(404).json({ error: 'Project not found' });
        projects[index] = {
            ...projects[index],
            ...req.body,
            id,
        };
        saveProjects(projects);
        return res.status(200).json({ project: projects[index] });
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
