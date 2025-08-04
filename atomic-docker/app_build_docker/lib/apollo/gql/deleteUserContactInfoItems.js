"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query DeleteUserContactInfoItems($itemIds: [String!]!) {
    User_Contact_Info(where: { id: { _in: $itemIds } }) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlVXNlckNvbnRhY3RJbmZvSXRlbXMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVVc2VyQ29udGFjdEluZm9JdGVtcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7O0NBWWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgRGVsZXRlVXNlckNvbnRhY3RJbmZvSXRlbXMoJGl0ZW1JZHM6IFtTdHJpbmchXSEpIHtcbiAgICBVc2VyX0NvbnRhY3RfSW5mbyh3aGVyZTogeyBpZDogeyBfaW46ICRpdGVtSWRzIH0gfSkge1xuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGlkXG4gICAgICBuYW1lXG4gICAgICBwcmltYXJ5XG4gICAgICB0eXBlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==