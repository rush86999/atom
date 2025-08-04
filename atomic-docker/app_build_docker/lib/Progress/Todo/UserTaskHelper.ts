import { Dispatch, SetStateAction } from 'react';

import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';

import * as math from 'mathjs';
import { RRule } from 'rrule';

import { dayjs } from '@lib/date-utils';

import _ from 'lodash';
// import axios from 'axios'

// import { CONVERT_TO_WEBP_API } from 'react-native-dotenv'

import {
  updateTaskInStore,
  TableName,
} from '@lib/Progress/Todo/IntegrationHelper';

import {
  DisplayUIType,
  TaskPlusType,
  TaskSubType,
} from '@pages/Progress/Todo/UserTask';

// const CONVERTOWEBAPIDEV = CONVERT_TO_WEBP_API

// dayjs.extend(utc)
// dayjs.extend(quarterOfYear)

import { TaskStatus } from '@lib/Progress/Todo/constants';
import { updateTaskByIdInDb, upsertManyTasksInDb } from './UserTaskHelper3';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import type {
  DraggableProvided,
  DraggableStateSnapshot,
  DropResult,
  DraggableLocation,
} from 'react-beautiful-dnd';
const bucketRegion = 'us-east-1';
const bucketName = 'atomiclife-app-public-image-prod-uncompressed';
// const format = "png"
// const result = Platform.OS === "android" ? "zip-base64" : "base64"

// type setS3 = React.Dispatch<React.SetStateAction<S3Client>>
type s3El = React.MutableRefObject<S3Client>;

// type setCredId = React.Dispatch<React.SetStateAction<string>>
type credIdEl = React.MutableRefObject<string>;

type userIdEl = React.MutableRefObject<string>;

type pointRewardEl = React.MutableRefObject<number>;

export type CalendarEventIdElType = React.MutableRefObject<string>;

type RecurrenceFrequency = 'daily' | 'weekly' | 'monthly' | 'yearly';

type dayType = 'MO' | 'TU' | 'WE' | 'TH' | 'FR' | 'SA' | 'SU';

type TaskType = 'Daily' | 'Weekly' | 'Master' | 'Grocery' | string;

const escapeUnsafe = (unsafe: string) =>
  unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/ /gi, '-');

const TODO = 'To Do';
const DOING = 'Doing';
const DONE = 'Done';

export type dragEnd<T> = {
  data: T[];
  from: number;
  to: number;
};

export const removeParent = async (
  client: ApolloClient<NormalizedCacheObject>,
  index: number,
  tasks: TaskPlusType[]
) => {
  try {
    tasks[index].parentId = null;

    await updateTaskByIdInDb(client, tasks[index]);
    console.log(tasks[index], ' successfully updated');
  } catch (e) {
    console.log(e, ' unable to remove parent');
  }
};

export const addParent = async (
  client: ApolloClient<NormalizedCacheObject>,
  index: number,
  indexBefore: number,
  tasks: TaskPlusType[]
) => {
  try {
    if (indexBefore < 0) {
      console.log(' no parent in prior note');
      return;
    }

    console.log(index, indexBefore, ' type, index, indexBefore');

    const newDate = dayjs().format();

    let taskIdOfBefore = tasks[indexBefore]?.id;
    let indexOfBefore = indexBefore;
    let parentIdOfBefore = tasks[indexBefore]?.parentId;
    while (parentIdOfBefore?.length > 0 && indexOfBefore > -2) {
      indexOfBefore--;
      taskIdOfBefore = tasks[indexOfBefore]?.id;
      parentIdOfBefore = tasks[indexOfBefore]?.parentId;
    }

    if (indexOfBefore < 0) {
      console.log(indexOfBefore, ' indexOfBefore < 0');
      return;
    }

    tasks[index].parentId = taskIdOfBefore;

    await updateTaskByIdInDb(client, tasks[index]);

    console.log(tasks[index], ' parent added');
  } catch (e) {
    console.log(e, ' unable to add parent');
  }
};
export const sortByOrder = <T>(a: T[], orderArray: number[]) => {
  const newA = a.map((i, inx) => ({ a: i, order: orderArray[inx] }));

  newA.sort((a, b) => a.order - b.order);

  const sortedA = newA.map((i) => i.a);
  return sortedA;
};

