"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.nlu = nlu;
async function nlu(query, options) {
    // In a real application, this would call an NLU service powered by an LLM.
    // For now, we'll just return a mock response.
    return {
        intent: 'calculate_tax',
        parameters: {
            income: 50000,
            filingStatus: 'single',
            dependents: 0,
        },
    };
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibmx1U2VydmljZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIm5sdVNlcnZpY2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFFQSxrQkFXQztBQVhNLEtBQUssVUFBVSxHQUFHLENBQUMsS0FBYSxFQUFFLE9BQVk7SUFDbkQsMkVBQTJFO0lBQzNFLDhDQUE4QztJQUM5QyxPQUFPO1FBQ0wsTUFBTSxFQUFFLGVBQWU7UUFDdkIsVUFBVSxFQUFFO1lBQ1YsTUFBTSxFQUFFLEtBQUs7WUFDYixZQUFZLEVBQUUsUUFBUTtZQUN0QixVQUFVLEVBQUUsQ0FBQztTQUNkO0tBQ0YsQ0FBQztBQUNKLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBUYXhRdWVyeSB9IGZyb20gJy4uL3NraWxscy90YXhFeHBlcnRTa2lsbHMnO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gbmx1KHF1ZXJ5OiBzdHJpbmcsIG9wdGlvbnM6IGFueSk6IFByb21pc2U8VGF4UXVlcnk+IHtcbiAgLy8gSW4gYSByZWFsIGFwcGxpY2F0aW9uLCB0aGlzIHdvdWxkIGNhbGwgYW4gTkxVIHNlcnZpY2UgcG93ZXJlZCBieSBhbiBMTE0uXG4gIC8vIEZvciBub3csIHdlJ2xsIGp1c3QgcmV0dXJuIGEgbW9jayByZXNwb25zZS5cbiAgcmV0dXJuIHtcbiAgICBpbnRlbnQ6ICdjYWxjdWxhdGVfdGF4JyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICBpbmNvbWU6IDUwMDAwLFxuICAgICAgZmlsaW5nU3RhdHVzOiAnc2luZ2xlJyxcbiAgICAgIGRlcGVuZGVudHM6IDAsXG4gICAgfSxcbiAgfTtcbn1cbiJdfQ==