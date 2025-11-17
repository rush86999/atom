export class Timer {
  private timerId: NodeJS.Timeout | null = null;
  private remaining: number;
  private callback: () => void | Promise<void>;
  private startTime: number = 0;

  constructor(callback: () => void | Promise<void>, delay: number) {
    this.callback = callback;
    this.remaining = delay;
    this.resume();
  }

  pause() {
    if (this.timerId) {
      clearTimeout(this.timerId);
      this.timerId = null;
      this.remaining -= Date.now() - this.startTime;
    }
  }

  resume() {
    if (this.timerId) {
      return;
    }

    this.startTime = Date.now();
    this.timerId = setTimeout(this.callback, this.remaining);
  }

  stop() {
    if (this.timerId) {
      clearTimeout(this.timerId);
      this.timerId = null;
    }
  }
}