const reorder = <T>(list: T[], startIndex: number, endIndex: number) => {
  const result = Array.from(list);
  const [removed] = result.splice(startIndex, 1);
  result.splice(endIndex, 0, removed);

  return result;
};

export const onDragEndUpdateForWeb = async <T>(
  dropResult: DropResult,
  tasks: TaskPlusType[],
  oldDisplayUIs: DisplayUIType[],
  setDisplayUIs: Dispatch<SetStateAction<DisplayUIType[]>>,
  dataIndexToDisplayArray: number[],
  setDataIndexToDisplayArray: Dispatch<SetStateAction<number[]>>,
  taskType: TaskSubType,
  userId: string,
  client: ApolloClient<NormalizedCacheObject>
) => {
  try {
    // dropped nowhere
    if (!dropResult.destination) {
      return;
    }

    const source: DraggableLocation = dropResult.source;
    const destination: DraggableLocation = dropResult.destination;

    // did not move anywhere - can bail early
    if (
      source.droppableId === destination.droppableId &&
      source.index === destination.index
    ) {
      return;
    }

    const from = source.index;
    const to = destination.index;
    const reorderedDisplayUIs = reorder(oldDisplayUIs, from, to);

    const tempDisplayUI = reorderDataArray(oldDisplayUIs, from, to);
    const tempDataIndex = reorderDataArray(dataIndexToDisplayArray, from, to);
    setDisplayUIs(tempDisplayUI);
    setDataIndexToDisplayArray(tempDataIndex);

    if (from < 0) {
      console.log('from < 0 something went wrong');
      return;
    }

    console.log(from, ' from value');

    console.log(tasks, ' old tasks');
    // find moved
    const movedValue = oldDisplayUIs[from];

    console.log(movedValue, ' movedValue');

    // check if parent
    const oldDataIndex = dataIndexToDisplayArray[from];
    console.log(oldDataIndex, ' oldDataIndex');
    const taskIdOfMovedValue = tasks[oldDataIndex]?.id;

    const isParent = checkTaskIsParent(tasks, taskIdOfMovedValue);
    console.log(isParent, ' isParent');
    // first update data arrays
    const { from: fromDataIndex, to: toDataIndex } =
      getIndexUpdatesFromUIForWeb(
        reorderedDisplayUIs,
        oldDisplayUIs,
        movedValue
      );
    console.log(fromDataIndex, toDataIndex, ' fromDataIndex toDataIndex');

    let newTasks = [];

    if (isParent) {
      newTasks = reorderParentAndChildDataArray(
        tasks,
        fromDataIndex,
        toDataIndex,
        tasks,
        taskIdOfMovedValue
      );
    } else {
      newTasks = reorderDataArray(tasks, fromDataIndex, toDataIndex);
    }

    // if child check if parent removed
    if (tasks?.[fromDataIndex]?.parentId) {
      const parentRemoved = checkIfParentRemovedOfChildMoved(
        newTasks,
        tasks?.[fromDataIndex]?.parentId,
        tasks[oldDataIndex]
      );

      console.log(parentRemoved, ' parentRemoved');

      if (parentRemoved) {
        // remove from db
        // updateTaskByIdInDb
        const movedTask = tasks[oldDataIndex];

        movedTask.parentId = null;

        await updateTaskByIdInDb(client, movedTask);

        console.log(newTasks, ' newTasks after parent removed');
      }
    }

    // check if status changed
    const newStatus = checkStatusChangeForWeb(
      reorderedDisplayUIs as DisplayUIType[],
      movedValue
    );

    console.log(newStatus, ' newStatus');

    // update status
    if (newStatus?.value !== tasks?.[fromDataIndex]?.status) {
      const movedTask = tasks[oldDataIndex];
      movedTask.status = newStatus?.value || TaskStatus.TODO;

      await updateTaskByIdInDb(client, movedTask);

      console.log(newTasks, ' newTasks after status update');
    }

    console.log(newTasks, ' newTasks');

    // update order in db
    newTasks?.forEach((t, inx) => (t.order = inx));

    await upsertManyTasksInDb(
      client,
      newTasks?.map((i) => _.omit(i, ['startDate', 'endDate', 'nextDay']))
    );

    const newStatusArray = newTasks.map((t) => t?.status);

    const {
      displayUIArray: newDisplayUIArray,
      dataIndexToDisplayArray: newDataIndexToDisplayArray,
    } = getDisplayUIForWeb(newTasks, newStatusArray, taskType, userId);

    console.log(newDataIndexToDisplayArray, ' newDataIndexToDisplayArray');
    setDataIndexToDisplayArray(newDataIndexToDisplayArray);
    setDisplayUIs(newDisplayUIArray);
  } catch (e) {
    console.log(e, ' unable to update values');
  }
};

