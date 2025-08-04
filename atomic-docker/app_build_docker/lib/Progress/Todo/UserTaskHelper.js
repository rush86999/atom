"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.sortTasksByParent = exports.removeFromDataArray = exports.updateDataArray = exports.addToOrderArrayAfterIndexWithNewOrder = exports.addToDataArrayAfterIndex = exports.getIndexUpdatesFromUIForWeb = exports.getDisplayUIForWeb = exports.sortByStatus = exports.updateDataToDisplayUI = exports.reorderParentAndChildDataArray = exports.reorderDataArray = exports.checkStatusChangeForWeb = exports.findParentOfTaskForWeb = exports.checkIfParentRemovedOfChildMoved = exports.checkTaskIsParent = exports.onDragEndUpdateForWeb = exports.sortByOrder = exports.addParent = exports.removeParent = void 0;
const date_utils_1 = require("@lib/date-utils");
const lodash_1 = __importDefault(require("lodash"));
// const CONVERTOWEBAPIDEV = CONVERT_TO_WEBP_API
// dayjs.extend(utc)
// dayjs.extend(quarterOfYear)
const constants_1 = require("@lib/Progress/Todo/constants");
const UserTaskHelper3_1 = require("./UserTaskHelper3");
const bucketRegion = 'us-east-1';
const bucketName = 'atomiclife-app-public-image-prod-uncompressed';
const escapeUnsafe = (unsafe) => unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/ /gi, '-');
const TODO = 'To Do';
const DOING = 'Doing';
const DONE = 'Done';
const removeParent = async (client, index, tasks) => {
    try {
        tasks[index].parentId = null;
        await (0, UserTaskHelper3_1.updateTaskByIdInDb)(client, tasks[index]);
        console.log(tasks[index], ' successfully updated');
    }
    catch (e) {
        console.log(e, ' unable to remove parent');
    }
};
exports.removeParent = removeParent;
const addParent = async (client, index, indexBefore, tasks) => {
    try {
        if (indexBefore < 0) {
            console.log(' no parent in prior note');
            return;
        }
        console.log(index, indexBefore, ' type, index, indexBefore');
        const newDate = (0, date_utils_1.dayjs)().format();
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
        await (0, UserTaskHelper3_1.updateTaskByIdInDb)(client, tasks[index]);
        console.log(tasks[index], ' parent added');
    }
    catch (e) {
        console.log(e, ' unable to add parent');
    }
};
exports.addParent = addParent;
const sortByOrder = (a, orderArray) => {
    const newA = a.map((i, inx) => ({ a: i, order: orderArray[inx] }));
    newA.sort((a, b) => a.order - b.order);
    const sortedA = newA.map((i) => i.a);
    return sortedA;
};
exports.sortByOrder = sortByOrder;
const reorder = (list, startIndex, endIndex) => {
    const result = Array.from(list);
    const [removed] = result.splice(startIndex, 1);
    result.splice(endIndex, 0, removed);
    return result;
};
const onDragEndUpdateForWeb = async (dropResult, tasks, oldDisplayUIs, setDisplayUIs, dataIndexToDisplayArray, setDataIndexToDisplayArray, taskType, userId, client) => {
    try {
        // dropped nowhere
        if (!dropResult.destination) {
            return;
        }
        const source = dropResult.source;
        const destination = dropResult.destination;
        // did not move anywhere - can bail early
        if (source.droppableId === destination.droppableId &&
            source.index === destination.index) {
            return;
        }
        const from = source.index;
        const to = destination.index;
        const reorderedDisplayUIs = reorder(oldDisplayUIs, from, to);
        const tempDisplayUI = (0, exports.reorderDataArray)(oldDisplayUIs, from, to);
        const tempDataIndex = (0, exports.reorderDataArray)(dataIndexToDisplayArray, from, to);
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
        const isParent = (0, exports.checkTaskIsParent)(tasks, taskIdOfMovedValue);
        console.log(isParent, ' isParent');
        // first update data arrays
        const { from: fromDataIndex, to: toDataIndex } = (0, exports.getIndexUpdatesFromUIForWeb)(reorderedDisplayUIs, oldDisplayUIs, movedValue);
        console.log(fromDataIndex, toDataIndex, ' fromDataIndex toDataIndex');
        let newTasks = [];
        if (isParent) {
            newTasks = (0, exports.reorderParentAndChildDataArray)(tasks, fromDataIndex, toDataIndex, tasks, taskIdOfMovedValue);
        }
        else {
            newTasks = (0, exports.reorderDataArray)(tasks, fromDataIndex, toDataIndex);
        }
        // if child check if parent removed
        if (tasks?.[fromDataIndex]?.parentId) {
            const parentRemoved = (0, exports.checkIfParentRemovedOfChildMoved)(newTasks, tasks?.[fromDataIndex]?.parentId, tasks[oldDataIndex]);
            console.log(parentRemoved, ' parentRemoved');
            if (parentRemoved) {
                // remove from db
                // updateTaskByIdInDb
                const movedTask = tasks[oldDataIndex];
                movedTask.parentId = null;
                await (0, UserTaskHelper3_1.updateTaskByIdInDb)(client, movedTask);
                console.log(newTasks, ' newTasks after parent removed');
            }
        }
        // check if status changed
        const newStatus = (0, exports.checkStatusChangeForWeb)(reorderedDisplayUIs, movedValue);
        console.log(newStatus, ' newStatus');
        // update status
        if (newStatus?.value !== tasks?.[fromDataIndex]?.status) {
            const movedTask = tasks[oldDataIndex];
            movedTask.status = newStatus?.value || constants_1.TaskStatus.TODO;
            await (0, UserTaskHelper3_1.updateTaskByIdInDb)(client, movedTask);
            console.log(newTasks, ' newTasks after status update');
        }
        console.log(newTasks, ' newTasks');
        // update order in db
        newTasks?.forEach((t, inx) => (t.order = inx));
        await (0, UserTaskHelper3_1.upsertManyTasksInDb)(client, newTasks?.map((i) => lodash_1.default.omit(i, ['startDate', 'endDate', 'nextDay'])));
        const newStatusArray = newTasks.map((t) => t?.status);
        const { displayUIArray: newDisplayUIArray, dataIndexToDisplayArray: newDataIndexToDisplayArray, } = (0, exports.getDisplayUIForWeb)(newTasks, newStatusArray, taskType, userId);
        console.log(newDataIndexToDisplayArray, ' newDataIndexToDisplayArray');
        setDataIndexToDisplayArray(newDataIndexToDisplayArray);
        setDisplayUIs(newDisplayUIArray);
    }
    catch (e) {
        console.log(e, ' unable to update values');
    }
};
exports.onDragEndUpdateForWeb = onDragEndUpdateForWeb;
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
const checkTaskIsParent = (tasks, taskId) => {
    const found = tasks.find((i) => i?.parentId === taskId);
    return !!found;
};
exports.checkTaskIsParent = checkTaskIsParent;
const checkIfParentRemovedOfChildMoved = (newTasks, oldParentId, movedTask) => {
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
exports.checkIfParentRemovedOfChildMoved = checkIfParentRemovedOfChildMoved;
const findParentOfTaskForWeb = (displayUIs, indexOfChild) => {
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
        console.log('indexOfChild greater than last indexOfChild inside findparentoftask');
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
exports.findParentOfTaskForWeb = findParentOfTaskForWeb;
const checkStatusChangeForWeb = (reorderedDisplayUIs, valueMoved) => {
    const reversed = lodash_1.default.reverse(reorderedDisplayUIs);
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
                    value: constants_1.TaskStatus.TODO,
                };
            }
            else if (found === DOING) {
                return {
                    label: DOING,
                    value: constants_1.TaskStatus.DOING,
                };
            }
            else if (found === DONE) {
                return {
                    label: DONE,
                    value: constants_1.TaskStatus.DONE,
                };
            }
        }
    }
};
exports.checkStatusChangeForWeb = checkStatusChangeForWeb;
const reorderDataArray = (a, from, to) => {
    const backwards = to < from;
    const same = to === from;
    const movedValue = a[from];
    const newA = [];
    for (let i = 0; i < a.length; i++) {
        if (i === to) {
            if (backwards) {
                newA.push(movedValue);
                newA.push(a[i]);
                continue;
            }
            else if (same) {
                newA.push(a[i]);
                continue;
            }
            else {
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
exports.reorderDataArray = reorderDataArray;
const reorderParentAndChildDataArray = (a, from, to, oldTasks, taskIdOfMovedValue) => {
    console.log(oldTasks, ' oldParentIdArray');
    const backwards = to < from;
    const movedValue = a[from];
    const newA = [];
    let same = true;
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
            }
            else if (same) {
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
            }
            else {
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
exports.reorderParentAndChildDataArray = reorderParentAndChildDataArray;
const updateDataToDisplayUI = (data, setData, dataIndexToDisplayArray) => {
    // reorder data indices to displayUI order
    const newData = [];
    for (let i = 0; i < dataIndexToDisplayArray.length; i++) {
        const oldIndex = dataIndexToDisplayArray[i];
        if (oldIndex > -1) {
            newData.push(data[oldIndex]);
        }
    }
    setData(newData);
};
exports.updateDataToDisplayUI = updateDataToDisplayUI;
const sortByStatus = (aArray, statusArray) => {
    const toDoArray = [];
    const doingArray = [];
    const doneArray = [];
    aArray.forEach((a, index) => {
        const status = statusArray[index];
        if (status === constants_1.TaskStatus.TODO || !status) {
            toDoArray.push(a);
        }
        else if (status === constants_1.TaskStatus.DOING) {
            doingArray.push(a);
        }
        else if (status === constants_1.TaskStatus.DONE) {
            doneArray.push(a);
        }
    });
    const newArray = toDoArray.concat(doingArray).concat(doneArray);
    return newArray;
};
exports.sortByStatus = sortByStatus;
const getDisplayUIForWeb = (taskPluses, statusArray, type, userId) => {
    const sortedOrder = [];
    const toDoArray = [];
    const doingArray = [];
    const doneArray = [];
    const indexToDoWithStatusArray = [];
    const indexDoingWithStatusArray = [];
    const indexDoneWithStatusArray = [];
    taskPluses.forEach((taskPlus, index) => {
        const status = statusArray[index];
        if (status === constants_1.TaskStatus.TODO || !status) {
            const found = sortedOrder.find((i) => i === constants_1.TaskStatus.TODO);
            if (!found) {
                sortedOrder.push(constants_1.TaskStatus.TODO);
                toDoArray.push({ id: constants_1.TaskStatus.TODO, type, userId, notes: 'To Do' });
                toDoArray.push(taskPlus);
                indexToDoWithStatusArray.push(-1);
                indexToDoWithStatusArray.push(index);
            }
            else {
                toDoArray.push(taskPlus);
                indexToDoWithStatusArray.push(index);
            }
        }
        else if (status === constants_1.TaskStatus.DOING) {
            const found = sortedOrder.find((i) => i === constants_1.TaskStatus.DOING);
            if (!found) {
                sortedOrder.push(constants_1.TaskStatus.DOING);
                doingArray.push({ id: constants_1.TaskStatus.DOING, type, userId, notes: 'Doing' });
                doingArray.push(taskPlus);
                indexDoingWithStatusArray.push(-1);
                indexDoingWithStatusArray.push(index);
            }
            else {
                doingArray.push(taskPlus);
                indexDoingWithStatusArray.push(index);
            }
        }
        else if (status === constants_1.TaskStatus.DONE) {
            const found = sortedOrder.find((i) => i === constants_1.TaskStatus.DONE);
            if (!found) {
                sortedOrder.push(constants_1.TaskStatus.DONE);
                doneArray.push({ id: constants_1.TaskStatus.DONE, type, userId, notes: 'Done' });
                doneArray.push(taskPlus);
                indexDoneWithStatusArray.push(-1);
                indexDoneWithStatusArray.push(index);
            }
            else {
                doneArray.push(taskPlus);
                indexDoneWithStatusArray.push(index);
            }
        }
    });
    if (toDoArray?.length > 0 &&
        !(doingArray?.length > 0) &&
        !(doneArray?.length > 0)) {
        const newArray = toDoArray
            .concat([{ id: constants_1.TaskStatus.DOING, type, userId, notes: 'Doing' }])
            .concat([{ id: constants_1.TaskStatus.DONE, type, userId, notes: 'Done' }]);
        const newIndexArray = indexToDoWithStatusArray
            .concat([-1])
            .concat([-1]);
        return {
            displayUIArray: newArray,
            dataIndexToDisplayArray: newIndexArray,
        };
    }
    else if (toDoArray?.length > 0 &&
        !(doingArray?.length > 0) &&
        doneArray?.length > 0) {
        const newArray = toDoArray
            .concat([{ id: constants_1.TaskStatus.DOING, type, userId, notes: 'Doing' }])
            .concat(doneArray);
        const newIndexArray = indexToDoWithStatusArray
            .concat([-1])
            .concat(indexDoneWithStatusArray);
        return {
            displayUIArray: newArray,
            dataIndexToDisplayArray: newIndexArray,
        };
    }
    else if (toDoArray?.length > 0 &&
        doingArray?.length > 0 &&
        !(doneArray?.length > 0)) {
        const newArray = toDoArray
            .concat(doingArray)
            .concat([{ id: constants_1.TaskStatus.DONE, type, userId, notes: 'Done' }]);
        const newIndexArray = indexToDoWithStatusArray
            .concat(indexDoingWithStatusArray)
            .concat([-1]);
        return {
            displayUIArray: newArray,
            dataIndexToDisplayArray: newIndexArray,
        };
    }
    else if (!(toDoArray?.length > 0) &&
        doingArray?.length > 0 &&
        !(doneArray?.length > 0)) {
        const newArray = [
            { id: constants_1.TaskStatus.TODO, type, userId, notes: 'To Do' },
        ]
            .concat(doingArray)
            .concat([{ id: constants_1.TaskStatus.DONE, type, userId, notes: 'Done' }]);
        const newIndexArray = [-1]
            .concat(indexDoingWithStatusArray)
            .concat([-1]);
        return {
            displayUIArray: newArray,
            dataIndexToDisplayArray: newIndexArray,
        };
    }
    else if (!(toDoArray?.length > 0) &&
        !(doingArray?.length > 0) &&
        doneArray?.length > 0) {
        const newArray = [
            { id: constants_1.TaskStatus.TODO, type, userId, notes: 'To Do' },
        ]
            .concat([{ id: constants_1.TaskStatus.DOING, type, userId, notes: 'Doing' }])
            .concat(doneArray);
        const newIndexArray = [-1]
            .concat([-1])
            .concat(indexDoneWithStatusArray);
        return {
            displayUIArray: newArray,
            dataIndexToDisplayArray: newIndexArray,
        };
    }
    else if (!(toDoArray?.length > 0) &&
        doingArray?.length > 0 &&
        doneArray?.length > 0) {
        const newArray = [
            { id: constants_1.TaskStatus.TODO, type, userId, notes: 'To Do' },
        ]
            .concat(doingArray)
            .concat(doneArray);
        const newIndexArray = [-1]
            .concat(indexDoingWithStatusArray)
            .concat(indexDoneWithStatusArray);
        return {
            displayUIArray: newArray,
            dataIndexToDisplayArray: newIndexArray,
        };
    }
    else if (!(toDoArray?.length > 0) &&
        !(doingArray?.length > 0) &&
        !(doneArray?.length > 0)) {
        const newArray = [
            { id: constants_1.TaskStatus.TODO, type, userId, notes: 'To Do' },
        ]
            .concat([{ id: constants_1.TaskStatus.DOING, type, userId, notes: 'Doing' }])
            .concat([{ id: constants_1.TaskStatus.DONE, type, userId, notes: 'Done' }]);
        const newIndexArray = [-1].concat([-1]).concat([-1]);
        return {
            displayUIArray: newArray,
            dataIndexToDisplayArray: newIndexArray,
        };
    }
    const newArray = toDoArray
        .concat(doingArray)
        .concat(doneArray);
    const newIndexArray = indexToDoWithStatusArray
        .concat(indexDoingWithStatusArray)
        .concat(indexDoneWithStatusArray);
    return {
        displayUIArray: newArray,
        dataIndexToDisplayArray: newIndexArray,
    };
};
exports.getDisplayUIForWeb = getDisplayUIForWeb;
const getIndexUpdatesFromUIForWeb = (reorderedDisplayUIs, oldDisplayUIs, valueMoved) => {
    const filteredReorderedDisplayUIs = reorderedDisplayUIs
        .filter((i) => i.notes !== TODO)
        .filter((i) => i.notes !== DOING)
        .filter((i) => i.notes !== DONE);
    const filteredOldDisplayUIs = oldDisplayUIs
        .filter((i) => i.notes !== TODO)
        .filter((i) => i.notes !== DOING)
        .filter((i) => i.notes !== DONE);
    const from = filteredOldDisplayUIs.findIndex((i) => i.id === valueMoved.id);
    const to = filteredReorderedDisplayUIs.findIndex((i) => i.id === valueMoved.id);
    return { from, to };
};
exports.getIndexUpdatesFromUIForWeb = getIndexUpdatesFromUIForWeb;
const addToDataArrayAfterIndex = (a, aArray, isInitial, index) => {
    console.log(index, ' inside inside addToDataArrayAfterIndex');
    if (!isInitial) {
        if (typeof index !== 'number') {
            console.log(a, aArray, 'no index exiting inside addToDataArrayAfterIndex');
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
exports.addToDataArrayAfterIndex = addToDataArrayAfterIndex;
const addToOrderArrayAfterIndexWithNewOrder = (orderArray, isInitial, setOrderArray, index) => {
    if (!isInitial) {
        if (typeof index !== 'number') {
            console.log(orderArray, 'no index exiting inside addToOrderArrayAfterIndex');
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
exports.addToOrderArrayAfterIndexWithNewOrder = addToOrderArrayAfterIndexWithNewOrder;
const updateDataArray = (t, tArray, setTArray, index) => {
    console.log(tArray, ' tArray');
    const newTArray = tArray
        .slice(0, index)
        .concat([t])
        .concat(tArray.slice(index + 1));
    setTArray(newTArray);
    return newTArray;
};
exports.updateDataArray = updateDataArray;
const removeFromDataArray = (index, dataArray, setDataArray) => {
    const newDataArray = [
        ...dataArray.slice(0, index),
        ...dataArray.slice(index + 1),
    ];
    setDataArray(newDataArray);
    return newDataArray;
};
exports.removeFromDataArray = removeFromDataArray;
// export const closeRealm = () => // realm.close()
const sortTasksByParent = (parentIdArray, taskPluses) => {
    let doneSortedTaskPluses = [];
    let sortedTaskPluses = [];
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
exports.sortTasksByParent = sortTasksByParent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlclRhc2tIZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJVc2VyVGFza0hlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFPQSxnREFBd0M7QUFFeEMsb0RBQXVCO0FBZ0J2QixnREFBZ0Q7QUFFaEQsb0JBQW9CO0FBQ3BCLDhCQUE4QjtBQUU5Qiw0REFBMEQ7QUFDMUQsdURBQTRFO0FBUTVFLE1BQU0sWUFBWSxHQUFHLFdBQVcsQ0FBQztBQUNqQyxNQUFNLFVBQVUsR0FBRywrQ0FBK0MsQ0FBQztBQXNCbkUsTUFBTSxZQUFZLEdBQUcsQ0FBQyxNQUFjLEVBQUUsRUFBRSxDQUN0QyxNQUFNO0tBQ0gsT0FBTyxDQUFDLElBQUksRUFBRSxPQUFPLENBQUM7S0FDdEIsT0FBTyxDQUFDLElBQUksRUFBRSxNQUFNLENBQUM7S0FDckIsT0FBTyxDQUFDLElBQUksRUFBRSxNQUFNLENBQUM7S0FDckIsT0FBTyxDQUFDLElBQUksRUFBRSxRQUFRLENBQUM7S0FDdkIsT0FBTyxDQUFDLElBQUksRUFBRSxRQUFRLENBQUM7S0FDdkIsT0FBTyxDQUFDLEtBQUssRUFBRSxHQUFHLENBQUMsQ0FBQztBQUV6QixNQUFNLElBQUksR0FBRyxPQUFPLENBQUM7QUFDckIsTUFBTSxLQUFLLEdBQUcsT0FBTyxDQUFDO0FBQ3RCLE1BQU0sSUFBSSxHQUFHLE1BQU0sQ0FBQztBQVFiLE1BQU0sWUFBWSxHQUFHLEtBQUssRUFDL0IsTUFBMkMsRUFDM0MsS0FBYSxFQUNiLEtBQXFCLEVBQ3JCLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxLQUFLLENBQUMsS0FBSyxDQUFDLENBQUMsUUFBUSxHQUFHLElBQUksQ0FBQztRQUU3QixNQUFNLElBQUEsb0NBQWtCLEVBQUMsTUFBTSxFQUFFLEtBQUssQ0FBQyxLQUFLLENBQUMsQ0FBQyxDQUFDO1FBQy9DLE9BQU8sQ0FBQyxHQUFHLENBQUMsS0FBSyxDQUFDLEtBQUssQ0FBQyxFQUFFLHVCQUF1QixDQUFDLENBQUM7SUFDckQsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSwwQkFBMEIsQ0FBQyxDQUFDO0lBQzdDLENBQUM7QUFDSCxDQUFDLENBQUM7QUFiVyxRQUFBLFlBQVksZ0JBYXZCO0FBRUssTUFBTSxTQUFTLEdBQUcsS0FBSyxFQUM1QixNQUEyQyxFQUMzQyxLQUFhLEVBQ2IsV0FBbUIsRUFDbkIsS0FBcUIsRUFDckIsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILElBQUksV0FBVyxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ3BCLE9BQU8sQ0FBQyxHQUFHLENBQUMsMEJBQTBCLENBQUMsQ0FBQztZQUN4QyxPQUFPO1FBQ1QsQ0FBQztRQUVELE9BQU8sQ0FBQyxHQUFHLENBQUMsS0FBSyxFQUFFLFdBQVcsRUFBRSwyQkFBMkIsQ0FBQyxDQUFDO1FBRTdELE1BQU0sT0FBTyxHQUFHLElBQUEsa0JBQUssR0FBRSxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBRWpDLElBQUksY0FBYyxHQUFHLEtBQUssQ0FBQyxXQUFXLENBQUMsRUFBRSxFQUFFLENBQUM7UUFDNUMsSUFBSSxhQUFhLEdBQUcsV0FBVyxDQUFDO1FBQ2hDLElBQUksZ0JBQWdCLEdBQUcsS0FBSyxDQUFDLFdBQVcsQ0FBQyxFQUFFLFFBQVEsQ0FBQztRQUNwRCxPQUFPLGdCQUFnQixFQUFFLE1BQU0sR0FBRyxDQUFDLElBQUksYUFBYSxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7WUFDMUQsYUFBYSxFQUFFLENBQUM7WUFDaEIsY0FBYyxHQUFHLEtBQUssQ0FBQyxhQUFhLENBQUMsRUFBRSxFQUFFLENBQUM7WUFDMUMsZ0JBQWdCLEdBQUcsS0FBSyxDQUFDLGFBQWEsQ0FBQyxFQUFFLFFBQVEsQ0FBQztRQUNwRCxDQUFDO1FBRUQsSUFBSSxhQUFhLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDdEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxhQUFhLEVBQUUsb0JBQW9CLENBQUMsQ0FBQztZQUNqRCxPQUFPO1FBQ1QsQ0FBQztRQUVELEtBQUssQ0FBQyxLQUFLLENBQUMsQ0FBQyxRQUFRLEdBQUcsY0FBYyxDQUFDO1FBRXZDLE1BQU0sSUFBQSxvQ0FBa0IsRUFBQyxNQUFNLEVBQUUsS0FBSyxDQUFDLEtBQUssQ0FBQyxDQUFDLENBQUM7UUFFL0MsT0FBTyxDQUFDLEdBQUcsQ0FBQyxLQUFLLENBQUMsS0FBSyxDQUFDLEVBQUUsZUFBZSxDQUFDLENBQUM7SUFDN0MsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSx1QkFBdUIsQ0FBQyxDQUFDO0lBQzFDLENBQUM7QUFDSCxDQUFDLENBQUM7QUF0Q1csUUFBQSxTQUFTLGFBc0NwQjtBQUNLLE1BQU0sV0FBVyxHQUFHLENBQUksQ0FBTSxFQUFFLFVBQW9CLEVBQUUsRUFBRTtJQUM3RCxNQUFNLElBQUksR0FBRyxDQUFDLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEdBQUcsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLENBQUMsRUFBRSxDQUFDLEVBQUUsS0FBSyxFQUFFLFVBQVUsQ0FBQyxHQUFHLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQztJQUVuRSxJQUFJLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLEtBQUssR0FBRyxDQUFDLENBQUMsS0FBSyxDQUFDLENBQUM7SUFFdkMsTUFBTSxPQUFPLEdBQUcsSUFBSSxDQUFDLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO0lBQ3JDLE9BQU8sT0FBTyxDQUFDO0FBQ2pCLENBQUMsQ0FBQztBQVBXLFFBQUEsV0FBVyxlQU90QjtBQUVGLE1BQU0sT0FBTyxHQUFHLENBQUksSUFBUyxFQUFFLFVBQWtCLEVBQUUsUUFBZ0IsRUFBRSxFQUFFO0lBQ3JFLE1BQU0sTUFBTSxHQUFHLEtBQUssQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLENBQUM7SUFDaEMsTUFBTSxDQUFDLE9BQU8sQ0FBQyxHQUFHLE1BQU0sQ0FBQyxNQUFNLENBQUMsVUFBVSxFQUFFLENBQUMsQ0FBQyxDQUFDO0lBQy9DLE1BQU0sQ0FBQyxNQUFNLENBQUMsUUFBUSxFQUFFLENBQUMsRUFBRSxPQUFPLENBQUMsQ0FBQztJQUVwQyxPQUFPLE1BQU0sQ0FBQztBQUNoQixDQUFDLENBQUM7QUFFSyxNQUFNLHFCQUFxQixHQUFHLEtBQUssRUFDeEMsVUFBc0IsRUFDdEIsS0FBcUIsRUFDckIsYUFBOEIsRUFDOUIsYUFBd0QsRUFDeEQsdUJBQWlDLEVBQ2pDLDBCQUE4RCxFQUM5RCxRQUFxQixFQUNyQixNQUFjLEVBQ2QsTUFBMkMsRUFDM0MsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILGtCQUFrQjtRQUNsQixJQUFJLENBQUMsVUFBVSxDQUFDLFdBQVcsRUFBRSxDQUFDO1lBQzVCLE9BQU87UUFDVCxDQUFDO1FBRUQsTUFBTSxNQUFNLEdBQXNCLFVBQVUsQ0FBQyxNQUFNLENBQUM7UUFDcEQsTUFBTSxXQUFXLEdBQXNCLFVBQVUsQ0FBQyxXQUFXLENBQUM7UUFFOUQseUNBQXlDO1FBQ3pDLElBQ0UsTUFBTSxDQUFDLFdBQVcsS0FBSyxXQUFXLENBQUMsV0FBVztZQUM5QyxNQUFNLENBQUMsS0FBSyxLQUFLLFdBQVcsQ0FBQyxLQUFLLEVBQ2xDLENBQUM7WUFDRCxPQUFPO1FBQ1QsQ0FBQztRQUVELE1BQU0sSUFBSSxHQUFHLE1BQU0sQ0FBQyxLQUFLLENBQUM7UUFDMUIsTUFBTSxFQUFFLEdBQUcsV0FBVyxDQUFDLEtBQUssQ0FBQztRQUM3QixNQUFNLG1CQUFtQixHQUFHLE9BQU8sQ0FBQyxhQUFhLEVBQUUsSUFBSSxFQUFFLEVBQUUsQ0FBQyxDQUFDO1FBRTdELE1BQU0sYUFBYSxHQUFHLElBQUEsd0JBQWdCLEVBQUMsYUFBYSxFQUFFLElBQUksRUFBRSxFQUFFLENBQUMsQ0FBQztRQUNoRSxNQUFNLGFBQWEsR0FBRyxJQUFBLHdCQUFnQixFQUFDLHVCQUF1QixFQUFFLElBQUksRUFBRSxFQUFFLENBQUMsQ0FBQztRQUMxRSxhQUFhLENBQUMsYUFBYSxDQUFDLENBQUM7UUFDN0IsMEJBQTBCLENBQUMsYUFBYSxDQUFDLENBQUM7UUFFMUMsSUFBSSxJQUFJLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDYixPQUFPLENBQUMsR0FBRyxDQUFDLCtCQUErQixDQUFDLENBQUM7WUFDN0MsT0FBTztRQUNULENBQUM7UUFFRCxPQUFPLENBQUMsR0FBRyxDQUFDLElBQUksRUFBRSxhQUFhLENBQUMsQ0FBQztRQUVqQyxPQUFPLENBQUMsR0FBRyxDQUFDLEtBQUssRUFBRSxZQUFZLENBQUMsQ0FBQztRQUNqQyxhQUFhO1FBQ2IsTUFBTSxVQUFVLEdBQUcsYUFBYSxDQUFDLElBQUksQ0FBQyxDQUFDO1FBRXZDLE9BQU8sQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFLGFBQWEsQ0FBQyxDQUFDO1FBRXZDLGtCQUFrQjtRQUNsQixNQUFNLFlBQVksR0FBRyx1QkFBdUIsQ0FBQyxJQUFJLENBQUMsQ0FBQztRQUNuRCxPQUFPLENBQUMsR0FBRyxDQUFDLFlBQVksRUFBRSxlQUFlLENBQUMsQ0FBQztRQUMzQyxNQUFNLGtCQUFrQixHQUFHLEtBQUssQ0FBQyxZQUFZLENBQUMsRUFBRSxFQUFFLENBQUM7UUFFbkQsTUFBTSxRQUFRLEdBQUcsSUFBQSx5QkFBaUIsRUFBQyxLQUFLLEVBQUUsa0JBQWtCLENBQUMsQ0FBQztRQUM5RCxPQUFPLENBQUMsR0FBRyxDQUFDLFFBQVEsRUFBRSxXQUFXLENBQUMsQ0FBQztRQUNuQywyQkFBMkI7UUFDM0IsTUFBTSxFQUFFLElBQUksRUFBRSxhQUFhLEVBQUUsRUFBRSxFQUFFLFdBQVcsRUFBRSxHQUM1QyxJQUFBLG1DQUEyQixFQUN6QixtQkFBbUIsRUFDbkIsYUFBYSxFQUNiLFVBQVUsQ0FDWCxDQUFDO1FBQ0osT0FBTyxDQUFDLEdBQUcsQ0FBQyxhQUFhLEVBQUUsV0FBVyxFQUFFLDRCQUE0QixDQUFDLENBQUM7UUFFdEUsSUFBSSxRQUFRLEdBQUcsRUFBRSxDQUFDO1FBRWxCLElBQUksUUFBUSxFQUFFLENBQUM7WUFDYixRQUFRLEdBQUcsSUFBQSxzQ0FBOEIsRUFDdkMsS0FBSyxFQUNMLGFBQWEsRUFDYixXQUFXLEVBQ1gsS0FBSyxFQUNMLGtCQUFrQixDQUNuQixDQUFDO1FBQ0osQ0FBQzthQUFNLENBQUM7WUFDTixRQUFRLEdBQUcsSUFBQSx3QkFBZ0IsRUFBQyxLQUFLLEVBQUUsYUFBYSxFQUFFLFdBQVcsQ0FBQyxDQUFDO1FBQ2pFLENBQUM7UUFFRCxtQ0FBbUM7UUFDbkMsSUFBSSxLQUFLLEVBQUUsQ0FBQyxhQUFhLENBQUMsRUFBRSxRQUFRLEVBQUUsQ0FBQztZQUNyQyxNQUFNLGFBQWEsR0FBRyxJQUFBLHdDQUFnQyxFQUNwRCxRQUFRLEVBQ1IsS0FBSyxFQUFFLENBQUMsYUFBYSxDQUFDLEVBQUUsUUFBUSxFQUNoQyxLQUFLLENBQUMsWUFBWSxDQUFDLENBQ3BCLENBQUM7WUFFRixPQUFPLENBQUMsR0FBRyxDQUFDLGFBQWEsRUFBRSxnQkFBZ0IsQ0FBQyxDQUFDO1lBRTdDLElBQUksYUFBYSxFQUFFLENBQUM7Z0JBQ2xCLGlCQUFpQjtnQkFDakIscUJBQXFCO2dCQUNyQixNQUFNLFNBQVMsR0FBRyxLQUFLLENBQUMsWUFBWSxDQUFDLENBQUM7Z0JBRXRDLFNBQVMsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO2dCQUUxQixNQUFNLElBQUEsb0NBQWtCLEVBQUMsTUFBTSxFQUFFLFNBQVMsQ0FBQyxDQUFDO2dCQUU1QyxPQUFPLENBQUMsR0FBRyxDQUFDLFFBQVEsRUFBRSxnQ0FBZ0MsQ0FBQyxDQUFDO1lBQzFELENBQUM7UUFDSCxDQUFDO1FBRUQsMEJBQTBCO1FBQzFCLE1BQU0sU0FBUyxHQUFHLElBQUEsK0JBQXVCLEVBQ3ZDLG1CQUFzQyxFQUN0QyxVQUFVLENBQ1gsQ0FBQztRQUVGLE9BQU8sQ0FBQyxHQUFHLENBQUMsU0FBUyxFQUFFLFlBQVksQ0FBQyxDQUFDO1FBRXJDLGdCQUFnQjtRQUNoQixJQUFJLFNBQVMsRUFBRSxLQUFLLEtBQUssS0FBSyxFQUFFLENBQUMsYUFBYSxDQUFDLEVBQUUsTUFBTSxFQUFFLENBQUM7WUFDeEQsTUFBTSxTQUFTLEdBQUcsS0FBSyxDQUFDLFlBQVksQ0FBQyxDQUFDO1lBQ3RDLFNBQVMsQ0FBQyxNQUFNLEdBQUcsU0FBUyxFQUFFLEtBQUssSUFBSSxzQkFBVSxDQUFDLElBQUksQ0FBQztZQUV2RCxNQUFNLElBQUEsb0NBQWtCLEVBQUMsTUFBTSxFQUFFLFNBQVMsQ0FBQyxDQUFDO1lBRTVDLE9BQU8sQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLCtCQUErQixDQUFDLENBQUM7UUFDekQsQ0FBQztRQUVELE9BQU8sQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLFdBQVcsQ0FBQyxDQUFDO1FBRW5DLHFCQUFxQjtRQUNyQixRQUFRLEVBQUUsT0FBTyxDQUFDLENBQUMsQ0FBQyxFQUFFLEdBQUcsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUMsS0FBSyxHQUFHLEdBQUcsQ0FBQyxDQUFDLENBQUM7UUFFL0MsTUFBTSxJQUFBLHFDQUFtQixFQUN2QixNQUFNLEVBQ04sUUFBUSxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsZ0JBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxFQUFFLENBQUMsV0FBVyxFQUFFLFNBQVMsRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDLENBQ3JFLENBQUM7UUFFRixNQUFNLGNBQWMsR0FBRyxRQUFRLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsTUFBTSxDQUFDLENBQUM7UUFFdEQsTUFBTSxFQUNKLGNBQWMsRUFBRSxpQkFBaUIsRUFDakMsdUJBQXVCLEVBQUUsMEJBQTBCLEdBQ3BELEdBQUcsSUFBQSwwQkFBa0IsRUFBQyxRQUFRLEVBQUUsY0FBYyxFQUFFLFFBQVEsRUFBRSxNQUFNLENBQUMsQ0FBQztRQUVuRSxPQUFPLENBQUMsR0FBRyxDQUFDLDBCQUEwQixFQUFFLDZCQUE2QixDQUFDLENBQUM7UUFDdkUsMEJBQTBCLENBQUMsMEJBQTBCLENBQUMsQ0FBQztRQUN2RCxhQUFhLENBQUMsaUJBQWlCLENBQUMsQ0FBQztJQUNuQyxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDBCQUEwQixDQUFDLENBQUM7SUFDN0MsQ0FBQztBQUNILENBQUMsQ0FBQztBQWhKVyxRQUFBLHFCQUFxQix5QkFnSmhDO0FBRUYsNENBQTRDO0FBQzVDLHlCQUF5QjtBQUN6QiwyQkFBMkI7QUFDM0IsNkJBQTZCO0FBQzdCLHVEQUF1RDtBQUN2RCx1Q0FBdUM7QUFDdkMsb0VBQW9FO0FBQ3BFLGlEQUFpRDtBQUNqRCxTQUFTO0FBQ1QsVUFBVTtBQUNWLHlDQUF5QztBQUN6QyxzRUFBc0U7QUFDdEUsZ0ZBQWdGO0FBQ2hGLG1DQUFtQztBQUNuQyxnREFBZ0Q7QUFFaEQsc0JBQXNCO0FBQ3RCLHFEQUFxRDtBQUNyRCxlQUFlO0FBQ2YsUUFBUTtBQUVSLHVDQUF1QztBQUN2QyxzREFBc0Q7QUFDdEQsdUNBQXVDO0FBQ3ZDLG9CQUFvQjtBQUNwQiw2Q0FBNkM7QUFFN0MsNkNBQTZDO0FBRTdDLHlCQUF5QjtBQUN6Qix5REFBeUQ7QUFDekQsaURBQWlEO0FBQ2pELHlEQUF5RDtBQUV6RCxvRUFBb0U7QUFDcEUseUNBQXlDO0FBQ3pDLGtDQUFrQztBQUNsQyw4SUFBOEk7QUFDOUksNEVBQTRFO0FBRTVFLHdCQUF3QjtBQUV4QixzQkFBc0I7QUFFdEIsZ0hBQWdIO0FBRWhILGVBQWU7QUFFZix1RUFBdUU7QUFFdkUsUUFBUTtBQUVSLDBDQUEwQztBQUMxQyw4Q0FBOEM7QUFFOUMsZ0VBQWdFO0FBQ2hFLG9CQUFvQjtBQUNwQiw0Q0FBNEM7QUFDNUMsK0JBQStCO0FBQy9CLFVBQVU7QUFFVixxREFBcUQ7QUFFckQsNkJBQTZCO0FBRTdCLDRCQUE0QjtBQUM1QixnQ0FBZ0M7QUFDaEMsZ0RBQWdEO0FBRWhELG9DQUFvQztBQUVwQyxzREFBc0Q7QUFFdEQsa0VBQWtFO0FBQ2xFLFVBQVU7QUFDVixRQUFRO0FBRVIsaUNBQWlDO0FBQ2pDLGlEQUFpRDtBQUNqRCw4Q0FBOEM7QUFDOUMsb0JBQW9CO0FBQ3BCLFFBQVE7QUFFUiwyQ0FBMkM7QUFFM0MsdUJBQXVCO0FBQ3ZCLGlFQUFpRTtBQUVqRSw4Q0FBOEM7QUFDOUMsK0RBQStEO0FBRS9ELG9EQUFvRDtBQUVwRCwrREFBK0Q7QUFDL0QsUUFBUTtBQUVSLHlDQUF5QztBQUV6Qyw0QkFBNEI7QUFDNUIscURBQXFEO0FBRXJELDRHQUE0RztBQUU1RywwREFBMEQ7QUFFMUQsY0FBYztBQUNkLDJDQUEyQztBQUMzQyw2REFBNkQ7QUFDN0QsaURBQWlEO0FBRWpELDZFQUE2RTtBQUM3RSw2REFBNkQ7QUFDN0QsdUNBQXVDO0FBQ3ZDLGtCQUFrQjtBQUNsQixpREFBaUQ7QUFDakQsTUFBTTtBQUNOLElBQUk7QUFFRyxNQUFNLGlCQUFpQixHQUFHLENBQUMsS0FBcUIsRUFBRSxNQUFjLEVBQUUsRUFBRTtJQUN6RSxNQUFNLEtBQUssR0FBRyxLQUFLLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsUUFBUSxLQUFLLE1BQU0sQ0FBQyxDQUFDO0lBQ3hELE9BQU8sQ0FBQyxDQUFDLEtBQUssQ0FBQztBQUNqQixDQUFDLENBQUM7QUFIVyxRQUFBLGlCQUFpQixxQkFHNUI7QUFFSyxNQUFNLGdDQUFnQyxHQUFHLENBQzlDLFFBQXdCLEVBQ3hCLFdBQW1CLEVBQ25CLFNBQXVCLEVBQ3ZCLEVBQUU7SUFDRixPQUFPLENBQUMsR0FBRyxDQUFDLFNBQVMsRUFBRSxvREFBb0QsQ0FBQyxDQUFDO0lBQzdFLE1BQU0sVUFBVSxHQUFHLFFBQVEsRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxFQUFFLEtBQUssU0FBUyxFQUFFLEVBQUUsQ0FBQyxDQUFDO0lBQ3ZFLE9BQU8sQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFLGFBQWEsQ0FBQyxDQUFDO0lBRXZDLElBQUksVUFBVSxLQUFLLENBQUMsQ0FBQyxFQUFFLENBQUM7UUFDdEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxzQkFBc0IsQ0FBQyxDQUFDO1FBQ3BDLE9BQU87SUFDVCxDQUFDO0lBRUQsTUFBTSxvQkFBb0IsR0FBRyxRQUFRLENBQUMsVUFBVSxHQUFHLENBQUMsQ0FBQyxFQUFFLFFBQVEsQ0FBQztJQUNoRSxPQUFPLENBQUMsR0FBRyxDQUFDLG9CQUFvQixFQUFFLHVCQUF1QixDQUFDLENBQUM7SUFFM0QsSUFBSSxvQkFBb0IsS0FBSyxXQUFXLEVBQUUsQ0FBQztRQUN6QyxPQUFPLEtBQUssQ0FBQztJQUNmLENBQUM7SUFFRCxNQUFNLGtCQUFrQixHQUFHLFFBQVEsQ0FBQyxVQUFVLEdBQUcsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDO0lBQ3hELE9BQU8sQ0FBQyxHQUFHLENBQUMsa0JBQWtCLEVBQUUscUJBQXFCLENBQUMsQ0FBQztJQUV2RCxJQUFJLGtCQUFrQixLQUFLLFdBQVcsRUFBRSxDQUFDO1FBQ3ZDLE9BQU8sS0FBSyxDQUFDO0lBQ2YsQ0FBQztJQUVELE9BQU8sSUFBSSxDQUFDO0FBQ2QsQ0FBQyxDQUFDO0FBN0JXLFFBQUEsZ0NBQWdDLG9DQTZCM0M7QUFFSyxNQUFNLHNCQUFzQixHQUFHLENBQ3BDLFVBQTJCLEVBQzNCLFlBQW9CLEVBQ3BCLEVBQUU7SUFDRixrQkFBa0I7SUFDbEIsSUFBSSxZQUFZLEtBQUssQ0FBQyxFQUFFLENBQUM7UUFDdkIsT0FBTyxDQUFDLEdBQUcsQ0FBQyw4Q0FBOEMsQ0FBQyxDQUFDO1FBQzVELE9BQU87SUFDVCxDQUFDO0lBRUQsSUFBSSxZQUFZLEtBQUssQ0FBQyxFQUFFLENBQUM7UUFDdkIsT0FBTyxDQUFDLEdBQUcsQ0FBQywyQ0FBMkMsQ0FBQyxDQUFDO1FBQ3pELE9BQU87SUFDVCxDQUFDO0lBRUQsSUFBSSxZQUFZLEdBQUcsVUFBVSxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztRQUN6QyxPQUFPLENBQUMsR0FBRyxDQUNULHFFQUFxRSxDQUN0RSxDQUFDO1FBQ0YsT0FBTztJQUNULENBQUM7SUFFRCxNQUFNLFdBQVcsR0FBRyxVQUFVLENBQUMsWUFBWSxHQUFHLENBQUMsQ0FBQyxDQUFDO0lBRWpELE1BQU0sS0FBSyxHQUFHLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxJQUFJLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxXQUFXLEVBQUUsS0FBSyxDQUFDLENBQUM7SUFFeEUsSUFBSSxLQUFLLEVBQUUsQ0FBQztRQUNWLE9BQU8sQ0FBQyxHQUFHLENBQUMsS0FBSyxFQUFFLHNDQUFzQyxDQUFDLENBQUM7UUFDM0QsT0FBTztJQUNULENBQUM7SUFFRCxPQUFPLFdBQVcsQ0FBQztBQUNyQixDQUFDLENBQUM7QUFoQ1csUUFBQSxzQkFBc0IsMEJBZ0NqQztBQUNLLE1BQU0sdUJBQXVCLEdBQUcsQ0FDckMsbUJBQW9DLEVBQ3BDLFVBQXlCLEVBQ3pCLEVBQUU7SUFDRixNQUFNLFFBQVEsR0FBRyxnQkFBQyxDQUFDLE9BQU8sQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDO0lBQ2hELE9BQU8sQ0FBQyxHQUFHLENBQUMsbUJBQW1CLEVBQUUsMkNBQTJDLENBQUMsQ0FBQztJQUM5RSxPQUFPLENBQUMsR0FBRyxDQUFDLFFBQVEsRUFBRSxnQ0FBZ0MsQ0FBQyxDQUFDO0lBQ3hELE9BQU8sQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFLGtDQUFrQyxDQUFDLENBQUM7SUFDNUQsTUFBTSxLQUFLLEdBQUcsUUFBUSxDQUFDLFNBQVMsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsS0FBSyxVQUFVLENBQUMsRUFBRSxDQUFDLENBQUM7SUFDaEUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxLQUFLLEVBQUUsNkJBQTZCLENBQUMsQ0FBQztJQUNsRCxNQUFNLE1BQU0sR0FBRyxRQUFRLENBQUMsS0FBSyxDQUFDLEtBQUssQ0FBQyxDQUFDO0lBQ3JDLE9BQU8sQ0FBQyxHQUFHLENBQUMsTUFBTSxFQUFFLDhCQUE4QixDQUFDLENBQUM7SUFDcEQsTUFBTSxXQUFXLEdBQUcsQ0FBQyxJQUFJLEVBQUUsS0FBSyxFQUFFLElBQUksQ0FBQyxDQUFDO0lBRXhDLEtBQUssSUFBSSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsR0FBRyxNQUFNLENBQUMsTUFBTSxFQUFFLENBQUMsRUFBRSxFQUFFLENBQUM7UUFDdkMsTUFBTSxLQUFLLEdBQUcsV0FBVyxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLE1BQU0sQ0FBQyxDQUFDLENBQUMsQ0FBQyxLQUFLLENBQUMsQ0FBQztRQUM3RCxPQUFPLENBQUMsR0FBRyxDQUFDLEtBQUssRUFBRSw2QkFBNkIsQ0FBQyxDQUFDO1FBQ2xELElBQUksS0FBSyxFQUFFLENBQUM7WUFDVixJQUFJLEtBQUssS0FBSyxJQUFJLEVBQUUsQ0FBQztnQkFDbkIsT0FBTztvQkFDTCxLQUFLLEVBQUUsSUFBSTtvQkFDWCxLQUFLLEVBQUUsc0JBQVUsQ0FBQyxJQUFJO2lCQUN2QixDQUFDO1lBQ0osQ0FBQztpQkFBTSxJQUFJLEtBQUssS0FBSyxLQUFLLEVBQUUsQ0FBQztnQkFDM0IsT0FBTztvQkFDTCxLQUFLLEVBQUUsS0FBSztvQkFDWixLQUFLLEVBQUUsc0JBQVUsQ0FBQyxLQUFLO2lCQUN4QixDQUFDO1lBQ0osQ0FBQztpQkFBTSxJQUFJLEtBQUssS0FBSyxJQUFJLEVBQUUsQ0FBQztnQkFDMUIsT0FBTztvQkFDTCxLQUFLLEVBQUUsSUFBSTtvQkFDWCxLQUFLLEVBQUUsc0JBQVUsQ0FBQyxJQUFJO2lCQUN2QixDQUFDO1lBQ0osQ0FBQztRQUNILENBQUM7SUFDSCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBcENXLFFBQUEsdUJBQXVCLDJCQW9DbEM7QUFDSyxNQUFNLGdCQUFnQixHQUFHLENBQUksQ0FBTSxFQUFFLElBQVksRUFBRSxFQUFVLEVBQUUsRUFBRTtJQUN0RSxNQUFNLFNBQVMsR0FBRyxFQUFFLEdBQUcsSUFBSSxDQUFDO0lBQzVCLE1BQU0sSUFBSSxHQUFHLEVBQUUsS0FBSyxJQUFJLENBQUM7SUFDekIsTUFBTSxVQUFVLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxDQUFDO0lBQzNCLE1BQU0sSUFBSSxHQUFRLEVBQUUsQ0FBQztJQUVyQixLQUFLLElBQUksQ0FBQyxHQUFHLENBQUMsRUFBRSxDQUFDLEdBQUcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDLEVBQUUsRUFBRSxDQUFDO1FBQ2xDLElBQUksQ0FBQyxLQUFLLEVBQUUsRUFBRSxDQUFDO1lBQ2IsSUFBSSxTQUFTLEVBQUUsQ0FBQztnQkFDZCxJQUFJLENBQUMsSUFBSSxDQUFDLFVBQVUsQ0FBQyxDQUFDO2dCQUN0QixJQUFJLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO2dCQUNoQixTQUFTO1lBQ1gsQ0FBQztpQkFBTSxJQUFJLElBQUksRUFBRSxDQUFDO2dCQUNoQixJQUFJLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO2dCQUNoQixTQUFTO1lBQ1gsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7Z0JBQ2hCLElBQUksQ0FBQyxJQUFJLENBQUMsVUFBVSxDQUFDLENBQUM7Z0JBQ3RCLFNBQVM7WUFDWCxDQUFDO1FBQ0gsQ0FBQztRQUVELElBQUksQ0FBQyxLQUFLLElBQUksRUFBRSxDQUFDO1lBQ2YsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUNsQixDQUFDO0lBQ0gsQ0FBQztJQUVELE9BQU8sSUFBSSxDQUFDO0FBQ2QsQ0FBQyxDQUFDO0FBNUJXLFFBQUEsZ0JBQWdCLG9CQTRCM0I7QUFFSyxNQUFNLDhCQUE4QixHQUFHLENBQzVDLENBQU0sRUFDTixJQUFZLEVBQ1osRUFBVSxFQUNWLFFBQXdCLEVBQ3hCLGtCQUEwQixFQUMxQixFQUFFO0lBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxRQUFRLEVBQUUsbUJBQW1CLENBQUMsQ0FBQztJQUMzQyxNQUFNLFNBQVMsR0FBRyxFQUFFLEdBQUcsSUFBSSxDQUFDO0lBRTVCLE1BQU0sVUFBVSxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQztJQUMzQixNQUFNLElBQUksR0FBUSxFQUFFLENBQUM7SUFFckIsSUFBSSxJQUFJLEdBQVksSUFBSSxDQUFDO0lBRXpCLElBQUksQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUNmLE9BQU8sQ0FBQyxHQUFHLENBQUMsZ0NBQWdDLENBQUMsQ0FBQztRQUM5QyxLQUFLLElBQUksQ0FBQyxHQUFHLElBQUksR0FBRyxDQUFDLEVBQUUsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUFDLEVBQUUsRUFBRSxDQUFDO1lBQ3BDLElBQUksa0JBQWtCLEtBQUssUUFBUSxDQUFDLENBQUMsQ0FBQyxFQUFFLFFBQVEsRUFBRSxDQUFDO2dCQUNqRCxPQUFPLENBQUMsR0FBRyxDQUFDLGtDQUFrQyxDQUFDLENBQUM7Z0JBQ2hELElBQUksR0FBRyxLQUFLLENBQUM7WUFDZixDQUFDO1FBQ0gsQ0FBQztJQUNILENBQUM7SUFFRCw4Q0FBOEM7SUFDOUMsSUFBSSxJQUFJLEVBQUUsQ0FBQztRQUNULE9BQU8sQ0FBQyxDQUFDO0lBQ1gsQ0FBQztJQUVELElBQUksR0FBRyxFQUFFLEtBQUssSUFBSSxDQUFDO0lBRW5CLE1BQU0sa0JBQWtCLEdBQUcsUUFBUTtTQUNoQyxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsS0FBSyxFQUFFLEVBQUU7UUFDaEIsSUFBSSxDQUFDLEVBQUUsUUFBUSxLQUFLLGtCQUFrQixFQUFFLENBQUM7WUFDdkMsT0FBTyxLQUFLLENBQUM7UUFDZixDQUFDO1FBQ0QsT0FBTyxJQUFJLENBQUM7SUFDZCxDQUFDLENBQUM7U0FDRCxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxJQUFJLENBQUMsQ0FBQztJQUU3QixPQUFPLENBQUMsR0FBRyxDQUFDLGtCQUFrQixFQUFFLHFCQUFxQixDQUFDLENBQUM7SUFFdkQsS0FBSyxJQUFJLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxHQUFHLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztRQUNsQyxJQUFJLENBQUMsS0FBSyxFQUFFLEVBQUUsQ0FBQztZQUNiLElBQUksU0FBUyxFQUFFLENBQUM7Z0JBQ2QsSUFBSSxDQUFDLElBQUksQ0FBQyxVQUFVLENBQUMsQ0FBQztnQkFDdEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxJQUFJLEVBQUUscUNBQXFDLENBQUMsQ0FBQztnQkFDekQsS0FBSyxJQUFJLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxHQUFHLGtCQUFrQixDQUFDLE1BQU0sRUFBRSxDQUFDLEVBQUUsRUFBRSxDQUFDO29CQUNuRCxNQUFNLFFBQVEsR0FBRyxrQkFBa0IsQ0FBQyxDQUFDLENBQUMsQ0FBQztvQkFDdkMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxRQUFRLEVBQUUscUNBQXFDLENBQUMsQ0FBQztvQkFDN0QsSUFBSSxFQUFFLEtBQUssUUFBUSxFQUFFLENBQUM7d0JBQ3BCLFNBQVM7b0JBQ1gsQ0FBQztvQkFFRCxJQUFJLElBQUksS0FBSyxRQUFRLEVBQUUsQ0FBQzt3QkFDdEIsU0FBUztvQkFDWCxDQUFDO29CQUNELElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUM7Z0JBQ3pCLENBQUM7Z0JBQ0QsT0FBTyxDQUFDLEdBQUcsQ0FBQyxJQUFJLEVBQUUsb0NBQW9DLENBQUMsQ0FBQztnQkFDeEQsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztnQkFDaEIsU0FBUztZQUNYLENBQUM7aUJBQU0sSUFBSSxJQUFJLEVBQUUsQ0FBQztnQkFDaEIsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztnQkFDaEIsS0FBSyxJQUFJLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxHQUFHLGtCQUFrQixDQUFDLE1BQU0sRUFBRSxDQUFDLEVBQUUsRUFBRSxDQUFDO29CQUNuRCxNQUFNLFFBQVEsR0FBRyxrQkFBa0IsQ0FBQyxDQUFDLENBQUMsQ0FBQztvQkFDdkMsSUFBSSxFQUFFLEtBQUssUUFBUSxFQUFFLENBQUM7d0JBQ3BCLFNBQVM7b0JBQ1gsQ0FBQztvQkFFRCxJQUFJLElBQUksS0FBSyxRQUFRLEVBQUUsQ0FBQzt3QkFDdEIsU0FBUztvQkFDWCxDQUFDO29CQUNELElBQUksQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUM7Z0JBQ3pCLENBQUM7Z0JBQ0QsU0FBUztZQUNYLENBQUM7aUJBQU0sQ0FBQztnQkFDTixJQUFJLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO2dCQUNoQixJQUFJLENBQUMsSUFBSSxDQUFDLFVBQVUsQ0FBQyxDQUFDO2dCQUN0QixLQUFLLElBQUksQ0FBQyxHQUFHLENBQUMsRUFBRSxDQUFDLEdBQUcsa0JBQWtCLENBQUMsTUFBTSxFQUFFLENBQUMsRUFBRSxFQUFFLENBQUM7b0JBQ25ELE1BQU0sUUFBUSxHQUFHLGtCQUFrQixDQUFDLENBQUMsQ0FBQyxDQUFDO29CQUN2QyxJQUFJLEVBQUUsS0FBSyxRQUFRLEVBQUUsQ0FBQzt3QkFDcEIsU0FBUztvQkFDWCxDQUFDO29CQUVELElBQUksSUFBSSxLQUFLLFFBQVEsRUFBRSxDQUFDO3dCQUN0QixTQUFTO29CQUNYLENBQUM7b0JBQ0QsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQztnQkFDekIsQ0FBQztnQkFDRCxTQUFTO1lBQ1gsQ0FBQztRQUNILENBQUM7UUFFRCxJQUFJLGtCQUFrQixDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDO1lBQ25DLFNBQVM7UUFDWCxDQUFDO1FBRUQsSUFBSSxDQUFDLEtBQUssSUFBSSxFQUFFLENBQUM7WUFDZixTQUFTO1FBQ1gsQ0FBQztRQUVELE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxFQUFFLDRDQUE0QyxDQUFDLENBQUM7UUFFaEUsSUFBSSxDQUFDLEtBQUssSUFBSSxFQUFFLENBQUM7WUFDZixJQUFJLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBQ2xCLENBQUM7UUFDRCxPQUFPLENBQUMsR0FBRyxDQUFDLElBQUksRUFBRSxpQkFBaUIsQ0FBQyxDQUFDO0lBQ3ZDLENBQUM7SUFFRCxPQUFPLElBQUksQ0FBQztBQUNkLENBQUMsQ0FBQztBQWhIVyxRQUFBLDhCQUE4QixrQ0FnSHpDO0FBRUssTUFBTSxxQkFBcUIsR0FBRyxDQUNuQyxJQUFTLEVBQ1QsT0FBc0MsRUFDdEMsdUJBQWlDLEVBQ2pDLEVBQUU7SUFDRiwwQ0FBMEM7SUFDMUMsTUFBTSxPQUFPLEdBQVEsRUFBRSxDQUFDO0lBRXhCLEtBQUssSUFBSSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsR0FBRyx1QkFBdUIsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztRQUN4RCxNQUFNLFFBQVEsR0FBRyx1QkFBdUIsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUM1QyxJQUFJLFFBQVEsR0FBRyxDQUFDLENBQUMsRUFBRSxDQUFDO1lBQ2xCLE9BQU8sQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUM7UUFDL0IsQ0FBQztJQUNILENBQUM7SUFDRCxPQUFPLENBQUMsT0FBTyxDQUFDLENBQUM7QUFDbkIsQ0FBQyxDQUFDO0FBZlcsUUFBQSxxQkFBcUIseUJBZWhDO0FBRUssTUFBTSxZQUFZLEdBQUcsQ0FBSSxNQUFXLEVBQUUsV0FBeUIsRUFBRSxFQUFFO0lBQ3hFLE1BQU0sU0FBUyxHQUFRLEVBQUUsQ0FBQztJQUMxQixNQUFNLFVBQVUsR0FBUSxFQUFFLENBQUM7SUFDM0IsTUFBTSxTQUFTLEdBQVEsRUFBRSxDQUFDO0lBRTFCLE1BQU0sQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDLEVBQUUsS0FBSyxFQUFFLEVBQUU7UUFDMUIsTUFBTSxNQUFNLEdBQUcsV0FBVyxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBRWxDLElBQUksTUFBTSxLQUFLLHNCQUFVLENBQUMsSUFBSSxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7WUFDMUMsU0FBUyxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUNwQixDQUFDO2FBQU0sSUFBSSxNQUFNLEtBQUssc0JBQVUsQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUN2QyxVQUFVLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBQ3JCLENBQUM7YUFBTSxJQUFJLE1BQU0sS0FBSyxzQkFBVSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ3RDLFNBQVMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFDcEIsQ0FBQztJQUNILENBQUMsQ0FBQyxDQUFDO0lBRUgsTUFBTSxRQUFRLEdBQVEsU0FBUyxDQUFDLE1BQU0sQ0FBQyxVQUFVLENBQUMsQ0FBQyxNQUFNLENBQUMsU0FBUyxDQUFDLENBQUM7SUFFckUsT0FBTyxRQUFRLENBQUM7QUFDbEIsQ0FBQyxDQUFDO0FBcEJXLFFBQUEsWUFBWSxnQkFvQnZCO0FBRUssTUFBTSxrQkFBa0IsR0FBRyxDQUNoQyxVQUEwQixFQUMxQixXQUF5QixFQUN6QixJQUFpQixFQUNqQixNQUFjLEVBQ2QsRUFBRTtJQUNGLE1BQU0sV0FBVyxHQUFpQixFQUFFLENBQUM7SUFDckMsTUFBTSxTQUFTLEdBQW1CLEVBQUUsQ0FBQztJQUNyQyxNQUFNLFVBQVUsR0FBbUIsRUFBRSxDQUFDO0lBQ3RDLE1BQU0sU0FBUyxHQUFtQixFQUFFLENBQUM7SUFFckMsTUFBTSx3QkFBd0IsR0FBYSxFQUFFLENBQUM7SUFDOUMsTUFBTSx5QkFBeUIsR0FBYSxFQUFFLENBQUM7SUFDL0MsTUFBTSx3QkFBd0IsR0FBYSxFQUFFLENBQUM7SUFFOUMsVUFBVSxDQUFDLE9BQU8sQ0FBQyxDQUFDLFFBQVEsRUFBRSxLQUFLLEVBQUUsRUFBRTtRQUNyQyxNQUFNLE1BQU0sR0FBRyxXQUFXLENBQUMsS0FBSyxDQUFDLENBQUM7UUFFbEMsSUFBSSxNQUFNLEtBQUssc0JBQVUsQ0FBQyxJQUFJLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUMxQyxNQUFNLEtBQUssR0FBRyxXQUFXLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssc0JBQVUsQ0FBQyxJQUFJLENBQUMsQ0FBQztZQUM3RCxJQUFJLENBQUMsS0FBSyxFQUFFLENBQUM7Z0JBQ1gsV0FBVyxDQUFDLElBQUksQ0FBQyxzQkFBVSxDQUFDLElBQUksQ0FBQyxDQUFDO2dCQUNsQyxTQUFTLENBQUMsSUFBSSxDQUFDLEVBQUUsRUFBRSxFQUFFLHNCQUFVLENBQUMsSUFBSSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLENBQUM7Z0JBQ3RFLFNBQVMsQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLENBQUM7Z0JBQ3pCLHdCQUF3QixDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO2dCQUNsQyx3QkFBd0IsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDdkMsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLFNBQVMsQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLENBQUM7Z0JBQ3pCLHdCQUF3QixDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUN2QyxDQUFDO1FBQ0gsQ0FBQzthQUFNLElBQUksTUFBTSxLQUFLLHNCQUFVLENBQUMsS0FBSyxFQUFFLENBQUM7WUFDdkMsTUFBTSxLQUFLLEdBQUcsV0FBVyxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLHNCQUFVLENBQUMsS0FBSyxDQUFDLENBQUM7WUFFOUQsSUFBSSxDQUFDLEtBQUssRUFBRSxDQUFDO2dCQUNYLFdBQVcsQ0FBQyxJQUFJLENBQUMsc0JBQVUsQ0FBQyxLQUFLLENBQUMsQ0FBQztnQkFDbkMsVUFBVSxDQUFDLElBQUksQ0FBQyxFQUFFLEVBQUUsRUFBRSxzQkFBVSxDQUFDLEtBQUssRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxDQUFDO2dCQUN4RSxVQUFVLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxDQUFDO2dCQUMxQix5QkFBeUIsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztnQkFDbkMseUJBQXlCLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO1lBQ3hDLENBQUM7aUJBQU0sQ0FBQztnQkFDTixVQUFVLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxDQUFDO2dCQUMxQix5QkFBeUIsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDeEMsQ0FBQztRQUNILENBQUM7YUFBTSxJQUFJLE1BQU0sS0FBSyxzQkFBVSxDQUFDLElBQUksRUFBRSxDQUFDO1lBQ3RDLE1BQU0sS0FBSyxHQUFHLFdBQVcsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxzQkFBVSxDQUFDLElBQUksQ0FBQyxDQUFDO1lBRTdELElBQUksQ0FBQyxLQUFLLEVBQUUsQ0FBQztnQkFDWCxXQUFXLENBQUMsSUFBSSxDQUFDLHNCQUFVLENBQUMsSUFBSSxDQUFDLENBQUM7Z0JBQ2xDLFNBQVMsQ0FBQyxJQUFJLENBQUMsRUFBRSxFQUFFLEVBQUUsc0JBQVUsQ0FBQyxJQUFJLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLENBQUMsQ0FBQztnQkFDckUsU0FBUyxDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztnQkFDekIsd0JBQXdCLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7Z0JBQ2xDLHdCQUF3QixDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUN2QyxDQUFDO2lCQUFNLENBQUM7Z0JBQ04sU0FBUyxDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztnQkFDekIsd0JBQXdCLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO1lBQ3ZDLENBQUM7UUFDSCxDQUFDO0lBQ0gsQ0FBQyxDQUFDLENBQUM7SUFFSCxJQUNFLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQztRQUNyQixDQUFDLENBQUMsVUFBVSxFQUFFLE1BQU0sR0FBRyxDQUFDLENBQUM7UUFDekIsQ0FBQyxDQUFDLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLEVBQ3hCLENBQUM7UUFDRCxNQUFNLFFBQVEsR0FBb0IsU0FBUzthQUN4QyxNQUFNLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRSxzQkFBVSxDQUFDLEtBQUssRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxDQUFDO2FBQ2hFLE1BQU0sQ0FBQyxDQUFDLEVBQUUsRUFBRSxFQUFFLHNCQUFVLENBQUMsSUFBSSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxDQUFDLENBQUMsQ0FBQztRQUNsRSxNQUFNLGFBQWEsR0FBYSx3QkFBd0I7YUFDckQsTUFBTSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQzthQUNaLE1BQU0sQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUNoQixPQUFPO1lBQ0wsY0FBYyxFQUFFLFFBQVE7WUFDeEIsdUJBQXVCLEVBQUUsYUFBYTtTQUN2QyxDQUFDO0lBQ0osQ0FBQztTQUFNLElBQ0wsU0FBUyxFQUFFLE1BQU0sR0FBRyxDQUFDO1FBQ3JCLENBQUMsQ0FBQyxVQUFVLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQztRQUN6QixTQUFTLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFDckIsQ0FBQztRQUNELE1BQU0sUUFBUSxHQUFvQixTQUFTO2FBQ3hDLE1BQU0sQ0FBQyxDQUFDLEVBQUUsRUFBRSxFQUFFLHNCQUFVLENBQUMsS0FBSyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLENBQUM7YUFDaEUsTUFBTSxDQUFDLFNBQVMsQ0FBQyxDQUFDO1FBQ3JCLE1BQU0sYUFBYSxHQUFhLHdCQUF3QjthQUNyRCxNQUFNLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO2FBQ1osTUFBTSxDQUFDLHdCQUF3QixDQUFDLENBQUM7UUFFcEMsT0FBTztZQUNMLGNBQWMsRUFBRSxRQUFRO1lBQ3hCLHVCQUF1QixFQUFFLGFBQWE7U0FDdkMsQ0FBQztJQUNKLENBQUM7U0FBTSxJQUNMLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQztRQUNyQixVQUFVLEVBQUUsTUFBTSxHQUFHLENBQUM7UUFDdEIsQ0FBQyxDQUFDLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLEVBQ3hCLENBQUM7UUFDRCxNQUFNLFFBQVEsR0FBb0IsU0FBUzthQUN4QyxNQUFNLENBQUMsVUFBVSxDQUFDO2FBQ2xCLE1BQU0sQ0FBQyxDQUFDLEVBQUUsRUFBRSxFQUFFLHNCQUFVLENBQUMsSUFBSSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLE1BQU0sRUFBRSxDQUFDLENBQUMsQ0FBQztRQUNsRSxNQUFNLGFBQWEsR0FBYSx3QkFBd0I7YUFDckQsTUFBTSxDQUFDLHlCQUF5QixDQUFDO2FBQ2pDLE1BQU0sQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUVoQixPQUFPO1lBQ0wsY0FBYyxFQUFFLFFBQVE7WUFDeEIsdUJBQXVCLEVBQUUsYUFBYTtTQUN2QyxDQUFDO0lBQ0osQ0FBQztTQUFNLElBQ0wsQ0FBQyxDQUFDLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDO1FBQ3hCLFVBQVUsRUFBRSxNQUFNLEdBQUcsQ0FBQztRQUN0QixDQUFDLENBQUMsU0FBUyxFQUFFLE1BQU0sR0FBRyxDQUFDLENBQUMsRUFDeEIsQ0FBQztRQUNELE1BQU0sUUFBUSxHQUFvQjtZQUNoQyxFQUFFLEVBQUUsRUFBRSxzQkFBVSxDQUFDLElBQUksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQW1CO1NBQ3ZFO2FBQ0UsTUFBTSxDQUFDLFVBQVUsQ0FBQzthQUNsQixNQUFNLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRSxzQkFBVSxDQUFDLElBQUksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDbEUsTUFBTSxhQUFhLEdBQWEsQ0FBQyxDQUFDLENBQUMsQ0FBQzthQUNqQyxNQUFNLENBQUMseUJBQXlCLENBQUM7YUFDakMsTUFBTSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBRWhCLE9BQU87WUFDTCxjQUFjLEVBQUUsUUFBUTtZQUN4Qix1QkFBdUIsRUFBRSxhQUFhO1NBQ3ZDLENBQUM7SUFDSixDQUFDO1NBQU0sSUFDTCxDQUFDLENBQUMsU0FBUyxFQUFFLE1BQU0sR0FBRyxDQUFDLENBQUM7UUFDeEIsQ0FBQyxDQUFDLFVBQVUsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDO1FBQ3pCLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUNyQixDQUFDO1FBQ0QsTUFBTSxRQUFRLEdBQW9CO1lBQ2hDLEVBQUUsRUFBRSxFQUFFLHNCQUFVLENBQUMsSUFBSSxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBbUI7U0FDdkU7YUFDRSxNQUFNLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRSxzQkFBVSxDQUFDLEtBQUssRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FBQyxDQUFDO2FBQ2hFLE1BQU0sQ0FBQyxTQUFTLENBQUMsQ0FBQztRQUNyQixNQUFNLGFBQWEsR0FBYSxDQUFDLENBQUMsQ0FBQyxDQUFDO2FBQ2pDLE1BQU0sQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7YUFDWixNQUFNLENBQUMsd0JBQXdCLENBQUMsQ0FBQztRQUVwQyxPQUFPO1lBQ0wsY0FBYyxFQUFFLFFBQVE7WUFDeEIsdUJBQXVCLEVBQUUsYUFBYTtTQUN2QyxDQUFDO0lBQ0osQ0FBQztTQUFNLElBQ0wsQ0FBQyxDQUFDLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDO1FBQ3hCLFVBQVUsRUFBRSxNQUFNLEdBQUcsQ0FBQztRQUN0QixTQUFTLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFDckIsQ0FBQztRQUNELE1BQU0sUUFBUSxHQUFvQjtZQUNoQyxFQUFFLEVBQUUsRUFBRSxzQkFBVSxDQUFDLElBQUksRUFBRSxJQUFJLEVBQUUsTUFBTSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQW1CO1NBQ3ZFO2FBQ0UsTUFBTSxDQUFDLFVBQVUsQ0FBQzthQUNsQixNQUFNLENBQUMsU0FBUyxDQUFDLENBQUM7UUFDckIsTUFBTSxhQUFhLEdBQWEsQ0FBQyxDQUFDLENBQUMsQ0FBQzthQUNqQyxNQUFNLENBQUMseUJBQXlCLENBQUM7YUFDakMsTUFBTSxDQUFDLHdCQUF3QixDQUFDLENBQUM7UUFFcEMsT0FBTztZQUNMLGNBQWMsRUFBRSxRQUFRO1lBQ3hCLHVCQUF1QixFQUFFLGFBQWE7U0FDdkMsQ0FBQztJQUNKLENBQUM7U0FBTSxJQUNMLENBQUMsQ0FBQyxTQUFTLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQztRQUN4QixDQUFDLENBQUMsVUFBVSxFQUFFLE1BQU0sR0FBRyxDQUFDLENBQUM7UUFDekIsQ0FBQyxDQUFDLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLEVBQ3hCLENBQUM7UUFDRCxNQUFNLFFBQVEsR0FBb0I7WUFDaEMsRUFBRSxFQUFFLEVBQUUsc0JBQVUsQ0FBQyxJQUFJLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFtQjtTQUN2RTthQUNFLE1BQU0sQ0FBQyxDQUFDLEVBQUUsRUFBRSxFQUFFLHNCQUFVLENBQUMsS0FBSyxFQUFFLElBQUksRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUFDLENBQUM7YUFDaEUsTUFBTSxDQUFDLENBQUMsRUFBRSxFQUFFLEVBQUUsc0JBQVUsQ0FBQyxJQUFJLEVBQUUsSUFBSSxFQUFFLE1BQU0sRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLENBQUMsQ0FBQyxDQUFDO1FBQ2xFLE1BQU0sYUFBYSxHQUFhLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBRS9ELE9BQU87WUFDTCxjQUFjLEVBQUUsUUFBUTtZQUN4Qix1QkFBdUIsRUFBRSxhQUFhO1NBQ3ZDLENBQUM7SUFDSixDQUFDO0lBRUQsTUFBTSxRQUFRLEdBQW9CLFNBQVM7U0FDeEMsTUFBTSxDQUFDLFVBQVUsQ0FBQztTQUNsQixNQUFNLENBQUMsU0FBUyxDQUFDLENBQUM7SUFDckIsTUFBTSxhQUFhLEdBQWEsd0JBQXdCO1NBQ3JELE1BQU0sQ0FBQyx5QkFBeUIsQ0FBQztTQUNqQyxNQUFNLENBQUMsd0JBQXdCLENBQUMsQ0FBQztJQUVwQyxPQUFPO1FBQ0wsY0FBYyxFQUFFLFFBQVE7UUFDeEIsdUJBQXVCLEVBQUUsYUFBYTtLQUN2QyxDQUFDO0FBQ0osQ0FBQyxDQUFDO0FBN0xXLFFBQUEsa0JBQWtCLHNCQTZMN0I7QUFFSyxNQUFNLDJCQUEyQixHQUFHLENBQ3pDLG1CQUFvQyxFQUNwQyxhQUE4QixFQUM5QixVQUF5QixFQUNLLEVBQUU7SUFDaEMsTUFBTSwyQkFBMkIsR0FBRyxtQkFBbUI7U0FDcEQsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsS0FBSyxLQUFLLElBQUksQ0FBQztTQUMvQixNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxLQUFLLEtBQUssS0FBSyxDQUFDO1NBQ2hDLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLEtBQUssS0FBSyxJQUFJLENBQUMsQ0FBQztJQUVuQyxNQUFNLHFCQUFxQixHQUFHLGFBQWE7U0FDeEMsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsS0FBSyxLQUFLLElBQUksQ0FBQztTQUMvQixNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxLQUFLLEtBQUssS0FBSyxDQUFDO1NBQ2hDLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLEtBQUssS0FBSyxJQUFJLENBQUMsQ0FBQztJQUVuQyxNQUFNLElBQUksR0FBRyxxQkFBcUIsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLEtBQUssVUFBVSxDQUFDLEVBQUUsQ0FBQyxDQUFDO0lBQzVFLE1BQU0sRUFBRSxHQUFHLDJCQUEyQixDQUFDLFNBQVMsQ0FDOUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLEtBQUssVUFBVSxDQUFDLEVBQUUsQ0FDOUIsQ0FBQztJQUVGLE9BQU8sRUFBRSxJQUFJLEVBQUUsRUFBRSxFQUFFLENBQUM7QUFDdEIsQ0FBQyxDQUFDO0FBckJXLFFBQUEsMkJBQTJCLCtCQXFCdEM7QUFFSyxNQUFNLHdCQUF3QixHQUFHLENBQ3RDLENBQUksRUFDSixNQUFXLEVBQ1gsU0FBa0IsRUFDbEIsS0FBYyxFQUNkLEVBQUU7SUFDRixPQUFPLENBQUMsR0FBRyxDQUFDLEtBQUssRUFBRSx5Q0FBeUMsQ0FBQyxDQUFDO0lBQzlELElBQUksQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUNmLElBQUksT0FBTyxLQUFLLEtBQUssUUFBUSxFQUFFLENBQUM7WUFDOUIsT0FBTyxDQUFDLEdBQUcsQ0FDVCxDQUFDLEVBQ0QsTUFBTSxFQUNOLGtEQUFrRCxDQUNuRCxDQUFDO1lBQ0YsT0FBTztRQUNULENBQUM7UUFDRCxNQUFNLFNBQVMsR0FBRyxNQUFNO2FBQ3JCLEtBQUssQ0FBQyxDQUFDLEVBQUUsS0FBSyxHQUFHLENBQUMsQ0FBQzthQUNuQixNQUFNLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQzthQUNYLE1BQU0sQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLEtBQUssR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBRW5DLE9BQU8sU0FBUyxDQUFDO0lBQ25CLENBQUM7SUFFRCxPQUFPLENBQUMsQ0FBQyxDQUFDLENBQUM7QUFDYixDQUFDLENBQUM7QUF6QlcsUUFBQSx3QkFBd0IsNEJBeUJuQztBQUVLLE1BQU0scUNBQXFDLEdBQUcsQ0FDbkQsVUFBb0IsRUFDcEIsU0FBa0IsRUFDbEIsYUFBaUQsRUFDakQsS0FBYyxFQUNkLEVBQUU7SUFDRixJQUFJLENBQUMsU0FBUyxFQUFFLENBQUM7UUFDZixJQUFJLE9BQU8sS0FBSyxLQUFLLFFBQVEsRUFBRSxDQUFDO1lBQzlCLE9BQU8sQ0FBQyxHQUFHLENBQ1QsVUFBVSxFQUNWLG1EQUFtRCxDQUNwRCxDQUFDO1lBQ0YsT0FBTztRQUNULENBQUM7UUFFRCxNQUFNLGFBQWEsR0FBRyxVQUFVLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxLQUFLLEdBQUcsQ0FBQyxDQUFDLENBQUM7UUFDckQsTUFBTSxtQkFBbUIsR0FBRyxVQUFVLENBQUMsS0FBSyxDQUFDLEtBQUssR0FBRyxDQUFDLENBQUMsQ0FBQztRQUV4RCxLQUFLLElBQUksQ0FBQyxHQUFHLENBQUMsRUFBRSxDQUFDLEdBQUcsbUJBQW1CLENBQUMsTUFBTSxFQUFFLENBQUMsRUFBRSxFQUFFLENBQUM7WUFDcEQsbUJBQW1CLENBQUMsQ0FBQyxDQUFDLElBQUksQ0FBQyxDQUFDO1FBQzlCLENBQUM7UUFFRCxNQUFNLGFBQWEsR0FBRyxhQUFhO2FBQ2hDLE1BQU0sQ0FBQyxDQUFDLGFBQWEsQ0FBQyxNQUFNLENBQUMsQ0FBQzthQUM5QixNQUFNLENBQUMsbUJBQW1CLENBQUMsQ0FBQztRQUUvQixhQUFhLENBQUMsYUFBYSxDQUFDLENBQUM7UUFDN0IsT0FBTyxhQUFhLENBQUM7SUFDdkIsQ0FBQztJQUVELGFBQWEsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7SUFDbkIsT0FBTyxDQUFDLENBQUMsQ0FBQyxDQUFDO0FBQ2IsQ0FBQyxDQUFDO0FBaENXLFFBQUEscUNBQXFDLHlDQWdDaEQ7QUFFSyxNQUFNLGVBQWUsR0FBRyxDQUM3QixDQUFJLEVBQ0osTUFBVyxFQUNYLFNBQXdDLEVBQ3hDLEtBQWEsRUFDYixFQUFFO0lBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxNQUFNLEVBQUUsU0FBUyxDQUFDLENBQUM7SUFDL0IsTUFBTSxTQUFTLEdBQUcsTUFBTTtTQUNyQixLQUFLLENBQUMsQ0FBQyxFQUFFLEtBQUssQ0FBQztTQUNmLE1BQU0sQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO1NBQ1gsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsS0FBSyxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUM7SUFFbkMsU0FBUyxDQUFDLFNBQVMsQ0FBQyxDQUFDO0lBQ3JCLE9BQU8sU0FBUyxDQUFDO0FBQ25CLENBQUMsQ0FBQztBQWRXLFFBQUEsZUFBZSxtQkFjMUI7QUFFSyxNQUFNLG1CQUFtQixHQUFHLENBQ2pDLEtBQWEsRUFDYixTQUFjLEVBQ2QsWUFBMkMsRUFDM0MsRUFBRTtJQUNGLE1BQU0sWUFBWSxHQUFHO1FBQ25CLEdBQUcsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsS0FBSyxDQUFDO1FBQzVCLEdBQUcsU0FBUyxDQUFDLEtBQUssQ0FBQyxLQUFLLEdBQUcsQ0FBQyxDQUFDO0tBQzlCLENBQUM7SUFFRixZQUFZLENBQUMsWUFBWSxDQUFDLENBQUM7SUFDM0IsT0FBTyxZQUFZLENBQUM7QUFDdEIsQ0FBQyxDQUFDO0FBWlcsUUFBQSxtQkFBbUIsdUJBWTlCO0FBQ0YsbURBQW1EO0FBRTVDLE1BQU0saUJBQWlCLEdBQUcsQ0FDL0IsYUFBdUIsRUFDdkIsVUFBMEIsRUFDMUIsRUFBRTtJQUNGLElBQUksb0JBQW9CLEdBQW1CLEVBQUUsQ0FBQztJQUU5QyxJQUFJLGdCQUFnQixHQUFtQixFQUFFLENBQUM7SUFFMUMsS0FBSyxJQUFJLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxHQUFHLFVBQVUsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztRQUMzQyxNQUFNLEtBQUssR0FBRyxvQkFBb0IsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxFQUFFLEtBQUssVUFBVSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1FBRTVFLElBQUksQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUNYLGdCQUFnQixDQUFDLElBQUksQ0FBQyxVQUFVLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUNyQyxvQkFBb0IsQ0FBQyxJQUFJLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7WUFFekMsS0FBSyxJQUFJLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxHQUFHLFVBQVUsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztnQkFDM0MsSUFBSSxVQUFVLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxLQUFLLGFBQWEsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDO29CQUMzQyxnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7b0JBQ3JDLG9CQUFvQixDQUFDLElBQUksQ0FBQyxVQUFVLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztnQkFDM0MsQ0FBQztZQUNILENBQUM7UUFDSCxDQUFDO0lBQ0gsQ0FBQztJQUVELE9BQU87UUFDTCxnQkFBZ0I7S0FDakIsQ0FBQztBQUNKLENBQUMsQ0FBQztBQTNCVyxRQUFBLGlCQUFpQixxQkEyQjVCIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgRGlzcGF0Y2gsIFNldFN0YXRlQWN0aW9uIH0gZnJvbSAncmVhY3QnO1xuXG5pbXBvcnQgeyBTM0NsaWVudCwgUHV0T2JqZWN0Q29tbWFuZCB9IGZyb20gJ0Bhd3Mtc2RrL2NsaWVudC1zMyc7XG5cbmltcG9ydCAqIGFzIG1hdGggZnJvbSAnbWF0aGpzJztcbmltcG9ydCB7IFJSdWxlIH0gZnJvbSAncnJ1bGUnO1xuXG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BsaWIvZGF0ZS11dGlscyc7XG5cbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG4vLyBpbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnXG5cbi8vIGltcG9ydCB7IENPTlZFUlRfVE9fV0VCUF9BUEkgfSBmcm9tICdyZWFjdC1uYXRpdmUtZG90ZW52J1xuXG5pbXBvcnQge1xuICB1cGRhdGVUYXNrSW5TdG9yZSxcbiAgVGFibGVOYW1lLFxufSBmcm9tICdAbGliL1Byb2dyZXNzL1RvZG8vSW50ZWdyYXRpb25IZWxwZXInO1xuXG5pbXBvcnQge1xuICBEaXNwbGF5VUlUeXBlLFxuICBUYXNrUGx1c1R5cGUsXG4gIFRhc2tTdWJUeXBlLFxufSBmcm9tICdAcGFnZXMvUHJvZ3Jlc3MvVG9kby9Vc2VyVGFzayc7XG5cbi8vIGNvbnN0IENPTlZFUlRPV0VCQVBJREVWID0gQ09OVkVSVF9UT19XRUJQX0FQSVxuXG4vLyBkYXlqcy5leHRlbmQodXRjKVxuLy8gZGF5anMuZXh0ZW5kKHF1YXJ0ZXJPZlllYXIpXG5cbmltcG9ydCB7IFRhc2tTdGF0dXMgfSBmcm9tICdAbGliL1Byb2dyZXNzL1RvZG8vY29uc3RhbnRzJztcbmltcG9ydCB7IHVwZGF0ZVRhc2tCeUlkSW5EYiwgdXBzZXJ0TWFueVRhc2tzSW5EYiB9IGZyb20gJy4vVXNlclRhc2tIZWxwZXIzJztcbmltcG9ydCB7IEFwb2xsb0NsaWVudCwgTm9ybWFsaXplZENhY2hlT2JqZWN0IH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuaW1wb3J0IHR5cGUge1xuICBEcmFnZ2FibGVQcm92aWRlZCxcbiAgRHJhZ2dhYmxlU3RhdGVTbmFwc2hvdCxcbiAgRHJvcFJlc3VsdCxcbiAgRHJhZ2dhYmxlTG9jYXRpb24sXG59IGZyb20gJ3JlYWN0LWJlYXV0aWZ1bC1kbmQnO1xuY29uc3QgYnVja2V0UmVnaW9uID0gJ3VzLWVhc3QtMSc7XG5jb25zdCBidWNrZXROYW1lID0gJ2F0b21pY2xpZmUtYXBwLXB1YmxpYy1pbWFnZS1wcm9kLXVuY29tcHJlc3NlZCc7XG4vLyBjb25zdCBmb3JtYXQgPSBcInBuZ1wiXG4vLyBjb25zdCByZXN1bHQgPSBQbGF0Zm9ybS5PUyA9PT0gXCJhbmRyb2lkXCIgPyBcInppcC1iYXNlNjRcIiA6IFwiYmFzZTY0XCJcblxuLy8gdHlwZSBzZXRTMyA9IFJlYWN0LkRpc3BhdGNoPFJlYWN0LlNldFN0YXRlQWN0aW9uPFMzQ2xpZW50Pj5cbnR5cGUgczNFbCA9IFJlYWN0Lk11dGFibGVSZWZPYmplY3Q8UzNDbGllbnQ+O1xuXG4vLyB0eXBlIHNldENyZWRJZCA9IFJlYWN0LkRpc3BhdGNoPFJlYWN0LlNldFN0YXRlQWN0aW9uPHN0cmluZz4+XG50eXBlIGNyZWRJZEVsID0gUmVhY3QuTXV0YWJsZVJlZk9iamVjdDxzdHJpbmc+O1xuXG50eXBlIHVzZXJJZEVsID0gUmVhY3QuTXV0YWJsZVJlZk9iamVjdDxzdHJpbmc+O1xuXG50eXBlIHBvaW50UmV3YXJkRWwgPSBSZWFjdC5NdXRhYmxlUmVmT2JqZWN0PG51bWJlcj47XG5cbmV4cG9ydCB0eXBlIENhbGVuZGFyRXZlbnRJZEVsVHlwZSA9IFJlYWN0Lk11dGFibGVSZWZPYmplY3Q8c3RyaW5nPjtcblxudHlwZSBSZWN1cnJlbmNlRnJlcXVlbmN5ID0gJ2RhaWx5JyB8ICd3ZWVrbHknIHwgJ21vbnRobHknIHwgJ3llYXJseSc7XG5cbnR5cGUgZGF5VHlwZSA9ICdNTycgfCAnVFUnIHwgJ1dFJyB8ICdUSCcgfCAnRlInIHwgJ1NBJyB8ICdTVSc7XG5cbnR5cGUgVGFza1R5cGUgPSAnRGFpbHknIHwgJ1dlZWtseScgfCAnTWFzdGVyJyB8ICdHcm9jZXJ5JyB8IHN0cmluZztcblxuY29uc3QgZXNjYXBlVW5zYWZlID0gKHVuc2FmZTogc3RyaW5nKSA9PlxuICB1bnNhZmVcbiAgICAucmVwbGFjZSgvJi9nLCAnJmFtcDsnKVxuICAgIC5yZXBsYWNlKC88L2csICcmbHQ7JylcbiAgICAucmVwbGFjZSgvPi9nLCAnJmd0OycpXG4gICAgLnJlcGxhY2UoL1wiL2csICcmcXVvdDsnKVxuICAgIC5yZXBsYWNlKC8nL2csICcmIzAzOTsnKVxuICAgIC5yZXBsYWNlKC8gL2dpLCAnLScpO1xuXG5jb25zdCBUT0RPID0gJ1RvIERvJztcbmNvbnN0IERPSU5HID0gJ0RvaW5nJztcbmNvbnN0IERPTkUgPSAnRG9uZSc7XG5cbmV4cG9ydCB0eXBlIGRyYWdFbmQ8VD4gPSB7XG4gIGRhdGE6IFRbXTtcbiAgZnJvbTogbnVtYmVyO1xuICB0bzogbnVtYmVyO1xufTtcblxuZXhwb3J0IGNvbnN0IHJlbW92ZVBhcmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgaW5kZXg6IG51bWJlcixcbiAgdGFza3M6IFRhc2tQbHVzVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICB0YXNrc1tpbmRleF0ucGFyZW50SWQgPSBudWxsO1xuXG4gICAgYXdhaXQgdXBkYXRlVGFza0J5SWRJbkRiKGNsaWVudCwgdGFza3NbaW5kZXhdKTtcbiAgICBjb25zb2xlLmxvZyh0YXNrc1tpbmRleF0sICcgc3VjY2Vzc2Z1bGx5IHVwZGF0ZWQnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlbW92ZSBwYXJlbnQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGFkZFBhcmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgaW5kZXg6IG51bWJlcixcbiAgaW5kZXhCZWZvcmU6IG51bWJlcixcbiAgdGFza3M6IFRhc2tQbHVzVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoaW5kZXhCZWZvcmUgPCAwKSB7XG4gICAgICBjb25zb2xlLmxvZygnIG5vIHBhcmVudCBpbiBwcmlvciBub3RlJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coaW5kZXgsIGluZGV4QmVmb3JlLCAnIHR5cGUsIGluZGV4LCBpbmRleEJlZm9yZScpO1xuXG4gICAgY29uc3QgbmV3RGF0ZSA9IGRheWpzKCkuZm9ybWF0KCk7XG5cbiAgICBsZXQgdGFza0lkT2ZCZWZvcmUgPSB0YXNrc1tpbmRleEJlZm9yZV0/LmlkO1xuICAgIGxldCBpbmRleE9mQmVmb3JlID0gaW5kZXhCZWZvcmU7XG4gICAgbGV0IHBhcmVudElkT2ZCZWZvcmUgPSB0YXNrc1tpbmRleEJlZm9yZV0/LnBhcmVudElkO1xuICAgIHdoaWxlIChwYXJlbnRJZE9mQmVmb3JlPy5sZW5ndGggPiAwICYmIGluZGV4T2ZCZWZvcmUgPiAtMikge1xuICAgICAgaW5kZXhPZkJlZm9yZS0tO1xuICAgICAgdGFza0lkT2ZCZWZvcmUgPSB0YXNrc1tpbmRleE9mQmVmb3JlXT8uaWQ7XG4gICAgICBwYXJlbnRJZE9mQmVmb3JlID0gdGFza3NbaW5kZXhPZkJlZm9yZV0/LnBhcmVudElkO1xuICAgIH1cblxuICAgIGlmIChpbmRleE9mQmVmb3JlIDwgMCkge1xuICAgICAgY29uc29sZS5sb2coaW5kZXhPZkJlZm9yZSwgJyBpbmRleE9mQmVmb3JlIDwgMCcpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIHRhc2tzW2luZGV4XS5wYXJlbnRJZCA9IHRhc2tJZE9mQmVmb3JlO1xuXG4gICAgYXdhaXQgdXBkYXRlVGFza0J5SWRJbkRiKGNsaWVudCwgdGFza3NbaW5kZXhdKTtcblxuICAgIGNvbnNvbGUubG9nKHRhc2tzW2luZGV4XSwgJyBwYXJlbnQgYWRkZWQnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGFkZCBwYXJlbnQnKTtcbiAgfVxufTtcbmV4cG9ydCBjb25zdCBzb3J0QnlPcmRlciA9IDxUPihhOiBUW10sIG9yZGVyQXJyYXk6IG51bWJlcltdKSA9PiB7XG4gIGNvbnN0IG5ld0EgPSBhLm1hcCgoaSwgaW54KSA9PiAoeyBhOiBpLCBvcmRlcjogb3JkZXJBcnJheVtpbnhdIH0pKTtcblxuICBuZXdBLnNvcnQoKGEsIGIpID0+IGEub3JkZXIgLSBiLm9yZGVyKTtcblxuICBjb25zdCBzb3J0ZWRBID0gbmV3QS5tYXAoKGkpID0+IGkuYSk7XG4gIHJldHVybiBzb3J0ZWRBO1xufTtcblxuY29uc3QgcmVvcmRlciA9IDxUPihsaXN0OiBUW10sIHN0YXJ0SW5kZXg6IG51bWJlciwgZW5kSW5kZXg6IG51bWJlcikgPT4ge1xuICBjb25zdCByZXN1bHQgPSBBcnJheS5mcm9tKGxpc3QpO1xuICBjb25zdCBbcmVtb3ZlZF0gPSByZXN1bHQuc3BsaWNlKHN0YXJ0SW5kZXgsIDEpO1xuICByZXN1bHQuc3BsaWNlKGVuZEluZGV4LCAwLCByZW1vdmVkKTtcblxuICByZXR1cm4gcmVzdWx0O1xufTtcblxuZXhwb3J0IGNvbnN0IG9uRHJhZ0VuZFVwZGF0ZUZvcldlYiA9IGFzeW5jIDxUPihcbiAgZHJvcFJlc3VsdDogRHJvcFJlc3VsdCxcbiAgdGFza3M6IFRhc2tQbHVzVHlwZVtdLFxuICBvbGREaXNwbGF5VUlzOiBEaXNwbGF5VUlUeXBlW10sXG4gIHNldERpc3BsYXlVSXM6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPERpc3BsYXlVSVR5cGVbXT4+LFxuICBkYXRhSW5kZXhUb0Rpc3BsYXlBcnJheTogbnVtYmVyW10sXG4gIHNldERhdGFJbmRleFRvRGlzcGxheUFycmF5OiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxudW1iZXJbXT4+LFxuICB0YXNrVHlwZTogVGFza1N1YlR5cGUsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+XG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBkcm9wcGVkIG5vd2hlcmVcbiAgICBpZiAoIWRyb3BSZXN1bHQuZGVzdGluYXRpb24pIHtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBjb25zdCBzb3VyY2U6IERyYWdnYWJsZUxvY2F0aW9uID0gZHJvcFJlc3VsdC5zb3VyY2U7XG4gICAgY29uc3QgZGVzdGluYXRpb246IERyYWdnYWJsZUxvY2F0aW9uID0gZHJvcFJlc3VsdC5kZXN0aW5hdGlvbjtcblxuICAgIC8vIGRpZCBub3QgbW92ZSBhbnl3aGVyZSAtIGNhbiBiYWlsIGVhcmx5XG4gICAgaWYgKFxuICAgICAgc291cmNlLmRyb3BwYWJsZUlkID09PSBkZXN0aW5hdGlvbi5kcm9wcGFibGVJZCAmJlxuICAgICAgc291cmNlLmluZGV4ID09PSBkZXN0aW5hdGlvbi5pbmRleFxuICAgICkge1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGNvbnN0IGZyb20gPSBzb3VyY2UuaW5kZXg7XG4gICAgY29uc3QgdG8gPSBkZXN0aW5hdGlvbi5pbmRleDtcbiAgICBjb25zdCByZW9yZGVyZWREaXNwbGF5VUlzID0gcmVvcmRlcihvbGREaXNwbGF5VUlzLCBmcm9tLCB0byk7XG5cbiAgICBjb25zdCB0ZW1wRGlzcGxheVVJID0gcmVvcmRlckRhdGFBcnJheShvbGREaXNwbGF5VUlzLCBmcm9tLCB0byk7XG4gICAgY29uc3QgdGVtcERhdGFJbmRleCA9IHJlb3JkZXJEYXRhQXJyYXkoZGF0YUluZGV4VG9EaXNwbGF5QXJyYXksIGZyb20sIHRvKTtcbiAgICBzZXREaXNwbGF5VUlzKHRlbXBEaXNwbGF5VUkpO1xuICAgIHNldERhdGFJbmRleFRvRGlzcGxheUFycmF5KHRlbXBEYXRhSW5kZXgpO1xuXG4gICAgaWYgKGZyb20gPCAwKSB7XG4gICAgICBjb25zb2xlLmxvZygnZnJvbSA8IDAgc29tZXRoaW5nIHdlbnQgd3JvbmcnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhmcm9tLCAnIGZyb20gdmFsdWUnKTtcblxuICAgIGNvbnNvbGUubG9nKHRhc2tzLCAnIG9sZCB0YXNrcycpO1xuICAgIC8vIGZpbmQgbW92ZWRcbiAgICBjb25zdCBtb3ZlZFZhbHVlID0gb2xkRGlzcGxheVVJc1tmcm9tXTtcblxuICAgIGNvbnNvbGUubG9nKG1vdmVkVmFsdWUsICcgbW92ZWRWYWx1ZScpO1xuXG4gICAgLy8gY2hlY2sgaWYgcGFyZW50XG4gICAgY29uc3Qgb2xkRGF0YUluZGV4ID0gZGF0YUluZGV4VG9EaXNwbGF5QXJyYXlbZnJvbV07XG4gICAgY29uc29sZS5sb2cob2xkRGF0YUluZGV4LCAnIG9sZERhdGFJbmRleCcpO1xuICAgIGNvbnN0IHRhc2tJZE9mTW92ZWRWYWx1ZSA9IHRhc2tzW29sZERhdGFJbmRleF0/LmlkO1xuXG4gICAgY29uc3QgaXNQYXJlbnQgPSBjaGVja1Rhc2tJc1BhcmVudCh0YXNrcywgdGFza0lkT2ZNb3ZlZFZhbHVlKTtcbiAgICBjb25zb2xlLmxvZyhpc1BhcmVudCwgJyBpc1BhcmVudCcpO1xuICAgIC8vIGZpcnN0IHVwZGF0ZSBkYXRhIGFycmF5c1xuICAgIGNvbnN0IHsgZnJvbTogZnJvbURhdGFJbmRleCwgdG86IHRvRGF0YUluZGV4IH0gPVxuICAgICAgZ2V0SW5kZXhVcGRhdGVzRnJvbVVJRm9yV2ViKFxuICAgICAgICByZW9yZGVyZWREaXNwbGF5VUlzLFxuICAgICAgICBvbGREaXNwbGF5VUlzLFxuICAgICAgICBtb3ZlZFZhbHVlXG4gICAgICApO1xuICAgIGNvbnNvbGUubG9nKGZyb21EYXRhSW5kZXgsIHRvRGF0YUluZGV4LCAnIGZyb21EYXRhSW5kZXggdG9EYXRhSW5kZXgnKTtcblxuICAgIGxldCBuZXdUYXNrcyA9IFtdO1xuXG4gICAgaWYgKGlzUGFyZW50KSB7XG4gICAgICBuZXdUYXNrcyA9IHJlb3JkZXJQYXJlbnRBbmRDaGlsZERhdGFBcnJheShcbiAgICAgICAgdGFza3MsXG4gICAgICAgIGZyb21EYXRhSW5kZXgsXG4gICAgICAgIHRvRGF0YUluZGV4LFxuICAgICAgICB0YXNrcyxcbiAgICAgICAgdGFza0lkT2ZNb3ZlZFZhbHVlXG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICBuZXdUYXNrcyA9IHJlb3JkZXJEYXRhQXJyYXkodGFza3MsIGZyb21EYXRhSW5kZXgsIHRvRGF0YUluZGV4KTtcbiAgICB9XG5cbiAgICAvLyBpZiBjaGlsZCBjaGVjayBpZiBwYXJlbnQgcmVtb3ZlZFxuICAgIGlmICh0YXNrcz8uW2Zyb21EYXRhSW5kZXhdPy5wYXJlbnRJZCkge1xuICAgICAgY29uc3QgcGFyZW50UmVtb3ZlZCA9IGNoZWNrSWZQYXJlbnRSZW1vdmVkT2ZDaGlsZE1vdmVkKFxuICAgICAgICBuZXdUYXNrcyxcbiAgICAgICAgdGFza3M/Lltmcm9tRGF0YUluZGV4XT8ucGFyZW50SWQsXG4gICAgICAgIHRhc2tzW29sZERhdGFJbmRleF1cbiAgICAgICk7XG5cbiAgICAgIGNvbnNvbGUubG9nKHBhcmVudFJlbW92ZWQsICcgcGFyZW50UmVtb3ZlZCcpO1xuXG4gICAgICBpZiAocGFyZW50UmVtb3ZlZCkge1xuICAgICAgICAvLyByZW1vdmUgZnJvbSBkYlxuICAgICAgICAvLyB1cGRhdGVUYXNrQnlJZEluRGJcbiAgICAgICAgY29uc3QgbW92ZWRUYXNrID0gdGFza3Nbb2xkRGF0YUluZGV4XTtcblxuICAgICAgICBtb3ZlZFRhc2sucGFyZW50SWQgPSBudWxsO1xuXG4gICAgICAgIGF3YWl0IHVwZGF0ZVRhc2tCeUlkSW5EYihjbGllbnQsIG1vdmVkVGFzayk7XG5cbiAgICAgICAgY29uc29sZS5sb2cobmV3VGFza3MsICcgbmV3VGFza3MgYWZ0ZXIgcGFyZW50IHJlbW92ZWQnKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBjaGVjayBpZiBzdGF0dXMgY2hhbmdlZFxuICAgIGNvbnN0IG5ld1N0YXR1cyA9IGNoZWNrU3RhdHVzQ2hhbmdlRm9yV2ViKFxuICAgICAgcmVvcmRlcmVkRGlzcGxheVVJcyBhcyBEaXNwbGF5VUlUeXBlW10sXG4gICAgICBtb3ZlZFZhbHVlXG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKG5ld1N0YXR1cywgJyBuZXdTdGF0dXMnKTtcblxuICAgIC8vIHVwZGF0ZSBzdGF0dXNcbiAgICBpZiAobmV3U3RhdHVzPy52YWx1ZSAhPT0gdGFza3M/Lltmcm9tRGF0YUluZGV4XT8uc3RhdHVzKSB7XG4gICAgICBjb25zdCBtb3ZlZFRhc2sgPSB0YXNrc1tvbGREYXRhSW5kZXhdO1xuICAgICAgbW92ZWRUYXNrLnN0YXR1cyA9IG5ld1N0YXR1cz8udmFsdWUgfHwgVGFza1N0YXR1cy5UT0RPO1xuXG4gICAgICBhd2FpdCB1cGRhdGVUYXNrQnlJZEluRGIoY2xpZW50LCBtb3ZlZFRhc2spO1xuXG4gICAgICBjb25zb2xlLmxvZyhuZXdUYXNrcywgJyBuZXdUYXNrcyBhZnRlciBzdGF0dXMgdXBkYXRlJyk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2cobmV3VGFza3MsICcgbmV3VGFza3MnKTtcblxuICAgIC8vIHVwZGF0ZSBvcmRlciBpbiBkYlxuICAgIG5ld1Rhc2tzPy5mb3JFYWNoKCh0LCBpbngpID0+ICh0Lm9yZGVyID0gaW54KSk7XG5cbiAgICBhd2FpdCB1cHNlcnRNYW55VGFza3NJbkRiKFxuICAgICAgY2xpZW50LFxuICAgICAgbmV3VGFza3M/Lm1hcCgoaSkgPT4gXy5vbWl0KGksIFsnc3RhcnREYXRlJywgJ2VuZERhdGUnLCAnbmV4dERheSddKSlcbiAgICApO1xuXG4gICAgY29uc3QgbmV3U3RhdHVzQXJyYXkgPSBuZXdUYXNrcy5tYXAoKHQpID0+IHQ/LnN0YXR1cyk7XG5cbiAgICBjb25zdCB7XG4gICAgICBkaXNwbGF5VUlBcnJheTogbmV3RGlzcGxheVVJQXJyYXksXG4gICAgICBkYXRhSW5kZXhUb0Rpc3BsYXlBcnJheTogbmV3RGF0YUluZGV4VG9EaXNwbGF5QXJyYXksXG4gICAgfSA9IGdldERpc3BsYXlVSUZvcldlYihuZXdUYXNrcywgbmV3U3RhdHVzQXJyYXksIHRhc2tUeXBlLCB1c2VySWQpO1xuXG4gICAgY29uc29sZS5sb2cobmV3RGF0YUluZGV4VG9EaXNwbGF5QXJyYXksICcgbmV3RGF0YUluZGV4VG9EaXNwbGF5QXJyYXknKTtcbiAgICBzZXREYXRhSW5kZXhUb0Rpc3BsYXlBcnJheShuZXdEYXRhSW5kZXhUb0Rpc3BsYXlBcnJheSk7XG4gICAgc2V0RGlzcGxheVVJcyhuZXdEaXNwbGF5VUlBcnJheSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgdmFsdWVzJyk7XG4gIH1cbn07XG5cbi8vIGV4cG9ydCBjb25zdCBvbkRyYWdFbmRVcGRhdGUgPSBhc3luYyA8VD4oXG4vLyAgIGRyYWdFbmQ6IGRyYWdFbmQ8VD4sXG4vLyAgIHRhc2tzOiBUYXNrUGx1c1R5cGVbXSxcbi8vICAgb2xkRGlzcGxheVVJczogc3RyaW5nW10sXG4vLyAgIHNldERpc3BsYXlVSXM6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPHN0cmluZ1tdPj4sXG4vLyAgIGRhdGFJbmRleFRvRGlzcGxheUFycmF5OiBudW1iZXJbXSxcbi8vICAgc2V0RGF0YUluZGV4VG9EaXNwbGF5QXJyYXk6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPG51bWJlcltdPj4sXG4vLyAgIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4vLyApID0+IHtcbi8vICAgdHJ5IHtcbi8vICAgICBjb25zdCB7IGRhdGEsIGZyb20sIHRvIH0gPSBkcmFnRW5kXG4vLyAgICAgY29uc3QgdGVtcERpc3BsYXlVSSA9IHJlb3JkZXJEYXRhQXJyYXkob2xkRGlzcGxheVVJcywgZnJvbSwgdG8pXG4vLyAgICAgY29uc3QgdGVtcERhdGFJbmRleCA9IHJlb3JkZXJEYXRhQXJyYXkoZGF0YUluZGV4VG9EaXNwbGF5QXJyYXksIGZyb20sIHRvKVxuLy8gICAgIHNldERpc3BsYXlVSXModGVtcERpc3BsYXlVSSlcbi8vICAgICBzZXREYXRhSW5kZXhUb0Rpc3BsYXlBcnJheSh0ZW1wRGF0YUluZGV4KVxuXG4vLyAgICAgaWYgKGZyb20gPCAwKSB7XG4vLyAgICAgICBjb25zb2xlLmxvZygnZnJvbSA8IDAgc29tZXRoaW5nIHdlbnQgd3JvbmcnKVxuLy8gICAgICAgcmV0dXJuXG4vLyAgICAgfVxuXG4vLyAgICAgY29uc29sZS5sb2coZnJvbSwgJyBmcm9tIHZhbHVlJylcbi8vICAgICBjb25zb2xlLmxvZyhkYXRhLCAnIGRhdGEgZnJvbSBvbkRyYWdFbmRVcGRhdGUnKVxuLy8gICAgIGNvbnNvbGUubG9nKHRhc2tzLCAnIG9sZCB0YXNrcycpXG4vLyAgICAgLy8gZmluZCBtb3ZlZFxuLy8gICAgIGNvbnN0IG1vdmVkVmFsdWUgPSBvbGREaXNwbGF5VUlzW2Zyb21dXG5cbi8vICAgICBjb25zb2xlLmxvZyhtb3ZlZFZhbHVlLCAnIG1vdmVkVmFsdWUnKVxuXG4vLyAgICAgLy8gY2hlY2sgaWYgcGFyZW50XG4vLyAgICAgY29uc3Qgb2xkRGF0YUluZGV4ID0gZGF0YUluZGV4VG9EaXNwbGF5QXJyYXlbZnJvbV1cbi8vICAgICBjb25zb2xlLmxvZyhvbGREYXRhSW5kZXgsICcgb2xkRGF0YUluZGV4Jylcbi8vICAgICBjb25zdCB0YXNrSWRPZk1vdmVkVmFsdWUgPSB0YXNrc1tvbGREYXRhSW5kZXhdPy5pZFxuXG4vLyAgICAgY29uc3QgaXNQYXJlbnQgPSBjaGVja1Rhc2tJc1BhcmVudCh0YXNrcywgdGFza0lkT2ZNb3ZlZFZhbHVlKVxuLy8gICAgIGNvbnNvbGUubG9nKGlzUGFyZW50LCAnIGlzUGFyZW50Jylcbi8vICAgICAvLyBmaXJzdCB1cGRhdGUgZGF0YSBhcnJheXNcbi8vICAgICBjb25zdCB7IGZyb206IGZyb21EYXRhSW5kZXgsIHRvOiB0b0RhdGFJbmRleCB9ID0gZ2V0SW5kZXhVcGRhdGVzRnJvbVVJKGRhdGEgYXMgdW5rbm93bltdIGFzIERpc3BsYXlVSVR5cGVbXSwgb2xkRGlzcGxheVVJcywgbW92ZWRWYWx1ZSlcbi8vICAgICBjb25zb2xlLmxvZyhmcm9tRGF0YUluZGV4LCB0b0RhdGFJbmRleCwgJyBmcm9tRGF0YUluZGV4IHRvRGF0YUluZGV4JylcblxuLy8gICAgIGxldCBuZXdUYXNrcyA9IFtdXG5cbi8vICAgICBpZiAoaXNQYXJlbnQpIHtcblxuLy8gICAgICAgbmV3VGFza3MgPSByZW9yZGVyUGFyZW50QW5kQ2hpbGREYXRhQXJyYXkodGFza3MsIGZyb21EYXRhSW5kZXgsIHRvRGF0YUluZGV4LCB0YXNrcywgdGFza0lkT2ZNb3ZlZFZhbHVlKVxuXG4vLyAgICAgfSBlbHNlIHtcblxuLy8gICAgICAgbmV3VGFza3MgPSByZW9yZGVyRGF0YUFycmF5KHRhc2tzLCBmcm9tRGF0YUluZGV4LCB0b0RhdGFJbmRleClcblxuLy8gICAgIH1cblxuLy8gICAgIC8vIGlmIGNoaWxkIGNoZWNrIGlmIHBhcmVudCByZW1vdmVkXG4vLyAgICAgaWYgKHRhc2tzPy5bZnJvbURhdGFJbmRleF0/LnBhcmVudElkKSB7XG5cbi8vICAgICAgIGNvbnN0IHBhcmVudFJlbW92ZWQgPSBjaGVja0lmUGFyZW50UmVtb3ZlZE9mQ2hpbGRNb3ZlZChcbi8vICAgICAgICAgbmV3VGFza3MsXG4vLyAgICAgICAgIHRhc2tzPy5bZnJvbURhdGFJbmRleF0/LnBhcmVudElkLFxuLy8gICAgICAgICB0YXNrc1tvbGREYXRhSW5kZXhdLFxuLy8gICAgICAgKVxuXG4vLyAgICAgICBjb25zb2xlLmxvZyhwYXJlbnRSZW1vdmVkLCAnIHBhcmVudFJlbW92ZWQnKVxuXG4vLyAgICAgICBpZiAocGFyZW50UmVtb3ZlZCkge1xuXG4vLyAgICAgICAgIC8vIHJlbW92ZSBmcm9tIGRiXG4vLyAgICAgICAgIC8vIHVwZGF0ZVRhc2tCeUlkSW5EYlxuLy8gICAgICAgICBjb25zdCBtb3ZlZFRhc2sgPSB0YXNrc1tvbGREYXRhSW5kZXhdXG5cbi8vICAgICAgICAgbW92ZWRUYXNrLnBhcmVudElkID0gbnVsbFxuXG4vLyAgICAgICAgIGF3YWl0IHVwZGF0ZVRhc2tCeUlkSW5EYihjbGllbnQsIG1vdmVkVGFzaylcblxuLy8gICAgICAgICBjb25zb2xlLmxvZyhuZXdUYXNrcywgJyBuZXdUYXNrcyBhZnRlciBwYXJlbnQgcmVtb3ZlZCcpXG4vLyAgICAgICB9XG4vLyAgICAgfVxuXG4vLyAgICAgLy8gY2hlY2sgaWYgc3RhdHVzIGNoYW5nZWRcbi8vICAgICBjb25zdCBuZXdTdGF0dXMgPSBjaGVja1N0YXR1c0NoYW5nZUZvcldlYihcbi8vICAgICAgIGRhdGEgYXMgdW5rbm93bltdIGFzIERpc3BsYXlVSVR5cGVbXSxcbi8vICAgICAgIG1vdmVkVmFsdWUsXG4vLyAgICAgKVxuXG4vLyAgICAgY29uc29sZS5sb2cobmV3U3RhdHVzLCAnIG5ld1N0YXR1cycpXG5cbi8vICAgICAvLyB1cGRhdGUgc3RhdHVzXG4vLyAgICAgaWYgKG5ld1N0YXR1cz8udmFsdWUgIT09IHRhc2tzPy5bZnJvbURhdGFJbmRleF0/LnN0YXR1cykge1xuXG4vLyAgICAgICBjb25zdCBtb3ZlZFRhc2sgPSB0YXNrc1tvbGREYXRhSW5kZXhdXG4vLyAgICAgICBtb3ZlZFRhc2suc3RhdHVzID0gbmV3U3RhdHVzPy52YWx1ZSB8fCBUYXNrU3RhdHVzLlRPRE9cblxuLy8gICAgICAgYXdhaXQgdXBkYXRlVGFza0J5SWRJbkRiKGNsaWVudCwgbW92ZWRUYXNrKVxuXG4vLyAgICAgICBjb25zb2xlLmxvZyhuZXdUYXNrcywgJyBuZXdUYXNrcyBhZnRlciBzdGF0dXMgdXBkYXRlJylcbi8vICAgICB9XG5cbi8vICAgICBjb25zb2xlLmxvZyhuZXdUYXNrcywgJyBuZXdUYXNrcycpXG5cbi8vICAgICAvLyB1cGRhdGUgb3JkZXIgaW4gZGJcbi8vICAgICBuZXdUYXNrcz8uZm9yRWFjaCgodCwgaW54KSA9PiAodC5vcmRlciA9IGlueCkpXG5cbi8vICAgICBhd2FpdCB1cHNlcnRNYW55VGFza3NJbkRiKGNsaWVudCwgbmV3VGFza3M/Lm1hcChpID0+IF8ub21pdChpLCBbJ3N0YXJ0RGF0ZScsICdlbmREYXRlJywgJ25leHREYXknXSkpKVxuXG4vLyAgICAgY29uc3QgbmV3U3RhdHVzQXJyYXkgPSBuZXdUYXNrcy5tYXAodCA9PiB0Py5zdGF0dXMpXG5cbi8vICAgICBjb25zdCB7XG4vLyAgICAgICBkaXNwbGF5VUlBcnJheTogbmV3RGlzcGxheVVJQXJyYXksXG4vLyAgICAgICBkYXRhSW5kZXhUb0Rpc3BsYXlBcnJheTogbmV3RGF0YUluZGV4VG9EaXNwbGF5QXJyYXksXG4vLyAgICAgfSA9IGdldERpc3BsYXlVSShuZXdUYXNrcywgbmV3U3RhdHVzQXJyYXkpXG5cbi8vICAgICBjb25zb2xlLmxvZyhuZXdEYXRhSW5kZXhUb0Rpc3BsYXlBcnJheSwgJyBuZXdEYXRhSW5kZXhUb0Rpc3BsYXlBcnJheScpXG4vLyAgICAgc2V0RGF0YUluZGV4VG9EaXNwbGF5QXJyYXkobmV3RGF0YUluZGV4VG9EaXNwbGF5QXJyYXkpXG4vLyAgICAgc2V0RGlzcGxheVVJcyhuZXdEaXNwbGF5VUlBcnJheSlcbi8vICAgfSBjYXRjaCAoZSkge1xuLy8gICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSB2YWx1ZXMnKVxuLy8gICB9XG4vLyB9XG5cbmV4cG9ydCBjb25zdCBjaGVja1Rhc2tJc1BhcmVudCA9ICh0YXNrczogVGFza1BsdXNUeXBlW10sIHRhc2tJZDogc3RyaW5nKSA9PiB7XG4gIGNvbnN0IGZvdW5kID0gdGFza3MuZmluZCgoaSkgPT4gaT8ucGFyZW50SWQgPT09IHRhc2tJZCk7XG4gIHJldHVybiAhIWZvdW5kO1xufTtcblxuZXhwb3J0IGNvbnN0IGNoZWNrSWZQYXJlbnRSZW1vdmVkT2ZDaGlsZE1vdmVkID0gKFxuICBuZXdUYXNrczogVGFza1BsdXNUeXBlW10sXG4gIG9sZFBhcmVudElkOiBzdHJpbmcsXG4gIG1vdmVkVGFzazogVGFza1BsdXNUeXBlXG4pID0+IHtcbiAgY29uc29sZS5sb2cobW92ZWRUYXNrLCAnIG1vdmVkVGFzayBpbnNpZGUgY2hlY2tJZlBhcmVudFJlbW92ZWRPZkNoaWxkTW92ZWQnKTtcbiAgY29uc3QgbW92ZWRJbmRleCA9IG5ld1Rhc2tzPy5maW5kSW5kZXgoKG4pID0+IG4/LmlkID09PSBtb3ZlZFRhc2s/LmlkKTtcbiAgY29uc29sZS5sb2cobW92ZWRJbmRleCwgJyBtb3ZlZEluZGV4Jyk7XG5cbiAgaWYgKG1vdmVkSW5kZXggPT09IC0xKSB7XG4gICAgY29uc29sZS5sb2coJyBtb3ZlZEluZGV4IGlzIHdyb25nJyk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgY29uc3QgbmV3T25lQmVmb3JlUGFyZW50SWQgPSBuZXdUYXNrc1ttb3ZlZEluZGV4IC0gMV0/LnBhcmVudElkO1xuICBjb25zb2xlLmxvZyhuZXdPbmVCZWZvcmVQYXJlbnRJZCwgJyBuZXdPbmVCZWZvcmVQYXJlbnRJZCcpO1xuXG4gIGlmIChuZXdPbmVCZWZvcmVQYXJlbnRJZCA9PT0gb2xkUGFyZW50SWQpIHtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBjb25zdCBuZXdPbmVCZWZvcmVUYXNrSWQgPSBuZXdUYXNrc1ttb3ZlZEluZGV4IC0gMV0/LmlkO1xuICBjb25zb2xlLmxvZyhuZXdPbmVCZWZvcmVUYXNrSWQsICcgbmV3T25lQmVmb3JlVGFza0lkJyk7XG5cbiAgaWYgKG5ld09uZUJlZm9yZVRhc2tJZCA9PT0gb2xkUGFyZW50SWQpIHtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICByZXR1cm4gdHJ1ZTtcbn07XG5cbmV4cG9ydCBjb25zdCBmaW5kUGFyZW50T2ZUYXNrRm9yV2ViID0gKFxuICBkaXNwbGF5VUlzOiBEaXNwbGF5VUlUeXBlW10sXG4gIGluZGV4T2ZDaGlsZDogbnVtYmVyXG4pID0+IHtcbiAgLy8gdmFsaWRhdGUgdmFsdWVzXG4gIGlmIChpbmRleE9mQ2hpbGQgPT09IDApIHtcbiAgICBjb25zb2xlLmxvZygnaW5kZXhPZkNoaWxkIGlzIDAgaW5zaWRlIGZpbmQgcGFyZW50IG9mIHRhc2snKTtcbiAgICByZXR1cm47XG4gIH1cblxuICBpZiAoaW5kZXhPZkNoaWxkID09PSAxKSB7XG4gICAgY29uc29sZS5sb2coJ2luZGV4T2ZDaGlsZCBpcyAxIGluc2lkZSBmaW5kcGFyZW50b2Z0YXNrJyk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgaWYgKGluZGV4T2ZDaGlsZCA+IGRpc3BsYXlVSXMubGVuZ3RoIC0gMSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ2luZGV4T2ZDaGlsZCBncmVhdGVyIHRoYW4gbGFzdCBpbmRleE9mQ2hpbGQgaW5zaWRlIGZpbmRwYXJlbnRvZnRhc2snXG4gICAgKTtcbiAgICByZXR1cm47XG4gIH1cblxuICBjb25zdCBwYXJlbnRWYWx1ZSA9IGRpc3BsYXlVSXNbaW5kZXhPZkNoaWxkIC0gMV07XG5cbiAgY29uc3QgZm91bmQgPSBbVE9ETywgRE9JTkcsIERPTkVdLmZpbmQoKGkpID0+IGkgPT09IHBhcmVudFZhbHVlPy5ub3Rlcyk7XG5cbiAgaWYgKGZvdW5kKSB7XG4gICAgY29uc29sZS5sb2coZm91bmQsICcgb3JkZXIgdmFsdWUgaW5zaWRlIGZpbmRwYXJlbnRvZnRhc2snKTtcbiAgICByZXR1cm47XG4gIH1cblxuICByZXR1cm4gcGFyZW50VmFsdWU7XG59O1xuZXhwb3J0IGNvbnN0IGNoZWNrU3RhdHVzQ2hhbmdlRm9yV2ViID0gKFxuICByZW9yZGVyZWREaXNwbGF5VUlzOiBEaXNwbGF5VUlUeXBlW10sXG4gIHZhbHVlTW92ZWQ6IERpc3BsYXlVSVR5cGVcbikgPT4ge1xuICBjb25zdCByZXZlcnNlZCA9IF8ucmV2ZXJzZShyZW9yZGVyZWREaXNwbGF5VUlzKTtcbiAgY29uc29sZS5sb2cocmVvcmRlcmVkRGlzcGxheVVJcywgJyByZW9yZGVyZWREaXNwbGF5VUlzIGluIGNoZWNrU3RhdHVzQ2hhbmdlJyk7XG4gIGNvbnNvbGUubG9nKHJldmVyc2VkLCAnIHJldmVyc2VkIGluIGNoZWNrU3RhdHVzQ2hhbmdlJyk7XG4gIGNvbnNvbGUubG9nKHZhbHVlTW92ZWQsICcgdmFsdWVNb3ZlZCBpbiBjaGVja1N0YXR1c0NoYW5nZScpO1xuICBjb25zdCBpbmRleCA9IHJldmVyc2VkLmZpbmRJbmRleCgocikgPT4gci5pZCA9PT0gdmFsdWVNb3ZlZC5pZCk7XG4gIGNvbnNvbGUubG9nKGluZGV4LCAnIGluZGV4IGluIGNoZWNrU3RhdHVzQ2hhbmdlJyk7XG4gIGNvbnN0IHNsaWNlZCA9IHJldmVyc2VkLnNsaWNlKGluZGV4KTtcbiAgY29uc29sZS5sb2coc2xpY2VkLCAnIHNsaWNlZCBpbiBjaGVja1N0YXR1c0NoYW5nZScpO1xuICBjb25zdCBoZWFkZXJBcnJheSA9IFtUT0RPLCBET0lORywgRE9ORV07XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBzbGljZWQubGVuZ3RoOyBpKyspIHtcbiAgICBjb25zdCBmb3VuZCA9IGhlYWRlckFycmF5LmZpbmQoKGopID0+IGogPT09IHNsaWNlZFtpXS5ub3Rlcyk7XG4gICAgY29uc29sZS5sb2coZm91bmQsICcgZm91bmQgaW4gY2hlY2tTdGF0dXNDaGFuZ2UnKTtcbiAgICBpZiAoZm91bmQpIHtcbiAgICAgIGlmIChmb3VuZCA9PT0gVE9ETykge1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIGxhYmVsOiBUT0RPLFxuICAgICAgICAgIHZhbHVlOiBUYXNrU3RhdHVzLlRPRE8sXG4gICAgICAgIH07XG4gICAgICB9IGVsc2UgaWYgKGZvdW5kID09PSBET0lORykge1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIGxhYmVsOiBET0lORyxcbiAgICAgICAgICB2YWx1ZTogVGFza1N0YXR1cy5ET0lORyxcbiAgICAgICAgfTtcbiAgICAgIH0gZWxzZSBpZiAoZm91bmQgPT09IERPTkUpIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICBsYWJlbDogRE9ORSxcbiAgICAgICAgICB2YWx1ZTogVGFza1N0YXR1cy5ET05FLFxuICAgICAgICB9O1xuICAgICAgfVxuICAgIH1cbiAgfVxufTtcbmV4cG9ydCBjb25zdCByZW9yZGVyRGF0YUFycmF5ID0gPFQ+KGE6IFRbXSwgZnJvbTogbnVtYmVyLCB0bzogbnVtYmVyKSA9PiB7XG4gIGNvbnN0IGJhY2t3YXJkcyA9IHRvIDwgZnJvbTtcbiAgY29uc3Qgc2FtZSA9IHRvID09PSBmcm9tO1xuICBjb25zdCBtb3ZlZFZhbHVlID0gYVtmcm9tXTtcbiAgY29uc3QgbmV3QTogVFtdID0gW107XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBhLmxlbmd0aDsgaSsrKSB7XG4gICAgaWYgKGkgPT09IHRvKSB7XG4gICAgICBpZiAoYmFja3dhcmRzKSB7XG4gICAgICAgIG5ld0EucHVzaChtb3ZlZFZhbHVlKTtcbiAgICAgICAgbmV3QS5wdXNoKGFbaV0pO1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH0gZWxzZSBpZiAoc2FtZSkge1xuICAgICAgICBuZXdBLnB1c2goYVtpXSk7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3QS5wdXNoKGFbaV0pO1xuICAgICAgICBuZXdBLnB1c2gobW92ZWRWYWx1ZSk7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChpICE9PSBmcm9tKSB7XG4gICAgICBuZXdBLnB1c2goYVtpXSk7XG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIG5ld0E7XG59O1xuXG5leHBvcnQgY29uc3QgcmVvcmRlclBhcmVudEFuZENoaWxkRGF0YUFycmF5ID0gPFQ+KFxuICBhOiBUW10sXG4gIGZyb206IG51bWJlcixcbiAgdG86IG51bWJlcixcbiAgb2xkVGFza3M6IFRhc2tQbHVzVHlwZVtdLFxuICB0YXNrSWRPZk1vdmVkVmFsdWU6IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnNvbGUubG9nKG9sZFRhc2tzLCAnIG9sZFBhcmVudElkQXJyYXknKTtcbiAgY29uc3QgYmFja3dhcmRzID0gdG8gPCBmcm9tO1xuXG4gIGNvbnN0IG1vdmVkVmFsdWUgPSBhW2Zyb21dO1xuICBjb25zdCBuZXdBOiBUW10gPSBbXTtcblxuICBsZXQgc2FtZTogYm9vbGVhbiA9IHRydWU7XG5cbiAgaWYgKCFiYWNrd2FyZHMpIHtcbiAgICBjb25zb2xlLmxvZygnICFiYWNrd2FyZHMgaW5zaWRlIHVuaXF1ZSBjYXNlJyk7XG4gICAgZm9yIChsZXQgaSA9IGZyb20gKyAxOyBpIDw9IHRvOyBpKyspIHtcbiAgICAgIGlmICh0YXNrSWRPZk1vdmVkVmFsdWUgIT09IG9sZFRhc2tzW2ldPy5wYXJlbnRJZCkge1xuICAgICAgICBjb25zb2xlLmxvZygnIHNhbWUgPSBmYWxzZSBpbnNpZGUgdW5pcXVlIGNhc2UnKTtcbiAgICAgICAgc2FtZSA9IGZhbHNlO1xuICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIC8vIG1vdmluZyBhcm91bmQgY2hpbGRyZW4gb25seSBhbmQgZGlmZiBzdGF0dXNcbiAgaWYgKHNhbWUpIHtcbiAgICByZXR1cm4gYTtcbiAgfVxuXG4gIHNhbWUgPSB0byA9PT0gZnJvbTtcblxuICBjb25zdCBjaGlsZFRhc2tJZEluZGV4ZXMgPSBvbGRUYXNrc1xuICAgIC5tYXAoKGksIGluZGV4KSA9PiB7XG4gICAgICBpZiAoaT8ucGFyZW50SWQgPT09IHRhc2tJZE9mTW92ZWRWYWx1ZSkge1xuICAgICAgICByZXR1cm4gaW5kZXg7XG4gICAgICB9XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9KVxuICAgIC5maWx0ZXIoKGkpID0+IGkgIT09IG51bGwpO1xuXG4gIGNvbnNvbGUubG9nKGNoaWxkVGFza0lkSW5kZXhlcywgJyBjaGlsZFRhc2tJZEluZGV4ZXMnKTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGEubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoaSA9PT0gdG8pIHtcbiAgICAgIGlmIChiYWNrd2FyZHMpIHtcbiAgICAgICAgbmV3QS5wdXNoKG1vdmVkVmFsdWUpO1xuICAgICAgICBjb25zb2xlLmxvZyhuZXdBLCAnIG5ld0EgaW5zaWRlIGJhY2t3YXJkcyBiZWZvcmUgY2hpbGQnKTtcbiAgICAgICAgZm9yIChsZXQgaiA9IDA7IGogPCBjaGlsZFRhc2tJZEluZGV4ZXMubGVuZ3RoOyBqKyspIHtcbiAgICAgICAgICBjb25zdCBvbGRJbmRleCA9IGNoaWxkVGFza0lkSW5kZXhlc1tqXTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhvbGRJbmRleCwgJyBvbGRJbmRleCBpbnNpZGUgY2hpbGRUYXNrSWRJbmRleGVzJyk7XG4gICAgICAgICAgaWYgKHRvID09PSBvbGRJbmRleCkge1xuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKGZyb20gPT09IG9sZEluZGV4KSB7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG4gICAgICAgICAgbmV3QS5wdXNoKGFbb2xkSW5kZXhdKTtcbiAgICAgICAgfVxuICAgICAgICBjb25zb2xlLmxvZyhuZXdBLCAnIG5ld0EgaW5zaWRlIGJhY2t3YXJkcyBhZnRlciBjaGlsZCcpO1xuICAgICAgICBuZXdBLnB1c2goYVtpXSk7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChzYW1lKSB7XG4gICAgICAgIG5ld0EucHVzaChhW2ldKTtcbiAgICAgICAgZm9yIChsZXQgaiA9IDA7IGogPCBjaGlsZFRhc2tJZEluZGV4ZXMubGVuZ3RoOyBqKyspIHtcbiAgICAgICAgICBjb25zdCBvbGRJbmRleCA9IGNoaWxkVGFza0lkSW5kZXhlc1tqXTtcbiAgICAgICAgICBpZiAodG8gPT09IG9sZEluZGV4KSB7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAoZnJvbSA9PT0gb2xkSW5kZXgpIHtcbiAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgIH1cbiAgICAgICAgICBuZXdBLnB1c2goYVtvbGRJbmRleF0pO1xuICAgICAgICB9XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3QS5wdXNoKGFbaV0pO1xuICAgICAgICBuZXdBLnB1c2gobW92ZWRWYWx1ZSk7XG4gICAgICAgIGZvciAobGV0IGogPSAwOyBqIDwgY2hpbGRUYXNrSWRJbmRleGVzLmxlbmd0aDsgaisrKSB7XG4gICAgICAgICAgY29uc3Qgb2xkSW5kZXggPSBjaGlsZFRhc2tJZEluZGV4ZXNbal07XG4gICAgICAgICAgaWYgKHRvID09PSBvbGRJbmRleCkge1xuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKGZyb20gPT09IG9sZEluZGV4KSB7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG4gICAgICAgICAgbmV3QS5wdXNoKGFbb2xkSW5kZXhdKTtcbiAgICAgICAgfVxuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoY2hpbGRUYXNrSWRJbmRleGVzLmluY2x1ZGVzKGkpKSB7XG4gICAgICBjb250aW51ZTtcbiAgICB9XG5cbiAgICBpZiAoaSA9PT0gZnJvbSkge1xuICAgICAgY29udGludWU7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2cobmV3QSwgJyBuZXdBIGFmdGVyIGNoaWxkVGFza0lkSW5kZXhlcy5pbmNsdWRlcyhpKScpO1xuXG4gICAgaWYgKGkgIT09IGZyb20pIHtcbiAgICAgIG5ld0EucHVzaChhW2ldKTtcbiAgICB9XG4gICAgY29uc29sZS5sb2cobmV3QSwgJyBuZXdBIGxhc3QgcHVzaCcpO1xuICB9XG5cbiAgcmV0dXJuIG5ld0E7XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlRGF0YVRvRGlzcGxheVVJID0gPFQ+KFxuICBkYXRhOiBUW10sXG4gIHNldERhdGE6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPFRbXT4+LFxuICBkYXRhSW5kZXhUb0Rpc3BsYXlBcnJheTogbnVtYmVyW11cbikgPT4ge1xuICAvLyByZW9yZGVyIGRhdGEgaW5kaWNlcyB0byBkaXNwbGF5VUkgb3JkZXJcbiAgY29uc3QgbmV3RGF0YTogVFtdID0gW107XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBkYXRhSW5kZXhUb0Rpc3BsYXlBcnJheS5sZW5ndGg7IGkrKykge1xuICAgIGNvbnN0IG9sZEluZGV4ID0gZGF0YUluZGV4VG9EaXNwbGF5QXJyYXlbaV07XG4gICAgaWYgKG9sZEluZGV4ID4gLTEpIHtcbiAgICAgIG5ld0RhdGEucHVzaChkYXRhW29sZEluZGV4XSk7XG4gICAgfVxuICB9XG4gIHNldERhdGEobmV3RGF0YSk7XG59O1xuXG5leHBvcnQgY29uc3Qgc29ydEJ5U3RhdHVzID0gPFQ+KGFBcnJheTogVFtdLCBzdGF0dXNBcnJheTogVGFza1N0YXR1c1tdKSA9PiB7XG4gIGNvbnN0IHRvRG9BcnJheTogVFtdID0gW107XG4gIGNvbnN0IGRvaW5nQXJyYXk6IFRbXSA9IFtdO1xuICBjb25zdCBkb25lQXJyYXk6IFRbXSA9IFtdO1xuXG4gIGFBcnJheS5mb3JFYWNoKChhLCBpbmRleCkgPT4ge1xuICAgIGNvbnN0IHN0YXR1cyA9IHN0YXR1c0FycmF5W2luZGV4XTtcblxuICAgIGlmIChzdGF0dXMgPT09IFRhc2tTdGF0dXMuVE9ETyB8fCAhc3RhdHVzKSB7XG4gICAgICB0b0RvQXJyYXkucHVzaChhKTtcbiAgICB9IGVsc2UgaWYgKHN0YXR1cyA9PT0gVGFza1N0YXR1cy5ET0lORykge1xuICAgICAgZG9pbmdBcnJheS5wdXNoKGEpO1xuICAgIH0gZWxzZSBpZiAoc3RhdHVzID09PSBUYXNrU3RhdHVzLkRPTkUpIHtcbiAgICAgIGRvbmVBcnJheS5wdXNoKGEpO1xuICAgIH1cbiAgfSk7XG5cbiAgY29uc3QgbmV3QXJyYXk6IFRbXSA9IHRvRG9BcnJheS5jb25jYXQoZG9pbmdBcnJheSkuY29uY2F0KGRvbmVBcnJheSk7XG5cbiAgcmV0dXJuIG5ld0FycmF5O1xufTtcblxuZXhwb3J0IGNvbnN0IGdldERpc3BsYXlVSUZvcldlYiA9IChcbiAgdGFza1BsdXNlczogVGFza1BsdXNUeXBlW10sXG4gIHN0YXR1c0FycmF5OiBUYXNrU3RhdHVzW10sXG4gIHR5cGU6IFRhc2tTdWJUeXBlLFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IHNvcnRlZE9yZGVyOiBUYXNrU3RhdHVzW10gPSBbXTtcbiAgY29uc3QgdG9Eb0FycmF5OiBUYXNrUGx1c1R5cGVbXSA9IFtdO1xuICBjb25zdCBkb2luZ0FycmF5OiBUYXNrUGx1c1R5cGVbXSA9IFtdO1xuICBjb25zdCBkb25lQXJyYXk6IFRhc2tQbHVzVHlwZVtdID0gW107XG5cbiAgY29uc3QgaW5kZXhUb0RvV2l0aFN0YXR1c0FycmF5OiBudW1iZXJbXSA9IFtdO1xuICBjb25zdCBpbmRleERvaW5nV2l0aFN0YXR1c0FycmF5OiBudW1iZXJbXSA9IFtdO1xuICBjb25zdCBpbmRleERvbmVXaXRoU3RhdHVzQXJyYXk6IG51bWJlcltdID0gW107XG5cbiAgdGFza1BsdXNlcy5mb3JFYWNoKCh0YXNrUGx1cywgaW5kZXgpID0+IHtcbiAgICBjb25zdCBzdGF0dXMgPSBzdGF0dXNBcnJheVtpbmRleF07XG5cbiAgICBpZiAoc3RhdHVzID09PSBUYXNrU3RhdHVzLlRPRE8gfHwgIXN0YXR1cykge1xuICAgICAgY29uc3QgZm91bmQgPSBzb3J0ZWRPcmRlci5maW5kKChpKSA9PiBpID09PSBUYXNrU3RhdHVzLlRPRE8pO1xuICAgICAgaWYgKCFmb3VuZCkge1xuICAgICAgICBzb3J0ZWRPcmRlci5wdXNoKFRhc2tTdGF0dXMuVE9ETyk7XG4gICAgICAgIHRvRG9BcnJheS5wdXNoKHsgaWQ6IFRhc2tTdGF0dXMuVE9ETywgdHlwZSwgdXNlcklkLCBub3RlczogJ1RvIERvJyB9KTtcbiAgICAgICAgdG9Eb0FycmF5LnB1c2godGFza1BsdXMpO1xuICAgICAgICBpbmRleFRvRG9XaXRoU3RhdHVzQXJyYXkucHVzaCgtMSk7XG4gICAgICAgIGluZGV4VG9Eb1dpdGhTdGF0dXNBcnJheS5wdXNoKGluZGV4KTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHRvRG9BcnJheS5wdXNoKHRhc2tQbHVzKTtcbiAgICAgICAgaW5kZXhUb0RvV2l0aFN0YXR1c0FycmF5LnB1c2goaW5kZXgpO1xuICAgICAgfVxuICAgIH0gZWxzZSBpZiAoc3RhdHVzID09PSBUYXNrU3RhdHVzLkRPSU5HKSB7XG4gICAgICBjb25zdCBmb3VuZCA9IHNvcnRlZE9yZGVyLmZpbmQoKGkpID0+IGkgPT09IFRhc2tTdGF0dXMuRE9JTkcpO1xuXG4gICAgICBpZiAoIWZvdW5kKSB7XG4gICAgICAgIHNvcnRlZE9yZGVyLnB1c2goVGFza1N0YXR1cy5ET0lORyk7XG4gICAgICAgIGRvaW5nQXJyYXkucHVzaCh7IGlkOiBUYXNrU3RhdHVzLkRPSU5HLCB0eXBlLCB1c2VySWQsIG5vdGVzOiAnRG9pbmcnIH0pO1xuICAgICAgICBkb2luZ0FycmF5LnB1c2godGFza1BsdXMpO1xuICAgICAgICBpbmRleERvaW5nV2l0aFN0YXR1c0FycmF5LnB1c2goLTEpO1xuICAgICAgICBpbmRleERvaW5nV2l0aFN0YXR1c0FycmF5LnB1c2goaW5kZXgpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgZG9pbmdBcnJheS5wdXNoKHRhc2tQbHVzKTtcbiAgICAgICAgaW5kZXhEb2luZ1dpdGhTdGF0dXNBcnJheS5wdXNoKGluZGV4KTtcbiAgICAgIH1cbiAgICB9IGVsc2UgaWYgKHN0YXR1cyA9PT0gVGFza1N0YXR1cy5ET05FKSB7XG4gICAgICBjb25zdCBmb3VuZCA9IHNvcnRlZE9yZGVyLmZpbmQoKGkpID0+IGkgPT09IFRhc2tTdGF0dXMuRE9ORSk7XG5cbiAgICAgIGlmICghZm91bmQpIHtcbiAgICAgICAgc29ydGVkT3JkZXIucHVzaChUYXNrU3RhdHVzLkRPTkUpO1xuICAgICAgICBkb25lQXJyYXkucHVzaCh7IGlkOiBUYXNrU3RhdHVzLkRPTkUsIHR5cGUsIHVzZXJJZCwgbm90ZXM6ICdEb25lJyB9KTtcbiAgICAgICAgZG9uZUFycmF5LnB1c2godGFza1BsdXMpO1xuICAgICAgICBpbmRleERvbmVXaXRoU3RhdHVzQXJyYXkucHVzaCgtMSk7XG4gICAgICAgIGluZGV4RG9uZVdpdGhTdGF0dXNBcnJheS5wdXNoKGluZGV4KTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGRvbmVBcnJheS5wdXNoKHRhc2tQbHVzKTtcbiAgICAgICAgaW5kZXhEb25lV2l0aFN0YXR1c0FycmF5LnB1c2goaW5kZXgpO1xuICAgICAgfVxuICAgIH1cbiAgfSk7XG5cbiAgaWYgKFxuICAgIHRvRG9BcnJheT8ubGVuZ3RoID4gMCAmJlxuICAgICEoZG9pbmdBcnJheT8ubGVuZ3RoID4gMCkgJiZcbiAgICAhKGRvbmVBcnJheT8ubGVuZ3RoID4gMClcbiAgKSB7XG4gICAgY29uc3QgbmV3QXJyYXk6IERpc3BsYXlVSVR5cGVbXSA9IHRvRG9BcnJheVxuICAgICAgLmNvbmNhdChbeyBpZDogVGFza1N0YXR1cy5ET0lORywgdHlwZSwgdXNlcklkLCBub3RlczogJ0RvaW5nJyB9XSlcbiAgICAgIC5jb25jYXQoW3sgaWQ6IFRhc2tTdGF0dXMuRE9ORSwgdHlwZSwgdXNlcklkLCBub3RlczogJ0RvbmUnIH1dKTtcbiAgICBjb25zdCBuZXdJbmRleEFycmF5OiBudW1iZXJbXSA9IGluZGV4VG9Eb1dpdGhTdGF0dXNBcnJheVxuICAgICAgLmNvbmNhdChbLTFdKVxuICAgICAgLmNvbmNhdChbLTFdKTtcbiAgICByZXR1cm4ge1xuICAgICAgZGlzcGxheVVJQXJyYXk6IG5ld0FycmF5LFxuICAgICAgZGF0YUluZGV4VG9EaXNwbGF5QXJyYXk6IG5ld0luZGV4QXJyYXksXG4gICAgfTtcbiAgfSBlbHNlIGlmIChcbiAgICB0b0RvQXJyYXk/Lmxlbmd0aCA+IDAgJiZcbiAgICAhKGRvaW5nQXJyYXk/Lmxlbmd0aCA+IDApICYmXG4gICAgZG9uZUFycmF5Py5sZW5ndGggPiAwXG4gICkge1xuICAgIGNvbnN0IG5ld0FycmF5OiBEaXNwbGF5VUlUeXBlW10gPSB0b0RvQXJyYXlcbiAgICAgIC5jb25jYXQoW3sgaWQ6IFRhc2tTdGF0dXMuRE9JTkcsIHR5cGUsIHVzZXJJZCwgbm90ZXM6ICdEb2luZycgfV0pXG4gICAgICAuY29uY2F0KGRvbmVBcnJheSk7XG4gICAgY29uc3QgbmV3SW5kZXhBcnJheTogbnVtYmVyW10gPSBpbmRleFRvRG9XaXRoU3RhdHVzQXJyYXlcbiAgICAgIC5jb25jYXQoWy0xXSlcbiAgICAgIC5jb25jYXQoaW5kZXhEb25lV2l0aFN0YXR1c0FycmF5KTtcblxuICAgIHJldHVybiB7XG4gICAgICBkaXNwbGF5VUlBcnJheTogbmV3QXJyYXksXG4gICAgICBkYXRhSW5kZXhUb0Rpc3BsYXlBcnJheTogbmV3SW5kZXhBcnJheSxcbiAgICB9O1xuICB9IGVsc2UgaWYgKFxuICAgIHRvRG9BcnJheT8ubGVuZ3RoID4gMCAmJlxuICAgIGRvaW5nQXJyYXk/Lmxlbmd0aCA+IDAgJiZcbiAgICAhKGRvbmVBcnJheT8ubGVuZ3RoID4gMClcbiAgKSB7XG4gICAgY29uc3QgbmV3QXJyYXk6IERpc3BsYXlVSVR5cGVbXSA9IHRvRG9BcnJheVxuICAgICAgLmNvbmNhdChkb2luZ0FycmF5KVxuICAgICAgLmNvbmNhdChbeyBpZDogVGFza1N0YXR1cy5ET05FLCB0eXBlLCB1c2VySWQsIG5vdGVzOiAnRG9uZScgfV0pO1xuICAgIGNvbnN0IG5ld0luZGV4QXJyYXk6IG51bWJlcltdID0gaW5kZXhUb0RvV2l0aFN0YXR1c0FycmF5XG4gICAgICAuY29uY2F0KGluZGV4RG9pbmdXaXRoU3RhdHVzQXJyYXkpXG4gICAgICAuY29uY2F0KFstMV0pO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIGRpc3BsYXlVSUFycmF5OiBuZXdBcnJheSxcbiAgICAgIGRhdGFJbmRleFRvRGlzcGxheUFycmF5OiBuZXdJbmRleEFycmF5LFxuICAgIH07XG4gIH0gZWxzZSBpZiAoXG4gICAgISh0b0RvQXJyYXk/Lmxlbmd0aCA+IDApICYmXG4gICAgZG9pbmdBcnJheT8ubGVuZ3RoID4gMCAmJlxuICAgICEoZG9uZUFycmF5Py5sZW5ndGggPiAwKVxuICApIHtcbiAgICBjb25zdCBuZXdBcnJheTogRGlzcGxheVVJVHlwZVtdID0gW1xuICAgICAgeyBpZDogVGFza1N0YXR1cy5UT0RPLCB0eXBlLCB1c2VySWQsIG5vdGVzOiAnVG8gRG8nIH0gYXMgRGlzcGxheVVJVHlwZSxcbiAgICBdXG4gICAgICAuY29uY2F0KGRvaW5nQXJyYXkpXG4gICAgICAuY29uY2F0KFt7IGlkOiBUYXNrU3RhdHVzLkRPTkUsIHR5cGUsIHVzZXJJZCwgbm90ZXM6ICdEb25lJyB9XSk7XG4gICAgY29uc3QgbmV3SW5kZXhBcnJheTogbnVtYmVyW10gPSBbLTFdXG4gICAgICAuY29uY2F0KGluZGV4RG9pbmdXaXRoU3RhdHVzQXJyYXkpXG4gICAgICAuY29uY2F0KFstMV0pO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIGRpc3BsYXlVSUFycmF5OiBuZXdBcnJheSxcbiAgICAgIGRhdGFJbmRleFRvRGlzcGxheUFycmF5OiBuZXdJbmRleEFycmF5LFxuICAgIH07XG4gIH0gZWxzZSBpZiAoXG4gICAgISh0b0RvQXJyYXk/Lmxlbmd0aCA+IDApICYmXG4gICAgIShkb2luZ0FycmF5Py5sZW5ndGggPiAwKSAmJlxuICAgIGRvbmVBcnJheT8ubGVuZ3RoID4gMFxuICApIHtcbiAgICBjb25zdCBuZXdBcnJheTogRGlzcGxheVVJVHlwZVtdID0gW1xuICAgICAgeyBpZDogVGFza1N0YXR1cy5UT0RPLCB0eXBlLCB1c2VySWQsIG5vdGVzOiAnVG8gRG8nIH0gYXMgRGlzcGxheVVJVHlwZSxcbiAgICBdXG4gICAgICAuY29uY2F0KFt7IGlkOiBUYXNrU3RhdHVzLkRPSU5HLCB0eXBlLCB1c2VySWQsIG5vdGVzOiAnRG9pbmcnIH1dKVxuICAgICAgLmNvbmNhdChkb25lQXJyYXkpO1xuICAgIGNvbnN0IG5ld0luZGV4QXJyYXk6IG51bWJlcltdID0gWy0xXVxuICAgICAgLmNvbmNhdChbLTFdKVxuICAgICAgLmNvbmNhdChpbmRleERvbmVXaXRoU3RhdHVzQXJyYXkpO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIGRpc3BsYXlVSUFycmF5OiBuZXdBcnJheSxcbiAgICAgIGRhdGFJbmRleFRvRGlzcGxheUFycmF5OiBuZXdJbmRleEFycmF5LFxuICAgIH07XG4gIH0gZWxzZSBpZiAoXG4gICAgISh0b0RvQXJyYXk/Lmxlbmd0aCA+IDApICYmXG4gICAgZG9pbmdBcnJheT8ubGVuZ3RoID4gMCAmJlxuICAgIGRvbmVBcnJheT8ubGVuZ3RoID4gMFxuICApIHtcbiAgICBjb25zdCBuZXdBcnJheTogRGlzcGxheVVJVHlwZVtdID0gW1xuICAgICAgeyBpZDogVGFza1N0YXR1cy5UT0RPLCB0eXBlLCB1c2VySWQsIG5vdGVzOiAnVG8gRG8nIH0gYXMgRGlzcGxheVVJVHlwZSxcbiAgICBdXG4gICAgICAuY29uY2F0KGRvaW5nQXJyYXkpXG4gICAgICAuY29uY2F0KGRvbmVBcnJheSk7XG4gICAgY29uc3QgbmV3SW5kZXhBcnJheTogbnVtYmVyW10gPSBbLTFdXG4gICAgICAuY29uY2F0KGluZGV4RG9pbmdXaXRoU3RhdHVzQXJyYXkpXG4gICAgICAuY29uY2F0KGluZGV4RG9uZVdpdGhTdGF0dXNBcnJheSk7XG5cbiAgICByZXR1cm4ge1xuICAgICAgZGlzcGxheVVJQXJyYXk6IG5ld0FycmF5LFxuICAgICAgZGF0YUluZGV4VG9EaXNwbGF5QXJyYXk6IG5ld0luZGV4QXJyYXksXG4gICAgfTtcbiAgfSBlbHNlIGlmIChcbiAgICAhKHRvRG9BcnJheT8ubGVuZ3RoID4gMCkgJiZcbiAgICAhKGRvaW5nQXJyYXk/Lmxlbmd0aCA+IDApICYmXG4gICAgIShkb25lQXJyYXk/Lmxlbmd0aCA+IDApXG4gICkge1xuICAgIGNvbnN0IG5ld0FycmF5OiBEaXNwbGF5VUlUeXBlW10gPSBbXG4gICAgICB7IGlkOiBUYXNrU3RhdHVzLlRPRE8sIHR5cGUsIHVzZXJJZCwgbm90ZXM6ICdUbyBEbycgfSBhcyBEaXNwbGF5VUlUeXBlLFxuICAgIF1cbiAgICAgIC5jb25jYXQoW3sgaWQ6IFRhc2tTdGF0dXMuRE9JTkcsIHR5cGUsIHVzZXJJZCwgbm90ZXM6ICdEb2luZycgfV0pXG4gICAgICAuY29uY2F0KFt7IGlkOiBUYXNrU3RhdHVzLkRPTkUsIHR5cGUsIHVzZXJJZCwgbm90ZXM6ICdEb25lJyB9XSk7XG4gICAgY29uc3QgbmV3SW5kZXhBcnJheTogbnVtYmVyW10gPSBbLTFdLmNvbmNhdChbLTFdKS5jb25jYXQoWy0xXSk7XG5cbiAgICByZXR1cm4ge1xuICAgICAgZGlzcGxheVVJQXJyYXk6IG5ld0FycmF5LFxuICAgICAgZGF0YUluZGV4VG9EaXNwbGF5QXJyYXk6IG5ld0luZGV4QXJyYXksXG4gICAgfTtcbiAgfVxuXG4gIGNvbnN0IG5ld0FycmF5OiBEaXNwbGF5VUlUeXBlW10gPSB0b0RvQXJyYXlcbiAgICAuY29uY2F0KGRvaW5nQXJyYXkpXG4gICAgLmNvbmNhdChkb25lQXJyYXkpO1xuICBjb25zdCBuZXdJbmRleEFycmF5OiBudW1iZXJbXSA9IGluZGV4VG9Eb1dpdGhTdGF0dXNBcnJheVxuICAgIC5jb25jYXQoaW5kZXhEb2luZ1dpdGhTdGF0dXNBcnJheSlcbiAgICAuY29uY2F0KGluZGV4RG9uZVdpdGhTdGF0dXNBcnJheSk7XG5cbiAgcmV0dXJuIHtcbiAgICBkaXNwbGF5VUlBcnJheTogbmV3QXJyYXksXG4gICAgZGF0YUluZGV4VG9EaXNwbGF5QXJyYXk6IG5ld0luZGV4QXJyYXksXG4gIH07XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0SW5kZXhVcGRhdGVzRnJvbVVJRm9yV2ViID0gKFxuICByZW9yZGVyZWREaXNwbGF5VUlzOiBEaXNwbGF5VUlUeXBlW10sXG4gIG9sZERpc3BsYXlVSXM6IERpc3BsYXlVSVR5cGVbXSxcbiAgdmFsdWVNb3ZlZDogRGlzcGxheVVJVHlwZVxuKTogeyBmcm9tOiBudW1iZXI7IHRvOiBudW1iZXIgfSA9PiB7XG4gIGNvbnN0IGZpbHRlcmVkUmVvcmRlcmVkRGlzcGxheVVJcyA9IHJlb3JkZXJlZERpc3BsYXlVSXNcbiAgICAuZmlsdGVyKChpKSA9PiBpLm5vdGVzICE9PSBUT0RPKVxuICAgIC5maWx0ZXIoKGkpID0+IGkubm90ZXMgIT09IERPSU5HKVxuICAgIC5maWx0ZXIoKGkpID0+IGkubm90ZXMgIT09IERPTkUpO1xuXG4gIGNvbnN0IGZpbHRlcmVkT2xkRGlzcGxheVVJcyA9IG9sZERpc3BsYXlVSXNcbiAgICAuZmlsdGVyKChpKSA9PiBpLm5vdGVzICE9PSBUT0RPKVxuICAgIC5maWx0ZXIoKGkpID0+IGkubm90ZXMgIT09IERPSU5HKVxuICAgIC5maWx0ZXIoKGkpID0+IGkubm90ZXMgIT09IERPTkUpO1xuXG4gIGNvbnN0IGZyb20gPSBmaWx0ZXJlZE9sZERpc3BsYXlVSXMuZmluZEluZGV4KChpKSA9PiBpLmlkID09PSB2YWx1ZU1vdmVkLmlkKTtcbiAgY29uc3QgdG8gPSBmaWx0ZXJlZFJlb3JkZXJlZERpc3BsYXlVSXMuZmluZEluZGV4KFxuICAgIChpKSA9PiBpLmlkID09PSB2YWx1ZU1vdmVkLmlkXG4gICk7XG5cbiAgcmV0dXJuIHsgZnJvbSwgdG8gfTtcbn07XG5cbmV4cG9ydCBjb25zdCBhZGRUb0RhdGFBcnJheUFmdGVySW5kZXggPSA8VD4oXG4gIGE6IFQsXG4gIGFBcnJheTogVFtdLFxuICBpc0luaXRpYWw6IGJvb2xlYW4sXG4gIGluZGV4PzogbnVtYmVyXG4pID0+IHtcbiAgY29uc29sZS5sb2coaW5kZXgsICcgaW5zaWRlIGluc2lkZSBhZGRUb0RhdGFBcnJheUFmdGVySW5kZXgnKTtcbiAgaWYgKCFpc0luaXRpYWwpIHtcbiAgICBpZiAodHlwZW9mIGluZGV4ICE9PSAnbnVtYmVyJykge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGEsXG4gICAgICAgIGFBcnJheSxcbiAgICAgICAgJ25vIGluZGV4IGV4aXRpbmcgaW5zaWRlIGFkZFRvRGF0YUFycmF5QWZ0ZXJJbmRleCdcbiAgICAgICk7XG4gICAgICByZXR1cm47XG4gICAgfVxuICAgIGNvbnN0IG5ld2FBcnJheSA9IGFBcnJheVxuICAgICAgLnNsaWNlKDAsIGluZGV4ICsgMSlcbiAgICAgIC5jb25jYXQoW2FdKVxuICAgICAgLmNvbmNhdChhQXJyYXkuc2xpY2UoaW5kZXggKyAxKSk7XG5cbiAgICByZXR1cm4gbmV3YUFycmF5O1xuICB9XG5cbiAgcmV0dXJuIFthXTtcbn07XG5cbmV4cG9ydCBjb25zdCBhZGRUb09yZGVyQXJyYXlBZnRlckluZGV4V2l0aE5ld09yZGVyID0gKFxuICBvcmRlckFycmF5OiBudW1iZXJbXSxcbiAgaXNJbml0aWFsOiBib29sZWFuLFxuICBzZXRPcmRlckFycmF5OiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxudW1iZXJbXT4+LFxuICBpbmRleD86IG51bWJlclxuKSA9PiB7XG4gIGlmICghaXNJbml0aWFsKSB7XG4gICAgaWYgKHR5cGVvZiBpbmRleCAhPT0gJ251bWJlcicpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBvcmRlckFycmF5LFxuICAgICAgICAnbm8gaW5kZXggZXhpdGluZyBpbnNpZGUgYWRkVG9PcmRlckFycmF5QWZ0ZXJJbmRleCdcbiAgICAgICk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3Qgc3ViT3JkZXJBcnJheSA9IG9yZGVyQXJyYXkuc2xpY2UoMCwgaW5kZXggKyAxKTtcbiAgICBjb25zdCBzZWNvbmRTdWJPcmRlckFycmF5ID0gb3JkZXJBcnJheS5zbGljZShpbmRleCArIDEpO1xuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCBzZWNvbmRTdWJPcmRlckFycmF5Lmxlbmd0aDsgaSsrKSB7XG4gICAgICBzZWNvbmRTdWJPcmRlckFycmF5W2ldICs9IDE7XG4gICAgfVxuXG4gICAgY29uc3QgbmV3T3JkZXJBcnJheSA9IHN1Yk9yZGVyQXJyYXlcbiAgICAgIC5jb25jYXQoW3N1Yk9yZGVyQXJyYXkubGVuZ3RoXSlcbiAgICAgIC5jb25jYXQoc2Vjb25kU3ViT3JkZXJBcnJheSk7XG5cbiAgICBzZXRPcmRlckFycmF5KG5ld09yZGVyQXJyYXkpO1xuICAgIHJldHVybiBuZXdPcmRlckFycmF5O1xuICB9XG5cbiAgc2V0T3JkZXJBcnJheShbMF0pO1xuICByZXR1cm4gWzBdO1xufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZURhdGFBcnJheSA9IDxUPihcbiAgdDogVCxcbiAgdEFycmF5OiBUW10sXG4gIHNldFRBcnJheTogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248VFtdPj4sXG4gIGluZGV4OiBudW1iZXJcbikgPT4ge1xuICBjb25zb2xlLmxvZyh0QXJyYXksICcgdEFycmF5Jyk7XG4gIGNvbnN0IG5ld1RBcnJheSA9IHRBcnJheVxuICAgIC5zbGljZSgwLCBpbmRleClcbiAgICAuY29uY2F0KFt0XSlcbiAgICAuY29uY2F0KHRBcnJheS5zbGljZShpbmRleCArIDEpKTtcblxuICBzZXRUQXJyYXkobmV3VEFycmF5KTtcbiAgcmV0dXJuIG5ld1RBcnJheTtcbn07XG5cbmV4cG9ydCBjb25zdCByZW1vdmVGcm9tRGF0YUFycmF5ID0gPFQ+KFxuICBpbmRleDogbnVtYmVyLFxuICBkYXRhQXJyYXk6IFRbXSxcbiAgc2V0RGF0YUFycmF5OiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxUW10+PlxuKSA9PiB7XG4gIGNvbnN0IG5ld0RhdGFBcnJheSA9IFtcbiAgICAuLi5kYXRhQXJyYXkuc2xpY2UoMCwgaW5kZXgpLFxuICAgIC4uLmRhdGFBcnJheS5zbGljZShpbmRleCArIDEpLFxuICBdO1xuXG4gIHNldERhdGFBcnJheShuZXdEYXRhQXJyYXkpO1xuICByZXR1cm4gbmV3RGF0YUFycmF5O1xufTtcbi8vIGV4cG9ydCBjb25zdCBjbG9zZVJlYWxtID0gKCkgPT4gLy8gcmVhbG0uY2xvc2UoKVxuXG5leHBvcnQgY29uc3Qgc29ydFRhc2tzQnlQYXJlbnQgPSAoXG4gIHBhcmVudElkQXJyYXk6IHN0cmluZ1tdLFxuICB0YXNrUGx1c2VzOiBUYXNrUGx1c1R5cGVbXVxuKSA9PiB7XG4gIGxldCBkb25lU29ydGVkVGFza1BsdXNlczogVGFza1BsdXNUeXBlW10gPSBbXTtcblxuICBsZXQgc29ydGVkVGFza1BsdXNlczogVGFza1BsdXNUeXBlW10gPSBbXTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHRhc2tQbHVzZXMubGVuZ3RoOyBpKyspIHtcbiAgICBjb25zdCB2YWx1ZSA9IGRvbmVTb3J0ZWRUYXNrUGx1c2VzLmZpbmQoKHUpID0+IHU/LmlkID09PSB0YXNrUGx1c2VzW2ldPy5pZCk7XG5cbiAgICBpZiAoIXZhbHVlKSB7XG4gICAgICBzb3J0ZWRUYXNrUGx1c2VzLnB1c2godGFza1BsdXNlc1tpXSk7XG4gICAgICBkb25lU29ydGVkVGFza1BsdXNlcy5wdXNoKHRhc2tQbHVzZXNbaV0pO1xuXG4gICAgICBmb3IgKGxldCBqID0gMDsgaiA8IHRhc2tQbHVzZXMubGVuZ3RoOyBqKyspIHtcbiAgICAgICAgaWYgKHRhc2tQbHVzZXNbaV0/LmlkID09PSBwYXJlbnRJZEFycmF5W2pdKSB7XG4gICAgICAgICAgc29ydGVkVGFza1BsdXNlcy5wdXNoKHRhc2tQbHVzZXNbal0pO1xuICAgICAgICAgIGRvbmVTb3J0ZWRUYXNrUGx1c2VzLnB1c2godGFza1BsdXNlc1tqXSk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICByZXR1cm4ge1xuICAgIHNvcnRlZFRhc2tQbHVzZXMsXG4gIH07XG59O1xuIl19