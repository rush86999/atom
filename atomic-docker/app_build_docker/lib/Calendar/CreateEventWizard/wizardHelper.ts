import { Dispatch, SetStateAction } from 'react';
import { Person, phoneNumber, imAddress, email } from '@lib/Calendar/types';
import { SelectedContactType } from '@pages/Calendar/CreateEventWizard/CreateEventAttendees';
import _ from 'lodash';
import { v4 as uuid } from 'uuid';
import { CategoryType } from '@lib/dataTypes/CategoryType';
import { OptionType } from '../../../pages/Calendar/CreateEventWizard/CreateEventAddCategories';

export const removeAttendeeFromAttendees = (
  a: Person[],
  setA: Dispatch<SetStateAction<Person[]>>,
  index: number,
  setParentA: Dispatch<SetStateAction<Person[]>>
) => {
  const newA = a.slice(0, index).concat(a.slice(index + 1));
  setA(newA);
  setParentA(newA);
};

export const addAttendeeToAttendees = (
  a: Person[],
  p: Person,
  setA: Dispatch<SetStateAction<Person[]>>,
  setParentA: Dispatch<SetStateAction<Person[]>>
) => {
  const newA = a.concat([p]);
  setA(newA);
  setParentA(newA);
};

export const addContactToAttendees = (
  c: SelectedContactType,
  attendees: Person[],
  setA: Dispatch<SetStateAction<Person[]>>,
  setParentA: Dispatch<SetStateAction<Person[]>>
) => {
  const formattedC: Person = {
    id: c?.id,
    name: c?.name,
    emails: c?.emails.map((e) => ({
      primary: e?.primary,
      value: e?.value,
      type: e?.type,
      displayName: e?.displayName,
    })),
    phoneNumbers: c?.phoneNumbers as phoneNumber[],
    imAddresses: c?.imAddresses as imAddress[],
  };

  const newAttendees = attendees.concat([formattedC]);
  setA(newAttendees);
  setParentA(newAttendees);
};

export const addEntryToManualEntries = (
  a: Person[],
  p: Person,
  setA: Dispatch<SetStateAction<Person[]>>,
  setParentA: Dispatch<SetStateAction<Person[]>>
) => {
  const newA = a.concat([p]);
  setA(newA);
  setParentA(newA);
};

export const removeEntryFromManualEntries = (
  manualEntries: Person[],
  setManualEntries: Dispatch<SetStateAction<Person[]>>,
  attendees: Person[],
  setAttendees: Dispatch<SetStateAction<Person[]>>,
  setParentA: Dispatch<SetStateAction<Person[]>>,
  index: number,
  parentIndex: number
) => {
  const newEntries = manualEntries
    .slice(0, index)
    .concat(manualEntries.slice(index + 1));
  setManualEntries(newEntries);
  const newAttendees = attendees
    .slice(0, parentIndex)
    .concat(attendees.slice(parentIndex + 1));
  setAttendees(newAttendees);
  setParentA(newAttendees);
};

export const removeContactFromAttendee = (
  c: SelectedContactType,
  attendees: Person[],
  setAttendees: Dispatch<SetStateAction<Person[]>>,
  setParentA: Dispatch<SetStateAction<Person[]>>
) => {
  const foundIndex = attendees.findIndex((a) => a?.id === c?.id);

  if (foundIndex > -1) {
    const newAttendees = attendees
      .slice(0, foundIndex)
      .concat(attendees.slice(foundIndex + 1));

    setAttendees(newAttendees);
    setParentA(newAttendees);
  }
};

export const updateContactSelection = (
  value: boolean,
  selectedCo: SelectedContactType,
  a: SelectedContactType[],
  setA: Dispatch<SetStateAction<SelectedContactType[]>>,
  index: number
) => {
  const newA = _.cloneDeep(
    a
      .slice(0, index)
      .concat([{ ...selectedCo, selected: value }])
      .concat(a.slice(index + 1))
  );
  setA(newA);
};

