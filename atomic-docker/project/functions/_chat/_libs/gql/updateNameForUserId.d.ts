declare const _default: "\nmutation UpdateNameForUserById($id: uuid!, $name: String!) {\n  update_User_by_pk(pk_columns: {id: $id}, _set: {name: $name}) {\n    createdDate\n    deleted\n    email\n    id\n    name\n    updatedAt\n    userPreferenceId\n  }\n}\n";
export default _default;
