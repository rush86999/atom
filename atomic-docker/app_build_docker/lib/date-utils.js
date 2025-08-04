"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.Dayjs = exports.dayjs = void 0;
const dayjs_1 = __importStar(require("dayjs"));
exports.dayjs = dayjs_1.default;
Object.defineProperty(exports, "Dayjs", { enumerable: true, get: function () { return dayjs_1.Dayjs; } });
const utc_1 = __importDefault(require("dayjs/plugin/utc"));
const timezone_1 = __importDefault(require("dayjs/plugin/timezone"));
const localizedFormat_1 = __importDefault(require("dayjs/plugin/localizedFormat"));
const advancedFormat_1 = __importDefault(require("dayjs/plugin/advancedFormat"));
const customParseFormat_1 = __importDefault(require("dayjs/plugin/customParseFormat"));
const isBetween_1 = __importDefault(require("dayjs/plugin/isBetween"));
const isYesterday_1 = __importDefault(require("dayjs/plugin/isYesterday"));
const isToday_1 = __importDefault(require("dayjs/plugin/isToday"));
const isTomorrow_1 = __importDefault(require("dayjs/plugin/isTomorrow"));
const relativeTime_1 = __importDefault(require("dayjs/plugin/relativeTime"));
const duration_1 = __importDefault(require("dayjs/plugin/duration"));
// import isoWeek from 'dayjs/plugin/isoWeek'
const isSameOrAfter_1 = __importDefault(require("dayjs/plugin/isSameOrAfter"));
const weekOfYear_1 = __importDefault(require("dayjs/plugin/weekOfYear"));
const isLeapYear_1 = __importDefault(require("dayjs/plugin/isLeapYear"));
const quarterOfYear_1 = __importDefault(require("dayjs/plugin/quarterOfYear"));
require("dayjs/locale/en");
dayjs_1.default.extend(utc_1.default);
dayjs_1.default.extend(timezone_1.default);
dayjs_1.default.extend(localizedFormat_1.default);
dayjs_1.default.extend(advancedFormat_1.default);
dayjs_1.default.extend(customParseFormat_1.default);
dayjs_1.default.extend(isBetween_1.default);
dayjs_1.default.extend(isYesterday_1.default);
dayjs_1.default.extend(isToday_1.default);
dayjs_1.default.extend(isTomorrow_1.default);
dayjs_1.default.extend(relativeTime_1.default);
dayjs_1.default.extend(duration_1.default);
// dayjs.extend(isoWeek)
dayjs_1.default.extend(isSameOrAfter_1.default);
dayjs_1.default.extend(weekOfYear_1.default);
dayjs_1.default.extend(isLeapYear_1.default);
dayjs_1.default.extend(quarterOfYear_1.default);
dayjs_1.default.locale('en');
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGF0ZS11dGlscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRhdGUtdXRpbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0FBQUEsK0NBQXFDO0FBc0M1QixnQkF0Q0YsZUFBSyxDQXNDRTtBQUFFLHNGQXRDQSxhQUFLLE9Bc0NBO0FBckNyQiwyREFBbUM7QUFDbkMscUVBQTZDO0FBQzdDLG1GQUEyRDtBQUMzRCxpRkFBeUQ7QUFDekQsdUZBQStEO0FBQy9ELHVFQUErQztBQUMvQywyRUFBbUQ7QUFDbkQsbUVBQTJDO0FBQzNDLHlFQUFpRDtBQUNqRCw2RUFBcUQ7QUFDckQscUVBQTZDO0FBQzdDLDZDQUE2QztBQUM3QywrRUFBdUQ7QUFDdkQseUVBQWlEO0FBQ2pELHlFQUFpRDtBQUNqRCwrRUFBdUQ7QUFFdkQsMkJBQXlCO0FBRXpCLGVBQUssQ0FBQyxNQUFNLENBQUMsYUFBRyxDQUFDLENBQUM7QUFDbEIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxrQkFBUSxDQUFDLENBQUM7QUFDdkIsZUFBSyxDQUFDLE1BQU0sQ0FBQyx5QkFBZSxDQUFDLENBQUM7QUFDOUIsZUFBSyxDQUFDLE1BQU0sQ0FBQyx3QkFBYyxDQUFDLENBQUM7QUFDN0IsZUFBSyxDQUFDLE1BQU0sQ0FBQywyQkFBaUIsQ0FBQyxDQUFDO0FBQ2hDLGVBQUssQ0FBQyxNQUFNLENBQUMsbUJBQVMsQ0FBQyxDQUFDO0FBQ3hCLGVBQUssQ0FBQyxNQUFNLENBQUMscUJBQVcsQ0FBQyxDQUFDO0FBQzFCLGVBQUssQ0FBQyxNQUFNLENBQUMsaUJBQU8sQ0FBQyxDQUFDO0FBQ3RCLGVBQUssQ0FBQyxNQUFNLENBQUMsb0JBQVUsQ0FBQyxDQUFDO0FBQ3pCLGVBQUssQ0FBQyxNQUFNLENBQUMsc0JBQVksQ0FBQyxDQUFDO0FBQzNCLGVBQUssQ0FBQyxNQUFNLENBQUMsa0JBQVEsQ0FBQyxDQUFDO0FBQ3ZCLHdCQUF3QjtBQUN4QixlQUFLLENBQUMsTUFBTSxDQUFDLHVCQUFhLENBQUMsQ0FBQztBQUM1QixlQUFLLENBQUMsTUFBTSxDQUFDLG9CQUFVLENBQUMsQ0FBQztBQUN6QixlQUFLLENBQUMsTUFBTSxDQUFDLG9CQUFVLENBQUMsQ0FBQztBQUN6QixlQUFLLENBQUMsTUFBTSxDQUFDLHVCQUFhLENBQUMsQ0FBQztBQUM1QixlQUFLLENBQUMsTUFBTSxDQUFDLElBQUksQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGRheWpzLCB7IERheWpzIH0gZnJvbSAnZGF5anMnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcbmltcG9ydCB0aW1lem9uZSBmcm9tICdkYXlqcy9wbHVnaW4vdGltZXpvbmUnO1xuaW1wb3J0IGxvY2FsaXplZEZvcm1hdCBmcm9tICdkYXlqcy9wbHVnaW4vbG9jYWxpemVkRm9ybWF0JztcbmltcG9ydCBhZHZhbmNlZEZvcm1hdCBmcm9tICdkYXlqcy9wbHVnaW4vYWR2YW5jZWRGb3JtYXQnO1xuaW1wb3J0IGN1c3RvbVBhcnNlRm9ybWF0IGZyb20gJ2RheWpzL3BsdWdpbi9jdXN0b21QYXJzZUZvcm1hdCc7XG5pbXBvcnQgaXNCZXR3ZWVuIGZyb20gJ2RheWpzL3BsdWdpbi9pc0JldHdlZW4nO1xuaW1wb3J0IGlzWWVzdGVyZGF5IGZyb20gJ2RheWpzL3BsdWdpbi9pc1llc3RlcmRheSc7XG5pbXBvcnQgaXNUb2RheSBmcm9tICdkYXlqcy9wbHVnaW4vaXNUb2RheSc7XG5pbXBvcnQgaXNUb21vcnJvdyBmcm9tICdkYXlqcy9wbHVnaW4vaXNUb21vcnJvdyc7XG5pbXBvcnQgcmVsYXRpdmVUaW1lIGZyb20gJ2RheWpzL3BsdWdpbi9yZWxhdGl2ZVRpbWUnO1xuaW1wb3J0IGR1cmF0aW9uIGZyb20gJ2RheWpzL3BsdWdpbi9kdXJhdGlvbic7XG4vLyBpbXBvcnQgaXNvV2VlayBmcm9tICdkYXlqcy9wbHVnaW4vaXNvV2VlaydcbmltcG9ydCBpc1NhbWVPckFmdGVyIGZyb20gJ2RheWpzL3BsdWdpbi9pc1NhbWVPckFmdGVyJztcbmltcG9ydCB3ZWVrT2ZZZWFyIGZyb20gJ2RheWpzL3BsdWdpbi93ZWVrT2ZZZWFyJztcbmltcG9ydCBpc0xlYXBZZWFyIGZyb20gJ2RheWpzL3BsdWdpbi9pc0xlYXBZZWFyJztcbmltcG9ydCBxdWFydGVyT2ZZZWFyIGZyb20gJ2RheWpzL3BsdWdpbi9xdWFydGVyT2ZZZWFyJztcblxuaW1wb3J0ICdkYXlqcy9sb2NhbGUvZW4nO1xuXG5kYXlqcy5leHRlbmQodXRjKTtcbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5kYXlqcy5leHRlbmQobG9jYWxpemVkRm9ybWF0KTtcbmRheWpzLmV4dGVuZChhZHZhbmNlZEZvcm1hdCk7XG5kYXlqcy5leHRlbmQoY3VzdG9tUGFyc2VGb3JtYXQpO1xuZGF5anMuZXh0ZW5kKGlzQmV0d2Vlbik7XG5kYXlqcy5leHRlbmQoaXNZZXN0ZXJkYXkpO1xuZGF5anMuZXh0ZW5kKGlzVG9kYXkpO1xuZGF5anMuZXh0ZW5kKGlzVG9tb3Jyb3cpO1xuZGF5anMuZXh0ZW5kKHJlbGF0aXZlVGltZSk7XG5kYXlqcy5leHRlbmQoZHVyYXRpb24pO1xuLy8gZGF5anMuZXh0ZW5kKGlzb1dlZWspXG5kYXlqcy5leHRlbmQoaXNTYW1lT3JBZnRlcik7XG5kYXlqcy5leHRlbmQod2Vla09mWWVhcik7XG5kYXlqcy5leHRlbmQoaXNMZWFwWWVhcik7XG5kYXlqcy5leHRlbmQocXVhcnRlck9mWWVhcik7XG5kYXlqcy5sb2NhbGUoJ2VuJyk7XG5cbmV4cG9ydCB7IGRheWpzLCBEYXlqcyB9O1xuIl19