"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.DataAnalystSkills = void 0;
const teams_ai_1 = require("@microsoft/teams-ai");
const echoSkill_1 = require("./echoSkill");
// Data Analyst Skills
class DataAnalystSkills extends echoSkill_1.IEchoSkill {
    constructor(context, memory, functions) {
        super(context, memory, functions);
    }
    async dataAnalysis(entity) {
        // Simulate data analysis
        console.log(`Analyzing data for: ${entity}`);
        // In a real scenario, you would connect to a data source,
        // perform analysis, and return the results.
        return `Data analysis for ${entity} completed.`;
    }
    async generateReport(topic) {
        // Simulate report generation
        console.log(`Generating report for: ${topic}`);
        // In a real scenario, this would involve compiling data
        // and formatting it into a report.
        return `Report for ${topic} has been generated.`;
    }
}
exports.DataAnalystSkills = DataAnalystSkills;
__decorate([
    (0, teams_ai_1.Tool)('dataAnalysis')
], DataAnalystSkills.prototype, "dataAnalysis", null);
__decorate([
    (0, teams_ai_1.Tool)('generateReport')
], DataAnalystSkills.prototype, "generateReport", null);
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGF0YUFuYWx5c3RTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkYXRhQW5hbHlzdFNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7QUFBQSxrREFBMkM7QUFFM0MsMkNBQXlDO0FBRXpDLHNCQUFzQjtBQUN0QixNQUFhLGlCQUFrQixTQUFRLHNCQUFVO0lBQy9DLFlBQVksT0FBb0IsRUFBRSxNQUFXLEVBQUUsU0FBYztRQUMzRCxLQUFLLENBQUMsT0FBTyxFQUFFLE1BQU0sRUFBRSxTQUFTLENBQUMsQ0FBQztJQUNwQyxDQUFDO0lBR0ssQUFBTixLQUFLLENBQUMsWUFBWSxDQUFDLE1BQWM7UUFDL0IseUJBQXlCO1FBQ3pCLE9BQU8sQ0FBQyxHQUFHLENBQUMsdUJBQXVCLE1BQU0sRUFBRSxDQUFDLENBQUM7UUFDN0MsMERBQTBEO1FBQzFELDRDQUE0QztRQUM1QyxPQUFPLHFCQUFxQixNQUFNLGFBQWEsQ0FBQztJQUNsRCxDQUFDO0lBR0ssQUFBTixLQUFLLENBQUMsY0FBYyxDQUFDLEtBQWE7UUFDaEMsNkJBQTZCO1FBQzdCLE9BQU8sQ0FBQyxHQUFHLENBQUMsMEJBQTBCLEtBQUssRUFBRSxDQUFDLENBQUM7UUFDL0Msd0RBQXdEO1FBQ3hELG1DQUFtQztRQUNuQyxPQUFPLGNBQWMsS0FBSyxzQkFBc0IsQ0FBQztJQUNuRCxDQUFDO0NBQ0Y7QUF0QkQsOENBc0JDO0FBaEJPO0lBREwsSUFBQSxlQUFJLEVBQUMsY0FBYyxDQUFDO3FEQU9wQjtBQUdLO0lBREwsSUFBQSxlQUFJLEVBQUMsZ0JBQWdCLENBQUM7dURBT3RCIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgVG9vbCB9IGZyb20gJ0BtaWNyb3NvZnQvdGVhbXMtYWknO1xuaW1wb3J0IHsgVHVybkNvbnRleHQgfSBmcm9tICdib3RidWlsZGVyJztcbmltcG9ydCB7IElFY2hvU2tpbGwgfSBmcm9tICcuL2VjaG9Ta2lsbCc7XG5cbi8vIERhdGEgQW5hbHlzdCBTa2lsbHNcbmV4cG9ydCBjbGFzcyBEYXRhQW5hbHlzdFNraWxscyBleHRlbmRzIElFY2hvU2tpbGwge1xuICBjb25zdHJ1Y3Rvcihjb250ZXh0OiBUdXJuQ29udGV4dCwgbWVtb3J5OiBhbnksIGZ1bmN0aW9uczogYW55KSB7XG4gICAgc3VwZXIoY29udGV4dCwgbWVtb3J5LCBmdW5jdGlvbnMpO1xuICB9XG5cbiAgQFRvb2woJ2RhdGFBbmFseXNpcycpXG4gIGFzeW5jIGRhdGFBbmFseXNpcyhlbnRpdHk6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nPiB7XG4gICAgLy8gU2ltdWxhdGUgZGF0YSBhbmFseXNpc1xuICAgIGNvbnNvbGUubG9nKGBBbmFseXppbmcgZGF0YSBmb3I6ICR7ZW50aXR5fWApO1xuICAgIC8vIEluIGEgcmVhbCBzY2VuYXJpbywgeW91IHdvdWxkIGNvbm5lY3QgdG8gYSBkYXRhIHNvdXJjZSxcbiAgICAvLyBwZXJmb3JtIGFuYWx5c2lzLCBhbmQgcmV0dXJuIHRoZSByZXN1bHRzLlxuICAgIHJldHVybiBgRGF0YSBhbmFseXNpcyBmb3IgJHtlbnRpdHl9IGNvbXBsZXRlZC5gO1xuICB9XG5cbiAgQFRvb2woJ2dlbmVyYXRlUmVwb3J0JylcbiAgYXN5bmMgZ2VuZXJhdGVSZXBvcnQodG9waWM6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nPiB7XG4gICAgLy8gU2ltdWxhdGUgcmVwb3J0IGdlbmVyYXRpb25cbiAgICBjb25zb2xlLmxvZyhgR2VuZXJhdGluZyByZXBvcnQgZm9yOiAke3RvcGljfWApO1xuICAgIC8vIEluIGEgcmVhbCBzY2VuYXJpbywgdGhpcyB3b3VsZCBpbnZvbHZlIGNvbXBpbGluZyBkYXRhXG4gICAgLy8gYW5kIGZvcm1hdHRpbmcgaXQgaW50byBhIHJlcG9ydC5cbiAgICByZXR1cm4gYFJlcG9ydCBmb3IgJHt0b3BpY30gaGFzIGJlZW4gZ2VuZXJhdGVkLmA7XG4gIH1cbn1cbiJdfQ==