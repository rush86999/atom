import { Dispatch, SetStateAction } from 'react';

export const updateCharacteristicInSenderCharacteristics = (
  index: number,
  senderCharacteristic: string,
  senderCharacteristics: string[],
  setSenderCharacteristics: Dispatch<SetStateAction<string[]>>,
  setParentSenderCharacteristics: Dispatch<SetStateAction<string[]>>
) => {
  const newSenderCharacteristics = senderCharacteristics
    .slice(0, index)
    .concat([senderCharacteristic])
    .concat(senderCharacteristics.slice(index + 1));

  setSenderCharacteristics(newSenderCharacteristics);
  setParentSenderCharacteristics(newSenderCharacteristics);
};

export const addCharacteristicToSenderCharacteristics = (
  senderCharacteristic: string,
  senderCharacteristics: string[],
  setSenderCharacteristics: Dispatch<SetStateAction<string[]>>,
  setParentSenderCharacteristics: Dispatch<SetStateAction<string[]>>
) => {
  const newSenderCharacteristics = senderCharacteristics.concat([
    senderCharacteristic,
  ]);
  setSenderCharacteristics(newSenderCharacteristics);
  setParentSenderCharacteristics(newSenderCharacteristics);
};

export const removeCharacteristicFromSenderCharacteristics = (
  index: number,
  senderCharacteristics: string[],
  setSenderCharacteristics: Dispatch<SetStateAction<string[]>>,
  setParentSenderCharacteristics: Dispatch<SetStateAction<string[]>>
) => {
  const newSenderCharacteristics = senderCharacteristics
    .slice(0, index)
    .concat(senderCharacteristics.slice(index + 1));

  setSenderCharacteristics(newSenderCharacteristics);
  setParentSenderCharacteristics(newSenderCharacteristics);
};

export const updateCharacteristicInReceiverCharacteristics = (
  index: number,
  receiverCharacteristic: string,
  receiverCharacteristics: string[],
  setReceiverCharacteristics: Dispatch<SetStateAction<string[]>>,
  setParentReceiverCharacteristics: Dispatch<SetStateAction<string[]>>
) => {
  const newReceiverCharacteristics = receiverCharacteristics
    .slice(0, index)
    .concat([receiverCharacteristic])
    .concat(receiverCharacteristics.slice(index + 1));

  setReceiverCharacteristics(newReceiverCharacteristics);
  setParentReceiverCharacteristics(newReceiverCharacteristics);
};

export const addCharacteristicToReceiverCharacteristics = (
  receiverCharacteristic: string,
  receiverCharacteristics: string[],
  setReceiverCharacteristics: Dispatch<SetStateAction<string[]>>,
  setParentReceiverCharacteristics: Dispatch<SetStateAction<string[]>>
) => {
  const newReceiverCharacteristics = receiverCharacteristics.concat([
    receiverCharacteristic,
  ]);
  setReceiverCharacteristics(newReceiverCharacteristics);
  setParentReceiverCharacteristics(newReceiverCharacteristics);
};

export const removeCharacteristicFromReceiverCharacteristics = (
  index: number,
  receiverCharacteristics: string[],
  setReceiverCharacteristics: Dispatch<SetStateAction<string[]>>,
  setParentReceiverCharacteristics: Dispatch<SetStateAction<string[]>>
) => {
  const newReceiverCharacteristics = receiverCharacteristics
    .slice(0, index)
    .concat(receiverCharacteristics.slice(index + 1));

  setReceiverCharacteristics(newReceiverCharacteristics);
  setParentReceiverCharacteristics(newReceiverCharacteristics);
};

export const updateGoalInSenderGoals = (
  index: number,
  senderGoal: string,
  senderGoals: string[],
  setSenderGoals: Dispatch<SetStateAction<string[]>>,
  setParentSenderGoals: Dispatch<SetStateAction<string[]>>
) => {
  const newSenderGoals = senderGoals
    .slice(0, index)
    .concat([senderGoal])
    .concat(senderGoals.slice(index + 1));

  setSenderGoals(newSenderGoals);
  setParentSenderGoals(newSenderGoals);
};

export const addGoalToSenderGoals = (
  senderGoal: string,
  senderGoals: string[],
  setSenderGoals: Dispatch<SetStateAction<string[]>>,
  setParentSenderGoals: Dispatch<SetStateAction<string[]>>
) => {
  const newSenderGoals = senderGoals.concat([senderGoal]);
  setSenderGoals(newSenderGoals);
  setParentSenderGoals(newSenderGoals);
};

export const removeGoalFromSenderGoals = (
  index: number,
  senderGoals: string[],
  setSenderGoals: Dispatch<SetStateAction<string[]>>,
  setParentSenderGoals: Dispatch<SetStateAction<string[]>>
) => {
  const newSenderGoals = senderGoals
    .slice(0, index)
    .concat(senderGoals.slice(index + 1));

  setSenderGoals(newSenderGoals);
  setParentSenderGoals(newSenderGoals);
};

export const updateGoalInReceiverGoals = (
  index: number,
  receiverGoal: string,
  receiverGoals: string[],
  setReceiverGoals: Dispatch<SetStateAction<string[]>>,
  setParentReceiverGoals: Dispatch<SetStateAction<string[]>>
) => {
  const newReceiverGoals = receiverGoals
    .slice(0, index)
    .concat([receiverGoal])
    .concat(receiverGoals.slice(index + 1));

  setReceiverGoals(newReceiverGoals);
  setParentReceiverGoals(newReceiverGoals);
};

export const addGoalToReceiverGoals = (
  receiverGoal: string,
  receiverGoals: string[],
  setReceiverGoals: Dispatch<SetStateAction<string[]>>,
  setParentReceiverGoals: Dispatch<SetStateAction<string[]>>
) => {
  const newReceiverGoals = receiverGoals.concat([receiverGoal]);
  setReceiverGoals(newReceiverGoals);
  setParentReceiverGoals(newReceiverGoals);
};

export const removeGoalFromReceiverGoals = (
  index: number,
  receiverGoals: string[],
  setReceiverGoals: Dispatch<SetStateAction<string[]>>,
  setParentReceiverGoals: Dispatch<SetStateAction<string[]>>
) => {
  const newReceiverGoals = receiverGoals
    .slice(0, index)
    .concat(receiverGoals.slice(index + 1));

  setReceiverGoals(newReceiverGoals);
  setParentReceiverGoals(newReceiverGoals);
};
