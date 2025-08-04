"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
async function handler(req, res) {
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }
    try {
        const userId = req.query.userId;
        const { period = 'current', month, categories } = req.query;
        if (!userId) {
            return res.status(400).json({ error: 'User ID required' });
        }
        // Mock budget data for demonstration
        const mockBudgetSummary = {
            totalBudget: 2500,
            spent: 1837.5,
            remaining: 662.5,
            categories: [
                {
                    category: 'Dining',
                    budgeted: 500,
                    spent: 485.75,
                    remaining: 14.25,
                    utilization: 97.15,
                },
                {
                    category: 'Groceries',
                    budgeted: 400,
                    spent: 312.8,
                    remaining: 87.2,
                    utilization: 78.2,
                },
                {
                    category: 'Transportation',
                    budgeted: 300,
                    spent: 198.45,
                    remaining: 101.55,
                    utilization: 66.15,
                },
                {
                    category: 'Entertainment',
                    budgeted: 200,
                    spent: 235.3,
                    remaining: -35.3,
                    utilization: 117.65,
                },
                {
                    category: 'Shopping',
                    budgeted: 350,
                    spent: 178.2,
                    remaining: 171.8,
                    utilization: 50.91,
                },
                {
                    category: 'Utilities',
                    budgeted: 250,
                    spent: 187.0,
                    remaining: 63.0,
                    utilization: 74.8,
                },
                {
                    category: 'Other',
                    budgeted: 500,
                    spent: 240.0,
                    remaining: 260.0,
                    utilization: 48.0,
                },
            ],
        };
        res.status(200).json({ data: mockBudgetSummary });
    }
    catch (error) {
        console.error('Budget summary error:', error);
        res.status(500).json({ error: 'Failed to retrieve budget summary' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3VtbWFyeS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInN1bW1hcnkudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFFQSwwQkErRUM7QUEvRWMsS0FBSyxVQUFVLE9BQU8sQ0FDbkMsR0FBbUIsRUFDbkIsR0FBb0I7SUFFcEIsSUFBSSxHQUFHLENBQUMsTUFBTSxLQUFLLEtBQUssRUFBRSxDQUFDO1FBQ3pCLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxLQUFLLEVBQUUsb0JBQW9CLEVBQUUsQ0FBQyxDQUFDO0lBQy9ELENBQUM7SUFFRCxJQUFJLENBQUM7UUFDSCxNQUFNLE1BQU0sR0FBRyxHQUFHLENBQUMsS0FBSyxDQUFDLE1BQWdCLENBQUM7UUFDMUMsTUFBTSxFQUFFLE1BQU0sR0FBRyxTQUFTLEVBQUUsS0FBSyxFQUFFLFVBQVUsRUFBRSxHQUFHLEdBQUcsQ0FBQyxLQUFLLENBQUM7UUFFNUQsSUFBSSxDQUFDLE1BQU0sRUFBRSxDQUFDO1lBQ1osT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSxrQkFBa0IsRUFBRSxDQUFDLENBQUM7UUFDN0QsQ0FBQztRQUVELHFDQUFxQztRQUNyQyxNQUFNLGlCQUFpQixHQUFHO1lBQ3hCLFdBQVcsRUFBRSxJQUFJO1lBQ2pCLEtBQUssRUFBRSxNQUFNO1lBQ2IsU0FBUyxFQUFFLEtBQUs7WUFDaEIsVUFBVSxFQUFFO2dCQUNWO29CQUNFLFFBQVEsRUFBRSxRQUFRO29CQUNsQixRQUFRLEVBQUUsR0FBRztvQkFDYixLQUFLLEVBQUUsTUFBTTtvQkFDYixTQUFTLEVBQUUsS0FBSztvQkFDaEIsV0FBVyxFQUFFLEtBQUs7aUJBQ25CO2dCQUNEO29CQUNFLFFBQVEsRUFBRSxXQUFXO29CQUNyQixRQUFRLEVBQUUsR0FBRztvQkFDYixLQUFLLEVBQUUsS0FBSztvQkFDWixTQUFTLEVBQUUsSUFBSTtvQkFDZixXQUFXLEVBQUUsSUFBSTtpQkFDbEI7Z0JBQ0Q7b0JBQ0UsUUFBUSxFQUFFLGdCQUFnQjtvQkFDMUIsUUFBUSxFQUFFLEdBQUc7b0JBQ2IsS0FBSyxFQUFFLE1BQU07b0JBQ2IsU0FBUyxFQUFFLE1BQU07b0JBQ2pCLFdBQVcsRUFBRSxLQUFLO2lCQUNuQjtnQkFDRDtvQkFDRSxRQUFRLEVBQUUsZUFBZTtvQkFDekIsUUFBUSxFQUFFLEdBQUc7b0JBQ2IsS0FBSyxFQUFFLEtBQUs7b0JBQ1osU0FBUyxFQUFFLENBQUMsSUFBSTtvQkFDaEIsV0FBVyxFQUFFLE1BQU07aUJBQ3BCO2dCQUNEO29CQUNFLFFBQVEsRUFBRSxVQUFVO29CQUNwQixRQUFRLEVBQUUsR0FBRztvQkFDYixLQUFLLEVBQUUsS0FBSztvQkFDWixTQUFTLEVBQUUsS0FBSztvQkFDaEIsV0FBVyxFQUFFLEtBQUs7aUJBQ25CO2dCQUNEO29CQUNFLFFBQVEsRUFBRSxXQUFXO29CQUNyQixRQUFRLEVBQUUsR0FBRztvQkFDYixLQUFLLEVBQUUsS0FBSztvQkFDWixTQUFTLEVBQUUsSUFBSTtvQkFDZixXQUFXLEVBQUUsSUFBSTtpQkFDbEI7Z0JBQ0Q7b0JBQ0UsUUFBUSxFQUFFLE9BQU87b0JBQ2pCLFFBQVEsRUFBRSxHQUFHO29CQUNiLEtBQUssRUFBRSxLQUFLO29CQUNaLFNBQVMsRUFBRSxLQUFLO29CQUNoQixXQUFXLEVBQUUsSUFBSTtpQkFDbEI7YUFDRjtTQUNGLENBQUM7UUFFRixHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLElBQUksRUFBRSxpQkFBaUIsRUFBRSxDQUFDLENBQUM7SUFDcEQsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLENBQUMsS0FBSyxDQUFDLHVCQUF1QixFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQzlDLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsS0FBSyxFQUFFLG1DQUFtQyxFQUFFLENBQUMsQ0FBQztJQUN2RSxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcblxuZXhwb3J0IGRlZmF1bHQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlcihcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2Vcbikge1xuICBpZiAocmVxLm1ldGhvZCAhPT0gJ0dFVCcpIHtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDUpLmpzb24oeyBlcnJvcjogJ01ldGhvZCBub3QgYWxsb3dlZCcgfSk7XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHVzZXJJZCA9IHJlcS5xdWVyeS51c2VySWQgYXMgc3RyaW5nO1xuICAgIGNvbnN0IHsgcGVyaW9kID0gJ2N1cnJlbnQnLCBtb250aCwgY2F0ZWdvcmllcyB9ID0gcmVxLnF1ZXJ5O1xuXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIHJldHVybiByZXMuc3RhdHVzKDQwMCkuanNvbih7IGVycm9yOiAnVXNlciBJRCByZXF1aXJlZCcgfSk7XG4gICAgfVxuXG4gICAgLy8gTW9jayBidWRnZXQgZGF0YSBmb3IgZGVtb25zdHJhdGlvblxuICAgIGNvbnN0IG1vY2tCdWRnZXRTdW1tYXJ5ID0ge1xuICAgICAgdG90YWxCdWRnZXQ6IDI1MDAsXG4gICAgICBzcGVudDogMTgzNy41LFxuICAgICAgcmVtYWluaW5nOiA2NjIuNSxcbiAgICAgIGNhdGVnb3JpZXM6IFtcbiAgICAgICAge1xuICAgICAgICAgIGNhdGVnb3J5OiAnRGluaW5nJyxcbiAgICAgICAgICBidWRnZXRlZDogNTAwLFxuICAgICAgICAgIHNwZW50OiA0ODUuNzUsXG4gICAgICAgICAgcmVtYWluaW5nOiAxNC4yNSxcbiAgICAgICAgICB1dGlsaXphdGlvbjogOTcuMTUsXG4gICAgICAgIH0sXG4gICAgICAgIHtcbiAgICAgICAgICBjYXRlZ29yeTogJ0dyb2NlcmllcycsXG4gICAgICAgICAgYnVkZ2V0ZWQ6IDQwMCxcbiAgICAgICAgICBzcGVudDogMzEyLjgsXG4gICAgICAgICAgcmVtYWluaW5nOiA4Ny4yLFxuICAgICAgICAgIHV0aWxpemF0aW9uOiA3OC4yLFxuICAgICAgICB9LFxuICAgICAgICB7XG4gICAgICAgICAgY2F0ZWdvcnk6ICdUcmFuc3BvcnRhdGlvbicsXG4gICAgICAgICAgYnVkZ2V0ZWQ6IDMwMCxcbiAgICAgICAgICBzcGVudDogMTk4LjQ1LFxuICAgICAgICAgIHJlbWFpbmluZzogMTAxLjU1LFxuICAgICAgICAgIHV0aWxpemF0aW9uOiA2Ni4xNSxcbiAgICAgICAgfSxcbiAgICAgICAge1xuICAgICAgICAgIGNhdGVnb3J5OiAnRW50ZXJ0YWlubWVudCcsXG4gICAgICAgICAgYnVkZ2V0ZWQ6IDIwMCxcbiAgICAgICAgICBzcGVudDogMjM1LjMsXG4gICAgICAgICAgcmVtYWluaW5nOiAtMzUuMyxcbiAgICAgICAgICB1dGlsaXphdGlvbjogMTE3LjY1LFxuICAgICAgICB9LFxuICAgICAgICB7XG4gICAgICAgICAgY2F0ZWdvcnk6ICdTaG9wcGluZycsXG4gICAgICAgICAgYnVkZ2V0ZWQ6IDM1MCxcbiAgICAgICAgICBzcGVudDogMTc4LjIsXG4gICAgICAgICAgcmVtYWluaW5nOiAxNzEuOCxcbiAgICAgICAgICB1dGlsaXphdGlvbjogNTAuOTEsXG4gICAgICAgIH0sXG4gICAgICAgIHtcbiAgICAgICAgICBjYXRlZ29yeTogJ1V0aWxpdGllcycsXG4gICAgICAgICAgYnVkZ2V0ZWQ6IDI1MCxcbiAgICAgICAgICBzcGVudDogMTg3LjAsXG4gICAgICAgICAgcmVtYWluaW5nOiA2My4wLFxuICAgICAgICAgIHV0aWxpemF0aW9uOiA3NC44LFxuICAgICAgICB9LFxuICAgICAgICB7XG4gICAgICAgICAgY2F0ZWdvcnk6ICdPdGhlcicsXG4gICAgICAgICAgYnVkZ2V0ZWQ6IDUwMCxcbiAgICAgICAgICBzcGVudDogMjQwLjAsXG4gICAgICAgICAgcmVtYWluaW5nOiAyNjAuMCxcbiAgICAgICAgICB1dGlsaXphdGlvbjogNDguMCxcbiAgICAgICAgfSxcbiAgICAgIF0sXG4gICAgfTtcblxuICAgIHJlcy5zdGF0dXMoMjAwKS5qc29uKHsgZGF0YTogbW9ja0J1ZGdldFN1bW1hcnkgfSk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignQnVkZ2V0IHN1bW1hcnkgZXJyb3I6JywgZXJyb3IpO1xuICAgIHJlcy5zdGF0dXMoNTAwKS5qc29uKHsgZXJyb3I6ICdGYWlsZWQgdG8gcmV0cmlldmUgYnVkZ2V0IHN1bW1hcnknIH0pO1xuICB9XG59XG4iXX0=