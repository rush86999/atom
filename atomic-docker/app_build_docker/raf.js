"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const raf_1 = __importDefault(require("raf"));
const polys = {};
raf_1.default.polyfill(polys);
// module.exports = polys.requestAnimationFrame;
exports.default = polys.requestAnimationFrame;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmFmLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicmFmLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7O0FBQUEsOENBQXNCO0FBQ3RCLE1BQU0sS0FBSyxHQUFRLEVBQUUsQ0FBQztBQUN0QixhQUFHLENBQUMsUUFBUSxDQUFDLEtBQUssQ0FBQyxDQUFDO0FBRXBCLGdEQUFnRDtBQUVoRCxrQkFBZSxLQUFLLENBQUMscUJBQXFCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgcmFmIGZyb20gJ3JhZic7XG5jb25zdCBwb2x5czogYW55ID0ge307XG5yYWYucG9seWZpbGwocG9seXMpO1xuXG4vLyBtb2R1bGUuZXhwb3J0cyA9IHBvbHlzLnJlcXVlc3RBbmltYXRpb25GcmFtZTtcblxuZXhwb3J0IGRlZmF1bHQgcG9seXMucmVxdWVzdEFuaW1hdGlvbkZyYW1lO1xuIl19