// export const onDragEndUpdate = async <T>(
//   dragEnd: dragEnd<T>,
//   tasks: TaskPlusType[],
//   oldDisplayUIs: string[],
//   setDisplayUIs: Dispatch<SetStateAction<string[]>>,
//   dataIndexToDisplayArray: number[],
//   setDataIndexToDisplayArray: Dispatch<SetStateAction<number[]>>,
//   client: ApolloClient<NormalizedCacheObject>,
// ) => {
//   try {
//     const { data, from, to } = dragEnd
//     const tempDisplayUI = reorderDataArray(oldDisplayUIs, from, to)
//     const tempDataIndex = reorderDataArray(dataIndexToDisplayArray, from, to)
//     setDisplayUIs(tempDisplayUI)
//     setDataIndexToDisplayArray(tempDataIndex)

//     if (from < 0) {
//       console.log('from < 0 something went wrong')
//       return
//     }

//     console.log(from, ' from value')
//     console.log(data, ' data from onDragEndUpdate')
//     console.log(tasks, ' old tasks')
//     // find moved
//     const movedValue = oldDisplayUIs[from]

//     console.log(movedValue, ' movedValue')

//     // check if parent
//     const oldDataIndex = dataIndexToDisplayArray[from]
//     console.log(oldDataIndex, ' oldDataIndex')
//     const taskIdOfMovedValue = tasks[oldDataIndex]?.id

//     const isParent = checkTaskIsParent(tasks, taskIdOfMovedValue)
//     console.log(isParent, ' isParent')
//     // first update data arrays
//     const { from: fromDataIndex, to: toDataIndex } = getIndexUpdatesFromUI(data as unknown[] as DisplayUIType[], oldDisplayUIs, movedValue)
//     console.log(fromDataIndex, toDataIndex, ' fromDataIndex toDataIndex')

//     let newTasks = []

//     if (isParent) {

//       newTasks = reorderParentAndChildDataArray(tasks, fromDataIndex, toDataIndex, tasks, taskIdOfMovedValue)

//     } else {

//       newTasks = reorderDataArray(tasks, fromDataIndex, toDataIndex)

//     }

//     // if child check if parent removed
//     if (tasks?.[fromDataIndex]?.parentId) {

//       const parentRemoved = checkIfParentRemovedOfChildMoved(
//         newTasks,
//         tasks?.[fromDataIndex]?.parentId,
//         tasks[oldDataIndex],
//       )

//       console.log(parentRemoved, ' parentRemoved')

//       if (parentRemoved) {

//         // remove from db
//         // updateTaskByIdInDb
//         const movedTask = tasks[oldDataIndex]

//         movedTask.parentId = null

//         await updateTaskByIdInDb(client, movedTask)

//         console.log(newTasks, ' newTasks after parent removed')
//       }
//     }

//     // check if status changed
//     const newStatus = checkStatusChangeForWeb(
//       data as unknown[] as DisplayUIType[],
//       movedValue,
//     )

