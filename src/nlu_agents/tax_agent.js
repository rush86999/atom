"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TaxAgent = void 0;
class TaxAgent {
    llmService;
    agentName = 'TaxAgent';
    constructor(llmService) {
        this.llmService = llmService;
    }
    async analyze(input) {
        const normalizedQuery = input.userInput.toLowerCase().trim();
        if (normalizedQuery.includes('tax') || normalizedQuery.includes('taxes')) {
            return {
                isTaxRelated: true,
                confidence: 0.9,
                details: 'The query contains tax-related keywords.',
            };
        }
        return null;
    }
}
exports.TaxAgent = TaxAgent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGF4X2FnZW50LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidGF4X2FnZW50LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUdBLE1BQWEsUUFBUTtJQUdDO0lBRlosU0FBUyxHQUFXLFVBQVUsQ0FBQztJQUV2QyxZQUFvQixVQUEyQjtRQUEzQixlQUFVLEdBQVYsVUFBVSxDQUFpQjtJQUFHLENBQUM7SUFFNUMsS0FBSyxDQUFDLE9BQU8sQ0FBQyxLQUFvQjtRQUN2QyxNQUFNLGVBQWUsR0FBRyxLQUFLLENBQUMsU0FBUyxDQUFDLFdBQVcsRUFBRSxDQUFDLElBQUksRUFBRSxDQUFDO1FBRTdELElBQUksZUFBZSxDQUFDLFFBQVEsQ0FBQyxLQUFLLENBQUMsSUFBSSxlQUFlLENBQUMsUUFBUSxDQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7WUFDekUsT0FBTztnQkFDTCxZQUFZLEVBQUUsSUFBSTtnQkFDbEIsVUFBVSxFQUFFLEdBQUc7Z0JBQ2YsT0FBTyxFQUFFLDBDQUEwQzthQUNwRCxDQUFDO1FBQ0osQ0FBQztRQUVELE9BQU8sSUFBSSxDQUFDO0lBQ2QsQ0FBQztDQUNGO0FBbEJELDRCQWtCQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFN1YkFnZW50SW5wdXQsIFRheEFnZW50UmVzcG9uc2UgfSBmcm9tICcuL25sdV90eXBlcyc7XG5pbXBvcnQgeyBBZ2VudExMTVNlcnZpY2UgfSBmcm9tICcuL25sdV90eXBlcyc7XG5cbmV4cG9ydCBjbGFzcyBUYXhBZ2VudCB7XG4gIHByaXZhdGUgYWdlbnROYW1lOiBzdHJpbmcgPSAnVGF4QWdlbnQnO1xuXG4gIGNvbnN0cnVjdG9yKHByaXZhdGUgbGxtU2VydmljZTogQWdlbnRMTE1TZXJ2aWNlKSB7fVxuXG4gIHB1YmxpYyBhc3luYyBhbmFseXplKGlucHV0OiBTdWJBZ2VudElucHV0KTogUHJvbWlzZTxUYXhBZ2VudFJlc3BvbnNlIHwgbnVsbD4ge1xuICAgIGNvbnN0IG5vcm1hbGl6ZWRRdWVyeSA9IGlucHV0LnVzZXJJbnB1dC50b0xvd2VyQ2FzZSgpLnRyaW0oKTtcblxuICAgIGlmIChub3JtYWxpemVkUXVlcnkuaW5jbHVkZXMoJ3RheCcpIHx8IG5vcm1hbGl6ZWRRdWVyeS5pbmNsdWRlcygndGF4ZXMnKSkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgaXNUYXhSZWxhdGVkOiB0cnVlLFxuICAgICAgICBjb25maWRlbmNlOiAwLjksXG4gICAgICAgIGRldGFpbHM6ICdUaGUgcXVlcnkgY29udGFpbnMgdGF4LXJlbGF0ZWQga2V5d29yZHMuJyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgcmV0dXJuIG51bGw7XG4gIH1cbn1cbiJdfQ==