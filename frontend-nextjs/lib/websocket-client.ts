export interface WebSocketMessage {
    type: string;
    timestamp: string;
    message?: string;
    execution_id?: string;
    data?: any;
}

export class WebSocketClient {
    private listeners: Record<string, Function[]> = {};

    constructor(private config: any) { }

    async connect() {
        console.log('Mock WebSocket connected');
        return Promise.resolve();
    }

    subscribe(channel: string) {
        console.log(`Subscribed to ${channel}`);
    }

    on(event: string, callback: (message: WebSocketMessage) => void) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
        return () => {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        };
    }

    disconnect() {
        console.log('Mock WebSocket disconnected');
    }
}

export const getWebSocketClient = (config: any) => {
    return new WebSocketClient(config);
};