//     console.log(newStatus, ' newStatus')

//     // update status
//     if (newStatus?.value !== tasks?.[fromDataIndex]?.status) {

//       const movedTask = tasks[oldDataIndex]
//       movedTask.status = newStatus?.value || TaskStatus.TODO

//       await updateTaskByIdInDb(client, movedTask)

//       console.log(newTasks, ' newTasks after status update')
//     }

//     console.log(newTasks, ' newTasks')

//     // update order in db
//     newTasks?.forEach((t, inx) => (t.order = inx))

//     await upsertManyTasksInDb(client, newTasks?.map(i => _.omit(i, ['startDate', 'endDate', 'nextDay'])))

//     const newStatusArray = newTasks.map(t => t?.status)

//     const {
//       displayUIArray: newDisplayUIArray,
//       dataIndexToDisplayArray: newDataIndexToDisplayArray,
//     } = getDisplayUI(newTasks, newStatusArray)

//     console.log(newDataIndexToDisplayArray, ' newDataIndexToDisplayArray')
//     setDataIndexToDisplayArray(newDataIndexToDisplayArray)
//     setDisplayUIs(newDisplayUIArray)
//   } catch (e) {
//     console.log(e, ' unable to update values')
//   }
// }

export const checkTaskIsParent = (tasks: TaskPlusType[], taskId: string) => {
  const found = tasks.find((i) => i?.parentId === taskId);
  return !!found;
};

export const checkIfParentRemovedOfChildMoved = (
  newTasks: TaskPlusType[],
  oldParentId: string,
  movedTask: TaskPlusType
) => {
  console.log(movedTask, ' movedTask inside checkIfParentRemovedOfChildMoved');
  const movedIndex = newTasks?.findIndex((n) => n?.id === movedTask?.id);
  console.log(movedIndex, ' movedIndex');

  if (movedIndex === -1) {
    console.log(' movedIndex is wrong');
    return;
  }

  const newOneBeforeParentId = newTasks[movedIndex - 1]?.parentId;
  console.log(newOneBeforeParentId, ' newOneBeforeParentId');

  if (newOneBeforeParentId === oldParentId) {
    return false;
  }

  const newOneBeforeTaskId = newTasks[movedIndex - 1]?.id;
  console.log(newOneBeforeTaskId, ' newOneBeforeTaskId');

  if (newOneBeforeTaskId === oldParentId) {
    return false;
  }

  return true;
};

export const findParentOfTaskForWeb = (
  displayUIs: DisplayUIType[],
  indexOfChild: number
) => {
  // validate values
  if (indexOfChild === 0) {
    console.log('indexOfChild is 0 inside find parent of task');
    return;
  }

  if (indexOfChild === 1) {
    console.log('indexOfChild is 1 inside findparentoftask');
    return;
  }

  if (indexOfChild > displayUIs.length - 1) {
    console.log(
      'indexOfChild greater than last indexOfChild inside findparentoftask'
    );
    return;
  }

  const parentValue = displayUIs[indexOfChild - 1];

  const found = [TODO, DOING, DONE].find((i) => i === parentValue?.notes);

  if (found) {
    console.log(found, ' order value inside findparentoftask');
    return;
  }

  return parentValue;
};
export const checkStatusChangeForWeb = (
  reorderedDisplayUIs: DisplayUIType[],
  valueMoved: DisplayUIType
) => {
  const reversed = _.reverse(reorderedDisplayUIs);
  console.log(reorderedDisplayUIs, ' reorderedDisplayUIs in checkStatusChange');
  console.log(reversed, ' reversed in checkStatusChange');
  console.log(valueMoved, ' valueMoved in checkStatusChange');
  const index = reversed.findIndex((r) => r.id === valueMoved.id);
  console.log(index, ' index in checkStatusChange');
  const sliced = reversed.slice(index);
  console.log(sliced, ' sliced in checkStatusChange');
  const headerArray = [TODO, DOING, DONE];

  for (let i = 0; i < sliced.length; i++) {
    const found = headerArray.find((j) => j === sliced[i].notes);
    console.log(found, ' found in checkStatusChange');
    if (found) {
      if (found === TODO) {
        return {
          label: TODO,
          value: TaskStatus.TODO,
        };
      } else if (found === DOING) {
        return {
          label: DOING,
          value: TaskStatus.DOING,
        };
      } else if (found === DONE) {
        return {
          label: DONE,
          value: TaskStatus.DONE,
        };
      }
    }
  }
};
export const reorderDataArray = <T>(a: T[], from: number, to: number) => {
  const backwards = to < from;
  const same = to === from;
  const movedValue = a[from];
  const newA: T[] = [];

  for (let i = 0; i < a.length; i++) {
    if (i === to) {
      if (backwards) {
        newA.push(movedValue);
        newA.push(a[i]);
        continue;
      } else if (same) {
        newA.push(a[i]);
        continue;
      } else {
        newA.push(a[i]);
        newA.push(movedValue);
        continue;
      }
    }

    if (i !== from) {
      newA.push(a[i]);
    }
  }

  return newA;
};

