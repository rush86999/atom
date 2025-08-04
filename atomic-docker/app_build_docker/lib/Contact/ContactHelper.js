"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteContact = exports.updateContact = exports.listUserContactsHelper = exports.searchContactsByName = exports.upsertContact = exports.createContact = exports.addUserContactInfo = exports.listUserContactInfosGivenUserId = exports.addInfoItemToItems = exports.removeInfoItemToItems = exports.updateInfoItemPrimaryValue = exports.updateInfoItemNameValue = exports.updateInfoItemIdValue = exports.updateInfoItemTypeValue = exports.upsertContactInfoItems = exports.deleteContactInfoItems = void 0;
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
const client_1 = require("@apollo/client");
const listContactsByUser_1 = __importDefault(require("@lib/apollo/gql/listContactsByUser"));
const deleteContactById_1 = __importDefault(require("@lib/apollo/gql/deleteContactById"));
const searchContactsByNameQuery_1 = __importDefault(require("@lib/apollo/gql/searchContactsByNameQuery"));
const insertUserContactInfoOne_1 = __importDefault(require("@lib/apollo/gql/insertUserContactInfoOne"));
const listUserContactInfosByUserId_1 = __importDefault(require("@lib/apollo/gql/listUserContactInfosByUserId"));
const lodash_1 = __importDefault(require("lodash"));
const upsertUserContactInfoItems_1 = __importDefault(require("@lib/apollo/gql/upsertUserContactInfoItems"));
const deleteUserContactInfoItems_1 = __importDefault(require("@lib/apollo/gql/deleteUserContactInfoItems"));
const deleteContactInfoItems = async (client, itemIds) => {
    try {
        const deleteContactInfoItems = (await client.mutate({
            mutation: deleteUserContactInfoItems_1.default,
            variables: {
                itemIds,
            },
            fetchPolicy: 'no-cache',
        }))?.data?.User_Contact_Info;
        console.log(deleteContactInfoItems, ' successfully deleted contact info items');
    }
    catch (e) {
        console.log(e, ' unable to delete contact info items');
    }
};
exports.deleteContactInfoItems = deleteContactInfoItems;
const upsertContactInfoItems = async (client, contactInfos) => {
    try {
        const affectedRows = (await client.mutate({
            mutation: upsertUserContactInfoItems_1.default,
            variables: {
                contactInfoItems: contactInfos?.map((c) => lodash_1.default.omit(c, ['__typename'])),
            },
            fetchPolicy: 'no-cache',
            update(cache, { data }) {
                cache.modify({
                    fields: {
                        User_Contact_Info(existingUserContactInfoItems = []) {
                            const newUserContactInfoRefs = data?.insert_User_Contact_Info?.returning?.map((i, inx) => cache.writeFragment({
                                data: data?.insert_User_Contact_Info?.returning[inx],
                                fragment: (0, client_1.gql) `
                        fragment NewUser_Contact_Info on User_Contact_Info {
                          createdDate
                          id
                          name
                          primary
                          type
                          updatedAt
                          userId
                        }
                      `,
                            }));
                            const filteredEvents = existingUserContactInfoItems?.filter((i) => data?.insert_User_Contact_Info?.returning?.find((n) => n?.id === i?.id));
                            return [...filteredEvents, ...newUserContactInfoRefs];
                        },
                    },
                });
            },
        }))?.data?.insert_User_Contact_Info?.affected_rows;
        console.log(affectedRows, ' successfully affectedRows inside upsertContactInfoItems');
    }
    catch (e) {
        console.log(e, ' unable to upsert contact info items');
    }
};
exports.upsertContactInfoItems = upsertContactInfoItems;
const updateInfoItemTypeValue = (infoItem, newItemIndex, newType, oldInfoItems, setInfoItems) => {
    if (!(newItemIndex > -1)) {
        console.log('newItemIndex > -1 is false');
        return;
    }
    const newInfoItem = { ...infoItem, type: newType };
    const newInfoItems = lodash_1.default.cloneDeep(oldInfoItems);
    const updatedNewInfoItems = newInfoItems
        .slice(0, newItemIndex)
        .concat([newInfoItem])
        .concat(newInfoItems.slice(newItemIndex + 1));
    setInfoItems(updatedNewInfoItems);
};
exports.updateInfoItemTypeValue = updateInfoItemTypeValue;
const updateInfoItemIdValue = (infoItem, newItemIndex, newId, oldInfoItems, setInfoItems) => {
    if (!(newItemIndex > -1)) {
        console.log('newItemIndex > -1 is false');
        return;
    }
    const newInfoItem = { ...infoItem, id: newId };
    const newInfoItems = lodash_1.default.cloneDeep(oldInfoItems);
    const updatedNewInfoItems = newInfoItems
        .slice(0, newItemIndex)
        .concat([newInfoItem])
        .concat(newInfoItems.slice(newItemIndex + 1));
    setInfoItems(updatedNewInfoItems);
};
exports.updateInfoItemIdValue = updateInfoItemIdValue;
const updateInfoItemNameValue = (infoItem, newItemIndex, newName, oldInfoItems, setInfoItems) => {
    if (!(newItemIndex > -1)) {
        console.log('newItemIndex > -1 is false');
        return;
    }
    const newInfoItem = { ...infoItem, name: newName };
    const newInfoItems = lodash_1.default.cloneDeep(oldInfoItems);
    const updatedNewInfoItems = newInfoItems
        .slice(0, newItemIndex)
        .concat([newInfoItem])
        .concat(newInfoItems.slice(newItemIndex + 1));
    setInfoItems(updatedNewInfoItems);
};
exports.updateInfoItemNameValue = updateInfoItemNameValue;
const updateInfoItemPrimaryValue = (infoItem, newItemIndex, newPrimary, oldInfoItems, setInfoItems) => {
    if (!(newItemIndex > -1)) {
        console.log('newItemIndex > -1 is false');
        return;
    }
    const newInfoItem = { ...infoItem, primary: newPrimary };
    const foundIndex = oldInfoItems?.findIndex((o) => o?.primary);
    let newInfoItems = [];
    if (foundIndex > -1) {
        const foundOldItem = oldInfoItems?.[foundIndex];
        const oldClonedInfoItems = lodash_1.default.cloneDeep(oldInfoItems);
        const oldItemUpdatedInfoItems = oldClonedInfoItems
            .slice(0, foundIndex)
            .concat([{ ...foundOldItem, primary: !foundOldItem?.primary }])
            .concat(oldClonedInfoItems?.slice(foundIndex + 1));
        newInfoItems = lodash_1.default.cloneDeep(oldItemUpdatedInfoItems);
    }
    else {
        newInfoItems = lodash_1.default.cloneDeep(oldInfoItems);
    }
    const updatedNewInfoItems = newInfoItems
        .slice(0, newItemIndex)
        .concat([newInfoItem])
        .concat(newInfoItems.slice(newItemIndex + 1));
    setInfoItems(updatedNewInfoItems);
};
exports.updateInfoItemPrimaryValue = updateInfoItemPrimaryValue;
const removeInfoItemToItems = (index, infoItems, setInfoItems) => {
    const newInfoItems = infoItems
        .slice(0, index)
        .concat(infoItems.slice(index + 1));
    setInfoItems(newInfoItems);
    return newInfoItems;
};
exports.removeInfoItemToItems = removeInfoItemToItems;
const addInfoItemToItems = (infoItem, infoItems, setInfoItems) => {
    const newInfoItems = [infoItem].concat(infoItems);
    setInfoItems(newInfoItems);
};
exports.addInfoItemToItems = addInfoItemToItems;
const listUserContactInfosGivenUserId = async (client, userId) => {
    try {
        const results = (await client.query({
            query: listUserContactInfosByUserId_1.default,
            variables: {
                userId,
            },
            fetchPolicy: 'no-cache',
        }))?.data?.User_Contact_Info;
        console.log(results, ' results of list user contact infos by userId');
        return results;
    }
    catch (e) {
        console.log(e, ' unable ot list user contact info given userId');
    }
};
exports.listUserContactInfosGivenUserId = listUserContactInfosGivenUserId;
const addUserContactInfo = async (client, contactInfo) => {
    try {
        const variables = {
            contactInfo,
        };
        const contactInfoDoc = (await client.mutate({
            mutation: insertUserContactInfoOne_1.default,
            variables: variables,
        }))?.data?.insert_User_Contact_Info_one;
        console.log(contactInfoDoc, ' successfully added contact info');
        return contactInfoDoc;
    }
    catch (e) {
        console.log(e, ' unable to add user contact info');
    }
};
exports.addUserContactInfo = addUserContactInfo;
const createContact = async (client, userId, imageAvailable, name, firstName, middleName, lastName, maidenName, namePrefix, nameSuffix, nickname, phoneticFirstName, phoneticMiddleName, phoneticLastName, company, jobTitle, department, notes, contactType, emails, phoneNumbers, imAddresses, linkAddresses, app) => {
    try {
        const upsertContactMutation = (0, client_1.gql) `
    mutation InsertContact($contacts: [Contact_insert_input!]!) {
      insert_Contact(
          objects: $contacts,
          on_conflict: {
              constraint: Contact_pkey,
              update_columns: [
                ${name ? 'name,' : ''} 
                ${firstName ? 'firstName,' : ''} 
                ${middleName ? 'middleName,' : ''}
              ${lastName ? 'lastName,' : ''}
              ${maidenName ? 'maidenName,' : ''}
              ${namePrefix ? 'namePrefix,' : ''}
              ${nameSuffix ? 'nameSuffix,' : ''}
              ${nickname ? 'nickname,' : ''}
              ${phoneticFirstName ? 'phoneticFirstName,' : ''}
              ${phoneticMiddleName ? 'phoneticMiddleName,' : ''}
              ${phoneticLastName ? 'phoneticLastName,' : ''}
              ${company ? 'company,' : ''}
              ${jobTitle ? 'jobTitle,' : ''}
              ${department ? 'department,' : ''}
              ${notes ? 'notes,' : ''}
              ${imageAvailable !== undefined ? 'imageAvailable,' : ''}
              ${contactType ? 'contactType,' : ''}
              ${emails?.length > 0 ? 'emails,' : ''}
              ${phoneNumbers?.length > 0 ? 'phoneNumbers,' : ''}
              ${imAddresses?.length > 0 ? 'imAddresses,' : ''}
              ${linkAddresses?.length > 0 ? 'linkAddresses,' : ''}
              ${app ? 'app,' : ''}
              deleted,
              updatedAt,
            ]
          }){
          returning {
            id
          }
        }
      }
    `;
        const id = (0, uuid_1.v4)();
        let valueToUpsert = {
            id,
            userId,
        };
        if (name) {
            valueToUpsert = {
                ...valueToUpsert,
                name,
            };
        }
        if (firstName) {
            valueToUpsert = {
                ...valueToUpsert,
                firstName,
            };
        }
        if (middleName) {
            valueToUpsert = {
                ...valueToUpsert,
                middleName,
            };
        }
        if (lastName) {
            valueToUpsert = {
                ...valueToUpsert,
                lastName,
            };
        }
        if (maidenName) {
            valueToUpsert = {
                ...valueToUpsert,
                maidenName,
            };
        }
        if (namePrefix) {
            valueToUpsert = {
                ...valueToUpsert,
                namePrefix,
            };
        }
        if (nameSuffix) {
            valueToUpsert = {
                ...valueToUpsert,
                nameSuffix,
            };
        }
        if (nickname) {
            valueToUpsert = {
                ...valueToUpsert,
                nickname,
            };
        }
        if (phoneticFirstName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticFirstName,
            };
        }
        if (phoneticMiddleName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticMiddleName,
            };
        }
        if (phoneticLastName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticLastName,
            };
        }
        if (company) {
            valueToUpsert = {
                ...valueToUpsert,
                company,
            };
        }
        if (jobTitle) {
            valueToUpsert = {
                ...valueToUpsert,
                jobTitle,
            };
        }
        if (department) {
            valueToUpsert = {
                ...valueToUpsert,
                department,
            };
        }
        if (notes) {
            valueToUpsert = {
                ...valueToUpsert,
                notes,
            };
        }
        if (imageAvailable !== undefined) {
            valueToUpsert = {
                ...valueToUpsert,
                imageAvailable,
            };
        }
        if (contactType) {
            valueToUpsert = {
                ...valueToUpsert,
                contactType,
            };
        }
        if (emails?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                emails,
            };
        }
        if (phoneNumbers?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneNumbers,
            };
        }
        if (imAddresses?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                imAddresses,
            };
        }
        if (linkAddresses?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                linkAddresses,
            };
        }
        if (app) {
            valueToUpsert = {
                ...valueToUpsert,
                app,
            };
        }
        valueToUpsert = {
            ...valueToUpsert,
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
            createdDate: (0, date_utils_1.dayjs)().toISOString(),
            deleted: false,
        };
        const { data } = await client.mutate({
            mutation: upsertContactMutation,
            variables: {
                contacts: [valueToUpsert],
            },
        });
        return data.insert_Contact.returning[0];
    }
    catch (e) {
        console.log(e, ' unable to create contacts');
    }
};
exports.createContact = createContact;
const upsertContact = async (client, userId, id, imageAvailable, name, firstName, middleName, lastName, maidenName, namePrefix, nameSuffix, nickname, phoneticFirstName, phoneticMiddleName, phoneticLastName, company, jobTitle, department, notes, contactType, emails, phoneNumbers, imAddresses, linkAddresses, app) => {
    try {
        const upsertContactMutation = (0, client_1.gql) `
    mutation InsertContact($contacts: [Contact_insert_input!]!) {
      insert_Contact(
          objects: $contacts,
          on_conflict: {
              constraint: Contact_pkey,
              update_columns: [
                ${name ? 'name,' : ''} 
                ${firstName ? 'firstName,' : ''} 
                ${middleName ? 'middleName,' : ''}
              ${lastName ? 'lastName,' : ''}
              ${maidenName ? 'maidenName,' : ''}
              ${namePrefix ? 'namePrefix,' : ''}
              ${nameSuffix ? 'nameSuffix,' : ''}
              ${nickname ? 'nickname,' : ''}
              ${phoneticFirstName ? 'phoneticFirstName,' : ''}
              ${phoneticMiddleName ? 'phoneticMiddleName,' : ''}
              ${phoneticLastName ? 'phoneticLastName,' : ''}
              ${company ? 'company,' : ''}
              ${jobTitle ? 'jobTitle,' : ''}
              ${department ? 'department,' : ''}
              ${notes ? 'notes,' : ''}
              ${imageAvailable !== undefined ? 'imageAvailable,' : ''}
              ${contactType ? 'contactType,' : ''}
              ${emails?.length > 0 ? 'emails,' : ''}
              ${phoneNumbers?.length > 0 ? 'phoneNumbers,' : ''}
              ${imAddresses?.length > 0 ? 'imAddresses,' : ''}
              ${linkAddresses?.length > 0 ? 'linkAddresses,' : ''}
              ${app ? 'app,' : ''}
              deleted,
              updatedAt,
            ]
          }){
          returning {
            id
          }
        }
      }
    `;
        let valueToUpsert = {
            id,
            userId,
        };
        if (name) {
            valueToUpsert = {
                ...valueToUpsert,
                name,
            };
        }
        if (firstName) {
            valueToUpsert = {
                ...valueToUpsert,
                firstName,
            };
        }
        if (middleName) {
            valueToUpsert = {
                ...valueToUpsert,
                middleName,
            };
        }
        if (lastName) {
            valueToUpsert = {
                ...valueToUpsert,
                lastName,
            };
        }
        if (maidenName) {
            valueToUpsert = {
                ...valueToUpsert,
                maidenName,
            };
        }
        if (namePrefix) {
            valueToUpsert = {
                ...valueToUpsert,
                namePrefix,
            };
        }
        if (nameSuffix) {
            valueToUpsert = {
                ...valueToUpsert,
                nameSuffix,
            };
        }
        if (nickname) {
            valueToUpsert = {
                ...valueToUpsert,
                nickname,
            };
        }
        if (phoneticFirstName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticFirstName,
            };
        }
        if (phoneticMiddleName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticMiddleName,
            };
        }
        if (phoneticLastName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticLastName,
            };
        }
        if (company) {
            valueToUpsert = {
                ...valueToUpsert,
                company,
            };
        }
        if (jobTitle) {
            valueToUpsert = {
                ...valueToUpsert,
                jobTitle,
            };
        }
        if (department) {
            valueToUpsert = {
                ...valueToUpsert,
                department,
            };
        }
        if (notes) {
            valueToUpsert = {
                ...valueToUpsert,
                notes,
            };
        }
        if (imageAvailable !== undefined) {
            valueToUpsert = {
                ...valueToUpsert,
                imageAvailable,
            };
        }
        if (contactType) {
            valueToUpsert = {
                ...valueToUpsert,
                contactType,
            };
        }
        if (emails?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                emails,
            };
        }
        if (phoneNumbers?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneNumbers,
            };
        }
        if (imAddresses?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                imAddresses,
            };
        }
        if (linkAddresses?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                linkAddresses,
            };
        }
        if (app) {
            valueToUpsert = {
                ...valueToUpsert,
                app,
            };
        }
        valueToUpsert = {
            ...valueToUpsert,
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
            createdDate: (0, date_utils_1.dayjs)().toISOString(),
            deleted: false,
        };
        const { data } = await client.mutate({
            mutation: upsertContactMutation,
            variables: {
                contacts: [valueToUpsert],
            },
        });
        return data.insert_Contact.returning[0];
    }
    catch (e) {
        console.log(e, ' unable to create contacts');
    }
};
exports.upsertContact = upsertContact;
const searchContactsByName = async (client, userId, name) => {
    try {
        const formattedName = `%${name}%`;
        console.log(userId, ' userId inside listUserContactsHelper');
        const results = (await client.query({
            query: searchContactsByNameQuery_1.default,
            variables: {
                userId,
                name: formattedName,
            },
            fetchPolicy: 'no-cache',
        }))?.data?.Contact;
        console.log(results, ' results inside searchContactsByName');
        return results;
    }
    catch (e) {
        console.log(e, ' unable to search name');
        return [];
    }
};
exports.searchContactsByName = searchContactsByName;
const listUserContactsHelper = async (client, userId) => {
    try {
        console.log(userId, ' userId inside listUserContactsHelper');
        const results = (await client.query({
            query: listContactsByUser_1.default,
            variables: {
                userId,
            },
            fetchPolicy: 'no-cache',
        }))?.data?.Contact;
        console.log(results, ' successfully listed contacts');
        return results;
    }
    catch (e) {
        console.log(e, ' unable to get user contacts');
    }
};
exports.listUserContactsHelper = listUserContactsHelper;
// for search concat "%" like "%amet%"
const updateContact = async (client, contactId, imageAvailable, name, firstName, middleName, lastName, maidenName, namePrefix, nameSuffix, nickname, phoneticFirstName, phoneticMiddleName, phoneticLastName, company, jobTitle, department, notes, contactType, emails, phoneNumbers, imAddresses, linkAddresses, app) => {
    try {
        const upsertContactMutation = (0, client_1.gql) `
    mutation InsertContact($contacts: [Contact_insert_input!]!) {
      insert_Contact(
          objects: $contacts,
          on_conflict: {
              constraint: Contact_pkey,
              update_columns: [
                ${name ? 'name,' : ''} 
                ${firstName ? 'firstName,' : ''} 
                ${middleName ? 'middleName,' : ''}
                ${lastName ? 'lastName,' : ''}
                ${maidenName ? 'maidenName,' : ''}
                ${namePrefix ? 'namePrefix,' : ''}
                ${nameSuffix ? 'nameSuffix,' : ''}
                ${nickname ? 'nickname,' : ''}
                ${phoneticFirstName ? 'phoneticFirstName,' : ''}
                ${phoneticMiddleName ? 'phoneticMiddleName,' : ''}
                ${phoneticLastName ? 'phoneticLastName,' : ''}
                ${company ? 'company,' : ''}
                ${jobTitle ? 'jobTitle,' : ''}
                ${department ? 'department,' : ''}
                ${notes ? 'notes,' : ''}
                ${imageAvailable !== undefined ? 'imageAvailable,' : ''}
                ${contactType ? 'contactType,' : ''}
                ${emails?.length > 0 ? 'emails,' : ''}
                ${phoneNumbers?.length > 0 ? 'phoneNumbers,' : ''}
                ${imAddresses?.length > 0 ? 'imAddresses,' : ''}
                ${linkAddresses?.length > 0 ? 'linkAddresses,' : ''}
                ${app ? 'app,' : ''}
                updatedAt,
            ]
          }){
          returning {
            id
          }
        }
      }
    `;
        let valueToUpsert = {
            id: contactId,
        };
        if (name) {
            valueToUpsert = {
                ...valueToUpsert,
                name,
            };
        }
        if (firstName) {
            valueToUpsert = {
                ...valueToUpsert,
                firstName,
            };
        }
        if (middleName) {
            valueToUpsert = {
                ...valueToUpsert,
                middleName,
            };
        }
        if (lastName) {
            valueToUpsert = {
                ...valueToUpsert,
                lastName,
            };
        }
        if (maidenName) {
            valueToUpsert = {
                ...valueToUpsert,
                maidenName,
            };
        }
        if (namePrefix) {
            valueToUpsert = {
                ...valueToUpsert,
                namePrefix,
            };
        }
        if (nameSuffix) {
            valueToUpsert = {
                ...valueToUpsert,
                nameSuffix,
            };
        }
        if (nickname) {
            valueToUpsert = {
                ...valueToUpsert,
                nickname,
            };
        }
        if (phoneticFirstName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticFirstName,
            };
        }
        if (phoneticMiddleName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticMiddleName,
            };
        }
        if (phoneticLastName) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneticLastName,
            };
        }
        if (company) {
            valueToUpsert = {
                ...valueToUpsert,
                company,
            };
        }
        if (jobTitle) {
            valueToUpsert = {
                ...valueToUpsert,
                jobTitle,
            };
        }
        if (department) {
            valueToUpsert = {
                ...valueToUpsert,
                department,
            };
        }
        if (notes) {
            valueToUpsert = {
                ...valueToUpsert,
                notes,
            };
        }
        if (imageAvailable !== undefined) {
            valueToUpsert = {
                ...valueToUpsert,
                imageAvailable,
            };
        }
        if (contactType) {
            valueToUpsert = {
                ...valueToUpsert,
                contactType,
            };
        }
        if (emails?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                emails,
            };
        }
        if (phoneNumbers?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                phoneNumbers,
            };
        }
        if (imAddresses?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                imAddresses,
            };
        }
        if (linkAddresses?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                linkAddresses,
            };
        }
        if (app) {
            valueToUpsert = {
                ...valueToUpsert,
                app,
            };
        }
        valueToUpsert = {
            ...valueToUpsert,
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        };
        const { data } = await client.mutate({
            mutation: upsertContactMutation,
            variables: {
                contacts: [valueToUpsert],
            },
        });
        return data.insert_Contact.returning[0];
    }
    catch (e) {
        console.log(e, ' unable to create contacts');
    }
};
exports.updateContact = updateContact;
const deleteContact = async (client, contactId) => {
    try {
        const { data } = await client.mutate({
            mutation: deleteContactById_1.default,
            variables: {
                id: contactId,
            },
        });
        console.log(data?.delete_Contact_by_pk, ' succesffully removed contact');
    }
    catch (e) {
        console.log(e, ' unable to delete contact');
    }
};
exports.deleteContact = deleteContact;
/** end */
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ29udGFjdEhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIkNvbnRhY3RIZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsK0JBQWtDO0FBQ2xDLGdEQUF3QztBQVN4QywyQ0FBMEU7QUFDMUUsNEZBQW9FO0FBQ3BFLDBGQUFrRTtBQUNsRSwwR0FBa0Y7QUFFbEYsd0dBQWdGO0FBQ2hGLGdIQUF3RjtBQUV4RixvREFBdUI7QUFDdkIsNEdBQW9GO0FBQ3BGLDRHQUFvRjtBQUU3RSxNQUFNLHNCQUFzQixHQUFHLEtBQUssRUFDekMsTUFBMkMsRUFDM0MsT0FBaUIsRUFDakIsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sc0JBQXNCLEdBQUcsQ0FDN0IsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUErQztZQUNoRSxRQUFRLEVBQUUsb0NBQTBCO1lBQ3BDLFNBQVMsRUFBRTtnQkFDVCxPQUFPO2FBQ1I7WUFDRCxXQUFXLEVBQUUsVUFBVTtTQUN4QixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsaUJBQWlCLENBQUM7UUFFM0IsT0FBTyxDQUFDLEdBQUcsQ0FDVCxzQkFBc0IsRUFDdEIsMENBQTBDLENBQzNDLENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHNDQUFzQyxDQUFDLENBQUM7SUFDekQsQ0FBQztBQUNILENBQUMsQ0FBQztBQXRCVyxRQUFBLHNCQUFzQiwwQkFzQmpDO0FBRUssTUFBTSxzQkFBc0IsR0FBRyxLQUFLLEVBQ3pDLE1BQTJDLEVBQzNDLFlBQW1DLEVBQ25DLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLFlBQVksR0FBRyxDQUNuQixNQUFNLE1BQU0sQ0FBQyxNQUFNLENBS2hCO1lBQ0QsUUFBUSxFQUFFLG9DQUEwQjtZQUNwQyxTQUFTLEVBQUU7Z0JBQ1QsZ0JBQWdCLEVBQUUsWUFBWSxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsZ0JBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxFQUFFLENBQUMsWUFBWSxDQUFDLENBQUMsQ0FBQzthQUN0RTtZQUNELFdBQVcsRUFBRSxVQUFVO1lBQ3ZCLE1BQU0sQ0FBQyxLQUFLLEVBQUUsRUFBRSxJQUFJLEVBQUU7Z0JBQ3BCLEtBQUssQ0FBQyxNQUFNLENBQUM7b0JBQ1gsTUFBTSxFQUFFO3dCQUNOLGlCQUFpQixDQUFDLDRCQUE0QixHQUFHLEVBQUU7NEJBQ2pELE1BQU0sc0JBQXNCLEdBQzFCLElBQUksRUFBRSx3QkFBd0IsRUFBRSxTQUFTLEVBQUUsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEdBQUcsRUFBRSxFQUFFLENBQ3hELEtBQUssQ0FBQyxhQUFhLENBQUM7Z0NBQ2xCLElBQUksRUFBRSxJQUFJLEVBQUUsd0JBQXdCLEVBQUUsU0FBUyxDQUFDLEdBQUcsQ0FBQztnQ0FDcEQsUUFBUSxFQUFFLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7O3VCQVVaOzZCQUNGLENBQUMsQ0FDSCxDQUFDOzRCQUNKLE1BQU0sY0FBYyxHQUFHLDRCQUE0QixFQUFFLE1BQU0sQ0FDekQsQ0FBQyxDQUFzQixFQUFFLEVBQUUsQ0FDekIsSUFBSSxFQUFFLHdCQUF3QixFQUFFLFNBQVMsRUFBRSxJQUFJLENBQzdDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsRUFBRSxLQUFLLENBQUMsRUFBRSxFQUFFLENBQ3ZCLENBQ0osQ0FBQzs0QkFDRixPQUFPLENBQUMsR0FBRyxjQUFjLEVBQUUsR0FBRyxzQkFBc0IsQ0FBQyxDQUFDO3dCQUN4RCxDQUFDO3FCQUNGO2lCQUNGLENBQUMsQ0FBQztZQUNMLENBQUM7U0FDRixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsd0JBQXdCLEVBQUUsYUFBYSxDQUFDO1FBRWpELE9BQU8sQ0FBQyxHQUFHLENBQ1QsWUFBWSxFQUNaLDBEQUEwRCxDQUMzRCxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxzQ0FBc0MsQ0FBQyxDQUFDO0lBQ3pELENBQUM7QUFDSCxDQUFDLENBQUM7QUEzRFcsUUFBQSxzQkFBc0IsMEJBMkRqQztBQUVLLE1BQU0sdUJBQXVCLEdBQUcsQ0FDckMsUUFBNkIsRUFDN0IsWUFBb0IsRUFDcEIsT0FBMEIsRUFDMUIsWUFBbUMsRUFDbkMsWUFBNkQsRUFDN0QsRUFBRTtJQUNGLElBQUksQ0FBQyxDQUFDLFlBQVksR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUM7UUFDekIsT0FBTyxDQUFDLEdBQUcsQ0FBQyw0QkFBNEIsQ0FBQyxDQUFDO1FBQzFDLE9BQU87SUFDVCxDQUFDO0lBRUQsTUFBTSxXQUFXLEdBQUcsRUFBRSxHQUFHLFFBQVEsRUFBRSxJQUFJLEVBQUUsT0FBTyxFQUFFLENBQUM7SUFFbkQsTUFBTSxZQUFZLEdBQUcsZ0JBQUMsQ0FBQyxTQUFTLENBQUMsWUFBWSxDQUFDLENBQUM7SUFFL0MsTUFBTSxtQkFBbUIsR0FBRyxZQUFZO1NBQ3JDLEtBQUssQ0FBQyxDQUFDLEVBQUUsWUFBWSxDQUFDO1NBQ3RCLE1BQU0sQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDO1NBQ3JCLE1BQU0sQ0FBQyxZQUFZLENBQUMsS0FBSyxDQUFDLFlBQVksR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO0lBRWhELFlBQVksQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDO0FBQ3BDLENBQUMsQ0FBQztBQXRCVyxRQUFBLHVCQUF1QiwyQkFzQmxDO0FBRUssTUFBTSxxQkFBcUIsR0FBRyxDQUNuQyxRQUE2QixFQUM3QixZQUFvQixFQUNwQixLQUFhLEVBQ2IsWUFBbUMsRUFDbkMsWUFBNkQsRUFDN0QsRUFBRTtJQUNGLElBQUksQ0FBQyxDQUFDLFlBQVksR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUM7UUFDekIsT0FBTyxDQUFDLEdBQUcsQ0FBQyw0QkFBNEIsQ0FBQyxDQUFDO1FBQzFDLE9BQU87SUFDVCxDQUFDO0lBRUQsTUFBTSxXQUFXLEdBQUcsRUFBRSxHQUFHLFFBQVEsRUFBRSxFQUFFLEVBQUUsS0FBSyxFQUFFLENBQUM7SUFFL0MsTUFBTSxZQUFZLEdBQUcsZ0JBQUMsQ0FBQyxTQUFTLENBQUMsWUFBWSxDQUFDLENBQUM7SUFFL0MsTUFBTSxtQkFBbUIsR0FBRyxZQUFZO1NBQ3JDLEtBQUssQ0FBQyxDQUFDLEVBQUUsWUFBWSxDQUFDO1NBQ3RCLE1BQU0sQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDO1NBQ3JCLE1BQU0sQ0FBQyxZQUFZLENBQUMsS0FBSyxDQUFDLFlBQVksR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO0lBRWhELFlBQVksQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDO0FBQ3BDLENBQUMsQ0FBQztBQXRCVyxRQUFBLHFCQUFxQix5QkFzQmhDO0FBRUssTUFBTSx1QkFBdUIsR0FBRyxDQUNyQyxRQUE2QixFQUM3QixZQUFvQixFQUNwQixPQUFlLEVBQ2YsWUFBbUMsRUFDbkMsWUFBNkQsRUFDN0QsRUFBRTtJQUNGLElBQUksQ0FBQyxDQUFDLFlBQVksR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUM7UUFDekIsT0FBTyxDQUFDLEdBQUcsQ0FBQyw0QkFBNEIsQ0FBQyxDQUFDO1FBQzFDLE9BQU87SUFDVCxDQUFDO0lBRUQsTUFBTSxXQUFXLEdBQUcsRUFBRSxHQUFHLFFBQVEsRUFBRSxJQUFJLEVBQUUsT0FBTyxFQUFFLENBQUM7SUFFbkQsTUFBTSxZQUFZLEdBQUcsZ0JBQUMsQ0FBQyxTQUFTLENBQUMsWUFBWSxDQUFDLENBQUM7SUFFL0MsTUFBTSxtQkFBbUIsR0FBRyxZQUFZO1NBQ3JDLEtBQUssQ0FBQyxDQUFDLEVBQUUsWUFBWSxDQUFDO1NBQ3RCLE1BQU0sQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDO1NBQ3JCLE1BQU0sQ0FBQyxZQUFZLENBQUMsS0FBSyxDQUFDLFlBQVksR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO0lBRWhELFlBQVksQ0FBQyxtQkFBbUIsQ0FBQyxDQUFDO0FBQ3BDLENBQUMsQ0FBQztBQXRCVyxRQUFBLHVCQUF1QiwyQkFzQmxDO0FBRUssTUFBTSwwQkFBMEIsR0FBRyxDQUN4QyxRQUE2QixFQUM3QixZQUFvQixFQUNwQixVQUFtQixFQUNuQixZQUFtQyxFQUNuQyxZQUE2RCxFQUM3RCxFQUFFO0lBQ0YsSUFBSSxDQUFDLENBQUMsWUFBWSxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsQ0FBQztRQUN6QixPQUFPLENBQUMsR0FBRyxDQUFDLDRCQUE0QixDQUFDLENBQUM7UUFDMUMsT0FBTztJQUNULENBQUM7SUFFRCxNQUFNLFdBQVcsR0FBRyxFQUFFLEdBQUcsUUFBUSxFQUFFLE9BQU8sRUFBRSxVQUFVLEVBQUUsQ0FBQztJQUV6RCxNQUFNLFVBQVUsR0FBRyxZQUFZLEVBQUUsU0FBUyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsT0FBTyxDQUFDLENBQUM7SUFFOUQsSUFBSSxZQUFZLEdBQTBCLEVBQUUsQ0FBQztJQUU3QyxJQUFJLFVBQVUsR0FBRyxDQUFDLENBQUMsRUFBRSxDQUFDO1FBQ3BCLE1BQU0sWUFBWSxHQUFHLFlBQVksRUFBRSxDQUFDLFVBQVUsQ0FBQyxDQUFDO1FBRWhELE1BQU0sa0JBQWtCLEdBQUcsZ0JBQUMsQ0FBQyxTQUFTLENBQUMsWUFBWSxDQUFDLENBQUM7UUFFckQsTUFBTSx1QkFBdUIsR0FBRyxrQkFBa0I7YUFDL0MsS0FBSyxDQUFDLENBQUMsRUFBRSxVQUFVLENBQUM7YUFDcEIsTUFBTSxDQUFDLENBQUMsRUFBRSxHQUFHLFlBQVksRUFBRSxPQUFPLEVBQUUsQ0FBQyxZQUFZLEVBQUUsT0FBTyxFQUFFLENBQUMsQ0FBQzthQUM5RCxNQUFNLENBQUMsa0JBQWtCLEVBQUUsS0FBSyxDQUFDLFVBQVUsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBRXJELFlBQVksR0FBRyxnQkFBQyxDQUFDLFNBQVMsQ0FBQyx1QkFBdUIsQ0FBQyxDQUFDO0lBQ3RELENBQUM7U0FBTSxDQUFDO1FBQ04sWUFBWSxHQUFHLGdCQUFDLENBQUMsU0FBUyxDQUFDLFlBQVksQ0FBQyxDQUFDO0lBQzNDLENBQUM7SUFFRCxNQUFNLG1CQUFtQixHQUFHLFlBQVk7U0FDckMsS0FBSyxDQUFDLENBQUMsRUFBRSxZQUFZLENBQUM7U0FDdEIsTUFBTSxDQUFDLENBQUMsV0FBVyxDQUFDLENBQUM7U0FDckIsTUFBTSxDQUFDLFlBQVksQ0FBQyxLQUFLLENBQUMsWUFBWSxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUM7SUFFaEQsWUFBWSxDQUFDLG1CQUFtQixDQUFDLENBQUM7QUFDcEMsQ0FBQyxDQUFDO0FBdkNXLFFBQUEsMEJBQTBCLDhCQXVDckM7QUFFSyxNQUFNLHFCQUFxQixHQUFHLENBQ25DLEtBQWEsRUFDYixTQUFnQyxFQUNoQyxZQUE2RCxFQUM3RCxFQUFFO0lBQ0YsTUFBTSxZQUFZLEdBQUcsU0FBUztTQUMzQixLQUFLLENBQUMsQ0FBQyxFQUFFLEtBQUssQ0FBQztTQUNmLE1BQU0sQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLEtBQUssR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDO0lBRXRDLFlBQVksQ0FBQyxZQUFZLENBQUMsQ0FBQztJQUMzQixPQUFPLFlBQVksQ0FBQztBQUN0QixDQUFDLENBQUM7QUFYVyxRQUFBLHFCQUFxQix5QkFXaEM7QUFFSyxNQUFNLGtCQUFrQixHQUFHLENBQ2hDLFFBQTZCLEVBQzdCLFNBQWdDLEVBQ2hDLFlBQTZELEVBQzdELEVBQUU7SUFDRixNQUFNLFlBQVksR0FBRyxDQUFDLFFBQVEsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxTQUFTLENBQUMsQ0FBQztJQUNsRCxZQUFZLENBQUMsWUFBWSxDQUFDLENBQUM7QUFDN0IsQ0FBQyxDQUFDO0FBUFcsUUFBQSxrQkFBa0Isc0JBTzdCO0FBRUssTUFBTSwrQkFBK0IsR0FBRyxLQUFLLEVBQ2xELE1BQTJDLEVBQzNDLE1BQWMsRUFDZCxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxPQUFPLEdBQUcsQ0FDZCxNQUFNLE1BQU0sQ0FBQyxLQUFLLENBQStDO1lBQy9ELEtBQUssRUFBRSxzQ0FBNEI7WUFDbkMsU0FBUyxFQUFFO2dCQUNULE1BQU07YUFDUDtZQUNELFdBQVcsRUFBRSxVQUFVO1NBQ3hCLENBQUMsQ0FDSCxFQUFFLElBQUksRUFBRSxpQkFBaUIsQ0FBQztRQUUzQixPQUFPLENBQUMsR0FBRyxDQUFDLE9BQU8sRUFBRSwrQ0FBK0MsQ0FBQyxDQUFDO1FBRXRFLE9BQU8sT0FBTyxDQUFDO0lBQ2pCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsZ0RBQWdELENBQUMsQ0FBQztJQUNuRSxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBckJXLFFBQUEsK0JBQStCLG1DQXFCMUM7QUFFSyxNQUFNLGtCQUFrQixHQUFHLEtBQUssRUFDckMsTUFBMkMsRUFDM0MsV0FBZ0MsRUFDaEMsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sU0FBUyxHQUFHO1lBQ2hCLFdBQVc7U0FDWixDQUFDO1FBRUYsTUFBTSxjQUFjLEdBQUcsQ0FDckIsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUVoQjtZQUNELFFBQVEsRUFBRSxrQ0FBd0I7WUFDbEMsU0FBUyxFQUFFLFNBQVM7U0FDckIsQ0FBQyxDQUNILEVBQUUsSUFBSSxFQUFFLDRCQUE0QixDQUFDO1FBRXRDLE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYyxFQUFFLGtDQUFrQyxDQUFDLENBQUM7UUFFaEUsT0FBTyxjQUFjLENBQUM7SUFDeEIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxrQ0FBa0MsQ0FBQyxDQUFDO0lBQ3JELENBQUM7QUFDSCxDQUFDLENBQUM7QUF4QlcsUUFBQSxrQkFBa0Isc0JBd0I3QjtBQUVLLE1BQU0sYUFBYSxHQUFHLEtBQUssRUFDaEMsTUFBMkMsRUFDM0MsTUFBYyxFQUNkLGNBQXVCLEVBQ3ZCLElBQWEsRUFDYixTQUFrQixFQUNsQixVQUFtQixFQUNuQixRQUFpQixFQUNqQixVQUFtQixFQUNuQixVQUFtQixFQUNuQixVQUFtQixFQUNuQixRQUFpQixFQUNqQixpQkFBMEIsRUFDMUIsa0JBQTJCLEVBQzNCLGdCQUF5QixFQUN6QixPQUFnQixFQUNoQixRQUFpQixFQUNqQixVQUFtQixFQUNuQixLQUFjLEVBQ2QsV0FBb0IsRUFDcEIsTUFBMkIsRUFDM0IsWUFBaUMsRUFDakMsV0FBNkIsRUFDN0IsYUFBNkIsRUFDN0IsR0FBWSxFQUNaLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLHFCQUFxQixHQUFHLElBQUEsWUFBRyxFQUFBOzs7Ozs7O2tCQU9uQixJQUFJLENBQUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDbkIsU0FBUyxDQUFDLENBQUMsQ0FBQyxZQUFZLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQzdCLFVBQVUsQ0FBQyxDQUFDLENBQUMsYUFBYSxDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUNqQyxRQUFRLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDM0IsVUFBVSxDQUFDLENBQUMsQ0FBQyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQy9CLFVBQVUsQ0FBQyxDQUFDLENBQUMsYUFBYSxDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUMvQixVQUFVLENBQUMsQ0FBQyxDQUFDLGFBQWEsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDL0IsUUFBUSxDQUFDLENBQUMsQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQzNCLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxvQkFBb0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDN0Msa0JBQWtCLENBQUMsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUMvQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsbUJBQW1CLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQzNDLE9BQU8sQ0FBQyxDQUFDLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUN6QixRQUFRLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDM0IsVUFBVSxDQUFDLENBQUMsQ0FBQyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQy9CLEtBQUssQ0FBQyxDQUFDLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUNyQixjQUFjLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDckQsV0FBVyxDQUFDLENBQUMsQ0FBQyxjQUFjLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQ2pDLE1BQU0sRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQ25DLFlBQVksRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxlQUFlLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQy9DLFdBQVcsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxjQUFjLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQzdDLGFBQWEsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDakQsR0FBRyxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUU7Ozs7Ozs7Ozs7S0FVNUIsQ0FBQztRQUNGLE1BQU0sRUFBRSxHQUFHLElBQUEsU0FBSSxHQUFFLENBQUM7UUFDbEIsSUFBSSxhQUFhLEdBQVE7WUFDdkIsRUFBRTtZQUNGLE1BQU07U0FDUCxDQUFDO1FBRUYsSUFBSSxJQUFJLEVBQUUsQ0FBQztZQUNULGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLElBQUk7YUFDTCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksU0FBUyxFQUFFLENBQUM7WUFDZCxhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixTQUFTO2FBQ1YsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFVBQVUsRUFBRSxDQUFDO1lBQ2YsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsVUFBVTthQUNYLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxRQUFRLEVBQUUsQ0FBQztZQUNiLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFFBQVE7YUFDVCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksVUFBVSxFQUFFLENBQUM7WUFDZixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixVQUFVO2FBQ1gsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFVBQVUsRUFBRSxDQUFDO1lBQ2YsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsVUFBVTthQUNYLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxVQUFVLEVBQUUsQ0FBQztZQUNmLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFVBQVU7YUFDWCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLENBQUM7WUFDYixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixRQUFRO2FBQ1QsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLGlCQUFpQixFQUFFLENBQUM7WUFDdEIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsaUJBQWlCO2FBQ2xCLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxrQkFBa0IsRUFBRSxDQUFDO1lBQ3ZCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLGtCQUFrQjthQUNuQixDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksZ0JBQWdCLEVBQUUsQ0FBQztZQUNyQixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixnQkFBZ0I7YUFDakIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLE9BQU8sRUFBRSxDQUFDO1lBQ1osYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsT0FBTzthQUNSLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxRQUFRLEVBQUUsQ0FBQztZQUNiLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFFBQVE7YUFDVCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksVUFBVSxFQUFFLENBQUM7WUFDZixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixVQUFVO2FBQ1gsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLEtBQUssRUFBRSxDQUFDO1lBQ1YsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsS0FBSzthQUNOLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxjQUFjLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDakMsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsY0FBYzthQUNmLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxXQUFXLEVBQUUsQ0FBQztZQUNoQixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixXQUFXO2FBQ1osQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLE1BQU0sRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDdkIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsTUFBTTthQUNQLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxZQUFZLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQzdCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFlBQVk7YUFDYixDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksV0FBVyxFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUM1QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixXQUFXO2FBQ1osQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLGFBQWEsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDOUIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsYUFBYTthQUNkLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxHQUFHLEVBQUUsQ0FBQztZQUNSLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLEdBQUc7YUFDSixDQUFDO1FBQ0osQ0FBQztRQUVELGFBQWEsR0FBRztZQUNkLEdBQUcsYUFBYTtZQUNoQixTQUFTLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsV0FBVyxFQUFFO1lBQ2hDLFdBQVcsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUU7WUFDbEMsT0FBTyxFQUFFLEtBQUs7U0FDZixDQUFDO1FBRUYsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FFakM7WUFDRCxRQUFRLEVBQUUscUJBQXFCO1lBQy9CLFNBQVMsRUFBRTtnQkFDVCxRQUFRLEVBQUUsQ0FBQyxhQUFhLENBQUM7YUFDMUI7U0FDRixDQUFDLENBQUM7UUFFSCxPQUFPLElBQUksQ0FBQyxjQUFjLENBQUMsU0FBUyxDQUFDLENBQUMsQ0FBQyxDQUFDO0lBQzFDLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsNEJBQTRCLENBQUMsQ0FBQztJQUMvQyxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBdFBXLFFBQUEsYUFBYSxpQkFzUHhCO0FBRUssTUFBTSxhQUFhLEdBQUcsS0FBSyxFQUNoQyxNQUEyQyxFQUMzQyxNQUFjLEVBQ2QsRUFBVSxFQUNWLGNBQStCLEVBQy9CLElBQW9CLEVBQ3BCLFNBQXlCLEVBQ3pCLFVBQTBCLEVBQzFCLFFBQXdCLEVBQ3hCLFVBQTBCLEVBQzFCLFVBQTBCLEVBQzFCLFVBQTBCLEVBQzFCLFFBQXdCLEVBQ3hCLGlCQUFpQyxFQUNqQyxrQkFBa0MsRUFDbEMsZ0JBQWdDLEVBQ2hDLE9BQXVCLEVBQ3ZCLFFBQXdCLEVBQ3hCLFVBQTBCLEVBQzFCLEtBQXFCLEVBQ3JCLFdBQTJCLEVBQzNCLE1BQWtDLEVBQ2xDLFlBQXdDLEVBQ3hDLFdBQW9DLEVBQ3BDLGFBQW9DLEVBQ3BDLEdBQW1CLEVBQ25CLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLHFCQUFxQixHQUFHLElBQUEsWUFBRyxFQUFBOzs7Ozs7O2tCQU9uQixJQUFJLENBQUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDbkIsU0FBUyxDQUFDLENBQUMsQ0FBQyxZQUFZLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQzdCLFVBQVUsQ0FBQyxDQUFDLENBQUMsYUFBYSxDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUNqQyxRQUFRLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDM0IsVUFBVSxDQUFDLENBQUMsQ0FBQyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQy9CLFVBQVUsQ0FBQyxDQUFDLENBQUMsYUFBYSxDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUMvQixVQUFVLENBQUMsQ0FBQyxDQUFDLGFBQWEsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDL0IsUUFBUSxDQUFDLENBQUMsQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQzNCLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxvQkFBb0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDN0Msa0JBQWtCLENBQUMsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUMvQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsbUJBQW1CLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQzNDLE9BQU8sQ0FBQyxDQUFDLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUN6QixRQUFRLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDM0IsVUFBVSxDQUFDLENBQUMsQ0FBQyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQy9CLEtBQUssQ0FBQyxDQUFDLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxFQUFFO2dCQUNyQixjQUFjLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDckQsV0FBVyxDQUFDLENBQUMsQ0FBQyxjQUFjLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQ2pDLE1BQU0sRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQ25DLFlBQVksRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxlQUFlLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQy9DLFdBQVcsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxjQUFjLENBQUMsQ0FBQyxDQUFDLEVBQUU7Z0JBQzdDLGFBQWEsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtnQkFDakQsR0FBRyxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUU7Ozs7Ozs7Ozs7S0FVNUIsQ0FBQztRQUNGLElBQUksYUFBYSxHQUFRO1lBQ3ZCLEVBQUU7WUFDRixNQUFNO1NBQ1AsQ0FBQztRQUVGLElBQUksSUFBSSxFQUFFLENBQUM7WUFDVCxhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixJQUFJO2FBQ0wsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFNBQVMsRUFBRSxDQUFDO1lBQ2QsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsU0FBUzthQUNWLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxVQUFVLEVBQUUsQ0FBQztZQUNmLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFVBQVU7YUFDWCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLENBQUM7WUFDYixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixRQUFRO2FBQ1QsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFVBQVUsRUFBRSxDQUFDO1lBQ2YsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsVUFBVTthQUNYLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxVQUFVLEVBQUUsQ0FBQztZQUNmLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFVBQVU7YUFDWCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksVUFBVSxFQUFFLENBQUM7WUFDZixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixVQUFVO2FBQ1gsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxDQUFDO1lBQ2IsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsUUFBUTthQUNULENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxpQkFBaUIsRUFBRSxDQUFDO1lBQ3RCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLGlCQUFpQjthQUNsQixDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksa0JBQWtCLEVBQUUsQ0FBQztZQUN2QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixrQkFBa0I7YUFDbkIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLGdCQUFnQixFQUFFLENBQUM7WUFDckIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsZ0JBQWdCO2FBQ2pCLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxPQUFPLEVBQUUsQ0FBQztZQUNaLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLE9BQU87YUFDUixDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLENBQUM7WUFDYixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixRQUFRO2FBQ1QsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFVBQVUsRUFBRSxDQUFDO1lBQ2YsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsVUFBVTthQUNYLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxLQUFLLEVBQUUsQ0FBQztZQUNWLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLEtBQUs7YUFDTixDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksY0FBYyxLQUFLLFNBQVMsRUFBRSxDQUFDO1lBQ2pDLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLGNBQWM7YUFDZixDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksV0FBVyxFQUFFLENBQUM7WUFDaEIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsV0FBVzthQUNaLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxNQUFNLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ3ZCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLE1BQU07YUFDUCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksWUFBWSxFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUM3QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixZQUFZO2FBQ2IsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFdBQVcsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDNUIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsV0FBVzthQUNaLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxhQUFhLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQzlCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLGFBQWE7YUFDZCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksR0FBRyxFQUFFLENBQUM7WUFDUixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixHQUFHO2FBQ0osQ0FBQztRQUNKLENBQUM7UUFFRCxhQUFhLEdBQUc7WUFDZCxHQUFHLGFBQWE7WUFDaEIsU0FBUyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLFdBQVcsRUFBRTtZQUNoQyxXQUFXLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsV0FBVyxFQUFFO1lBQ2xDLE9BQU8sRUFBRSxLQUFLO1NBQ2YsQ0FBQztRQUVGLE1BQU0sRUFBRSxJQUFJLEVBQUUsR0FBRyxNQUFNLE1BQU0sQ0FBQyxNQUFNLENBRWpDO1lBQ0QsUUFBUSxFQUFFLHFCQUFxQjtZQUMvQixTQUFTLEVBQUU7Z0JBQ1QsUUFBUSxFQUFFLENBQUMsYUFBYSxDQUFDO2FBQzFCO1NBQ0YsQ0FBQyxDQUFDO1FBRUgsT0FBTyxJQUFJLENBQUMsY0FBYyxDQUFDLFNBQVMsQ0FBQyxDQUFDLENBQUMsQ0FBQztJQUMxQyxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDRCQUE0QixDQUFDLENBQUM7SUFDL0MsQ0FBQztBQUNILENBQUMsQ0FBQztBQXRQVyxRQUFBLGFBQWEsaUJBc1B4QjtBQUVLLE1BQU0sb0JBQW9CLEdBQUcsS0FBSyxFQUN2QyxNQUEyQyxFQUMzQyxNQUFjLEVBQ2QsSUFBWSxFQUNpQixFQUFFO0lBQy9CLElBQUksQ0FBQztRQUNILE1BQU0sYUFBYSxHQUFHLElBQUksSUFBSSxHQUFHLENBQUM7UUFFbEMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxNQUFNLEVBQUUsdUNBQXVDLENBQUMsQ0FBQztRQUM3RCxNQUFNLE9BQU8sR0FBRyxDQUNkLE1BQU0sTUFBTSxDQUFDLEtBQUssQ0FBNkI7WUFDN0MsS0FBSyxFQUFFLG1DQUF5QjtZQUNoQyxTQUFTLEVBQUU7Z0JBQ1QsTUFBTTtnQkFDTixJQUFJLEVBQUUsYUFBYTthQUNwQjtZQUNELFdBQVcsRUFBRSxVQUFVO1NBQ3hCLENBQUMsQ0FDSCxFQUFFLElBQUksRUFBRSxPQUFPLENBQUM7UUFFakIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxPQUFPLEVBQUUsc0NBQXNDLENBQUMsQ0FBQztRQUM3RCxPQUFPLE9BQU8sQ0FBQztJQUNqQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHdCQUF3QixDQUFDLENBQUM7UUFDekMsT0FBTyxFQUFFLENBQUM7SUFDWixDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBMUJXLFFBQUEsb0JBQW9CLHdCQTBCL0I7QUFFSyxNQUFNLHNCQUFzQixHQUFHLEtBQUssRUFDekMsTUFBMkMsRUFDM0MsTUFBYyxFQUNkLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxPQUFPLENBQUMsR0FBRyxDQUFDLE1BQU0sRUFBRSx1Q0FBdUMsQ0FBQyxDQUFDO1FBQzdELE1BQU0sT0FBTyxHQUFHLENBQ2QsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUE2QjtZQUM3QyxLQUFLLEVBQUUsNEJBQWtCO1lBQ3pCLFNBQVMsRUFBRTtnQkFDVCxNQUFNO2FBQ1A7WUFDRCxXQUFXLEVBQUUsVUFBVTtTQUN4QixDQUFDLENBQ0gsRUFBRSxJQUFJLEVBQUUsT0FBTyxDQUFDO1FBRWpCLE9BQU8sQ0FBQyxHQUFHLENBQUMsT0FBTyxFQUFFLCtCQUErQixDQUFDLENBQUM7UUFDdEQsT0FBTyxPQUFPLENBQUM7SUFDakIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSw4QkFBOEIsQ0FBQyxDQUFDO0lBQ2pELENBQUM7QUFDSCxDQUFDLENBQUM7QUFyQlcsUUFBQSxzQkFBc0IsMEJBcUJqQztBQUVGLHNDQUFzQztBQUUvQixNQUFNLGFBQWEsR0FBRyxLQUFLLEVBQ2hDLE1BQTJDLEVBQzNDLFNBQWlCLEVBQ2pCLGNBQXdCLEVBQ3hCLElBQWEsRUFDYixTQUFrQixFQUNsQixVQUFtQixFQUNuQixRQUFpQixFQUNqQixVQUFtQixFQUNuQixVQUFtQixFQUNuQixVQUFtQixFQUNuQixRQUFpQixFQUNqQixpQkFBMEIsRUFDMUIsa0JBQTJCLEVBQzNCLGdCQUF5QixFQUN6QixPQUFnQixFQUNoQixRQUFpQixFQUNqQixVQUFtQixFQUNuQixLQUFjLEVBQ2QsV0FBb0IsRUFDcEIsTUFBMkIsRUFDM0IsWUFBaUMsRUFDakMsV0FBNkIsRUFDN0IsYUFBNkIsRUFDN0IsR0FBWSxFQUNaLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLHFCQUFxQixHQUFHLElBQUEsWUFBRyxFQUFBOzs7Ozs7O2tCQU9uQixJQUFJLENBQUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDbkIsU0FBUyxDQUFDLENBQUMsQ0FBQyxZQUFZLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQzdCLFVBQVUsQ0FBQyxDQUFDLENBQUMsYUFBYSxDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUMvQixRQUFRLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDM0IsVUFBVSxDQUFDLENBQUMsQ0FBQyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQy9CLFVBQVUsQ0FBQyxDQUFDLENBQUMsYUFBYSxDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUMvQixVQUFVLENBQUMsQ0FBQyxDQUFDLGFBQWEsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDL0IsUUFBUSxDQUFDLENBQUMsQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQzNCLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxvQkFBb0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDN0Msa0JBQWtCLENBQUMsQ0FBQyxDQUFDLHFCQUFxQixDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUMvQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsbUJBQW1CLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQzNDLE9BQU8sQ0FBQyxDQUFDLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUN6QixRQUFRLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDM0IsVUFBVSxDQUFDLENBQUMsQ0FBQyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQy9CLEtBQUssQ0FBQyxDQUFDLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUNyQixjQUFjLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDckQsV0FBVyxDQUFDLENBQUMsQ0FBQyxjQUFjLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ2pDLE1BQU0sRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ25DLFlBQVksRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxlQUFlLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQy9DLFdBQVcsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxjQUFjLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQzdDLGFBQWEsRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDakQsR0FBRyxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUU7Ozs7Ozs7OztLQVM5QixDQUFDO1FBQ0YsSUFBSSxhQUFhLEdBQVE7WUFDdkIsRUFBRSxFQUFFLFNBQVM7U0FDZCxDQUFDO1FBRUYsSUFBSSxJQUFJLEVBQUUsQ0FBQztZQUNULGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLElBQUk7YUFDTCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksU0FBUyxFQUFFLENBQUM7WUFDZCxhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixTQUFTO2FBQ1YsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFVBQVUsRUFBRSxDQUFDO1lBQ2YsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsVUFBVTthQUNYLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxRQUFRLEVBQUUsQ0FBQztZQUNiLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFFBQVE7YUFDVCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksVUFBVSxFQUFFLENBQUM7WUFDZixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixVQUFVO2FBQ1gsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFVBQVUsRUFBRSxDQUFDO1lBQ2YsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsVUFBVTthQUNYLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxVQUFVLEVBQUUsQ0FBQztZQUNmLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFVBQVU7YUFDWCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLENBQUM7WUFDYixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixRQUFRO2FBQ1QsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLGlCQUFpQixFQUFFLENBQUM7WUFDdEIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsaUJBQWlCO2FBQ2xCLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxrQkFBa0IsRUFBRSxDQUFDO1lBQ3ZCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLGtCQUFrQjthQUNuQixDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksZ0JBQWdCLEVBQUUsQ0FBQztZQUNyQixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixnQkFBZ0I7YUFDakIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLE9BQU8sRUFBRSxDQUFDO1lBQ1osYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsT0FBTzthQUNSLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxRQUFRLEVBQUUsQ0FBQztZQUNiLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFFBQVE7YUFDVCxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksVUFBVSxFQUFFLENBQUM7WUFDZixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixVQUFVO2FBQ1gsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLEtBQUssRUFBRSxDQUFDO1lBQ1YsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsS0FBSzthQUNOLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxjQUFjLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDakMsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsY0FBYzthQUNmLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxXQUFXLEVBQUUsQ0FBQztZQUNoQixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixXQUFXO2FBQ1osQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLE1BQU0sRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDdkIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsTUFBTTthQUNQLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxZQUFZLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQzdCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLFlBQVk7YUFDYixDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksV0FBVyxFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUM1QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixXQUFXO2FBQ1osQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLGFBQWEsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDOUIsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsYUFBYTthQUNkLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxHQUFHLEVBQUUsQ0FBQztZQUNSLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLEdBQUc7YUFDSixDQUFDO1FBQ0osQ0FBQztRQUVELGFBQWEsR0FBRztZQUNkLEdBQUcsYUFBYTtZQUNoQixTQUFTLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsV0FBVyxFQUFFO1NBQ2pDLENBQUM7UUFFRixNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUVqQztZQUNELFFBQVEsRUFBRSxxQkFBcUI7WUFDL0IsU0FBUyxFQUFFO2dCQUNULFFBQVEsRUFBRSxDQUFDLGFBQWEsQ0FBQzthQUMxQjtTQUNGLENBQUMsQ0FBQztRQUVILE9BQU8sSUFBSSxDQUFDLGNBQWMsQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLENBQUM7SUFDMUMsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSw0QkFBNEIsQ0FBQyxDQUFDO0lBQy9DLENBQUM7QUFDSCxDQUFDLENBQUM7QUFqUFcsUUFBQSxhQUFhLGlCQWlQeEI7QUFFSyxNQUFNLGFBQWEsR0FBRyxLQUFLLEVBQ2hDLE1BQTJDLEVBQzNDLFNBQWlCLEVBQ2pCLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUNsQztZQUNFLFFBQVEsRUFBRSwyQkFBaUI7WUFDM0IsU0FBUyxFQUFFO2dCQUNULEVBQUUsRUFBRSxTQUFTO2FBQ2Q7U0FDRixDQUNGLENBQUM7UUFDRixPQUFPLENBQUMsR0FBRyxDQUFDLElBQUksRUFBRSxvQkFBb0IsRUFBRSwrQkFBK0IsQ0FBQyxDQUFDO0lBQzNFLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsMkJBQTJCLENBQUMsQ0FBQztJQUM5QyxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBakJXLFFBQUEsYUFBYSxpQkFpQnhCO0FBRUYsVUFBVSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJztcblxuaW1wb3J0IHtcbiAgQ29udGFjdEVtYWlsVHlwZSxcbiAgQ29udGFjdFBob25lVHlwZSxcbiAgQ29udGFjdFR5cGUsXG4gIEltQWRkcmVzc1R5cGUsXG4gIGxpbmtBZGRyZXNzLFxufSBmcm9tICdAbGliL2RhdGFUeXBlcy9Db250YWN0VHlwZSc7XG5pbXBvcnQgeyBBcG9sbG9DbGllbnQsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCwgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuaW1wb3J0IGxpc3RDb250YWN0c0J5VXNlciBmcm9tICdAbGliL2Fwb2xsby9ncWwvbGlzdENvbnRhY3RzQnlVc2VyJztcbmltcG9ydCBkZWxldGVDb250YWN0QnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlQ29udGFjdEJ5SWQnO1xuaW1wb3J0IHNlYXJjaENvbnRhY3RzQnlOYW1lUXVlcnkgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3NlYXJjaENvbnRhY3RzQnlOYW1lUXVlcnknO1xuaW1wb3J0IHsgVXNlckNvbnRhY3RJbmZvVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL1VzZXJDb250YWN0SW5mb1R5cGUnO1xuaW1wb3J0IGluc2VydFVzZXJDb250YWN0SW5mb09uZSBmcm9tICdAbGliL2Fwb2xsby9ncWwvaW5zZXJ0VXNlckNvbnRhY3RJbmZvT25lJztcbmltcG9ydCBsaXN0VXNlckNvbnRhY3RJbmZvc0J5VXNlcklkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0VXNlckNvbnRhY3RJbmZvc0J5VXNlcklkJztcbmltcG9ydCB7IERpc3BhdGNoLCBTZXRTdGF0ZUFjdGlvbiB9IGZyb20gJ3JlYWN0JztcbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG5pbXBvcnQgdXBzZXJ0VXNlckNvbnRhY3RJbmZvSXRlbXMgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3Vwc2VydFVzZXJDb250YWN0SW5mb0l0ZW1zJztcbmltcG9ydCBkZWxldGVVc2VyQ29udGFjdEluZm9JdGVtcyBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlVXNlckNvbnRhY3RJbmZvSXRlbXMnO1xuXG5leHBvcnQgY29uc3QgZGVsZXRlQ29udGFjdEluZm9JdGVtcyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgaXRlbUlkczogc3RyaW5nW11cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGRlbGV0ZUNvbnRhY3RJbmZvSXRlbXMgPSAoXG4gICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHsgVXNlcl9Db250YWN0X0luZm86IFVzZXJDb250YWN0SW5mb1R5cGVbXSB9Pih7XG4gICAgICAgIG11dGF0aW9uOiBkZWxldGVVc2VyQ29udGFjdEluZm9JdGVtcyxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgaXRlbUlkcyxcbiAgICAgICAgfSxcbiAgICAgICAgZmV0Y2hQb2xpY3k6ICduby1jYWNoZScsXG4gICAgICB9KVxuICAgICk/LmRhdGE/LlVzZXJfQ29udGFjdF9JbmZvO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBkZWxldGVDb250YWN0SW5mb0l0ZW1zLFxuICAgICAgJyBzdWNjZXNzZnVsbHkgZGVsZXRlZCBjb250YWN0IGluZm8gaXRlbXMnXG4gICAgKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBjb250YWN0IGluZm8gaXRlbXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydENvbnRhY3RJbmZvSXRlbXMgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNvbnRhY3RJbmZvczogVXNlckNvbnRhY3RJbmZvVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBhZmZlY3RlZFJvd3MgPSAoXG4gICAgICBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgICAgaW5zZXJ0X1VzZXJfQ29udGFjdF9JbmZvOiB7XG4gICAgICAgICAgYWZmZWN0ZWRfcm93czogbnVtYmVyO1xuICAgICAgICAgIHJldHVybmluZzogVXNlckNvbnRhY3RJbmZvVHlwZVtdO1xuICAgICAgICB9O1xuICAgICAgfT4oe1xuICAgICAgICBtdXRhdGlvbjogdXBzZXJ0VXNlckNvbnRhY3RJbmZvSXRlbXMsXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIGNvbnRhY3RJbmZvSXRlbXM6IGNvbnRhY3RJbmZvcz8ubWFwKChjKSA9PiBfLm9taXQoYywgWydfX3R5cGVuYW1lJ10pKSxcbiAgICAgICAgfSxcbiAgICAgICAgZmV0Y2hQb2xpY3k6ICduby1jYWNoZScsXG4gICAgICAgIHVwZGF0ZShjYWNoZSwgeyBkYXRhIH0pIHtcbiAgICAgICAgICBjYWNoZS5tb2RpZnkoe1xuICAgICAgICAgICAgZmllbGRzOiB7XG4gICAgICAgICAgICAgIFVzZXJfQ29udGFjdF9JbmZvKGV4aXN0aW5nVXNlckNvbnRhY3RJbmZvSXRlbXMgPSBbXSkge1xuICAgICAgICAgICAgICAgIGNvbnN0IG5ld1VzZXJDb250YWN0SW5mb1JlZnMgPVxuICAgICAgICAgICAgICAgICAgZGF0YT8uaW5zZXJ0X1VzZXJfQ29udGFjdF9JbmZvPy5yZXR1cm5pbmc/Lm1hcCgoaSwgaW54KSA9PlxuICAgICAgICAgICAgICAgICAgICBjYWNoZS53cml0ZUZyYWdtZW50KHtcbiAgICAgICAgICAgICAgICAgICAgICBkYXRhOiBkYXRhPy5pbnNlcnRfVXNlcl9Db250YWN0X0luZm8/LnJldHVybmluZ1tpbnhdLFxuICAgICAgICAgICAgICAgICAgICAgIGZyYWdtZW50OiBncWxgXG4gICAgICAgICAgICAgICAgICAgICAgICBmcmFnbWVudCBOZXdVc2VyX0NvbnRhY3RfSW5mbyBvbiBVc2VyX0NvbnRhY3RfSW5mbyB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgICAgICAgcHJpbWFyeVxuICAgICAgICAgICAgICAgICAgICAgICAgICB0eXBlXG4gICAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICBgLFxuICAgICAgICAgICAgICAgICAgICB9KVxuICAgICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV4aXN0aW5nVXNlckNvbnRhY3RJbmZvSXRlbXM/LmZpbHRlcihcbiAgICAgICAgICAgICAgICAgIChpOiBVc2VyQ29udGFjdEluZm9UeXBlKSA9PlxuICAgICAgICAgICAgICAgICAgICBkYXRhPy5pbnNlcnRfVXNlcl9Db250YWN0X0luZm8/LnJldHVybmluZz8uZmluZChcbiAgICAgICAgICAgICAgICAgICAgICAobikgPT4gbj8uaWQgPT09IGk/LmlkXG4gICAgICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgICAgIHJldHVybiBbLi4uZmlsdGVyZWRFdmVudHMsIC4uLm5ld1VzZXJDb250YWN0SW5mb1JlZnNdO1xuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KTtcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8uaW5zZXJ0X1VzZXJfQ29udGFjdF9JbmZvPy5hZmZlY3RlZF9yb3dzO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBhZmZlY3RlZFJvd3MsXG4gICAgICAnIHN1Y2Nlc3NmdWxseSBhZmZlY3RlZFJvd3MgaW5zaWRlIHVwc2VydENvbnRhY3RJbmZvSXRlbXMnXG4gICAgKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwc2VydCBjb250YWN0IGluZm8gaXRlbXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUluZm9JdGVtVHlwZVZhbHVlID0gKFxuICBpbmZvSXRlbTogVXNlckNvbnRhY3RJbmZvVHlwZSxcbiAgbmV3SXRlbUluZGV4OiBudW1iZXIsXG4gIG5ld1R5cGU6ICdlbWFpbCcgfCAncGhvbmUnLFxuICBvbGRJbmZvSXRlbXM6IFVzZXJDb250YWN0SW5mb1R5cGVbXSxcbiAgc2V0SW5mb0l0ZW1zOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxVc2VyQ29udGFjdEluZm9UeXBlW10+PlxuKSA9PiB7XG4gIGlmICghKG5ld0l0ZW1JbmRleCA+IC0xKSkge1xuICAgIGNvbnNvbGUubG9nKCduZXdJdGVtSW5kZXggPiAtMSBpcyBmYWxzZScpO1xuICAgIHJldHVybjtcbiAgfVxuXG4gIGNvbnN0IG5ld0luZm9JdGVtID0geyAuLi5pbmZvSXRlbSwgdHlwZTogbmV3VHlwZSB9O1xuXG4gIGNvbnN0IG5ld0luZm9JdGVtcyA9IF8uY2xvbmVEZWVwKG9sZEluZm9JdGVtcyk7XG5cbiAgY29uc3QgdXBkYXRlZE5ld0luZm9JdGVtcyA9IG5ld0luZm9JdGVtc1xuICAgIC5zbGljZSgwLCBuZXdJdGVtSW5kZXgpXG4gICAgLmNvbmNhdChbbmV3SW5mb0l0ZW1dKVxuICAgIC5jb25jYXQobmV3SW5mb0l0ZW1zLnNsaWNlKG5ld0l0ZW1JbmRleCArIDEpKTtcblxuICBzZXRJbmZvSXRlbXModXBkYXRlZE5ld0luZm9JdGVtcyk7XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlSW5mb0l0ZW1JZFZhbHVlID0gKFxuICBpbmZvSXRlbTogVXNlckNvbnRhY3RJbmZvVHlwZSxcbiAgbmV3SXRlbUluZGV4OiBudW1iZXIsXG4gIG5ld0lkOiBzdHJpbmcsXG4gIG9sZEluZm9JdGVtczogVXNlckNvbnRhY3RJbmZvVHlwZVtdLFxuICBzZXRJbmZvSXRlbXM6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPFVzZXJDb250YWN0SW5mb1R5cGVbXT4+XG4pID0+IHtcbiAgaWYgKCEobmV3SXRlbUluZGV4ID4gLTEpKSB7XG4gICAgY29uc29sZS5sb2coJ25ld0l0ZW1JbmRleCA+IC0xIGlzIGZhbHNlJyk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgY29uc3QgbmV3SW5mb0l0ZW0gPSB7IC4uLmluZm9JdGVtLCBpZDogbmV3SWQgfTtcblxuICBjb25zdCBuZXdJbmZvSXRlbXMgPSBfLmNsb25lRGVlcChvbGRJbmZvSXRlbXMpO1xuXG4gIGNvbnN0IHVwZGF0ZWROZXdJbmZvSXRlbXMgPSBuZXdJbmZvSXRlbXNcbiAgICAuc2xpY2UoMCwgbmV3SXRlbUluZGV4KVxuICAgIC5jb25jYXQoW25ld0luZm9JdGVtXSlcbiAgICAuY29uY2F0KG5ld0luZm9JdGVtcy5zbGljZShuZXdJdGVtSW5kZXggKyAxKSk7XG5cbiAgc2V0SW5mb0l0ZW1zKHVwZGF0ZWROZXdJbmZvSXRlbXMpO1xufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUluZm9JdGVtTmFtZVZhbHVlID0gKFxuICBpbmZvSXRlbTogVXNlckNvbnRhY3RJbmZvVHlwZSxcbiAgbmV3SXRlbUluZGV4OiBudW1iZXIsXG4gIG5ld05hbWU6IHN0cmluZyxcbiAgb2xkSW5mb0l0ZW1zOiBVc2VyQ29udGFjdEluZm9UeXBlW10sXG4gIHNldEluZm9JdGVtczogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248VXNlckNvbnRhY3RJbmZvVHlwZVtdPj5cbikgPT4ge1xuICBpZiAoIShuZXdJdGVtSW5kZXggPiAtMSkpIHtcbiAgICBjb25zb2xlLmxvZygnbmV3SXRlbUluZGV4ID4gLTEgaXMgZmFsc2UnKTtcbiAgICByZXR1cm47XG4gIH1cblxuICBjb25zdCBuZXdJbmZvSXRlbSA9IHsgLi4uaW5mb0l0ZW0sIG5hbWU6IG5ld05hbWUgfTtcblxuICBjb25zdCBuZXdJbmZvSXRlbXMgPSBfLmNsb25lRGVlcChvbGRJbmZvSXRlbXMpO1xuXG4gIGNvbnN0IHVwZGF0ZWROZXdJbmZvSXRlbXMgPSBuZXdJbmZvSXRlbXNcbiAgICAuc2xpY2UoMCwgbmV3SXRlbUluZGV4KVxuICAgIC5jb25jYXQoW25ld0luZm9JdGVtXSlcbiAgICAuY29uY2F0KG5ld0luZm9JdGVtcy5zbGljZShuZXdJdGVtSW5kZXggKyAxKSk7XG5cbiAgc2V0SW5mb0l0ZW1zKHVwZGF0ZWROZXdJbmZvSXRlbXMpO1xufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUluZm9JdGVtUHJpbWFyeVZhbHVlID0gKFxuICBpbmZvSXRlbTogVXNlckNvbnRhY3RJbmZvVHlwZSxcbiAgbmV3SXRlbUluZGV4OiBudW1iZXIsXG4gIG5ld1ByaW1hcnk6IGJvb2xlYW4sXG4gIG9sZEluZm9JdGVtczogVXNlckNvbnRhY3RJbmZvVHlwZVtdLFxuICBzZXRJbmZvSXRlbXM6IERpc3BhdGNoPFNldFN0YXRlQWN0aW9uPFVzZXJDb250YWN0SW5mb1R5cGVbXT4+XG4pID0+IHtcbiAgaWYgKCEobmV3SXRlbUluZGV4ID4gLTEpKSB7XG4gICAgY29uc29sZS5sb2coJ25ld0l0ZW1JbmRleCA+IC0xIGlzIGZhbHNlJyk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgY29uc3QgbmV3SW5mb0l0ZW0gPSB7IC4uLmluZm9JdGVtLCBwcmltYXJ5OiBuZXdQcmltYXJ5IH07XG5cbiAgY29uc3QgZm91bmRJbmRleCA9IG9sZEluZm9JdGVtcz8uZmluZEluZGV4KChvKSA9PiBvPy5wcmltYXJ5KTtcblxuICBsZXQgbmV3SW5mb0l0ZW1zOiBVc2VyQ29udGFjdEluZm9UeXBlW10gPSBbXTtcblxuICBpZiAoZm91bmRJbmRleCA+IC0xKSB7XG4gICAgY29uc3QgZm91bmRPbGRJdGVtID0gb2xkSW5mb0l0ZW1zPy5bZm91bmRJbmRleF07XG5cbiAgICBjb25zdCBvbGRDbG9uZWRJbmZvSXRlbXMgPSBfLmNsb25lRGVlcChvbGRJbmZvSXRlbXMpO1xuXG4gICAgY29uc3Qgb2xkSXRlbVVwZGF0ZWRJbmZvSXRlbXMgPSBvbGRDbG9uZWRJbmZvSXRlbXNcbiAgICAgIC5zbGljZSgwLCBmb3VuZEluZGV4KVxuICAgICAgLmNvbmNhdChbeyAuLi5mb3VuZE9sZEl0ZW0sIHByaW1hcnk6ICFmb3VuZE9sZEl0ZW0/LnByaW1hcnkgfV0pXG4gICAgICAuY29uY2F0KG9sZENsb25lZEluZm9JdGVtcz8uc2xpY2UoZm91bmRJbmRleCArIDEpKTtcblxuICAgIG5ld0luZm9JdGVtcyA9IF8uY2xvbmVEZWVwKG9sZEl0ZW1VcGRhdGVkSW5mb0l0ZW1zKTtcbiAgfSBlbHNlIHtcbiAgICBuZXdJbmZvSXRlbXMgPSBfLmNsb25lRGVlcChvbGRJbmZvSXRlbXMpO1xuICB9XG5cbiAgY29uc3QgdXBkYXRlZE5ld0luZm9JdGVtcyA9IG5ld0luZm9JdGVtc1xuICAgIC5zbGljZSgwLCBuZXdJdGVtSW5kZXgpXG4gICAgLmNvbmNhdChbbmV3SW5mb0l0ZW1dKVxuICAgIC5jb25jYXQobmV3SW5mb0l0ZW1zLnNsaWNlKG5ld0l0ZW1JbmRleCArIDEpKTtcblxuICBzZXRJbmZvSXRlbXModXBkYXRlZE5ld0luZm9JdGVtcyk7XG59O1xuXG5leHBvcnQgY29uc3QgcmVtb3ZlSW5mb0l0ZW1Ub0l0ZW1zID0gKFxuICBpbmRleDogbnVtYmVyLFxuICBpbmZvSXRlbXM6IFVzZXJDb250YWN0SW5mb1R5cGVbXSxcbiAgc2V0SW5mb0l0ZW1zOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxVc2VyQ29udGFjdEluZm9UeXBlW10+PlxuKSA9PiB7XG4gIGNvbnN0IG5ld0luZm9JdGVtcyA9IGluZm9JdGVtc1xuICAgIC5zbGljZSgwLCBpbmRleClcbiAgICAuY29uY2F0KGluZm9JdGVtcy5zbGljZShpbmRleCArIDEpKTtcblxuICBzZXRJbmZvSXRlbXMobmV3SW5mb0l0ZW1zKTtcbiAgcmV0dXJuIG5ld0luZm9JdGVtcztcbn07XG5cbmV4cG9ydCBjb25zdCBhZGRJbmZvSXRlbVRvSXRlbXMgPSAoXG4gIGluZm9JdGVtOiBVc2VyQ29udGFjdEluZm9UeXBlLFxuICBpbmZvSXRlbXM6IFVzZXJDb250YWN0SW5mb1R5cGVbXSxcbiAgc2V0SW5mb0l0ZW1zOiBEaXNwYXRjaDxTZXRTdGF0ZUFjdGlvbjxVc2VyQ29udGFjdEluZm9UeXBlW10+PlxuKSA9PiB7XG4gIGNvbnN0IG5ld0luZm9JdGVtcyA9IFtpbmZvSXRlbV0uY29uY2F0KGluZm9JdGVtcyk7XG4gIHNldEluZm9JdGVtcyhuZXdJbmZvSXRlbXMpO1xufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RVc2VyQ29udGFjdEluZm9zR2l2ZW5Vc2VySWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCByZXN1bHRzID0gKFxuICAgICAgYXdhaXQgY2xpZW50LnF1ZXJ5PHsgVXNlcl9Db250YWN0X0luZm86IFVzZXJDb250YWN0SW5mb1R5cGVbXSB9Pih7XG4gICAgICAgIHF1ZXJ5OiBsaXN0VXNlckNvbnRhY3RJbmZvc0J5VXNlcklkLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgIH0sXG4gICAgICAgIGZldGNoUG9saWN5OiAnbm8tY2FjaGUnLFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5Vc2VyX0NvbnRhY3RfSW5mbztcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgcmVzdWx0cyBvZiBsaXN0IHVzZXIgY29udGFjdCBpbmZvcyBieSB1c2VySWQnKTtcblxuICAgIHJldHVybiByZXN1bHRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgb3QgbGlzdCB1c2VyIGNvbnRhY3QgaW5mbyBnaXZlbiB1c2VySWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGFkZFVzZXJDb250YWN0SW5mbyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY29udGFjdEluZm86IFVzZXJDb250YWN0SW5mb1R5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGNvbnRhY3RJbmZvLFxuICAgIH07XG5cbiAgICBjb25zdCBjb250YWN0SW5mb0RvYyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgICBpbnNlcnRfVXNlcl9Db250YWN0X0luZm9fb25lOiBVc2VyQ29udGFjdEluZm9UeXBlO1xuICAgICAgfT4oe1xuICAgICAgICBtdXRhdGlvbjogaW5zZXJ0VXNlckNvbnRhY3RJbmZvT25lLFxuICAgICAgICB2YXJpYWJsZXM6IHZhcmlhYmxlcyxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8uaW5zZXJ0X1VzZXJfQ29udGFjdF9JbmZvX29uZTtcblxuICAgIGNvbnNvbGUubG9nKGNvbnRhY3RJbmZvRG9jLCAnIHN1Y2Nlc3NmdWxseSBhZGRlZCBjb250YWN0IGluZm8nKTtcblxuICAgIHJldHVybiBjb250YWN0SW5mb0RvYztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGFkZCB1c2VyIGNvbnRhY3QgaW5mbycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlQ29udGFjdCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGltYWdlQXZhaWxhYmxlOiBib29sZWFuLFxuICBuYW1lPzogc3RyaW5nLFxuICBmaXJzdE5hbWU/OiBzdHJpbmcsXG4gIG1pZGRsZU5hbWU/OiBzdHJpbmcsXG4gIGxhc3ROYW1lPzogc3RyaW5nLFxuICBtYWlkZW5OYW1lPzogc3RyaW5nLFxuICBuYW1lUHJlZml4Pzogc3RyaW5nLFxuICBuYW1lU3VmZml4Pzogc3RyaW5nLFxuICBuaWNrbmFtZT86IHN0cmluZyxcbiAgcGhvbmV0aWNGaXJzdE5hbWU/OiBzdHJpbmcsXG4gIHBob25ldGljTWlkZGxlTmFtZT86IHN0cmluZyxcbiAgcGhvbmV0aWNMYXN0TmFtZT86IHN0cmluZyxcbiAgY29tcGFueT86IHN0cmluZyxcbiAgam9iVGl0bGU/OiBzdHJpbmcsXG4gIGRlcGFydG1lbnQ/OiBzdHJpbmcsXG4gIG5vdGVzPzogc3RyaW5nLFxuICBjb250YWN0VHlwZT86IHN0cmluZyxcbiAgZW1haWxzPzogQ29udGFjdEVtYWlsVHlwZVtdLFxuICBwaG9uZU51bWJlcnM/OiBDb250YWN0UGhvbmVUeXBlW10sXG4gIGltQWRkcmVzc2VzPzogSW1BZGRyZXNzVHlwZVtdLFxuICBsaW5rQWRkcmVzc2VzPzogbGlua0FkZHJlc3NbXSxcbiAgYXBwPzogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB1cHNlcnRDb250YWN0TXV0YXRpb24gPSBncWxgXG4gICAgbXV0YXRpb24gSW5zZXJ0Q29udGFjdCgkY29udGFjdHM6IFtDb250YWN0X2luc2VydF9pbnB1dCFdISkge1xuICAgICAgaW5zZXJ0X0NvbnRhY3QoXG4gICAgICAgICAgb2JqZWN0czogJGNvbnRhY3RzLFxuICAgICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgICAgIGNvbnN0cmFpbnQ6IENvbnRhY3RfcGtleSxcbiAgICAgICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICAke25hbWUgPyAnbmFtZSwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Zmlyc3ROYW1lID8gJ2ZpcnN0TmFtZSwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7bWlkZGxlTmFtZSA/ICdtaWRkbGVOYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtsYXN0TmFtZSA/ICdsYXN0TmFtZSwnIDogJyd9XG4gICAgICAgICAgICAgICR7bWFpZGVuTmFtZSA/ICdtYWlkZW5OYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtuYW1lUHJlZml4ID8gJ25hbWVQcmVmaXgsJyA6ICcnfVxuICAgICAgICAgICAgICAke25hbWVTdWZmaXggPyAnbmFtZVN1ZmZpeCwnIDogJyd9XG4gICAgICAgICAgICAgICR7bmlja25hbWUgPyAnbmlja25hbWUsJyA6ICcnfVxuICAgICAgICAgICAgICAke3Bob25ldGljRmlyc3ROYW1lID8gJ3Bob25ldGljRmlyc3ROYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtwaG9uZXRpY01pZGRsZU5hbWUgPyAncGhvbmV0aWNNaWRkbGVOYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtwaG9uZXRpY0xhc3ROYW1lID8gJ3Bob25ldGljTGFzdE5hbWUsJyA6ICcnfVxuICAgICAgICAgICAgICAke2NvbXBhbnkgPyAnY29tcGFueSwnIDogJyd9XG4gICAgICAgICAgICAgICR7am9iVGl0bGUgPyAnam9iVGl0bGUsJyA6ICcnfVxuICAgICAgICAgICAgICAke2RlcGFydG1lbnQgPyAnZGVwYXJ0bWVudCwnIDogJyd9XG4gICAgICAgICAgICAgICR7bm90ZXMgPyAnbm90ZXMsJyA6ICcnfVxuICAgICAgICAgICAgICAke2ltYWdlQXZhaWxhYmxlICE9PSB1bmRlZmluZWQgPyAnaW1hZ2VBdmFpbGFibGUsJyA6ICcnfVxuICAgICAgICAgICAgICAke2NvbnRhY3RUeXBlID8gJ2NvbnRhY3RUeXBlLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtlbWFpbHM/Lmxlbmd0aCA+IDAgPyAnZW1haWxzLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtwaG9uZU51bWJlcnM/Lmxlbmd0aCA+IDAgPyAncGhvbmVOdW1iZXJzLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtpbUFkZHJlc3Nlcz8ubGVuZ3RoID4gMCA/ICdpbUFkZHJlc3NlcywnIDogJyd9XG4gICAgICAgICAgICAgICR7bGlua0FkZHJlc3Nlcz8ubGVuZ3RoID4gMCA/ICdsaW5rQWRkcmVzc2VzLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHthcHAgPyAnYXBwLCcgOiAnJ31cbiAgICAgICAgICAgICAgZGVsZXRlZCxcbiAgICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICAgICAgXVxuICAgICAgICAgIH0pe1xuICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICBpZFxuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgaWQgPSB1dWlkKCk7XG4gICAgbGV0IHZhbHVlVG9VcHNlcnQ6IGFueSA9IHtcbiAgICAgIGlkLFxuICAgICAgdXNlcklkLFxuICAgIH07XG5cbiAgICBpZiAobmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGZpcnN0TmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgZmlyc3ROYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobWlkZGxlTmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbWlkZGxlTmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGxhc3ROYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBsYXN0TmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKG1haWRlbk5hbWUpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIG1haWRlbk5hbWUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChuYW1lUHJlZml4KSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBuYW1lUHJlZml4LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobmFtZVN1ZmZpeCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbmFtZVN1ZmZpeCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKG5pY2tuYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBuaWNrbmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKHBob25ldGljRmlyc3ROYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBwaG9uZXRpY0ZpcnN0TmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKHBob25ldGljTWlkZGxlTmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgcGhvbmV0aWNNaWRkbGVOYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAocGhvbmV0aWNMYXN0TmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgcGhvbmV0aWNMYXN0TmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNvbXBhbnkpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGNvbXBhbnksXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChqb2JUaXRsZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgam9iVGl0bGUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChkZXBhcnRtZW50KSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBkZXBhcnRtZW50LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobm90ZXMpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIG5vdGVzLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoaW1hZ2VBdmFpbGFibGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgaW1hZ2VBdmFpbGFibGUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjb250YWN0VHlwZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgY29udGFjdFR5cGUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChlbWFpbHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGVtYWlscyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKHBob25lTnVtYmVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgcGhvbmVOdW1iZXJzLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoaW1BZGRyZXNzZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGltQWRkcmVzc2VzLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobGlua0FkZHJlc3Nlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbGlua0FkZHJlc3NlcyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGFwcCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgYXBwLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIH07XG5cbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgaW5zZXJ0X0NvbnRhY3Q6IHsgcmV0dXJuaW5nOiBDb250YWN0VHlwZVtdIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IHVwc2VydENvbnRhY3RNdXRhdGlvbixcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBjb250YWN0czogW3ZhbHVlVG9VcHNlcnRdLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIHJldHVybiBkYXRhLmluc2VydF9Db250YWN0LnJldHVybmluZ1swXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSBjb250YWN0cycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBzZXJ0Q29udGFjdCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGlkOiBzdHJpbmcsXG4gIGltYWdlQXZhaWxhYmxlPzogYm9vbGVhbiB8IG51bGwsXG4gIG5hbWU/OiBzdHJpbmcgfCBudWxsLFxuICBmaXJzdE5hbWU/OiBzdHJpbmcgfCBudWxsLFxuICBtaWRkbGVOYW1lPzogc3RyaW5nIHwgbnVsbCxcbiAgbGFzdE5hbWU/OiBzdHJpbmcgfCBudWxsLFxuICBtYWlkZW5OYW1lPzogc3RyaW5nIHwgbnVsbCxcbiAgbmFtZVByZWZpeD86IHN0cmluZyB8IG51bGwsXG4gIG5hbWVTdWZmaXg/OiBzdHJpbmcgfCBudWxsLFxuICBuaWNrbmFtZT86IHN0cmluZyB8IG51bGwsXG4gIHBob25ldGljRmlyc3ROYW1lPzogc3RyaW5nIHwgbnVsbCxcbiAgcGhvbmV0aWNNaWRkbGVOYW1lPzogc3RyaW5nIHwgbnVsbCxcbiAgcGhvbmV0aWNMYXN0TmFtZT86IHN0cmluZyB8IG51bGwsXG4gIGNvbXBhbnk/OiBzdHJpbmcgfCBudWxsLFxuICBqb2JUaXRsZT86IHN0cmluZyB8IG51bGwsXG4gIGRlcGFydG1lbnQ/OiBzdHJpbmcgfCBudWxsLFxuICBub3Rlcz86IHN0cmluZyB8IG51bGwsXG4gIGNvbnRhY3RUeXBlPzogc3RyaW5nIHwgbnVsbCxcbiAgZW1haWxzPzogQ29udGFjdEVtYWlsVHlwZVtdIHwgbnVsbCxcbiAgcGhvbmVOdW1iZXJzPzogQ29udGFjdFBob25lVHlwZVtdIHwgbnVsbCxcbiAgaW1BZGRyZXNzZXM/OiBJbUFkZHJlc3NUeXBlW10gfCBudWxsLFxuICBsaW5rQWRkcmVzc2VzPzogbGlua0FkZHJlc3NbXSB8IG51bGwsXG4gIGFwcD86IHN0cmluZyB8IG51bGxcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHVwc2VydENvbnRhY3RNdXRhdGlvbiA9IGdxbGBcbiAgICBtdXRhdGlvbiBJbnNlcnRDb250YWN0KCRjb250YWN0czogW0NvbnRhY3RfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICBpbnNlcnRfQ29udGFjdChcbiAgICAgICAgICBvYmplY3RzOiAkY29udGFjdHMsXG4gICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgY29uc3RyYWludDogQ29udGFjdF9wa2V5LFxuICAgICAgICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICR7bmFtZSA/ICduYW1lLCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgJHtmaXJzdE5hbWUgPyAnZmlyc3ROYW1lLCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgJHttaWRkbGVOYW1lID8gJ21pZGRsZU5hbWUsJyA6ICcnfVxuICAgICAgICAgICAgICAke2xhc3ROYW1lID8gJ2xhc3ROYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHttYWlkZW5OYW1lID8gJ21haWRlbk5hbWUsJyA6ICcnfVxuICAgICAgICAgICAgICAke25hbWVQcmVmaXggPyAnbmFtZVByZWZpeCwnIDogJyd9XG4gICAgICAgICAgICAgICR7bmFtZVN1ZmZpeCA/ICduYW1lU3VmZml4LCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtuaWNrbmFtZSA/ICduaWNrbmFtZSwnIDogJyd9XG4gICAgICAgICAgICAgICR7cGhvbmV0aWNGaXJzdE5hbWUgPyAncGhvbmV0aWNGaXJzdE5hbWUsJyA6ICcnfVxuICAgICAgICAgICAgICAke3Bob25ldGljTWlkZGxlTmFtZSA/ICdwaG9uZXRpY01pZGRsZU5hbWUsJyA6ICcnfVxuICAgICAgICAgICAgICAke3Bob25ldGljTGFzdE5hbWUgPyAncGhvbmV0aWNMYXN0TmFtZSwnIDogJyd9XG4gICAgICAgICAgICAgICR7Y29tcGFueSA/ICdjb21wYW55LCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtqb2JUaXRsZSA/ICdqb2JUaXRsZSwnIDogJyd9XG4gICAgICAgICAgICAgICR7ZGVwYXJ0bWVudCA/ICdkZXBhcnRtZW50LCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtub3RlcyA/ICdub3RlcywnIDogJyd9XG4gICAgICAgICAgICAgICR7aW1hZ2VBdmFpbGFibGUgIT09IHVuZGVmaW5lZCA/ICdpbWFnZUF2YWlsYWJsZSwnIDogJyd9XG4gICAgICAgICAgICAgICR7Y29udGFjdFR5cGUgPyAnY29udGFjdFR5cGUsJyA6ICcnfVxuICAgICAgICAgICAgICAke2VtYWlscz8ubGVuZ3RoID4gMCA/ICdlbWFpbHMsJyA6ICcnfVxuICAgICAgICAgICAgICAke3Bob25lTnVtYmVycz8ubGVuZ3RoID4gMCA/ICdwaG9uZU51bWJlcnMsJyA6ICcnfVxuICAgICAgICAgICAgICAke2ltQWRkcmVzc2VzPy5sZW5ndGggPiAwID8gJ2ltQWRkcmVzc2VzLCcgOiAnJ31cbiAgICAgICAgICAgICAgJHtsaW5rQWRkcmVzc2VzPy5sZW5ndGggPiAwID8gJ2xpbmtBZGRyZXNzZXMsJyA6ICcnfVxuICAgICAgICAgICAgICAke2FwcCA/ICdhcHAsJyA6ICcnfVxuICAgICAgICAgICAgICBkZWxldGVkLFxuICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICBdXG4gICAgICAgICAgfSl7XG4gICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBsZXQgdmFsdWVUb1Vwc2VydDogYW55ID0ge1xuICAgICAgaWQsXG4gICAgICB1c2VySWQsXG4gICAgfTtcblxuICAgIGlmIChuYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBuYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoZmlyc3ROYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBmaXJzdE5hbWUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChtaWRkbGVOYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBtaWRkbGVOYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobGFzdE5hbWUpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGxhc3ROYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobWFpZGVuTmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbWFpZGVuTmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKG5hbWVQcmVmaXgpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIG5hbWVQcmVmaXgsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChuYW1lU3VmZml4KSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBuYW1lU3VmZml4LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobmlja25hbWUpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIG5pY2tuYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAocGhvbmV0aWNGaXJzdE5hbWUpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIHBob25ldGljRmlyc3ROYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAocGhvbmV0aWNNaWRkbGVOYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBwaG9uZXRpY01pZGRsZU5hbWUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChwaG9uZXRpY0xhc3ROYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBwaG9uZXRpY0xhc3ROYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoY29tcGFueSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgY29tcGFueSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGpvYlRpdGxlKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBqb2JUaXRsZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGRlcGFydG1lbnQpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGRlcGFydG1lbnQsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChub3Rlcykge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbm90ZXMsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChpbWFnZUF2YWlsYWJsZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBpbWFnZUF2YWlsYWJsZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNvbnRhY3RUeXBlKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBjb250YWN0VHlwZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGVtYWlscz8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgZW1haWxzLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAocGhvbmVOdW1iZXJzPy5sZW5ndGggPiAwKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBwaG9uZU51bWJlcnMsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChpbUFkZHJlc3Nlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgaW1BZGRyZXNzZXMsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChsaW5rQWRkcmVzc2VzPy5sZW5ndGggPiAwKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBsaW5rQWRkcmVzc2VzLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoYXBwKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBhcHAsXG4gICAgICB9O1xuICAgIH1cblxuICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgfTtcblxuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICBpbnNlcnRfQ29udGFjdDogeyByZXR1cm5pbmc6IENvbnRhY3RUeXBlW10gfTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBzZXJ0Q29udGFjdE11dGF0aW9uLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGNvbnRhY3RzOiBbdmFsdWVUb1Vwc2VydF0sXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgcmV0dXJuIGRhdGEuaW5zZXJ0X0NvbnRhY3QucmV0dXJuaW5nWzBdO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gY3JlYXRlIGNvbnRhY3RzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBzZWFyY2hDb250YWN0c0J5TmFtZSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG5hbWU6IHN0cmluZ1xuKTogUHJvbWlzZTxDb250YWN0VHlwZVtdIHwgW10+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBmb3JtYXR0ZWROYW1lID0gYCUke25hbWV9JWA7XG5cbiAgICBjb25zb2xlLmxvZyh1c2VySWQsICcgdXNlcklkIGluc2lkZSBsaXN0VXNlckNvbnRhY3RzSGVscGVyJyk7XG4gICAgY29uc3QgcmVzdWx0cyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IENvbnRhY3Q6IENvbnRhY3RUeXBlW10gfT4oe1xuICAgICAgICBxdWVyeTogc2VhcmNoQ29udGFjdHNCeU5hbWVRdWVyeSxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIG5hbWU6IGZvcm1hdHRlZE5hbWUsXG4gICAgICAgIH0sXG4gICAgICAgIGZldGNoUG9saWN5OiAnbm8tY2FjaGUnLFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5Db250YWN0O1xuXG4gICAgY29uc29sZS5sb2cocmVzdWx0cywgJyByZXN1bHRzIGluc2lkZSBzZWFyY2hDb250YWN0c0J5TmFtZScpO1xuICAgIHJldHVybiByZXN1bHRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gc2VhcmNoIG5hbWUnKTtcbiAgICByZXR1cm4gW107XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0VXNlckNvbnRhY3RzSGVscGVyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2codXNlcklkLCAnIHVzZXJJZCBpbnNpZGUgbGlzdFVzZXJDb250YWN0c0hlbHBlcicpO1xuICAgIGNvbnN0IHJlc3VsdHMgPSAoXG4gICAgICBhd2FpdCBjbGllbnQucXVlcnk8eyBDb250YWN0OiBDb250YWN0VHlwZVtdIH0+KHtcbiAgICAgICAgcXVlcnk6IGxpc3RDb250YWN0c0J5VXNlcixcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICB9LFxuICAgICAgICBmZXRjaFBvbGljeTogJ25vLWNhY2hlJyxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8uQ29udGFjdDtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgc3VjY2Vzc2Z1bGx5IGxpc3RlZCBjb250YWN0cycpO1xuICAgIHJldHVybiByZXN1bHRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHVzZXIgY29udGFjdHMnKTtcbiAgfVxufTtcblxuLy8gZm9yIHNlYXJjaCBjb25jYXQgXCIlXCIgbGlrZSBcIiVhbWV0JVwiXG5cbmV4cG9ydCBjb25zdCB1cGRhdGVDb250YWN0ID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjb250YWN0SWQ6IHN0cmluZyxcbiAgaW1hZ2VBdmFpbGFibGU/OiBib29sZWFuLFxuICBuYW1lPzogc3RyaW5nLFxuICBmaXJzdE5hbWU/OiBzdHJpbmcsXG4gIG1pZGRsZU5hbWU/OiBzdHJpbmcsXG4gIGxhc3ROYW1lPzogc3RyaW5nLFxuICBtYWlkZW5OYW1lPzogc3RyaW5nLFxuICBuYW1lUHJlZml4Pzogc3RyaW5nLFxuICBuYW1lU3VmZml4Pzogc3RyaW5nLFxuICBuaWNrbmFtZT86IHN0cmluZyxcbiAgcGhvbmV0aWNGaXJzdE5hbWU/OiBzdHJpbmcsXG4gIHBob25ldGljTWlkZGxlTmFtZT86IHN0cmluZyxcbiAgcGhvbmV0aWNMYXN0TmFtZT86IHN0cmluZyxcbiAgY29tcGFueT86IHN0cmluZyxcbiAgam9iVGl0bGU/OiBzdHJpbmcsXG4gIGRlcGFydG1lbnQ/OiBzdHJpbmcsXG4gIG5vdGVzPzogc3RyaW5nLFxuICBjb250YWN0VHlwZT86IHN0cmluZyxcbiAgZW1haWxzPzogQ29udGFjdEVtYWlsVHlwZVtdLFxuICBwaG9uZU51bWJlcnM/OiBDb250YWN0UGhvbmVUeXBlW10sXG4gIGltQWRkcmVzc2VzPzogSW1BZGRyZXNzVHlwZVtdLFxuICBsaW5rQWRkcmVzc2VzPzogbGlua0FkZHJlc3NbXSxcbiAgYXBwPzogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB1cHNlcnRDb250YWN0TXV0YXRpb24gPSBncWxgXG4gICAgbXV0YXRpb24gSW5zZXJ0Q29udGFjdCgkY29udGFjdHM6IFtDb250YWN0X2luc2VydF9pbnB1dCFdISkge1xuICAgICAgaW5zZXJ0X0NvbnRhY3QoXG4gICAgICAgICAgb2JqZWN0czogJGNvbnRhY3RzLFxuICAgICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgICAgIGNvbnN0cmFpbnQ6IENvbnRhY3RfcGtleSxcbiAgICAgICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICAke25hbWUgPyAnbmFtZSwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Zmlyc3ROYW1lID8gJ2ZpcnN0TmFtZSwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7bWlkZGxlTmFtZSA/ICdtaWRkbGVOYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2xhc3ROYW1lID8gJ2xhc3ROYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke21haWRlbk5hbWUgPyAnbWFpZGVuTmFtZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtuYW1lUHJlZml4ID8gJ25hbWVQcmVmaXgsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7bmFtZVN1ZmZpeCA/ICduYW1lU3VmZml4LCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke25pY2tuYW1lID8gJ25pY2tuYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke3Bob25ldGljRmlyc3ROYW1lID8gJ3Bob25ldGljRmlyc3ROYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke3Bob25ldGljTWlkZGxlTmFtZSA/ICdwaG9uZXRpY01pZGRsZU5hbWUsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7cGhvbmV0aWNMYXN0TmFtZSA/ICdwaG9uZXRpY0xhc3ROYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NvbXBhbnkgPyAnY29tcGFueSwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtqb2JUaXRsZSA/ICdqb2JUaXRsZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtkZXBhcnRtZW50ID8gJ2RlcGFydG1lbnQsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7bm90ZXMgPyAnbm90ZXMsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7aW1hZ2VBdmFpbGFibGUgIT09IHVuZGVmaW5lZCA/ICdpbWFnZUF2YWlsYWJsZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtjb250YWN0VHlwZSA/ICdjb250YWN0VHlwZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtlbWFpbHM/Lmxlbmd0aCA+IDAgPyAnZW1haWxzLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke3Bob25lTnVtYmVycz8ubGVuZ3RoID4gMCA/ICdwaG9uZU51bWJlcnMsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7aW1BZGRyZXNzZXM/Lmxlbmd0aCA+IDAgPyAnaW1BZGRyZXNzZXMsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7bGlua0FkZHJlc3Nlcz8ubGVuZ3RoID4gMCA/ICdsaW5rQWRkcmVzc2VzLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2FwcCA/ICdhcHAsJyA6ICcnfVxuICAgICAgICAgICAgICAgIHVwZGF0ZWRBdCxcbiAgICAgICAgICAgIF1cbiAgICAgICAgICB9KXtcbiAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgaWRcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGxldCB2YWx1ZVRvVXBzZXJ0OiBhbnkgPSB7XG4gICAgICBpZDogY29udGFjdElkLFxuICAgIH07XG5cbiAgICBpZiAobmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGZpcnN0TmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgZmlyc3ROYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobWlkZGxlTmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbWlkZGxlTmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGxhc3ROYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBsYXN0TmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKG1haWRlbk5hbWUpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIG1haWRlbk5hbWUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChuYW1lUHJlZml4KSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBuYW1lUHJlZml4LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobmFtZVN1ZmZpeCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbmFtZVN1ZmZpeCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKG5pY2tuYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBuaWNrbmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKHBob25ldGljRmlyc3ROYW1lKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBwaG9uZXRpY0ZpcnN0TmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKHBob25ldGljTWlkZGxlTmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgcGhvbmV0aWNNaWRkbGVOYW1lLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAocGhvbmV0aWNMYXN0TmFtZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgcGhvbmV0aWNMYXN0TmFtZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNvbXBhbnkpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGNvbXBhbnksXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChqb2JUaXRsZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgam9iVGl0bGUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChkZXBhcnRtZW50KSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBkZXBhcnRtZW50LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobm90ZXMpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIG5vdGVzLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoaW1hZ2VBdmFpbGFibGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgaW1hZ2VBdmFpbGFibGUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjb250YWN0VHlwZSkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgY29udGFjdFR5cGUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChlbWFpbHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGVtYWlscyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKHBob25lTnVtYmVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgcGhvbmVOdW1iZXJzLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoaW1BZGRyZXNzZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGltQWRkcmVzc2VzLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAobGlua0FkZHJlc3Nlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgbGlua0FkZHJlc3NlcyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGFwcCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgYXBwLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIH07XG5cbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgaW5zZXJ0X0NvbnRhY3Q6IHsgcmV0dXJuaW5nOiBDb250YWN0VHlwZVtdIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IHVwc2VydENvbnRhY3RNdXRhdGlvbixcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBjb250YWN0czogW3ZhbHVlVG9VcHNlcnRdLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIHJldHVybiBkYXRhLmluc2VydF9Db250YWN0LnJldHVybmluZ1swXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSBjb250YWN0cycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlQ29udGFjdCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY29udGFjdElkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGRlbGV0ZV9Db250YWN0X2J5X3BrOiBDb250YWN0VHlwZSB9PihcbiAgICAgIHtcbiAgICAgICAgbXV0YXRpb246IGRlbGV0ZUNvbnRhY3RCeUlkLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICBpZDogY29udGFjdElkLFxuICAgICAgICB9LFxuICAgICAgfVxuICAgICk7XG4gICAgY29uc29sZS5sb2coZGF0YT8uZGVsZXRlX0NvbnRhY3RfYnlfcGssICcgc3VjY2VzZmZ1bGx5IHJlbW92ZWQgY29udGFjdCcpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGVsZXRlIGNvbnRhY3QnKTtcbiAgfVxufTtcblxuLyoqIGVuZCAqL1xuIl19