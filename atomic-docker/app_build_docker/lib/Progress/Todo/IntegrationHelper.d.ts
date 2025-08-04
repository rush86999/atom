import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { TaskStatus } from './constants';
export declare enum TableName {
    DAILY = "Daily",
    WEEKLY = "Weekly",
    MASTER = "Master",
    GROCERY = "Grocery"
}
type selectName = 'To Do' | 'Doing' | 'Done';
type todoResponse = {
    id: string;
    text: string;
    checked: boolean;
};
type responseData = {
    id: string;
    status: selectName;
    title: string;
    created_time: string;
    last_edited_time: string;
    list?: todoResponse[];
};
export declare const deleteNotionBlock: (tableName: string, syncId: string) => Promise<void>;
export declare const createTaskInStore: (userId: string, type: TableName, notes?: string, date?: string, nextDay?: boolean, event?: boolean, syncId?: string, syncName?: string, startDate?: string, endDate?: string, status?: TaskStatus, parentId?: string, order?: number) => Promise<void>;
export declare const updateTaskInStore: (type: TableName, id: string, notes?: string, date?: string, event?: boolean, completed?: boolean, startDate?: string, endDate?: string, completedDate?: string, scheduleId?: string, softDeadline?: string, hardDeadline?: string, important?: boolean, status?: TaskStatus, parentId?: string, order?: number, eventId?: string, duration?: number) => Promise<void>;
export declare const processTaskFromNotion: (results: responseData[], type: TableName, sub: string, client: ApolloClient<NormalizedCacheObject>) => Promise<void>;
export declare const updateTaskNote: (type: TableName, id: string, notes?: string, oldDate?: string, noteDate?: string, status?: selectName, oldEvent?: boolean, oldCompleted?: boolean, oldStartDate?: string, oldEndDate?: string, oldCompletedDate?: string, eventId?: string, duration?: number) => Promise<void>;
export declare const createTaskNote: (type: TableName, notes: string, syncId: string, syncName: string, userId: string, status: selectName, parentId?: string) => Promise<void>;
export declare const queryNotionDB: (integration: any) => Promise<responseData[] | undefined>;
export {};
