import { CreateTaskFromChatMessageNluEntities, CreateTaskFromChatMessageSkillResponse } from '../types';
/**
 * Creates a task in a task management system based on a referenced chat message.
 *
 * @param userId The ID of the user requesting the task creation.
 * @param nluEntities The parsed NLU entities from the CreateTaskFromChatMessage intent.
 * @returns A promise that resolves to CreateTaskFromChatMessageSkillResponse.
 */
export declare function createTaskFromChatMessage(userId: string, nluEntities: CreateTaskFromChatMessageNluEntities): Promise<CreateTaskFromChatMessageSkillResponse>;
