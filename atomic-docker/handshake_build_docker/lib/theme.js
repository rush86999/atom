"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
// 1. Import the extendTheme function
const react_1 = require("@chakra-ui/react");
// 2. Extend the theme to include custom colors, fonts, etc
const colors = {
    brand: {
        900: '#1a365d',
        800: '#153e75',
        700: '#2a69ac',
    },
};
const theme = (0, react_1.extendTheme)({ colors });
exports.default = theme;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGhlbWUuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ0aGVtZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLHFDQUFxQztBQUNyQyw0Q0FBK0M7QUFFL0MsMkRBQTJEO0FBQzNELE1BQU0sTUFBTSxHQUFHO0lBQ2IsS0FBSyxFQUFFO1FBQ0wsR0FBRyxFQUFFLFNBQVM7UUFDZCxHQUFHLEVBQUUsU0FBUztRQUNkLEdBQUcsRUFBRSxTQUFTO0tBQ2Y7Q0FDRixDQUFDO0FBRUYsTUFBTSxLQUFLLEdBQUcsSUFBQSxtQkFBVyxFQUFDLEVBQUUsTUFBTSxFQUFFLENBQUMsQ0FBQztBQUV0QyxrQkFBZSxLQUFLLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyIvLyAxLiBJbXBvcnQgdGhlIGV4dGVuZFRoZW1lIGZ1bmN0aW9uXG5pbXBvcnQgeyBleHRlbmRUaGVtZSB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnO1xuXG4vLyAyLiBFeHRlbmQgdGhlIHRoZW1lIHRvIGluY2x1ZGUgY3VzdG9tIGNvbG9ycywgZm9udHMsIGV0Y1xuY29uc3QgY29sb3JzID0ge1xuICBicmFuZDoge1xuICAgIDkwMDogJyMxYTM2NWQnLFxuICAgIDgwMDogJyMxNTNlNzUnLFxuICAgIDcwMDogJyMyYTY5YWMnLFxuICB9LFxufTtcblxuY29uc3QgdGhlbWUgPSBleHRlbmRUaGVtZSh7IGNvbG9ycyB9KTtcblxuZXhwb3J0IGRlZmF1bHQgdGhlbWU7XG4iXX0=