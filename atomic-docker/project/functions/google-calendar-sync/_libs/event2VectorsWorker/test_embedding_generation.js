// Import the function to test
import { convertEventTitleToOpenAIVector } from './api-helper.js'; // Assuming api-helper.ts compiles to api-helper.js

// Define a sample event title
const sampleTitle = 'Team meeting to discuss Q3 roadmap';

// Main test function
async function testEmbeddingGeneration() {
  console.log(`Attempting to generate embedding for title: "${sampleTitle}"`);
  try {
    const vector = await convertEventTitleToOpenAIVector(sampleTitle);

    if (vector && vector.length > 0) {
      console.log(
        `Successfully generated vector with dimensions: ${vector.length}`
      );
      console.log(
        `First 5 elements of the vector: [${vector.slice(0, 5).join(', ')}]`
      );
    } else {
      console.log(
        'Failed to generate vector or received an empty/invalid vector.'
      );
    }
  } catch (error) {
    console.error('Error during embedding generation:', error);
  }
}

// Run the test
testEmbeddingGeneration();
