import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

const DATA_FILE = path.join(process.cwd(), 'data', 'tasks.json');

function ensureDataDir() {
    const dir = path.join(process.cwd(), 'data');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function loadTasks(): any[] {
    ensureDataDir();
    if (!fs.existsSync(DATA_FILE)) return [];
    try {
        return JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
    } catch {
        return [];
    }
}

function saveTasks(tasks: any[]) {
    ensureDataDir();
    fs.writeFileSync(DATA_FILE, JSON.stringify(tasks, null, 2));
}

export default function handler(req: NextApiRequest, res: NextApiResponse) {
    const { id } = req.query;
    let tasks = loadTasks();
    const index = tasks.findIndex((t: any) => t.id === id);

    if (req.method === 'PUT') {
        if (index === -1) return res.status(404).json({ error: 'Task not found' });
        tasks[index] = {
            ...tasks[index],
            ...req.body,
            id,
            updatedAt: new Date().toISOString(),
        };
        saveTasks(tasks);
        return res.status(200).json({ task: tasks[index] });
    }

    if (req.method === 'DELETE') {
        if (index === -1) return res.status(404).json({ error: 'Task not found' });
        tasks.splice(index, 1);
        saveTasks(tasks);
        return res.status(200).json({ success: true });
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
