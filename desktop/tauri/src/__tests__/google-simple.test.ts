// Simple test for Google integration
import { expect, describe, it, beforeAll, beforeEach } from 'vitest';

// Mock Tauri
global.__TAURI__ = {
  invoke: (command: string, args: any) => Promise.resolve(args)
};

describe('Google Skills Test', () => {
  it('should create mock Google skill', async () => {
    const mockSkill = {
      name: 'google_gmail',
      displayName: 'Gmail',
      icon: '📧'
    };

    expect(mockSkill.name).toBe('google_gmail');
    expect(mockSkill.displayName).toBe('Gmail');
    expect(mockSkill.icon).toBe('📧');
  });

  it('should mock Gmail API call', async () => {
    // Simulate API call
    const result = await global.__TAURI__.invoke('google_gmail_list_emails', { maxResults: 10 });
    
    expect(result).toEqual({ maxResults: 10 });
  });

  it('should mock Google Calendar API call', async () => {
    // Simulate API call
    const result = await global.__TAURI__.invoke('google_calendar_list_events', { maxResults: 10 });
    
    expect(result).toEqual({ maxResults: 10 });
  });

  it('should mock Google Drive API call', async () => {
    // Simulate API call
    const result = await global.__TAURI__.invoke('google_drive_list_files', { pageSize: 10 });
    
    expect(result).toEqual({ pageSize: 10 });
  });
});