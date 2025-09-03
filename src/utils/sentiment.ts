import Sentiment from 'sentiment';

const sentiment = new Sentiment();

/**
 * Analyzes the sentiment of text and returns a score between -1 (negative) and 1 (positive)
 * @param text The text to analyze
 * @returns A sentiment score between -1 and 1
 */
export function analyzeSentiment(text: string): number {
  const result = sentiment.analyze(text);
  // Normalize the score to be between -1 and 1
  return Math.max(-1, Math.min(1, result.score / 5));
}

/**
 * Gets a sentiment label based on the score
 * @param score The sentiment score
 * @returns A human-readable sentiment label
 */
export function getSentimentLabel(score: number): string {
  if (score >= 0.6) return 'Very Positive';
  if (score >= 0.2) return 'Positive';
  if (score >= -0.2) return 'Neutral';
  if (score >= -0.6) return 'Negative';
  return 'Very Negative';
}

/**
 * Analyzes sentiment and returns both score and label
 * @param text The text to analyze
 * @returns An object with score and label
 */
export function analyzeSentimentWithLabel(text: string): { score: number; label: string } {
  const score = analyzeSentiment(text);
  const label = getSentimentLabel(score);
  return { score, label };
}
