interface CreateTaskHandlerNluEntities {
    task_description: string;
    due_date_text?: string;
    priority_text?: string;
    list_name_text?: string;
}
/**
 * Handles the "CreateTask" intent.
 * Calls the skill to create a Notion task and formats the result for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the CreateTask intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export declare function handleCreateTaskRequest(userId: string, nluEntities: CreateTaskHandlerNluEntities, integrations: any): Promise<string>;
export {};