export const reorderParentAndChildDataArray = <T>(
  a: T[],
  from: number,
  to: number,
  oldTasks: TaskPlusType[],
  taskIdOfMovedValue: string
) => {
  console.log(oldTasks, ' oldParentIdArray');
  const backwards = to < from;

  const movedValue = a[from];
  const newA: T[] = [];

  let same: boolean = true;

  if (!backwards) {
    console.log(' !backwards inside unique case');
    for (let i = from + 1; i <= to; i++) {
      if (taskIdOfMovedValue !== oldTasks[i]?.parentId) {
        console.log(' same = false inside unique case');
        same = false;
      }
    }
  }

  // moving around children only and diff status
  if (same) {
    return a;
  }

  same = to === from;

  const childTaskIdIndexes = oldTasks
    .map((i, index) => {
      if (i?.parentId === taskIdOfMovedValue) {
        return index;
      }
      return null;
    })
    .filter((i) => i !== null);

  console.log(childTaskIdIndexes, ' childTaskIdIndexes');

  for (let i = 0; i < a.length; i++) {
    if (i === to) {
      if (backwards) {
        newA.push(movedValue);
        console.log(newA, ' newA inside backwards before child');
        for (let j = 0; j < childTaskIdIndexes.length; j++) {
          const oldIndex = childTaskIdIndexes[j];
          console.log(oldIndex, ' oldIndex inside childTaskIdIndexes');
          if (to === oldIndex) {
            continue;
          }

          if (from === oldIndex) {
            continue;
          }
          newA.push(a[oldIndex]);
        }
        console.log(newA, ' newA inside backwards after child');
        newA.push(a[i]);
        continue;
      } else if (same) {
        newA.push(a[i]);
        for (let j = 0; j < childTaskIdIndexes.length; j++) {
          const oldIndex = childTaskIdIndexes[j];
          if (to === oldIndex) {
            continue;
          }

          if (from === oldIndex) {
            continue;
          }
          newA.push(a[oldIndex]);
        }
        continue;
      } else {
        newA.push(a[i]);
        newA.push(movedValue);
        for (let j = 0; j < childTaskIdIndexes.length; j++) {
          const oldIndex = childTaskIdIndexes[j];
          if (to === oldIndex) {
            continue;
          }

          if (from === oldIndex) {
            continue;
          }
          newA.push(a[oldIndex]);
        }
        continue;
      }
    }

    if (childTaskIdIndexes.includes(i)) {
      continue;
    }

    if (i === from) {
      continue;
    }

    console.log(newA, ' newA after childTaskIdIndexes.includes(i)');

    if (i !== from) {
      newA.push(a[i]);
    }
    console.log(newA, ' newA last push');
  }

  return newA;
};

