// /app/atomic-docker/project/functions/features-apply/_libs/temp_tests/test_categorization_logic.js

// 1. Define Inputs
const sentence = 'Project Alpha technical review. Discuss architecture.';
const labelNames = ['Technical', 'Meeting', 'Review', 'Marketing'];

// 2. Simulate (Mock) OpenAI Call and Response Processing
const mockedLlmResponseString = '["Technical", "Review"]'; // Simulate LLM identifying these two labels.
let matchedLabels = [];

try {
  matchedLabels = JSON.parse(mockedLlmResponseString);
  if (
    !Array.isArray(matchedLabels) ||
    !matchedLabels.every((item) => typeof item === 'string')
  ) {
    console.error(
      'Mocked LLM response is not a valid JSON array of strings:',
      mockedLlmResponseString
    );
    matchedLabels = []; // Fallback to empty if not a string array
  }
} catch (parseError) {
  console.error(
    'Error parsing mocked LLM response:',
    parseError,
    mockedLlmResponseString
  );
  matchedLabels = [];
}

const scores = labelNames.map((label) =>
  matchedLabels.includes(label) ? 0.9 : 0.1
);

// 3. Construct Expected Result
// For labelNames = ["Technical", "Meeting", "Review", "Marketing"]
// and matchedLabels = ["Technical", "Review"]
// Expected scores should be [0.9, 0.1, 0.9, 0.1]
const expectedScores = [0.9, 0.1, 0.9, 0.1];

// 4. Verify and Print Output
console.log('Input Sentence:', sentence);
console.log('Possible Labels:', labelNames);
console.log('Mocked LLM JSON Response:', mockedLlmResponseString);
console.log('Parsed Matched Labels from LLM:', matchedLabels);
console.log('Calculated Scores:', scores);
console.log('Expected Scores:', expectedScores);

const isMatch =
  scores.length === expectedScores.length &&
  scores.every((value, index) => value === expectedScores[index]);
console.log('Scores match expected:', isMatch);

console.log('Test script finished.');
