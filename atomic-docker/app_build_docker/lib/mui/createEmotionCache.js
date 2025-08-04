"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = createEmotionCache;
const cache_1 = __importDefault(require("@emotion/cache"));
const isBrowser = typeof document !== 'undefined';
// On the client side, Create a meta tag at the top of the <head> and set it as insertionPoint.
// This assures that MUI styles are loaded first.
// It allows developers to easily override MUI styles with other styling solutions, like CSS modules.
function createEmotionCache() {
    let insertionPoint;
    if (isBrowser) {
        const emotionInsertionPoint = document.querySelector('meta[name="emotion-insertion-point"]');
        insertionPoint = emotionInsertionPoint ?? undefined;
    }
    return (0, cache_1.default)({ key: 'mui-style', insertionPoint });
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY3JlYXRlRW1vdGlvbkNhY2hlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiY3JlYXRlRW1vdGlvbkNhY2hlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBT0EscUNBV0M7QUFsQkQsMkRBQXlDO0FBRXpDLE1BQU0sU0FBUyxHQUFHLE9BQU8sUUFBUSxLQUFLLFdBQVcsQ0FBQztBQUVsRCwrRkFBK0Y7QUFDL0YsaURBQWlEO0FBQ2pELHFHQUFxRztBQUNyRyxTQUF3QixrQkFBa0I7SUFDeEMsSUFBSSxjQUFjLENBQUM7SUFFbkIsSUFBSSxTQUFTLEVBQUUsQ0FBQztRQUNkLE1BQU0scUJBQXFCLEdBQWdCLFFBQVEsQ0FBQyxhQUFhLENBQy9ELHNDQUFzQyxDQUN2QyxDQUFDO1FBQ0YsY0FBYyxHQUFHLHFCQUFxQixJQUFJLFNBQVMsQ0FBQztJQUN0RCxDQUFDO0lBRUQsT0FBTyxJQUFBLGVBQVcsRUFBQyxFQUFFLEdBQUcsRUFBRSxXQUFXLEVBQUUsY0FBYyxFQUFFLENBQUMsQ0FBQztBQUMzRCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGNyZWF0ZUNhY2hlIGZyb20gJ0BlbW90aW9uL2NhY2hlJztcblxuY29uc3QgaXNCcm93c2VyID0gdHlwZW9mIGRvY3VtZW50ICE9PSAndW5kZWZpbmVkJztcblxuLy8gT24gdGhlIGNsaWVudCBzaWRlLCBDcmVhdGUgYSBtZXRhIHRhZyBhdCB0aGUgdG9wIG9mIHRoZSA8aGVhZD4gYW5kIHNldCBpdCBhcyBpbnNlcnRpb25Qb2ludC5cbi8vIFRoaXMgYXNzdXJlcyB0aGF0IE1VSSBzdHlsZXMgYXJlIGxvYWRlZCBmaXJzdC5cbi8vIEl0IGFsbG93cyBkZXZlbG9wZXJzIHRvIGVhc2lseSBvdmVycmlkZSBNVUkgc3R5bGVzIHdpdGggb3RoZXIgc3R5bGluZyBzb2x1dGlvbnMsIGxpa2UgQ1NTIG1vZHVsZXMuXG5leHBvcnQgZGVmYXVsdCBmdW5jdGlvbiBjcmVhdGVFbW90aW9uQ2FjaGUoKSB7XG4gIGxldCBpbnNlcnRpb25Qb2ludDtcblxuICBpZiAoaXNCcm93c2VyKSB7XG4gICAgY29uc3QgZW1vdGlvbkluc2VydGlvblBvaW50OiBIVE1MRWxlbWVudCA9IGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoXG4gICAgICAnbWV0YVtuYW1lPVwiZW1vdGlvbi1pbnNlcnRpb24tcG9pbnRcIl0nXG4gICAgKTtcbiAgICBpbnNlcnRpb25Qb2ludCA9IGVtb3Rpb25JbnNlcnRpb25Qb2ludCA/PyB1bmRlZmluZWQ7XG4gIH1cblxuICByZXR1cm4gY3JlYXRlQ2FjaGUoeyBrZXk6ICdtdWktc3R5bGUnLCBpbnNlcnRpb25Qb2ludCB9KTtcbn1cbiJdfQ==