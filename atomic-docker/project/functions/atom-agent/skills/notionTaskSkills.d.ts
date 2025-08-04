import { SkillResponse, NotionTask, CreateTaskData, UpdateTaskData } from '../types';
interface CreateTaskNluEntities {
    task_description: string;
    due_date_text?: string;
    priority_text?: string;
    list_name_text?: string;
}
interface QueryTasksNluEntities {
    date_condition_text?: string;
    priority_text?: string;
    list_name_text?: string;
    status_text?: string;
    description_contains_text?: string;
    sort_by_text?: 'dueDate' | 'priority' | 'createdDate';
    sort_order_text?: 'ascending' | 'descending';
    limit_number?: number;
}
interface UpdateTaskNluEntities {
    task_identifier_text: string;
    new_status_text?: string;
    new_due_date_text?: string;
    new_priority_text?: string;
    new_list_name_text?: string;
    new_description_text?: string;
}
interface SetTaskReminderNluEntities {
    task_identifier_text: string;
    reminder_date_text: string;
}
export declare function handleCreateNotionTask(userId: string, entities: CreateTaskNluEntities, integrations: any): Promise<SkillResponse<CreateTaskData & {
    userMessage: string;
}>>;
export declare function handleSetTaskReminder(userId: string, entities: SetTaskReminderNluEntities): Promise<SkillResponse<{
    userMessage: string;
}>>;
export declare function handleQueryNotionTasks(userId: string, entities: QueryTasksNluEntities): Promise<SkillResponse<{
    tasks: NotionTask[];
    userMessage: string;
}>>;
export declare function handleUpdateNotionTask(userId: string, entities: UpdateTaskNluEntities): Promise<SkillResponse<UpdateTaskData & {
    userMessage: string;
}>>;
export declare function handleAddSubtask(userId: string, entities: {
    parent_task_identifier_text: string;
    sub_task_description: string;
}): Promise<SkillResponse<CreateTaskData & {
    userMessage: string;
}>>;
export {};
