"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.analyzeSentiment = analyzeSentiment;
const sentiment_1 = __importDefault(require("sentiment"));
const sentiment = new sentiment_1.default();
function analyzeSentiment(text) {
    const result = sentiment.analyze(text);
    return result.score;
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VudGltZW50LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic2VudGltZW50LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBSUEsNENBR0M7QUFQRCwwREFBa0M7QUFFbEMsTUFBTSxTQUFTLEdBQUcsSUFBSSxtQkFBUyxFQUFFLENBQUM7QUFFbEMsU0FBZ0IsZ0JBQWdCLENBQUMsSUFBWTtJQUMzQyxNQUFNLE1BQU0sR0FBRyxTQUFTLENBQUMsT0FBTyxDQUFDLElBQUksQ0FBQyxDQUFDO0lBQ3ZDLE9BQU8sTUFBTSxDQUFDLEtBQUssQ0FBQztBQUN0QixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFNlbnRpbWVudCBmcm9tICdzZW50aW1lbnQnO1xuXG5jb25zdCBzZW50aW1lbnQgPSBuZXcgU2VudGltZW50KCk7XG5cbmV4cG9ydCBmdW5jdGlvbiBhbmFseXplU2VudGltZW50KHRleHQ6IHN0cmluZyk6IG51bWJlciB7XG4gIGNvbnN0IHJlc3VsdCA9IHNlbnRpbWVudC5hbmFseXplKHRleHQpO1xuICByZXR1cm4gcmVzdWx0LnNjb3JlO1xufVxuIl19