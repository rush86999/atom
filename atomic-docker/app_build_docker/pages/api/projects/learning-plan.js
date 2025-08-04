"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const nextjs_1 = require("supertokens-node/nextjs");
const learningAssistantSkills_1 = require("../../../../project/functions/atom-agent/skills/learningAssistantSkills");
async function handler(req, res) {
    let session;
    try {
        session = await (0, nextjs_1.getSession)(req, res, {
            overrideGlobalClaimValidators: () => [],
        });
    }
    catch (err) {
        return res.status(401).json({ message: 'Unauthorized' });
    }
    const userId = session.getUserId();
    const { notionDatabaseId } = req.body;
    if (!notionDatabaseId) {
        return res.status(400).json({ message: 'Notion Database ID is required' });
    }
    try {
        await (0, learningAssistantSkills_1.generateLearningPlan)(userId, notionDatabaseId);
        return res.status(200).json({ message: 'Learning plan generated' });
    }
    catch (error) {
        console.error('Error generating learning plan:', error);
        return res
            .status(500)
            .json({ message: 'Failed to generate learning plan' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGVhcm5pbmctcGxhbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxlYXJuaW5nLXBsYW4udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFLQSwwQkE2QkM7QUFqQ0Qsb0RBQXFEO0FBRXJELHFIQUErRztBQUVoRyxLQUFLLFVBQVUsT0FBTyxDQUNuQyxHQUFtQixFQUNuQixHQUFvQjtJQUVwQixJQUFJLE9BQXlCLENBQUM7SUFDOUIsSUFBSSxDQUFDO1FBQ0gsT0FBTyxHQUFHLE1BQU0sSUFBQSxtQkFBVSxFQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDbkMsNkJBQTZCLEVBQUUsR0FBRyxFQUFFLENBQUMsRUFBRTtTQUN4QyxDQUFDLENBQUM7SUFDTCxDQUFDO0lBQUMsT0FBTyxHQUFHLEVBQUUsQ0FBQztRQUNiLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsY0FBYyxFQUFFLENBQUMsQ0FBQztJQUMzRCxDQUFDO0lBRUQsTUFBTSxNQUFNLEdBQUcsT0FBTyxDQUFDLFNBQVMsRUFBRSxDQUFDO0lBQ25DLE1BQU0sRUFBRSxnQkFBZ0IsRUFBRSxHQUFHLEdBQUcsQ0FBQyxJQUFJLENBQUM7SUFFdEMsSUFBSSxDQUFDLGdCQUFnQixFQUFFLENBQUM7UUFDdEIsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxnQ0FBZ0MsRUFBRSxDQUFDLENBQUM7SUFDN0UsQ0FBQztJQUVELElBQUksQ0FBQztRQUNILE1BQU0sSUFBQSw4Q0FBb0IsRUFBQyxNQUFNLEVBQUUsZ0JBQWdCLENBQUMsQ0FBQztRQUNyRCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLHlCQUF5QixFQUFFLENBQUMsQ0FBQztJQUN0RSxDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sQ0FBQyxLQUFLLENBQUMsaUNBQWlDLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDeEQsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxrQ0FBa0MsRUFBRSxDQUFDLENBQUM7SUFDM0QsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgeyBnZXRTZXNzaW9uIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9uZXh0anMnO1xuaW1wb3J0IHsgU2Vzc2lvbkNvbnRhaW5lciB9IGZyb20gJ3N1cGVydG9rZW5zLW5vZGUvcmVjaXBlL3Nlc3Npb24nO1xuaW1wb3J0IHsgZ2VuZXJhdGVMZWFybmluZ1BsYW4gfSBmcm9tICcuLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L3NraWxscy9sZWFybmluZ0Fzc2lzdGFudFNraWxscyc7XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgbGV0IHNlc3Npb246IFNlc3Npb25Db250YWluZXI7XG4gIHRyeSB7XG4gICAgc2Vzc2lvbiA9IGF3YWl0IGdldFNlc3Npb24ocmVxLCByZXMsIHtcbiAgICAgIG92ZXJyaWRlR2xvYmFsQ2xhaW1WYWxpZGF0b3JzOiAoKSA9PiBbXSxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZXJyKSB7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAxKS5qc29uKHsgbWVzc2FnZTogJ1VuYXV0aG9yaXplZCcgfSk7XG4gIH1cblxuICBjb25zdCB1c2VySWQgPSBzZXNzaW9uLmdldFVzZXJJZCgpO1xuICBjb25zdCB7IG5vdGlvbkRhdGFiYXNlSWQgfSA9IHJlcS5ib2R5O1xuXG4gIGlmICghbm90aW9uRGF0YWJhc2VJZCkge1xuICAgIHJldHVybiByZXMuc3RhdHVzKDQwMCkuanNvbih7IG1lc3NhZ2U6ICdOb3Rpb24gRGF0YWJhc2UgSUQgaXMgcmVxdWlyZWQnIH0pO1xuICB9XG5cbiAgdHJ5IHtcbiAgICBhd2FpdCBnZW5lcmF0ZUxlYXJuaW5nUGxhbih1c2VySWQsIG5vdGlvbkRhdGFiYXNlSWQpO1xuICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7IG1lc3NhZ2U6ICdMZWFybmluZyBwbGFuIGdlbmVyYXRlZCcgfSk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgZ2VuZXJhdGluZyBsZWFybmluZyBwbGFuOicsIGVycm9yKTtcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDUwMClcbiAgICAgIC5qc29uKHsgbWVzc2FnZTogJ0ZhaWxlZCB0byBnZW5lcmF0ZSBsZWFybmluZyBwbGFuJyB9KTtcbiAgfVxufVxuIl19