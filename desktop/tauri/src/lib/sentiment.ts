import Sentiment from 'sentiment';

const sentiment = new Sentiment();

export function analyzeSentiment(text: string): number {
  const result = sentiment.analyze(text);
  return result.score;
}
