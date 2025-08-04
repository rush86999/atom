interface QueryTasksHandlerNluEntities {
    date_condition_text?: string;
    priority_text?: string;
    list_name_text?: string;
    status_text?: string;
    description_contains_text?: string;
    sort_by_text?: 'dueDate' | 'priority' | 'createdDate';
    sort_order_text?: 'ascending' | 'descending';
    limit_number?: number;
}
/**
 * Handles the "QueryTasks" intent.
 * Calls the skill to query Notion tasks and formats the result for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the QueryTasks intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export declare function handleQueryTasksRequest(userId: string, entities: QueryTasksHandlerNluEntities): Promise<string>;
export {};
