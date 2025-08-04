declare const _default: "\n    query ListUserContactInfoByUserId($userId: uuid!) {\n        User_Contact_Info(where: {userId: {_eq: $userId}}) {\n            createdDate\n            id\n            name\n            primary\n            type\n            updatedAt\n            userId\n        }\n    }\n";
export default _default;
