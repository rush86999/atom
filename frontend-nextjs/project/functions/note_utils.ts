// Basic note utilities for the project
export function createNoteFromText(text: string, title?: string): any {
  return {
    title: title || 'Untitled Note',
    content: text,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
}

export function extractNoteSummary(text: string, maxLength: number = 100): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

export function sanitizeNoteContent(content: string): string {
  // Basic sanitization - remove script tags and other potentially dangerous content
  return content
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/on\w+="[^"]*"/g, '')
    .replace(/on\w+='[^']*'/g, '')
    .replace(/on\w+=\w+/g, '');
}

export function formatNoteForDisplay(note: any): string {
  return `# ${note.title}\n\n${note.content}`;
}

// Default export for backward compatibility
export default {
  createNoteFromText,
  extractNoteSummary,
  sanitizeNoteContent,
  formatNoteForDisplay
};
