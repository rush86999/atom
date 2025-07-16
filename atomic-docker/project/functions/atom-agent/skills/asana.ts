import { SkillResponse } from '../../types';
import { ASANA_ACCESS_TOKEN } from '../../_libs/constants';
import { handleError } from '../../_utils/errorHandler';
import * as asana from 'asana';

const client = asana.Client.create().useAccessToken(ASANA_ACCESS_TOKEN);

export async function handleCreateAsanaTask(userId: string, entities: any): Promise<string> {
    try {
        const { task_name, project_id } = entities;

        if (!task_name || typeof task_name !== 'string') {
            return "Task name is required to create an Asana task.";
        }

        if (!project_id || typeof project_id !== 'string') {
            return "Project ID is required to create an Asana task.";
        }

        const task = await client.tasks.createTask({
            name: task_name,
            projects: [project_id],
        });

        return `Asana task created: ${task.name}`;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't create the Asana task due to an error.");
    }
}

export async function handleQueryAsanaTasks(userId: string, entities: any): Promise<string> {
    try {
        const { project_id } = entities;

        if (!project_id || typeof project_id !== 'string') {
            return "Project ID is required to query Asana tasks.";
        }

        const tasks = await client.tasks.getTasks({ project: project_id });

        if (!tasks.data.length) {
            return "No tasks found in the specified Asana project.";
        }

        let taskList = "Here are the tasks in the specified Asana project:\n";
        for (const task of tasks.data) {
            taskList += `- ${task.name}\n`;
        }

        return taskList;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't query the Asana tasks due to an error.");
    }
}

export async function handleUpdateAsanaTask(userId: string, entities: any): Promise<string> {
    try {
        const { task_id, task_name } = entities;

        if (!task_id || typeof task_id !== 'string') {
            return "Task ID is required to update an Asana task.";
        }

        if (!task_name || typeof task_name !== 'string') {
            return "Task name is required to update an Asana task.";
        }

        const task = await client.tasks.updateTask(task_id, {
            name: task_name,
        });

        return `Asana task updated: ${task.name}`;
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't update the Asana task due to an error.");
    }
}
