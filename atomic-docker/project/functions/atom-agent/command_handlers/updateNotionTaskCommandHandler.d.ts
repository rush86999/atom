interface UpdateTaskHandlerNluEntities {
    task_identifier_text: string;
    new_status_text?: string;
    new_due_date_text?: string;
    new_priority_text?: string;
    new_list_name_text?: string;
    new_description_text?: string;
    update_action?: 'complete' | 'set_due_date' | 'change_priority' | 'rename' | 'move_list' | 'add_notes';
}
/**
 * Handles the "UpdateTask" intent.
 * Calls the skill to update a Notion task and formats the result for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the UpdateTask intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export declare function handleUpdateTaskRequest(userId: string, entities: UpdateTaskHandlerNluEntities): Promise<string>;
export {};
