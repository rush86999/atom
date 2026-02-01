"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.tradingSkills = void 0;
const AutonomousTradingService_1 = require("../services/trading/AutonomousTradingService");
// A map to store the running autonomous trading services
const autonomousTradingServices = new Map();
exports.tradingSkills = [
    {
        name: 'start_autonomous_trading',
        description: 'Start the autonomous trading system.',
        parameters: {
            type: 'object',
            properties: {
                userId: { type: 'string' },
                strategyName: { type: 'string' },
            },
            required: ['userId', 'strategyName'],
        },
        handler: async (params) => {
            let service = autonomousTradingServices.get(params.userId);
            if (service) {
                return 'Autonomous trading is already running.';
            }
            service = new AutonomousTradingService_1.AutonomousTradingService(params.userId, params.strategyName);
            autonomousTradingServices.set(params.userId, service);
            return service.start();
        },
    },
    {
        name: 'stop_autonomous_trading',
        description: 'Stop the autonomous trading system.',
        parameters: {
            type: 'object',
            properties: {
                userId: { type: 'string' },
            },
            required: ['userId'],
        },
        handler: async (params) => {
            const service = autonomousTradingServices.get(params.userId);
            if (service) {
                const result = service.stop();
                autonomousTradingServices.delete(params.userId);
                return result;
            }
            return 'Autonomous trading is not running.';
        },
    },
];
//# sourceMappingURL=tradingSkills.js.map