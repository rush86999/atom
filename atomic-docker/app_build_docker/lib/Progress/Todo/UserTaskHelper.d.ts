import { Dispatch, SetStateAction } from 'react';
import { DisplayUIType, TaskPlusType, TaskSubType } from '@pages/Progress/Todo/UserTask';
import { TaskStatus } from '@lib/Progress/Todo/constants';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import type { DropResult } from 'react-beautiful-dnd';
export type CalendarEventIdElType = React.MutableRefObject<string>;
export type dragEnd<T> = {
    data: T[];
    from: number;
    to: number;
};
export declare const removeParent: (client: ApolloClient<NormalizedCacheObject>, index: number, tasks: TaskPlusType[]) => Promise<void>;
export declare const addParent: (client: ApolloClient<NormalizedCacheObject>, index: number, indexBefore: number, tasks: TaskPlusType[]) => Promise<void>;
export declare const sortByOrder: <T>(a: T[], orderArray: number[]) => T[];
export declare const onDragEndUpdateForWeb: <T>(dropResult: DropResult, tasks: TaskPlusType[], oldDisplayUIs: DisplayUIType[], setDisplayUIs: Dispatch<SetStateAction<DisplayUIType[]>>, dataIndexToDisplayArray: number[], setDataIndexToDisplayArray: Dispatch<SetStateAction<number[]>>, taskType: TaskSubType, userId: string, client: ApolloClient<NormalizedCacheObject>) => Promise<void>;
export declare const checkTaskIsParent: (tasks: TaskPlusType[], taskId: string) => boolean;
export declare const checkIfParentRemovedOfChildMoved: (newTasks: TaskPlusType[], oldParentId: string, movedTask: TaskPlusType) => boolean | undefined;
export declare const findParentOfTaskForWeb: (displayUIs: DisplayUIType[], indexOfChild: number) => any;
export declare const checkStatusChangeForWeb: (reorderedDisplayUIs: DisplayUIType[], valueMoved: DisplayUIType) => {
    label: string;
    value: any;
} | undefined;
export declare const reorderDataArray: <T>(a: T[], from: number, to: number) => T[];
export declare const reorderParentAndChildDataArray: <T>(a: T[], from: number, to: number, oldTasks: TaskPlusType[], taskIdOfMovedValue: string) => T[];
export declare const updateDataToDisplayUI: <T>(data: T[], setData: Dispatch<SetStateAction<T[]>>, dataIndexToDisplayArray: number[]) => void;
export declare const sortByStatus: <T>(aArray: T[], statusArray: TaskStatus[]) => T[];
export declare const getDisplayUIForWeb: (taskPluses: TaskPlusType[], statusArray: TaskStatus[], type: TaskSubType, userId: string) => {
    displayUIArray: DisplayUIType[];
    dataIndexToDisplayArray: number[];
};
export declare const getIndexUpdatesFromUIForWeb: (reorderedDisplayUIs: DisplayUIType[], oldDisplayUIs: DisplayUIType[], valueMoved: DisplayUIType) => {
    from: number;
    to: number;
};
export declare const addToDataArrayAfterIndex: <T>(a: T, aArray: T[], isInitial: boolean, index?: number) => T[] | undefined;
export declare const addToOrderArrayAfterIndexWithNewOrder: (orderArray: number[], isInitial: boolean, setOrderArray: Dispatch<SetStateAction<number[]>>, index?: number) => number[] | undefined;
export declare const updateDataArray: <T>(t: T, tArray: T[], setTArray: Dispatch<SetStateAction<T[]>>, index: number) => T[];
export declare const removeFromDataArray: <T>(index: number, dataArray: T[], setDataArray: Dispatch<SetStateAction<T[]>>) => T[];
export declare const sortTasksByParent: (parentIdArray: string[], taskPluses: TaskPlusType[]) => {
    sortedTaskPluses: TaskPlusType[];
};
