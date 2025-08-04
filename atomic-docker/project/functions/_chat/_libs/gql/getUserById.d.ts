declare const _default: "\nquery GetUserById($id: uuid!) {\n  User_by_pk(id: $id) {\n    createdDate\n    deleted\n    email\n    id\n    name\n    updatedAt\n    userPreferenceId\n  }\n}\n";
export default _default;
