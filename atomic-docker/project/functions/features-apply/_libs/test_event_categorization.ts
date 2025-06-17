// test_event_categorization.ts

// Dynamically import the target function and types
// Using .ts extension assuming direct execution with ts-node or similar
import { findBestMatchCategory2 } from './api-helper.ts';

// Simplified types for the test to avoid importing complex structures if not strictly necessary for the test's purpose.
// The 'as any' assertion will be used for eventDetails to bypass full type checking for this specific test.
type CategoryType = { name: string };
// type ClassificationResponseBodyType = { labels: string[]; scores: number[]; sentence: string }; // Type of 'result'

async function runTest() {
  // 1. Set placeholder API key
  process.env.OPENAI_API_KEY = "test_key_cat_123";
  console.log(`OPENAI_API_KEY set to: ${process.env.OPENAI_API_KEY}`);

  // 3. Define a sample eventDetails
  const eventDetails = {
    summary: 'Project Alpha technical review',
    notes: 'Discuss architecture and integration points.',
    // id: 'test-event-123' // Add other fields if findBestMatchCategory2 strictly needs them, though not for sentence construction
  };

  // 4. Define sample possibleLabels
  const possibleLabels: CategoryType[] = [
    { name: 'Technical' },
    { name: 'Meeting' },
    { name: 'Review' },
    { name: 'Planning' },
    { name: 'Marketing' }
  ];

  // 5. Announce call
  console.log(`Calling findBestMatchCategory2 with event: "${eventDetails.summary}" and labels: ${possibleLabels.map(l => l.name).join(', ')}`);

  // 6. Call the function and print result/error
  try {
    // Using 'as any' for eventDetails to simplify the test, as EventPlusType is complex.
    // The findBestMatchCategory2 function primarily uses summary and notes.
    const result = await findBestMatchCategory2(eventDetails as any, possibleLabels);
    console.log('Result from findBestMatchCategory2:', JSON.stringify(result, null, 2));
  } catch (e) {
    console.error('Error during findBestMatchCategory2 call in test script:', e);
  } finally {
    console.log("Test script finished.");
  }
}

runTest();