export const updateDataToDisplayUI = <T>(
  data: T[],
  setData: Dispatch<SetStateAction<T[]>>,
  dataIndexToDisplayArray: number[]
) => {
  // reorder data indices to displayUI order
  const newData: T[] = [];

  for (let i = 0; i < dataIndexToDisplayArray.length; i++) {
    const oldIndex = dataIndexToDisplayArray[i];
    if (oldIndex > -1) {
      newData.push(data[oldIndex]);
    }
  }
  setData(newData);
};

export const sortByStatus = <T>(aArray: T[], statusArray: TaskStatus[]) => {
  const toDoArray: T[] = [];
  const doingArray: T[] = [];
  const doneArray: T[] = [];

  aArray.forEach((a, index) => {
    const status = statusArray[index];

    if (status === TaskStatus.TODO || !status) {
      toDoArray.push(a);
    } else if (status === TaskStatus.DOING) {
      doingArray.push(a);
    } else if (status === TaskStatus.DONE) {
      doneArray.push(a);
    }
  });

  const newArray: T[] = toDoArray.concat(doingArray).concat(doneArray);

  return newArray;
};

export const getDisplayUIForWeb = (
  taskPluses: TaskPlusType[],
  statusArray: TaskStatus[],
  type: TaskSubType,
  userId: string
) => {
  const sortedOrder: TaskStatus[] = [];
  const toDoArray: TaskPlusType[] = [];
  const doingArray: TaskPlusType[] = [];
  const doneArray: TaskPlusType[] = [];

  const indexToDoWithStatusArray: number[] = [];
  const indexDoingWithStatusArray: number[] = [];
  const indexDoneWithStatusArray: number[] = [];

  taskPluses.forEach((taskPlus, index) => {
    const status = statusArray[index];

    if (status === TaskStatus.TODO || !status) {
      const found = sortedOrder.find((i) => i === TaskStatus.TODO);
      if (!found) {
        sortedOrder.push(TaskStatus.TODO);
        toDoArray.push({ id: TaskStatus.TODO, type, userId, notes: 'To Do' });
        toDoArray.push(taskPlus);
        indexToDoWithStatusArray.push(-1);
        indexToDoWithStatusArray.push(index);
      } else {
        toDoArray.push(taskPlus);
        indexToDoWithStatusArray.push(index);
      }
    } else if (status === TaskStatus.DOING) {
      const found = sortedOrder.find((i) => i === TaskStatus.DOING);

      if (!found) {
        sortedOrder.push(TaskStatus.DOING);
        doingArray.push({ id: TaskStatus.DOING, type, userId, notes: 'Doing' });
        doingArray.push(taskPlus);
        indexDoingWithStatusArray.push(-1);
        indexDoingWithStatusArray.push(index);
      } else {
        doingArray.push(taskPlus);
        indexDoingWithStatusArray.push(index);
      }
    } else if (status === TaskStatus.DONE) {
      const found = sortedOrder.find((i) => i === TaskStatus.DONE);

      if (!found) {
        sortedOrder.push(TaskStatus.DONE);
        doneArray.push({ id: TaskStatus.DONE, type, userId, notes: 'Done' });
        doneArray.push(taskPlus);
        indexDoneWithStatusArray.push(-1);
        indexDoneWithStatusArray.push(index);
      } else {
        doneArray.push(taskPlus);
        indexDoneWithStatusArray.push(index);
      }
    }
  });

  if (
    toDoArray?.length > 0 &&
    !(doingArray?.length > 0) &&
    !(doneArray?.length > 0)
  ) {
    const newArray: DisplayUIType[] = toDoArray
      .concat([{ id: TaskStatus.DOING, type, userId, notes: 'Doing' }])
      .concat([{ id: TaskStatus.DONE, type, userId, notes: 'Done' }]);
    const newIndexArray: number[] = indexToDoWithStatusArray
      .concat([-1])
      .concat([-1]);
    return {
      displayUIArray: newArray,
      dataIndexToDisplayArray: newIndexArray,
    };
  } else if (
    toDoArray?.length > 0 &&
    !(doingArray?.length > 0) &&
    doneArray?.length > 0
  ) {
    const newArray: DisplayUIType[] = toDoArray
      .concat([{ id: TaskStatus.DOING, type, userId, notes: 'Doing' }])
      .concat(doneArray);
    const newIndexArray: number[] = indexToDoWithStatusArray
      .concat([-1])
      .concat(indexDoneWithStatusArray);

    return {
      displayUIArray: newArray,
      dataIndexToDisplayArray: newIndexArray,
    };
  } else if (
    toDoArray?.length > 0 &&
    doingArray?.length > 0 &&
    !(doneArray?.length > 0)
  ) {
    const newArray: DisplayUIType[] = toDoArray
      .concat(doingArray)
      .concat([{ id: TaskStatus.DONE, type, userId, notes: 'Done' }]);
    const newIndexArray: number[] = indexToDoWithStatusArray
      .concat(indexDoingWithStatusArray)
      .concat([-1]);

    return {
      displayUIArray: newArray,
      dataIndexToDisplayArray: newIndexArray,
    };
  } else if (
    !(toDoArray?.length > 0) &&
    doingArray?.length > 0 &&
    !(doneArray?.length > 0)
  ) {
    const newArray: DisplayUIType[] = [
      { id: TaskStatus.TODO, type, userId, notes: 'To Do' } as DisplayUIType,
    ]
      .concat(doingArray)
      .concat([{ id: TaskStatus.DONE, type, userId, notes: 'Done' }]);
    const newIndexArray: number[] = [-1]
      .concat(indexDoingWithStatusArray)
      .concat([-1]);

    return {
      displayUIArray: newArray,
      dataIndexToDisplayArray: newIndexArray,
    };
  } else if (
    !(toDoArray?.length > 0) &&
    !(doingArray?.length > 0) &&
    doneArray?.length > 0
  ) {
    const newArray: DisplayUIType[] = [
      { id: TaskStatus.TODO, type, userId, notes: 'To Do' } as DisplayUIType,
    ]
      .concat([{ id: TaskStatus.DOING, type, userId, notes: 'Doing' }])
      .concat(doneArray);
    const newIndexArray: number[] = [-1]
      .concat([-1])
      .concat(indexDoneWithStatusArray);

    return {
      displayUIArray: newArray,
      dataIndexToDisplayArray: newIndexArray,
    };
  } else if (
    !(toDoArray?.length > 0) &&
    doingArray?.length > 0 &&
    doneArray?.length > 0
  ) {
    const newArray: DisplayUIType[] = [
      { id: TaskStatus.TODO, type, userId, notes: 'To Do' } as DisplayUIType,
    ]
      .concat(doingArray)
      .concat(doneArray);
    const newIndexArray: number[] = [-1]
      .concat(indexDoingWithStatusArray)
      .concat(indexDoneWithStatusArray);

    return {
      displayUIArray: newArray,
      dataIndexToDisplayArray: newIndexArray,
    };
  } else if (
    !(toDoArray?.length > 0) &&
    !(doingArray?.length > 0) &&
    !(doneArray?.length > 0)
  ) {
    const newArray: DisplayUIType[] = [
      { id: TaskStatus.TODO, type, userId, notes: 'To Do' } as DisplayUIType,
    ]
      .concat([{ id: TaskStatus.DOING, type, userId, notes: 'Doing' }])
      .concat([{ id: TaskStatus.DONE, type, userId, notes: 'Done' }]);
    const newIndexArray: number[] = [-1].concat([-1]).concat([-1]);

    return {
      displayUIArray: newArray,
      dataIndexToDisplayArray: newIndexArray,
    };
  }

  const newArray: DisplayUIType[] = toDoArray
    .concat(doingArray)
    .concat(doneArray);
  const newIndexArray: number[] = indexToDoWithStatusArray
    .concat(indexDoingWithStatusArray)
    .concat(indexDoneWithStatusArray);

  return {
    displayUIArray: newArray,
    dataIndexToDisplayArray: newIndexArray,
  };
};

