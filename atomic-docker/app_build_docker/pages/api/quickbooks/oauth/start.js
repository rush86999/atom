"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
const intuit_oauth_1 = __importDefault(require("intuit-oauth"));
function handler(req, res) {
    const oauthClient = new intuit_oauth_1.default({
        clientId: process.env.QUICKBOOKS_CLIENT_ID,
        clientSecret: process.env.QUICKBOOKS_CLIENT_SECRET,
        environment: 'sandbox', // or 'production'
        redirectUri: process.env.QUICKBOOKS_REDIRECT_URI,
    });
    const authUri = oauthClient.authorizeUri({
        scope: [intuit_oauth_1.default.scopes.Accounting],
        state: 'some-random-state', // Should be a random, unguessable string
    });
    res.redirect(authUri);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3RhcnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzdGFydC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7OztBQUdBLDBCQWNDO0FBaEJELGdFQUF1QztBQUV2QyxTQUF3QixPQUFPLENBQUMsR0FBbUIsRUFBRSxHQUFvQjtJQUN2RSxNQUFNLFdBQVcsR0FBRyxJQUFJLHNCQUFXLENBQUM7UUFDbEMsUUFBUSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsb0JBQW9CO1FBQzFDLFlBQVksRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLHdCQUF3QjtRQUNsRCxXQUFXLEVBQUUsU0FBUyxFQUFFLGtCQUFrQjtRQUMxQyxXQUFXLEVBQUUsT0FBTyxDQUFDLEdBQUcsQ0FBQyx1QkFBdUI7S0FDakQsQ0FBQyxDQUFDO0lBRUgsTUFBTSxPQUFPLEdBQUcsV0FBVyxDQUFDLFlBQVksQ0FBQztRQUN2QyxLQUFLLEVBQUUsQ0FBQyxzQkFBVyxDQUFDLE1BQU0sQ0FBQyxVQUFVLENBQUM7UUFDdEMsS0FBSyxFQUFFLG1CQUFtQixFQUFFLHlDQUF5QztLQUN0RSxDQUFDLENBQUM7SUFFSCxHQUFHLENBQUMsUUFBUSxDQUFDLE9BQU8sQ0FBQyxDQUFDO0FBQ3hCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5pbXBvcnQgT0F1dGhDbGllbnQgZnJvbSAnaW50dWl0LW9hdXRoJztcblxuZXhwb3J0IGRlZmF1bHQgZnVuY3Rpb24gaGFuZGxlcihyZXE6IE5leHRBcGlSZXF1ZXN0LCByZXM6IE5leHRBcGlSZXNwb25zZSkge1xuICBjb25zdCBvYXV0aENsaWVudCA9IG5ldyBPQXV0aENsaWVudCh7XG4gICAgY2xpZW50SWQ6IHByb2Nlc3MuZW52LlFVSUNLQk9PS1NfQ0xJRU5UX0lELFxuICAgIGNsaWVudFNlY3JldDogcHJvY2Vzcy5lbnYuUVVJQ0tCT09LU19DTElFTlRfU0VDUkVULFxuICAgIGVudmlyb25tZW50OiAnc2FuZGJveCcsIC8vIG9yICdwcm9kdWN0aW9uJ1xuICAgIHJlZGlyZWN0VXJpOiBwcm9jZXNzLmVudi5RVUlDS0JPT0tTX1JFRElSRUNUX1VSSSxcbiAgfSk7XG5cbiAgY29uc3QgYXV0aFVyaSA9IG9hdXRoQ2xpZW50LmF1dGhvcml6ZVVyaSh7XG4gICAgc2NvcGU6IFtPQXV0aENsaWVudC5zY29wZXMuQWNjb3VudGluZ10sXG4gICAgc3RhdGU6ICdzb21lLXJhbmRvbS1zdGF0ZScsIC8vIFNob3VsZCBiZSBhIHJhbmRvbSwgdW5ndWVzc2FibGUgc3RyaW5nXG4gIH0pO1xuXG4gIHJlcy5yZWRpcmVjdChhdXRoVXJpKTtcbn1cbiJdfQ==