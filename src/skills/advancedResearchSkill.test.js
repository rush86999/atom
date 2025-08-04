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
Object.defineProperty(exports, "__esModule", { value: true });
const advancedResearchSkill_1 = require("./advancedResearchSkill");
const canvaSkills = __importStar(require("./canvaSkills"));
jest.mock('./canvaSkills');
const mockedCreateDesign = canvaSkills.createDesign;
describe('AdvancedResearchAgent', () => {
    let agent;
    let llmService;
    beforeEach(() => {
        llmService = {
            generate: jest.fn(),
        };
        agent = new advancedResearchSkill_1.AdvancedResearchAgent(llmService);
    });
    it('should call createCanvaDesign when the chat command is detected', async () => {
        const input = {
            userInput: 'create canva design with title "My Test Design"',
            userId: 'test-user-id',
        };
        const designData = {
            id: 'design-id',
            title: 'My Test Design',
            urls: { edit_url: 'edit-url' },
        };
        mockedCreateDesign.mockResolvedValue(designData);
        const result = await agent.analyze(input);
        expect(mockedCreateDesign).toHaveBeenCalledWith('test-user-id', 'My Test Design');
        expect(result.researchSummary).toBe('Successfully created Canva design: "My Test Design"');
    });
    it('should call the LLM service when no Canva command is detected', async () => {
        const input = {
            userInput: 'what is the capital of France?',
            userId: 'test-user-id',
        };
        const llmResponse = {
            success: true,
            content: JSON.stringify({
                researchSummary: 'Paris',
                keyFindings: ['Paris is the capital of France'],
                sources: [],
            }),
        };
        llmService.generate.mockResolvedValue(llmResponse);
        const result = await agent.analyze(input);
        expect(llmService.generate).toHaveBeenCalled();
        expect(result.researchSummary).toBe('Paris');
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYWR2YW5jZWRSZXNlYXJjaFNraWxsLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJhZHZhbmNlZFJlc2VhcmNoU2tpbGwudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztBQUFBLG1FQUFnRTtBQUVoRSwyREFBNkM7QUFFN0MsSUFBSSxDQUFDLElBQUksQ0FBQyxlQUFlLENBQUMsQ0FBQztBQUUzQixNQUFNLGtCQUFrQixHQUFHLFdBQVcsQ0FBQyxZQUF5QixDQUFDO0FBRWpFLFFBQVEsQ0FBQyx1QkFBdUIsRUFBRSxHQUFHLEVBQUU7SUFDckMsSUFBSSxLQUE0QixDQUFDO0lBQ2pDLElBQUksVUFBMkIsQ0FBQztJQUVoQyxVQUFVLENBQUMsR0FBRyxFQUFFO1FBQ2QsVUFBVSxHQUFHO1lBQ1gsUUFBUSxFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7U0FDcEIsQ0FBQztRQUNGLEtBQUssR0FBRyxJQUFJLDZDQUFxQixDQUFDLFVBQVUsQ0FBQyxDQUFDO0lBQ2hELENBQUMsQ0FBQyxDQUFDO0lBRUgsRUFBRSxDQUFDLGlFQUFpRSxFQUFFLEtBQUssSUFBSSxFQUFFO1FBQy9FLE1BQU0sS0FBSyxHQUFrQjtZQUMzQixTQUFTLEVBQUUsaURBQWlEO1lBQzVELE1BQU0sRUFBRSxjQUFjO1NBQ3ZCLENBQUM7UUFDRixNQUFNLFVBQVUsR0FBRztZQUNqQixFQUFFLEVBQUUsV0FBVztZQUNmLEtBQUssRUFBRSxnQkFBZ0I7WUFDdkIsSUFBSSxFQUFFLEVBQUUsUUFBUSxFQUFFLFVBQVUsRUFBRTtTQUMvQixDQUFDO1FBQ0Ysa0JBQWtCLENBQUMsaUJBQWlCLENBQUMsVUFBVSxDQUFDLENBQUM7UUFFakQsTUFBTSxNQUFNLEdBQUcsTUFBTSxLQUFLLENBQUMsT0FBTyxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBRTFDLE1BQU0sQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDLG9CQUFvQixDQUM3QyxjQUFjLEVBQ2QsZ0JBQWdCLENBQ2pCLENBQUM7UUFDRixNQUFNLENBQUMsTUFBTSxDQUFDLGVBQWUsQ0FBQyxDQUFDLElBQUksQ0FDakMscURBQXFELENBQ3RELENBQUM7SUFDSixDQUFDLENBQUMsQ0FBQztJQUVILEVBQUUsQ0FBQywrREFBK0QsRUFBRSxLQUFLLElBQUksRUFBRTtRQUM3RSxNQUFNLEtBQUssR0FBa0I7WUFDM0IsU0FBUyxFQUFFLGdDQUFnQztZQUMzQyxNQUFNLEVBQUUsY0FBYztTQUN2QixDQUFDO1FBQ0YsTUFBTSxXQUFXLEdBQUc7WUFDbEIsT0FBTyxFQUFFLElBQUk7WUFDYixPQUFPLEVBQUUsSUFBSSxDQUFDLFNBQVMsQ0FBQztnQkFDdEIsZUFBZSxFQUFFLE9BQU87Z0JBQ3hCLFdBQVcsRUFBRSxDQUFDLGdDQUFnQyxDQUFDO2dCQUMvQyxPQUFPLEVBQUUsRUFBRTthQUNaLENBQUM7U0FDSCxDQUFDO1FBQ0QsVUFBVSxDQUFDLFFBQXNCLENBQUMsaUJBQWlCLENBQUMsV0FBVyxDQUFDLENBQUM7UUFFbEUsTUFBTSxNQUFNLEdBQUcsTUFBTSxLQUFLLENBQUMsT0FBTyxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBRTFDLE1BQU0sQ0FBQyxVQUFVLENBQUMsUUFBUSxDQUFDLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztRQUMvQyxNQUFNLENBQUMsTUFBTSxDQUFDLGVBQWUsQ0FBQyxDQUFDLElBQUksQ0FBQyxPQUFPLENBQUMsQ0FBQztJQUMvQyxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgQWR2YW5jZWRSZXNlYXJjaEFnZW50IH0gZnJvbSAnLi9hZHZhbmNlZFJlc2VhcmNoU2tpbGwnO1xuaW1wb3J0IHsgQWdlbnRMTE1TZXJ2aWNlLCBTdWJBZ2VudElucHV0IH0gZnJvbSAnLi4vbmx1X2FnZW50cy9ubHVfdHlwZXMnO1xuaW1wb3J0ICogYXMgY2FudmFTa2lsbHMgZnJvbSAnLi9jYW52YVNraWxscyc7XG5cbmplc3QubW9jaygnLi9jYW52YVNraWxscycpO1xuXG5jb25zdCBtb2NrZWRDcmVhdGVEZXNpZ24gPSBjYW52YVNraWxscy5jcmVhdGVEZXNpZ24gYXMgamVzdC5Nb2NrO1xuXG5kZXNjcmliZSgnQWR2YW5jZWRSZXNlYXJjaEFnZW50JywgKCkgPT4ge1xuICBsZXQgYWdlbnQ6IEFkdmFuY2VkUmVzZWFyY2hBZ2VudDtcbiAgbGV0IGxsbVNlcnZpY2U6IEFnZW50TExNU2VydmljZTtcblxuICBiZWZvcmVFYWNoKCgpID0+IHtcbiAgICBsbG1TZXJ2aWNlID0ge1xuICAgICAgZ2VuZXJhdGU6IGplc3QuZm4oKSxcbiAgICB9O1xuICAgIGFnZW50ID0gbmV3IEFkdmFuY2VkUmVzZWFyY2hBZ2VudChsbG1TZXJ2aWNlKTtcbiAgfSk7XG5cbiAgaXQoJ3Nob3VsZCBjYWxsIGNyZWF0ZUNhbnZhRGVzaWduIHdoZW4gdGhlIGNoYXQgY29tbWFuZCBpcyBkZXRlY3RlZCcsIGFzeW5jICgpID0+IHtcbiAgICBjb25zdCBpbnB1dDogU3ViQWdlbnRJbnB1dCA9IHtcbiAgICAgIHVzZXJJbnB1dDogJ2NyZWF0ZSBjYW52YSBkZXNpZ24gd2l0aCB0aXRsZSBcIk15IFRlc3QgRGVzaWduXCInLFxuICAgICAgdXNlcklkOiAndGVzdC11c2VyLWlkJyxcbiAgICB9O1xuICAgIGNvbnN0IGRlc2lnbkRhdGEgPSB7XG4gICAgICBpZDogJ2Rlc2lnbi1pZCcsXG4gICAgICB0aXRsZTogJ015IFRlc3QgRGVzaWduJyxcbiAgICAgIHVybHM6IHsgZWRpdF91cmw6ICdlZGl0LXVybCcgfSxcbiAgICB9O1xuICAgIG1vY2tlZENyZWF0ZURlc2lnbi5tb2NrUmVzb2x2ZWRWYWx1ZShkZXNpZ25EYXRhKTtcblxuICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGFnZW50LmFuYWx5emUoaW5wdXQpO1xuXG4gICAgZXhwZWN0KG1vY2tlZENyZWF0ZURlc2lnbikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAndGVzdC11c2VyLWlkJyxcbiAgICAgICdNeSBUZXN0IERlc2lnbidcbiAgICApO1xuICAgIGV4cGVjdChyZXN1bHQucmVzZWFyY2hTdW1tYXJ5KS50b0JlKFxuICAgICAgJ1N1Y2Nlc3NmdWxseSBjcmVhdGVkIENhbnZhIGRlc2lnbjogXCJNeSBUZXN0IERlc2lnblwiJ1xuICAgICk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgY2FsbCB0aGUgTExNIHNlcnZpY2Ugd2hlbiBubyBDYW52YSBjb21tYW5kIGlzIGRldGVjdGVkJywgYXN5bmMgKCkgPT4ge1xuICAgIGNvbnN0IGlucHV0OiBTdWJBZ2VudElucHV0ID0ge1xuICAgICAgdXNlcklucHV0OiAnd2hhdCBpcyB0aGUgY2FwaXRhbCBvZiBGcmFuY2U/JyxcbiAgICAgIHVzZXJJZDogJ3Rlc3QtdXNlci1pZCcsXG4gICAgfTtcbiAgICBjb25zdCBsbG1SZXNwb25zZSA9IHtcbiAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICBjb250ZW50OiBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgIHJlc2VhcmNoU3VtbWFyeTogJ1BhcmlzJyxcbiAgICAgICAga2V5RmluZGluZ3M6IFsnUGFyaXMgaXMgdGhlIGNhcGl0YWwgb2YgRnJhbmNlJ10sXG4gICAgICAgIHNvdXJjZXM6IFtdLFxuICAgICAgfSksXG4gICAgfTtcbiAgICAobGxtU2VydmljZS5nZW5lcmF0ZSBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKGxsbVJlc3BvbnNlKTtcblxuICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGFnZW50LmFuYWx5emUoaW5wdXQpO1xuXG4gICAgZXhwZWN0KGxsbVNlcnZpY2UuZ2VuZXJhdGUpLnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICBleHBlY3QocmVzdWx0LnJlc2VhcmNoU3VtbWFyeSkudG9CZSgnUGFyaXMnKTtcbiAgfSk7XG59KTtcbiJdfQ==