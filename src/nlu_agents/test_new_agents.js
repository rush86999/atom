"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const botbuilder_1 = require("botbuilder");
const nlu_lead_agent_1 = require("./nlu_lead_agent");
const llmUtils_1 = require("../lib/llmUtils");
async function testNewAgents() {
    const llmService = new llmUtils_1.MockLLMService();
    const context = new botbuilder_1.TurnContext({}, {});
    const memory = {};
    const functions = {};
    const leadAgent = new nlu_lead_agent_1.NLULeadAgent(llmService, context, memory, functions);
    const testCases = [
        {
            userInput: 'Research the latest trends in AI-powered personal assistants and summarize the key findings in a Notion document.',
        },
        {
            userInput: "Schedule a week's worth of social media posts about our new product launch.",
        },
        { userInput: "Find me a new laptop for work that's under $1000." },
        {
            userInput: 'Analyze this contract and identify any potential risks: [URL/filepath].',
        },
        {
            userInput: 'Find the best candidates for the Senior Software Engineer position.',
        },
        { userInput: 'Perform a red team test on our web application.' },
    ];
    for (const testCase of testCases) {
        console.log(`--- Testing with input: "${testCase.userInput}" ---`);
        const result = await leadAgent.analyzeIntent(testCase);
        console.log(JSON.stringify(result, null, 2));
    }
}
testNewAgents();
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGVzdF9uZXdfYWdlbnRzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidGVzdF9uZXdfYWdlbnRzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXlDO0FBQ3pDLHFEQUFnRDtBQUVoRCw4Q0FBaUQ7QUFFakQsS0FBSyxVQUFVLGFBQWE7SUFDMUIsTUFBTSxVQUFVLEdBQUcsSUFBSSx5QkFBYyxFQUFFLENBQUM7SUFDeEMsTUFBTSxPQUFPLEdBQUcsSUFBSSx3QkFBVyxDQUFDLEVBQVMsRUFBRSxFQUFTLENBQUMsQ0FBQztJQUN0RCxNQUFNLE1BQU0sR0FBRyxFQUFFLENBQUM7SUFDbEIsTUFBTSxTQUFTLEdBQUcsRUFBRSxDQUFDO0lBQ3JCLE1BQU0sU0FBUyxHQUFHLElBQUksNkJBQVksQ0FBQyxVQUFVLEVBQUUsT0FBTyxFQUFFLE1BQU0sRUFBRSxTQUFTLENBQUMsQ0FBQztJQUUzRSxNQUFNLFNBQVMsR0FBb0I7UUFDakM7WUFDRSxTQUFTLEVBQ1AsbUhBQW1IO1NBQ3RIO1FBQ0Q7WUFDRSxTQUFTLEVBQ1AsNkVBQTZFO1NBQ2hGO1FBQ0QsRUFBRSxTQUFTLEVBQUUsbURBQW1ELEVBQUU7UUFDbEU7WUFDRSxTQUFTLEVBQ1AseUVBQXlFO1NBQzVFO1FBQ0Q7WUFDRSxTQUFTLEVBQ1AscUVBQXFFO1NBQ3hFO1FBQ0QsRUFBRSxTQUFTLEVBQUUsaURBQWlELEVBQUU7S0FDakUsQ0FBQztJQUVGLEtBQUssTUFBTSxRQUFRLElBQUksU0FBUyxFQUFFLENBQUM7UUFDakMsT0FBTyxDQUFDLEdBQUcsQ0FBQyw0QkFBNEIsUUFBUSxDQUFDLFNBQVMsT0FBTyxDQUFDLENBQUM7UUFDbkUsTUFBTSxNQUFNLEdBQUcsTUFBTSxTQUFTLENBQUMsYUFBYSxDQUFDLFFBQVEsQ0FBQyxDQUFDO1FBQ3ZELE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxDQUFDLFNBQVMsQ0FBQyxNQUFNLEVBQUUsSUFBSSxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUM7SUFDL0MsQ0FBQztBQUNILENBQUM7QUFFRCxhQUFhLEVBQUUsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFR1cm5Db250ZXh0IH0gZnJvbSAnYm90YnVpbGRlcic7XG5pbXBvcnQgeyBOTFVMZWFkQWdlbnQgfSBmcm9tICcuL25sdV9sZWFkX2FnZW50JztcbmltcG9ydCB7IFN1YkFnZW50SW5wdXQgfSBmcm9tICcuL25sdV90eXBlcyc7XG5pbXBvcnQgeyBNb2NrTExNU2VydmljZSB9IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7XG5cbmFzeW5jIGZ1bmN0aW9uIHRlc3ROZXdBZ2VudHMoKSB7XG4gIGNvbnN0IGxsbVNlcnZpY2UgPSBuZXcgTW9ja0xMTVNlcnZpY2UoKTtcbiAgY29uc3QgY29udGV4dCA9IG5ldyBUdXJuQ29udGV4dCh7fSBhcyBhbnksIHt9IGFzIGFueSk7XG4gIGNvbnN0IG1lbW9yeSA9IHt9O1xuICBjb25zdCBmdW5jdGlvbnMgPSB7fTtcbiAgY29uc3QgbGVhZEFnZW50ID0gbmV3IE5MVUxlYWRBZ2VudChsbG1TZXJ2aWNlLCBjb250ZXh0LCBtZW1vcnksIGZ1bmN0aW9ucyk7XG5cbiAgY29uc3QgdGVzdENhc2VzOiBTdWJBZ2VudElucHV0W10gPSBbXG4gICAge1xuICAgICAgdXNlcklucHV0OlxuICAgICAgICAnUmVzZWFyY2ggdGhlIGxhdGVzdCB0cmVuZHMgaW4gQUktcG93ZXJlZCBwZXJzb25hbCBhc3Npc3RhbnRzIGFuZCBzdW1tYXJpemUgdGhlIGtleSBmaW5kaW5ncyBpbiBhIE5vdGlvbiBkb2N1bWVudC4nLFxuICAgIH0sXG4gICAge1xuICAgICAgdXNlcklucHV0OlxuICAgICAgICBcIlNjaGVkdWxlIGEgd2VlaydzIHdvcnRoIG9mIHNvY2lhbCBtZWRpYSBwb3N0cyBhYm91dCBvdXIgbmV3IHByb2R1Y3QgbGF1bmNoLlwiLFxuICAgIH0sXG4gICAgeyB1c2VySW5wdXQ6IFwiRmluZCBtZSBhIG5ldyBsYXB0b3AgZm9yIHdvcmsgdGhhdCdzIHVuZGVyICQxMDAwLlwiIH0sXG4gICAge1xuICAgICAgdXNlcklucHV0OlxuICAgICAgICAnQW5hbHl6ZSB0aGlzIGNvbnRyYWN0IGFuZCBpZGVudGlmeSBhbnkgcG90ZW50aWFsIHJpc2tzOiBbVVJML2ZpbGVwYXRoXS4nLFxuICAgIH0sXG4gICAge1xuICAgICAgdXNlcklucHV0OlxuICAgICAgICAnRmluZCB0aGUgYmVzdCBjYW5kaWRhdGVzIGZvciB0aGUgU2VuaW9yIFNvZnR3YXJlIEVuZ2luZWVyIHBvc2l0aW9uLicsXG4gICAgfSxcbiAgICB7IHVzZXJJbnB1dDogJ1BlcmZvcm0gYSByZWQgdGVhbSB0ZXN0IG9uIG91ciB3ZWIgYXBwbGljYXRpb24uJyB9LFxuICBdO1xuXG4gIGZvciAoY29uc3QgdGVzdENhc2Ugb2YgdGVzdENhc2VzKSB7XG4gICAgY29uc29sZS5sb2coYC0tLSBUZXN0aW5nIHdpdGggaW5wdXQ6IFwiJHt0ZXN0Q2FzZS51c2VySW5wdXR9XCIgLS0tYCk7XG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbGVhZEFnZW50LmFuYWx5emVJbnRlbnQodGVzdENhc2UpO1xuICAgIGNvbnNvbGUubG9nKEpTT04uc3RyaW5naWZ5KHJlc3VsdCwgbnVsbCwgMikpO1xuICB9XG59XG5cbnRlc3ROZXdBZ2VudHMoKTtcbiJdfQ==