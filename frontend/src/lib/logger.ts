type LogLevel = 'debug' | 'info' | 'warn' | 'error';

class FrontendLogger {
  private async log(level: LogLevel, message: string, data?: any) {
    // Also log to browser console for development
    if (level === 'error') {
      console.error(message, data);
    } else if (level === 'warn') {
      console.warn(message, data);
    } else {
      console.log(`[${level.toUpperCase()}]`, message, data);
    }

    try {
      await fetch('/api/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level, message, data }),
      });
    } catch (e) {
      // If logging fails, we just silent it to avoid infinite loops or crashes
    }
  }

  debug(message: string, data?: any) { this.log('debug', message, data); }
  info(message: string, data?: any) { this.log('info', message, data); }
  warn(message: string, data?: any) { this.log('warn', message, data); }
  error(message: string, data?: any) { this.log('error', message, data); }
}

export const logger = new FrontendLogger();
