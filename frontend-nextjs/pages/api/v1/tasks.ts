import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

// Persist to a local JSON file so tasks survive server restarts
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
    const tasks = loadTasks();

    if (req.method === 'GET') {
        return res.status(200).json({ tasks });
    }

    if (req.method === 'POST') {
        const now = new Date().toISOString();
        const newTask = {
            id: `task_${Date.now()}`,
            ...req.body,
            createdAt: now,
            updatedAt: now,
            dueDate: req.body.dueDate || now,
        };
        tasks.push(newTask);
        saveTasks(tasks);
        return res.status(201).json({ task: newTask });
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
