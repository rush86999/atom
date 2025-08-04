"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const nextjs_1 = require("supertokens-node/nextjs");
const competitorAnalysisSkills_1 = require("../../../../project/functions/atom-agent/skills/competitorAnalysisSkills");
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
    const { competitors, notionDatabaseId } = req.body;
    if (!competitors || !notionDatabaseId) {
        return res
            .status(400)
            .json({ message: 'Competitors and Notion Database ID are required' });
    }
    try {
        await (0, competitorAnalysisSkills_1.runCompetitorAnalysis)(userId, competitors, notionDatabaseId);
        return res.status(200).json({ message: 'Competitor analysis complete' });
    }
    catch (error) {
        console.error('Error running competitor analysis:', error);
        return res
            .status(500)
            .json({ message: 'Failed to run competitor analysis' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29tcGV0aXRvci1hbmFseXNpcy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNvbXBldGl0b3ItYW5hbHlzaXMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFLQSwwQkErQkM7QUFuQ0Qsb0RBQXFEO0FBRXJELHVIQUFpSDtBQUVsRyxLQUFLLFVBQVUsT0FBTyxDQUNuQyxHQUFtQixFQUNuQixHQUFvQjtJQUVwQixJQUFJLE9BQXlCLENBQUM7SUFDOUIsSUFBSSxDQUFDO1FBQ0gsT0FBTyxHQUFHLE1BQU0sSUFBQSxtQkFBVSxFQUFDLEdBQUcsRUFBRSxHQUFHLEVBQUU7WUFDbkMsNkJBQTZCLEVBQUUsR0FBRyxFQUFFLENBQUMsRUFBRTtTQUN4QyxDQUFDLENBQUM7SUFDTCxDQUFDO0lBQUMsT0FBTyxHQUFHLEVBQUUsQ0FBQztRQUNiLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsY0FBYyxFQUFFLENBQUMsQ0FBQztJQUMzRCxDQUFDO0lBRUQsTUFBTSxNQUFNLEdBQUcsT0FBTyxDQUFDLFNBQVMsRUFBRSxDQUFDO0lBQ25DLE1BQU0sRUFBRSxXQUFXLEVBQUUsZ0JBQWdCLEVBQUUsR0FBRyxHQUFHLENBQUMsSUFBSSxDQUFDO0lBRW5ELElBQUksQ0FBQyxXQUFXLElBQUksQ0FBQyxnQkFBZ0IsRUFBRSxDQUFDO1FBQ3RDLE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsaURBQWlELEVBQUUsQ0FBQyxDQUFDO0lBQzFFLENBQUM7SUFFRCxJQUFJLENBQUM7UUFDSCxNQUFNLElBQUEsZ0RBQXFCLEVBQUMsTUFBTSxFQUFFLFdBQVcsRUFBRSxnQkFBZ0IsQ0FBQyxDQUFDO1FBQ25FLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsOEJBQThCLEVBQUUsQ0FBQyxDQUFDO0lBQzNFLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyxvQ0FBb0MsRUFBRSxLQUFLLENBQUMsQ0FBQztRQUMzRCxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLG1DQUFtQyxFQUFFLENBQUMsQ0FBQztJQUM1RCxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCB7IGdldFNlc3Npb24gfSBmcm9tICdzdXBlcnRva2Vucy1ub2RlL25leHRqcyc7XG5pbXBvcnQgeyBTZXNzaW9uQ29udGFpbmVyIH0gZnJvbSAnc3VwZXJ0b2tlbnMtbm9kZS9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQgeyBydW5Db21wZXRpdG9yQW5hbHlzaXMgfSBmcm9tICcuLi8uLi8uLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L3NraWxscy9jb21wZXRpdG9yQW5hbHlzaXNTa2lsbHMnO1xuXG5leHBvcnQgZGVmYXVsdCBhc3luYyBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZVxuKSB7XG4gIGxldCBzZXNzaW9uOiBTZXNzaW9uQ29udGFpbmVyO1xuICB0cnkge1xuICAgIHNlc3Npb24gPSBhd2FpdCBnZXRTZXNzaW9uKHJlcSwgcmVzLCB7XG4gICAgICBvdmVycmlkZUdsb2JhbENsYWltVmFsaWRhdG9yczogKCkgPT4gW10sXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGVycikge1xuICAgIHJldHVybiByZXMuc3RhdHVzKDQwMSkuanNvbih7IG1lc3NhZ2U6ICdVbmF1dGhvcml6ZWQnIH0pO1xuICB9XG5cbiAgY29uc3QgdXNlcklkID0gc2Vzc2lvbi5nZXRVc2VySWQoKTtcbiAgY29uc3QgeyBjb21wZXRpdG9ycywgbm90aW9uRGF0YWJhc2VJZCB9ID0gcmVxLmJvZHk7XG5cbiAgaWYgKCFjb21wZXRpdG9ycyB8fCAhbm90aW9uRGF0YWJhc2VJZCkge1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgLmpzb24oeyBtZXNzYWdlOiAnQ29tcGV0aXRvcnMgYW5kIE5vdGlvbiBEYXRhYmFzZSBJRCBhcmUgcmVxdWlyZWQnIH0pO1xuICB9XG5cbiAgdHJ5IHtcbiAgICBhd2FpdCBydW5Db21wZXRpdG9yQW5hbHlzaXModXNlcklkLCBjb21wZXRpdG9ycywgbm90aW9uRGF0YWJhc2VJZCk7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHsgbWVzc2FnZTogJ0NvbXBldGl0b3IgYW5hbHlzaXMgY29tcGxldGUnIH0pO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIHJ1bm5pbmcgY29tcGV0aXRvciBhbmFseXNpczonLCBlcnJvcik7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7IG1lc3NhZ2U6ICdGYWlsZWQgdG8gcnVuIGNvbXBldGl0b3IgYW5hbHlzaXMnIH0pO1xuICB9XG59XG4iXX0=