export const addSelectedContactsToAttendees = (
  cc: SelectedContactType[],
  setCC: Dispatch<SetStateAction<SelectedContactType[]>>,
  at: Person[],
  setAt: Dispatch<SetStateAction<Person[]>>,
  setParentA: Dispatch<SetStateAction<Person[]>>
) => {
  const selectedContacts = cc.filter((c) => c?.selected === true);
  const unselectedContacts = cc.filter((c) => c?.selected === false);

  const removedUnselectedAt = _.differenceBy(
    at,
    unselectedContacts,
    (a) => a?.id
  );

  const formattedContacts: Person[] = selectedContacts.map((c) => ({
    id: c?.id,
    name: c?.name,
    emails: c?.emails.map((e) => ({
      primary: e?.primary,
      value: e?.value,
      type: e?.type,
      displayName: e?.displayName,
    })),
    phoneNumbers: c?.phoneNumbers as phoneNumber[],
    imAddresses: c?.imAddresses as imAddress[],
  }));

  const newAt = removedUnselectedAt.concat(formattedContacts);
  setAt(newAt);
  setParentA(newAt);
  setCC(cc.map((e) => ({ ...e, selected: false })));
};

export const addOneToManualEntries = (
  me: Person[],
  setMe: Dispatch<SetStateAction<Person[]>>,
  attendees: Person[],
  setAttendees: Dispatch<SetStateAction<Person[]>>,
  setParentA: Dispatch<SetStateAction<Person[]>>
) => {
  const newValue: Person = {
    id: uuid(),
    emails: [{ primary: false, value: '', type: '', displayName: '' }],
    additionalGuests: 0,
  };

  const newMe = _.uniqWith(me.concat([newValue]), _.isEqual);
  setMe(newMe);
  const newAttendees = _.uniqWith(attendees.concat([newValue]), _.isEqual);
  setAttendees(newAttendees);
  setParentA(newAttendees);
};

export const updateEntryInManualEntries = (
  me: Person[],
  setMe: Dispatch<SetStateAction<Person[]>>,
  index: number,
  attendees: Person[],
  setAttendees: Dispatch<SetStateAction<Person[]>>,
  setParentA: Dispatch<SetStateAction<Person[]>>,
  parentIndex: number,
  emails?: email[],
  displayName?: string,
  additionalGuests?: number
) => {
  const oldDoc = me[index];
  const newDoc: Person = {
    id: oldDoc?.id,
    name:
      displayName ||
      oldDoc?.name ||
      emails?.[0]?.displayName ||
      oldDoc?.emails?.[0]?.displayName,
    emails: emails || oldDoc?.emails,
    additionalGuests: additionalGuests || oldDoc?.additionalGuests,
  };

  const newMe = me
    .slice(0, index)
    .concat([newDoc])
    .concat(me.slice(index + 1));
  setMe(newMe);
  const newAttendees = attendees
    .slice(0, parentIndex)
    .concat([newDoc])
    .concat(attendees.slice(parentIndex + 1));
  setAttendees(newAttendees);
  setParentA(newAttendees);
};

export const addItemToCategories = (
  setTag: Dispatch<SetStateAction<OptionType>>,
  item: CategoryType = null,
  setItem: Dispatch<SetStateAction<CategoryType>>,
  categories: CategoryType[] = [],
  setCategories: Dispatch<SetStateAction<CategoryType[]>>,
  setParentCategories: Dispatch<SetStateAction<CategoryType[]>>
) => {
  const newCategories = _.uniqWith(categories.concat([item]), _.isEqual).filter(
    (e) => e !== null
  );
  setCategories(newCategories);
  setParentCategories(newCategories);
  setTag(undefined);
  setItem(null);
};

export const removeItemFromCategories = (
  categories: CategoryType[],
  setCategories: Dispatch<SetStateAction<CategoryType[]>>,
  setParentCategories: Dispatch<SetStateAction<CategoryType[]>>,
  index: number
) => {
  const newCategories = categories
    .slice(0, index)
    .concat(categories.slice(index + 1));
  setCategories(newCategories);
  setParentCategories(newCategories);
};

export const addItemToAlarms = (
  item: number,
  alarms: number[],
  setAlarms: Dispatch<SetStateAction<number[]>>,
  setParentAlarms: Dispatch<SetStateAction<number[]>>,
  setAlarm: Dispatch<SetStateAction<number>>
) => {
  const newAlarms = _.uniqWith(alarms.concat([item]), _.isEqual);
  setAlarms(newAlarms);
  setParentAlarms(newAlarms);
  setAlarm(0);
};

export const removeItemFromAlarms = (
  index: number,
  alarms: number[],
  setAlarms: Dispatch<SetStateAction<number[]>>,
  setParentAlarms: Dispatch<SetStateAction<number[]>>
) => {
  const newAlarms = alarms.slice(0, index).concat(alarms.slice(index + 1));

  setAlarms(newAlarms);
  setParentAlarms(newAlarms);
};

/** end */
