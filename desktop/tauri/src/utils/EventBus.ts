/**
 * Event Bus for Component Communication
 */

export type EventHandler = (data: any) => void;

export class EventBus {
  private static listeners: Map<string, EventHandler[]> = new Map();

  static on(event: string, handler: EventHandler): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(handler);
  }

  static off(event: string, handler?: EventHandler): void {
    if (!this.listeners.has(event)) return;

    if (handler) {
      const handlers = this.listeners.get(event)!;
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    } else {
      this.listeners.delete(event);
    }
  }

  static emit(event: string, data: any): void {
    const handlers = this.listeners.get(event);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in event handler for ${event}:`, error);
        }
      });
    }
  }

  static once(event: string, handler: EventHandler): void {
    const onceHandler = (data: any) => {
      handler(data);
      this.off(event, onceHandler);
    };
    this.on(event, onceHandler);
  }
}