export const getIndexUpdatesFromUIForWeb = (
  reorderedDisplayUIs: DisplayUIType[],
  oldDisplayUIs: DisplayUIType[],
  valueMoved: DisplayUIType
): { from: number; to: number } => {
  const filteredReorderedDisplayUIs = reorderedDisplayUIs
    .filter((i) => i.notes !== TODO)
    .filter((i) => i.notes !== DOING)
    .filter((i) => i.notes !== DONE);

  const filteredOldDisplayUIs = oldDisplayUIs
    .filter((i) => i.notes !== TODO)
    .filter((i) => i.notes !== DOING)
    .filter((i) => i.notes !== DONE);

  const from = filteredOldDisplayUIs.findIndex((i) => i.id === valueMoved.id);
  const to = filteredReorderedDisplayUIs.findIndex(
    (i) => i.id === valueMoved.id
  );

  return { from, to };
};

export const addToDataArrayAfterIndex = <T>(
  a: T,
  aArray: T[],
  isInitial: boolean,
  index?: number
) => {
  console.log(index, ' inside inside addToDataArrayAfterIndex');
  if (!isInitial) {
    if (typeof index !== 'number') {
      console.log(
        a,
        aArray,
        'no index exiting inside addToDataArrayAfterIndex'
      );
      return;
    }
    const newaArray = aArray
      .slice(0, index + 1)
      .concat([a])
      .concat(aArray.slice(index + 1));

    return newaArray;
  }

  return [a];
};

