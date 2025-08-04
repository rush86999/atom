"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
function handler(req, res) {
    if (req.method === 'POST') {
        const audioData = req.body;
        const filePath = path_1.default.join(process.cwd(), 'silent-audio-recordings', `${Date.now()}.wav`);
        fs_1.default.writeFileSync(filePath, audioData);
        res.status(200).json({ message: 'Audio data saved successfully' });
    }
    else {
        res.status(405).json({ message: 'Method not allowed' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2lsZW50LWF1ZGlvLXJlY29yZGluZy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNpbGVudC1hdWRpby1yZWNvcmRpbmcudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFJQSwwQkFhQztBQWhCRCw0Q0FBb0I7QUFDcEIsZ0RBQXdCO0FBRXhCLFNBQXdCLE9BQU8sQ0FBQyxHQUFtQixFQUFFLEdBQW9CO0lBQ3ZFLElBQUksR0FBRyxDQUFDLE1BQU0sS0FBSyxNQUFNLEVBQUUsQ0FBQztRQUMxQixNQUFNLFNBQVMsR0FBRyxHQUFHLENBQUMsSUFBSSxDQUFDO1FBQzNCLE1BQU0sUUFBUSxHQUFHLGNBQUksQ0FBQyxJQUFJLENBQ3hCLE9BQU8sQ0FBQyxHQUFHLEVBQUUsRUFDYix5QkFBeUIsRUFDekIsR0FBRyxJQUFJLENBQUMsR0FBRyxFQUFFLE1BQU0sQ0FDcEIsQ0FBQztRQUNGLFlBQUUsQ0FBQyxhQUFhLENBQUMsUUFBUSxFQUFFLFNBQVMsQ0FBQyxDQUFDO1FBQ3RDLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLCtCQUErQixFQUFFLENBQUMsQ0FBQztJQUNyRSxDQUFDO1NBQU0sQ0FBQztRQUNOLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLG9CQUFvQixFQUFFLENBQUMsQ0FBQztJQUMxRCxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB0eXBlIHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IGZzIGZyb20gJ2ZzJztcbmltcG9ydCBwYXRoIGZyb20gJ3BhdGgnO1xuXG5leHBvcnQgZGVmYXVsdCBmdW5jdGlvbiBoYW5kbGVyKHJlcTogTmV4dEFwaVJlcXVlc3QsIHJlczogTmV4dEFwaVJlc3BvbnNlKSB7XG4gIGlmIChyZXEubWV0aG9kID09PSAnUE9TVCcpIHtcbiAgICBjb25zdCBhdWRpb0RhdGEgPSByZXEuYm9keTtcbiAgICBjb25zdCBmaWxlUGF0aCA9IHBhdGguam9pbihcbiAgICAgIHByb2Nlc3MuY3dkKCksXG4gICAgICAnc2lsZW50LWF1ZGlvLXJlY29yZGluZ3MnLFxuICAgICAgYCR7RGF0ZS5ub3coKX0ud2F2YFxuICAgICk7XG4gICAgZnMud3JpdGVGaWxlU3luYyhmaWxlUGF0aCwgYXVkaW9EYXRhKTtcbiAgICByZXMuc3RhdHVzKDIwMCkuanNvbih7IG1lc3NhZ2U6ICdBdWRpbyBkYXRhIHNhdmVkIHN1Y2Nlc3NmdWxseScgfSk7XG4gIH0gZWxzZSB7XG4gICAgcmVzLnN0YXR1cyg0MDUpLmpzb24oeyBtZXNzYWdlOiAnTWV0aG9kIG5vdCBhbGxvd2VkJyB9KTtcbiAgfVxufVxuIl19