import { CreateTaskFromChatMessageNluEntities } from '../types';
/**
 * Handles the "CreateTaskFromChatMessage" intent.
 * Calls the skill to create a task from a chat message and formats the result for the user.
 *
 * @param userId The ID of the user.
 * @param entities The NLU entities extracted for the CreateTaskFromChatMessage intent.
 * @returns A promise that resolves to a user-facing string response.
 */
export declare function handleCreateTaskFromChatMessageRequest(userId: string, entities: CreateTaskFromChatMessageNluEntities): Promise<string>;
