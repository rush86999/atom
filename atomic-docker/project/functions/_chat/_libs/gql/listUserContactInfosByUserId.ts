export default `
    query ListUserContactInfoByUserId($userId: uuid!) {
        User_Contact_Info(where: {userId: {_eq: $userId}}) {
            createdDate
            id
            name
            primary
            type
            updatedAt
            userId
        }
    }
`;
