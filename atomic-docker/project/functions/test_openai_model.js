// test_openai_model.js
import OpenAI from 'openai'; // Imports the OpenAI class

async function main() {
  // 1. Set placeholder API key
  process.env.OPENAI_API_KEY = 'test_key_123';
  console.log(`OPENAI_API_KEY set to: ${process.env.OPENAI_API_KEY}`);

  // 2. Instantiate OpenAI client
  // Ensure apiKey is explicitly passed if process.env might not be picked up as expected by the lib
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  console.log('OpenAI client instantiated.');

  // 4. Announce API call attempt
  const modelToTest = 'text-embedding-3-small';
  const testInput = 'This is a test input string.';
  console.log(
    `Attempting to call OpenAI embeddings API with model: '${modelToTest}' and input: '${testInput}'`
  );

  try {
    // 5. Call OpenAI embeddings API
    const embedding = await openai.embeddings.create({
      model: modelToTest,
      input: testInput,
    });
    // 6. Partial success if call is attempted (even if it fails with auth error)
    console.log('OpenAI API call was made.'); // This line might not be reached if auth error is immediate
    console.log(
      'Embedding result (should not happen with placeholder key):',
      embedding
    );
  } catch (error) {
    // 7. Print full error message
    console.error('Error during OpenAI API call:', error);
  } finally {
    // 8. Announce script finish
    console.log('Test script finished.');
  }
}

main();
