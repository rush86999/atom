"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseMDX = void 0;
const serialize_1 = require("next-mdx-remote/serialize");
const rehype_slug_1 = __importDefault(require("rehype-slug"));
const remark_gfm_1 = __importDefault(require("remark-gfm"));
// mdx content parser
const parseMDX = async (content) => {
    const options = {
        mdxOptions: {
            rehypePlugins: [rehype_slug_1.default],
            remarkPlugins: [remark_gfm_1.default],
        },
    };
    return await (0, serialize_1.serialize)(content, options);
};
exports.parseMDX = parseMDX;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibWR4UGFyc2VyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibWR4UGFyc2VyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUFBLHlEQUFzRDtBQUN0RCw4REFBcUM7QUFDckMsNERBQW1DO0FBR25DLHFCQUFxQjtBQUNkLE1BQU0sUUFBUSxHQUFHLEtBQUssRUFBRSxPQUFtQixFQUFFLEVBQUU7SUFDcEQsTUFBTSxPQUFPLEdBQUc7UUFDZCxVQUFVLEVBQUU7WUFDVixhQUFhLEVBQUUsQ0FBQyxxQkFBVSxDQUFDO1lBQzNCLGFBQWEsRUFBRSxDQUFDLG9CQUFTLENBQUM7U0FDM0I7S0FDRixDQUFDO0lBQ0YsT0FBTyxNQUFNLElBQUEscUJBQVMsRUFBQyxPQUFPLEVBQUUsT0FBTyxDQUFDLENBQUM7QUFDM0MsQ0FBQyxDQUFDO0FBUlcsUUFBQSxRQUFRLFlBUW5CIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgc2VyaWFsaXplIH0gZnJvbSAnbmV4dC1tZHgtcmVtb3RlL3NlcmlhbGl6ZSc7XG5pbXBvcnQgcmVoeXBlU2x1ZyBmcm9tICdyZWh5cGUtc2x1Zyc7XG5pbXBvcnQgcmVtYXJrR2ZtIGZyb20gJ3JlbWFyay1nZm0nO1xuaW1wb3J0IHsgQ29tcGF0aWJsZSB9IGZyb20gJ3ZmaWxlJztcblxuLy8gbWR4IGNvbnRlbnQgcGFyc2VyXG5leHBvcnQgY29uc3QgcGFyc2VNRFggPSBhc3luYyAoY29udGVudDogQ29tcGF0aWJsZSkgPT4ge1xuICBjb25zdCBvcHRpb25zID0ge1xuICAgIG1keE9wdGlvbnM6IHtcbiAgICAgIHJlaHlwZVBsdWdpbnM6IFtyZWh5cGVTbHVnXSxcbiAgICAgIHJlbWFya1BsdWdpbnM6IFtyZW1hcmtHZm1dLFxuICAgIH0sXG4gIH07XG4gIHJldHVybiBhd2FpdCBzZXJpYWxpemUoY29udGVudCwgb3B0aW9ucyk7XG59O1xuIl19