export const addToOrderArrayAfterIndexWithNewOrder = (
  orderArray: number[],
  isInitial: boolean,
  setOrderArray: Dispatch<SetStateAction<number[]>>,
  index?: number
) => {
  if (!isInitial) {
    if (typeof index !== 'number') {
      console.log(
        orderArray,
        'no index exiting inside addToOrderArrayAfterIndex'
      );
      return;
    }

    const subOrderArray = orderArray.slice(0, index + 1);
    const secondSubOrderArray = orderArray.slice(index + 1);

    for (let i = 0; i < secondSubOrderArray.length; i++) {
      secondSubOrderArray[i] += 1;
    }

    const newOrderArray = subOrderArray
      .concat([subOrderArray.length])
      .concat(secondSubOrderArray);

    setOrderArray(newOrderArray);
    return newOrderArray;
  }

  setOrderArray([0]);
  return [0];
};

export const updateDataArray = <T>(
  t: T,
  tArray: T[],
  setTArray: Dispatch<SetStateAction<T[]>>,
  index: number
) => {
  console.log(tArray, ' tArray');
  const newTArray = tArray
    .slice(0, index)
    .concat([t])
    .concat(tArray.slice(index + 1));

  setTArray(newTArray);
  return newTArray;
};

export const removeFromDataArray = <T>(
  index: number,
  dataArray: T[],
  setDataArray: Dispatch<SetStateAction<T[]>>
) => {
  const newDataArray = [
    ...dataArray.slice(0, index),
    ...dataArray.slice(index + 1),
  ];

  setDataArray(newDataArray);
  return newDataArray;
};
// export const closeRealm = () => // realm.close()

export const sortTasksByParent = (
  parentIdArray: string[],
  taskPluses: TaskPlusType[]
) => {
  let doneSortedTaskPluses: TaskPlusType[] = [];

  let sortedTaskPluses: TaskPlusType[] = [];

  for (let i = 0; i < taskPluses.length; i++) {
    const value = doneSortedTaskPluses.find((u) => u?.id === taskPluses[i]?.id);

    if (!value) {
      sortedTaskPluses.push(taskPluses[i]);
      doneSortedTaskPluses.push(taskPluses[i]);

      for (let j = 0; j < taskPluses.length; j++) {
        if (taskPluses[i]?.id === parentIdArray[j]) {
          sortedTaskPluses.push(taskPluses[j]);
          doneSortedTaskPluses.push(taskPluses[j]);
        }
      }
    }
  }

  return {
    sortedTaskPluses,
  };
};
