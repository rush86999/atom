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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdFVzZXJDb250YWN0SW5mb3NCeVVzZXJJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxpc3RVc2VyQ29udGFjdEluZm9zQnlVc2VySWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsZUFBZTs7Ozs7Ozs7Ozs7O0NBWWQsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImV4cG9ydCBkZWZhdWx0IGBcbiAgICBxdWVyeSBMaXN0VXNlckNvbnRhY3RJbmZvQnlVc2VySWQoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgVXNlcl9Db250YWN0X0luZm8od2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICBwcmltYXJ5XG4gICAgICAgICAgICB0eXBlXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICB9XG4gICAgfVxuYDtcbiJdfQ==