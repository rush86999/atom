"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const react_native_1 = require("react-native");
const sizes_1 = __importDefault(require("@lib/theme/sizes"));
const StatusHeight = react_native_1.StatusBar.currentHeight;
const HeaderHeight = sizes_1.default.BASE * 3.5 + (StatusHeight || 0);
const iPhoneX = () => react_native_1.Platform.OS === 'ios' &&
    (react_native_1.Dimensions.get('window').height === 812 ||
        react_native_1.Dimensions.get('window').width === 812);
// eslint-disable-next-line import/no-anonymous-default-export
exports.default = {
    StatusHeight,
    HeaderHeight,
    iPhoneX,
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXRpbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1dGlscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQUFBLCtDQUErRDtBQUMvRCw2REFBcUM7QUFFckMsTUFBTSxZQUFZLEdBQUcsd0JBQVMsQ0FBQyxhQUFhLENBQUM7QUFDN0MsTUFBTSxZQUFZLEdBQUcsZUFBSyxDQUFDLElBQUksR0FBRyxHQUFHLEdBQUcsQ0FBQyxZQUFZLElBQUksQ0FBQyxDQUFDLENBQUM7QUFDNUQsTUFBTSxPQUFPLEdBQUcsR0FBRyxFQUFFLENBQ25CLHVCQUFRLENBQUMsRUFBRSxLQUFLLEtBQUs7SUFDckIsQ0FBQyx5QkFBVSxDQUFDLEdBQUcsQ0FBQyxRQUFRLENBQUMsQ0FBQyxNQUFNLEtBQUssR0FBRztRQUN0Qyx5QkFBVSxDQUFDLEdBQUcsQ0FBQyxRQUFRLENBQUMsQ0FBQyxLQUFLLEtBQUssR0FBRyxDQUFDLENBQUM7QUFFNUMsOERBQThEO0FBQzlELGtCQUFlO0lBQ2IsWUFBWTtJQUNaLFlBQVk7SUFDWixPQUFPO0NBQ1IsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFBsYXRmb3JtLCBTdGF0dXNCYXIsIERpbWVuc2lvbnMgfSBmcm9tICdyZWFjdC1uYXRpdmUnO1xuaW1wb3J0IFNJWkVTIGZyb20gJ0BsaWIvdGhlbWUvc2l6ZXMnO1xuXG5jb25zdCBTdGF0dXNIZWlnaHQgPSBTdGF0dXNCYXIuY3VycmVudEhlaWdodDtcbmNvbnN0IEhlYWRlckhlaWdodCA9IFNJWkVTLkJBU0UgKiAzLjUgKyAoU3RhdHVzSGVpZ2h0IHx8IDApO1xuY29uc3QgaVBob25lWCA9ICgpID0+XG4gIFBsYXRmb3JtLk9TID09PSAnaW9zJyAmJlxuICAoRGltZW5zaW9ucy5nZXQoJ3dpbmRvdycpLmhlaWdodCA9PT0gODEyIHx8XG4gICAgRGltZW5zaW9ucy5nZXQoJ3dpbmRvdycpLndpZHRoID09PSA4MTIpO1xuXG4vLyBlc2xpbnQtZGlzYWJsZS1uZXh0LWxpbmUgaW1wb3J0L25vLWFub255bW91cy1kZWZhdWx0LWV4cG9ydFxuZXhwb3J0IGRlZmF1bHQge1xuICBTdGF0dXNIZWlnaHQsXG4gIEhlYWRlckhlaWdodCxcbiAgaVBob25lWCxcbn07XG4iXX0=