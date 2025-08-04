declare const _default: "\nquery GetContactInfosWithIds($ids: [String!]!) {\n  User_Contact_Info(where: {id: {_in: $ids}}) {\n    createdDate\n    id\n    name\n    primary\n    type\n    updatedAt\n    userId\n  }\n}\n";
export default _default;
