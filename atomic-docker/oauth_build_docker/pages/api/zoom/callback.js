"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const qs_1 = __importDefault(require("qs"));
const cors_1 = __importDefault(require("cors"));
const constants_1 = require("@lib/constants");
// Initializing the cors middleware
// You can read more about the available options here: https://github.com/expressjs/cors#configuration-options
const cors = (0, cors_1.default)({
    methods: ['POST', 'GET', 'HEAD'],
    origin: ['https://atomiclife.app', /\.atomiclife\.app$/],
});
// Helper method to wait for a middleware to execute before continuing
// And to throw an error when an error happens in a middleware
function runMiddleware(req, res, fn) {
    return new Promise((resolve, reject) => {
        fn(req, res, (result) => {
            if (result instanceof Error) {
                return reject(result);
            }
            return resolve(result);
        });
    });
}
async function handler(req, res) {
    // Run the middleware
    await runMiddleware(req, res, cors);
    const { code, state } = req.query;
    if (!code) {
        console.log(' no code present');
        return;
    }
    let params = { code };
    if (state && state?.length > 0) {
        params = { ...params, state };
    }
    return res.redirect(`${constants_1.appUrl}?${qs_1.default.stringify(params)}`);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsbGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxsYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQThCQSwwQkFxQkM7QUFsREQsNENBQW9CO0FBQ3BCLGdEQUF3QjtBQUN4Qiw4Q0FBd0M7QUFFeEMsbUNBQW1DO0FBQ25DLDhHQUE4RztBQUM5RyxNQUFNLElBQUksR0FBRyxJQUFBLGNBQUksRUFBQztJQUNoQixPQUFPLEVBQUUsQ0FBQyxNQUFNLEVBQUUsS0FBSyxFQUFFLE1BQU0sQ0FBQztJQUNoQyxNQUFNLEVBQUUsQ0FBQyx3QkFBd0IsRUFBRSxvQkFBb0IsQ0FBQztDQUN6RCxDQUFDLENBQUM7QUFFSCxzRUFBc0U7QUFDdEUsOERBQThEO0FBQzlELFNBQVMsYUFBYSxDQUNwQixHQUFtQixFQUNuQixHQUFvQixFQUNwQixFQUFZO0lBRVosT0FBTyxJQUFJLE9BQU8sQ0FBQyxDQUFDLE9BQU8sRUFBRSxNQUFNLEVBQUUsRUFBRTtRQUNyQyxFQUFFLENBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRSxDQUFDLE1BQVcsRUFBRSxFQUFFO1lBQzNCLElBQUksTUFBTSxZQUFZLEtBQUssRUFBRSxDQUFDO2dCQUM1QixPQUFPLE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQztZQUN4QixDQUFDO1lBRUQsT0FBTyxPQUFPLENBQUMsTUFBTSxDQUFDLENBQUM7UUFDekIsQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUM7QUFFYyxLQUFLLFVBQVUsT0FBTyxDQUNuQyxHQUFtQixFQUNuQixHQUFvQjtJQUVwQixxQkFBcUI7SUFDckIsTUFBTSxhQUFhLENBQUMsR0FBRyxFQUFFLEdBQUcsRUFBRSxJQUFJLENBQUMsQ0FBQztJQUVwQyxNQUFNLEVBQUUsSUFBSSxFQUFFLEtBQUssRUFBRSxHQUFHLEdBQUcsQ0FBQyxLQUFLLENBQUM7SUFFbEMsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO1FBQ1YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDO1FBQ2hDLE9BQU87SUFDVCxDQUFDO0lBRUQsSUFBSSxNQUFNLEdBQVEsRUFBRSxJQUFJLEVBQUUsQ0FBQztJQUUzQixJQUFJLEtBQUssSUFBSSxLQUFLLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1FBQy9CLE1BQU0sR0FBRyxFQUFFLEdBQUcsTUFBTSxFQUFFLEtBQUssRUFBRSxDQUFDO0lBQ2hDLENBQUM7SUFFRCxPQUFPLEdBQUcsQ0FBQyxRQUFRLENBQUMsR0FBRyxrQkFBTSxJQUFJLFlBQUUsQ0FBQyxTQUFTLENBQUMsTUFBTSxDQUFDLEVBQUUsQ0FBQyxDQUFDO0FBQzNELENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBxcyBmcm9tICdxcyc7XG5pbXBvcnQgQ29ycyBmcm9tICdjb3JzJztcbmltcG9ydCB7IGFwcFVybCB9IGZyb20gJ0BsaWIvY29uc3RhbnRzJztcblxuLy8gSW5pdGlhbGl6aW5nIHRoZSBjb3JzIG1pZGRsZXdhcmVcbi8vIFlvdSBjYW4gcmVhZCBtb3JlIGFib3V0IHRoZSBhdmFpbGFibGUgb3B0aW9ucyBoZXJlOiBodHRwczovL2dpdGh1Yi5jb20vZXhwcmVzc2pzL2NvcnMjY29uZmlndXJhdGlvbi1vcHRpb25zXG5jb25zdCBjb3JzID0gQ29ycyh7XG4gIG1ldGhvZHM6IFsnUE9TVCcsICdHRVQnLCAnSEVBRCddLFxuICBvcmlnaW46IFsnaHR0cHM6Ly9hdG9taWNsaWZlLmFwcCcsIC9cXC5hdG9taWNsaWZlXFwuYXBwJC9dLFxufSk7XG5cbi8vIEhlbHBlciBtZXRob2QgdG8gd2FpdCBmb3IgYSBtaWRkbGV3YXJlIHRvIGV4ZWN1dGUgYmVmb3JlIGNvbnRpbnVpbmdcbi8vIEFuZCB0byB0aHJvdyBhbiBlcnJvciB3aGVuIGFuIGVycm9yIGhhcHBlbnMgaW4gYSBtaWRkbGV3YXJlXG5mdW5jdGlvbiBydW5NaWRkbGV3YXJlKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZSxcbiAgZm46IEZ1bmN0aW9uXG4pIHtcbiAgcmV0dXJuIG5ldyBQcm9taXNlKChyZXNvbHZlLCByZWplY3QpID0+IHtcbiAgICBmbihyZXEsIHJlcywgKHJlc3VsdDogYW55KSA9PiB7XG4gICAgICBpZiAocmVzdWx0IGluc3RhbmNlb2YgRXJyb3IpIHtcbiAgICAgICAgcmV0dXJuIHJlamVjdChyZXN1bHQpO1xuICAgICAgfVxuXG4gICAgICByZXR1cm4gcmVzb2x2ZShyZXN1bHQpO1xuICAgIH0pO1xuICB9KTtcbn1cblxuZXhwb3J0IGRlZmF1bHQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlcihcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2Vcbikge1xuICAvLyBSdW4gdGhlIG1pZGRsZXdhcmVcbiAgYXdhaXQgcnVuTWlkZGxld2FyZShyZXEsIHJlcywgY29ycyk7XG5cbiAgY29uc3QgeyBjb2RlLCBzdGF0ZSB9ID0gcmVxLnF1ZXJ5O1xuXG4gIGlmICghY29kZSkge1xuICAgIGNvbnNvbGUubG9nKCcgbm8gY29kZSBwcmVzZW50Jyk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgbGV0IHBhcmFtczogYW55ID0geyBjb2RlIH07XG5cbiAgaWYgKHN0YXRlICYmIHN0YXRlPy5sZW5ndGggPiAwKSB7XG4gICAgcGFyYW1zID0geyAuLi5wYXJhbXMsIHN0YXRlIH07XG4gIH1cblxuICByZXR1cm4gcmVzLnJlZGlyZWN0KGAke2FwcFVybH0/JHtxcy5zdHJpbmdpZnkocGFyYW1zKX1gKTtcbn1cbiJdfQ==