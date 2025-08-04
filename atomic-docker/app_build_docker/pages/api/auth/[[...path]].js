"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = superTokens;
const nextjs_1 = require("supertokens-node/nextjs");
const express_1 = require("supertokens-node/framework/express");
const supertokens_node_1 = __importDefault(require("supertokens-node"));
const backendConfig_1 = require("../../../config/backendConfig");
const nextjs_cors_1 = __importDefault(require("nextjs-cors"));
supertokens_node_1.default.init((0, backendConfig_1.backendConfig)());
async function superTokens(req, res) {
    // NOTE: We need CORS only if we are querying the APIs from a different origin
    await (0, nextjs_cors_1.default)(req, res, {
        methods: ['GET', 'HEAD', 'PUT', 'PATCH', 'POST', 'DELETE'],
        origin: 'https://tunnel.cloudflare-domain.co',
        credentials: true,
        allowedHeaders: ['content-type', ...supertokens_node_1.default.getAllCORSHeaders()],
    });
    await (0, nextjs_1.superTokensNextWrapper)(async (next) => {
        // This is needed for production deployments with Vercel
        res.setHeader('Cache-Control', 'no-cache, no-store, max-age=0, must-revalidate');
        await (0, express_1.middleware)()(req, res, next);
    }, req, res);
    if (!res.writableEnded) {
        res.status(404).send('Not found');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiW1suLi5wYXRoXV0uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJbWy4uLnBhdGhdXS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQVVBLDhCQTJCQztBQXJDRCxvREFBaUU7QUFDakUsZ0VBQWdFO0FBR2hFLHdFQUEyQztBQUMzQyxpRUFBOEQ7QUFDOUQsOERBQW1DO0FBRW5DLDBCQUFXLENBQUMsSUFBSSxDQUFDLElBQUEsNkJBQWEsR0FBRSxDQUFDLENBQUM7QUFFbkIsS0FBSyxVQUFVLFdBQVcsQ0FDdkMsR0FBNkIsRUFDN0IsR0FBK0I7SUFFL0IsOEVBQThFO0lBQzlFLE1BQU0sSUFBQSxxQkFBUSxFQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7UUFDdkIsT0FBTyxFQUFFLENBQUMsS0FBSyxFQUFFLE1BQU0sRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLE1BQU0sRUFBRSxRQUFRLENBQUM7UUFDMUQsTUFBTSxFQUFFLHFDQUFxQztRQUM3QyxXQUFXLEVBQUUsSUFBSTtRQUNqQixjQUFjLEVBQUUsQ0FBQyxjQUFjLEVBQUUsR0FBRywwQkFBVyxDQUFDLGlCQUFpQixFQUFFLENBQUM7S0FDckUsQ0FBQyxDQUFDO0lBRUgsTUFBTSxJQUFBLCtCQUFzQixFQUMxQixLQUFLLEVBQUUsSUFBSSxFQUFFLEVBQUU7UUFDYix3REFBd0Q7UUFDeEQsR0FBRyxDQUFDLFNBQVMsQ0FDWCxlQUFlLEVBQ2YsZ0RBQWdELENBQ2pELENBQUM7UUFDRixNQUFNLElBQUEsb0JBQVUsR0FBRSxDQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUUsSUFBSSxDQUFDLENBQUM7SUFDckMsQ0FBQyxFQUNELEdBQUcsRUFDSCxHQUFHLENBQ0osQ0FBQztJQUNGLElBQUksQ0FBQyxHQUFHLENBQUMsYUFBYSxFQUFFLENBQUM7UUFDdkIsR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsV0FBVyxDQUFDLENBQUM7SUFDcEMsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBzdXBlclRva2Vuc05leHRXcmFwcGVyIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9uZXh0anMnO1xuaW1wb3J0IHsgbWlkZGxld2FyZSB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvZnJhbWV3b3JrL2V4cHJlc3MnO1xuaW1wb3J0IHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbmltcG9ydCBzdXBlcnRva2VucyBmcm9tICdzdXBlcnRva2Vucy1ub2RlJztcbmltcG9ydCB7IGJhY2tlbmRDb25maWcgfSBmcm9tICcuLi8uLi8uLi9jb25maWcvYmFja2VuZENvbmZpZyc7XG5pbXBvcnQgTmV4dENvcnMgZnJvbSAnbmV4dGpzLWNvcnMnO1xuXG5zdXBlcnRva2Vucy5pbml0KGJhY2tlbmRDb25maWcoKSk7XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIHN1cGVyVG9rZW5zKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0ICYgUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2UgJiBSZXNwb25zZVxuKSB7XG4gIC8vIE5PVEU6IFdlIG5lZWQgQ09SUyBvbmx5IGlmIHdlIGFyZSBxdWVyeWluZyB0aGUgQVBJcyBmcm9tIGEgZGlmZmVyZW50IG9yaWdpblxuICBhd2FpdCBOZXh0Q29ycyhyZXEsIHJlcywge1xuICAgIG1ldGhvZHM6IFsnR0VUJywgJ0hFQUQnLCAnUFVUJywgJ1BBVENIJywgJ1BPU1QnLCAnREVMRVRFJ10sXG4gICAgb3JpZ2luOiAnaHR0cHM6Ly90dW5uZWwuY2xvdWRmbGFyZS1kb21haW4uY28nLFxuICAgIGNyZWRlbnRpYWxzOiB0cnVlLFxuICAgIGFsbG93ZWRIZWFkZXJzOiBbJ2NvbnRlbnQtdHlwZScsIC4uLnN1cGVydG9rZW5zLmdldEFsbENPUlNIZWFkZXJzKCldLFxuICB9KTtcblxuICBhd2FpdCBzdXBlclRva2Vuc05leHRXcmFwcGVyKFxuICAgIGFzeW5jIChuZXh0KSA9PiB7XG4gICAgICAvLyBUaGlzIGlzIG5lZWRlZCBmb3IgcHJvZHVjdGlvbiBkZXBsb3ltZW50cyB3aXRoIFZlcmNlbFxuICAgICAgcmVzLnNldEhlYWRlcihcbiAgICAgICAgJ0NhY2hlLUNvbnRyb2wnLFxuICAgICAgICAnbm8tY2FjaGUsIG5vLXN0b3JlLCBtYXgtYWdlPTAsIG11c3QtcmV2YWxpZGF0ZSdcbiAgICAgICk7XG4gICAgICBhd2FpdCBtaWRkbGV3YXJlKCkocmVxLCByZXMsIG5leHQpO1xuICAgIH0sXG4gICAgcmVxLFxuICAgIHJlc1xuICApO1xuICBpZiAoIXJlcy53cml0YWJsZUVuZGVkKSB7XG4gICAgcmVzLnN0YXR1cyg0MDQpLnNlbmQoJ05vdCBmb3VuZCcpO1xuICB9XG59XG4iXX0=