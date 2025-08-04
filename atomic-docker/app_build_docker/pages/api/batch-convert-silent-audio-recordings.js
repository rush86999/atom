"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const child_process_1 = require("child_process");
function handler(req, res) {
    if (req.method === 'POST') {
        const recordingsDir = path_1.default.join(process.cwd(), 'silent-audio-recordings');
        const files = fs_1.default.readdirSync(recordingsDir);
        files.forEach((file) => {
            if (file.endsWith('.wav')) {
                const wavFilePath = path_1.default.join(recordingsDir, file);
                const mp3FilePath = path_1.default.join(recordingsDir, file.replace('.wav', '.mp3'));
                (0, child_process_1.exec)(`ffmpeg -i ${wavFilePath} ${mp3FilePath}`, (error, stdout, stderr) => {
                    if (error) {
                        console.error(`exec error: ${error}`);
                        return;
                    }
                    fs_1.default.unlinkSync(wavFilePath);
                });
            }
        });
        res.status(200).json({ message: 'Batch conversion started' });
    }
    else {
        res.status(405).json({ message: 'Method not allowed' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYmF0Y2gtY29udmVydC1zaWxlbnQtYXVkaW8tcmVjb3JkaW5ncy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImJhdGNoLWNvbnZlcnQtc2lsZW50LWF1ZGlvLXJlY29yZGluZ3MudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFLQSwwQkEyQkM7QUEvQkQsNENBQW9CO0FBQ3BCLGdEQUF3QjtBQUN4QixpREFBcUM7QUFFckMsU0FBd0IsT0FBTyxDQUFDLEdBQW1CLEVBQUUsR0FBb0I7SUFDdkUsSUFBSSxHQUFHLENBQUMsTUFBTSxLQUFLLE1BQU0sRUFBRSxDQUFDO1FBQzFCLE1BQU0sYUFBYSxHQUFHLGNBQUksQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLEdBQUcsRUFBRSxFQUFFLHlCQUF5QixDQUFDLENBQUM7UUFDMUUsTUFBTSxLQUFLLEdBQUcsWUFBRSxDQUFDLFdBQVcsQ0FBQyxhQUFhLENBQUMsQ0FBQztRQUM1QyxLQUFLLENBQUMsT0FBTyxDQUFDLENBQUMsSUFBSSxFQUFFLEVBQUU7WUFDckIsSUFBSSxJQUFJLENBQUMsUUFBUSxDQUFDLE1BQU0sQ0FBQyxFQUFFLENBQUM7Z0JBQzFCLE1BQU0sV0FBVyxHQUFHLGNBQUksQ0FBQyxJQUFJLENBQUMsYUFBYSxFQUFFLElBQUksQ0FBQyxDQUFDO2dCQUNuRCxNQUFNLFdBQVcsR0FBRyxjQUFJLENBQUMsSUFBSSxDQUMzQixhQUFhLEVBQ2IsSUFBSSxDQUFDLE9BQU8sQ0FBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLENBQzdCLENBQUM7Z0JBQ0YsSUFBQSxvQkFBSSxFQUNGLGFBQWEsV0FBVyxJQUFJLFdBQVcsRUFBRSxFQUN6QyxDQUFDLEtBQUssRUFBRSxNQUFNLEVBQUUsTUFBTSxFQUFFLEVBQUU7b0JBQ3hCLElBQUksS0FBSyxFQUFFLENBQUM7d0JBQ1YsT0FBTyxDQUFDLEtBQUssQ0FBQyxlQUFlLEtBQUssRUFBRSxDQUFDLENBQUM7d0JBQ3RDLE9BQU87b0JBQ1QsQ0FBQztvQkFDRCxZQUFFLENBQUMsVUFBVSxDQUFDLFdBQVcsQ0FBQyxDQUFDO2dCQUM3QixDQUFDLENBQ0YsQ0FBQztZQUNKLENBQUM7UUFDSCxDQUFDLENBQUMsQ0FBQztRQUNILEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLDBCQUEwQixFQUFFLENBQUMsQ0FBQztJQUNoRSxDQUFDO1NBQU0sQ0FBQztRQUNOLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLG9CQUFvQixFQUFFLENBQUMsQ0FBQztJQUMxRCxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB0eXBlIHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IGZzIGZyb20gJ2ZzJztcbmltcG9ydCBwYXRoIGZyb20gJ3BhdGgnO1xuaW1wb3J0IHsgZXhlYyB9IGZyb20gJ2NoaWxkX3Byb2Nlc3MnO1xuXG5leHBvcnQgZGVmYXVsdCBmdW5jdGlvbiBoYW5kbGVyKHJlcTogTmV4dEFwaVJlcXVlc3QsIHJlczogTmV4dEFwaVJlc3BvbnNlKSB7XG4gIGlmIChyZXEubWV0aG9kID09PSAnUE9TVCcpIHtcbiAgICBjb25zdCByZWNvcmRpbmdzRGlyID0gcGF0aC5qb2luKHByb2Nlc3MuY3dkKCksICdzaWxlbnQtYXVkaW8tcmVjb3JkaW5ncycpO1xuICAgIGNvbnN0IGZpbGVzID0gZnMucmVhZGRpclN5bmMocmVjb3JkaW5nc0Rpcik7XG4gICAgZmlsZXMuZm9yRWFjaCgoZmlsZSkgPT4ge1xuICAgICAgaWYgKGZpbGUuZW5kc1dpdGgoJy53YXYnKSkge1xuICAgICAgICBjb25zdCB3YXZGaWxlUGF0aCA9IHBhdGguam9pbihyZWNvcmRpbmdzRGlyLCBmaWxlKTtcbiAgICAgICAgY29uc3QgbXAzRmlsZVBhdGggPSBwYXRoLmpvaW4oXG4gICAgICAgICAgcmVjb3JkaW5nc0RpcixcbiAgICAgICAgICBmaWxlLnJlcGxhY2UoJy53YXYnLCAnLm1wMycpXG4gICAgICAgICk7XG4gICAgICAgIGV4ZWMoXG4gICAgICAgICAgYGZmbXBlZyAtaSAke3dhdkZpbGVQYXRofSAke21wM0ZpbGVQYXRofWAsXG4gICAgICAgICAgKGVycm9yLCBzdGRvdXQsIHN0ZGVycikgPT4ge1xuICAgICAgICAgICAgaWYgKGVycm9yKSB7XG4gICAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoYGV4ZWMgZXJyb3I6ICR7ZXJyb3J9YCk7XG4gICAgICAgICAgICAgIHJldHVybjtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGZzLnVubGlua1N5bmMod2F2RmlsZVBhdGgpO1xuICAgICAgICAgIH1cbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9KTtcbiAgICByZXMuc3RhdHVzKDIwMCkuanNvbih7IG1lc3NhZ2U6ICdCYXRjaCBjb252ZXJzaW9uIHN0YXJ0ZWQnIH0pO1xuICB9IGVsc2Uge1xuICAgIHJlcy5zdGF0dXMoNDA1KS5qc29uKHsgbWVzc2FnZTogJ01ldGhvZCBub3QgYWxsb3dlZCcgfSk7XG4gIH1cbn1cbiJdfQ==