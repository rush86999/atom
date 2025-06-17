// test_embedding_384_logic.js

// 1. Set Placeholder API Key
process.env.OPENAI_API_KEY = "test_key_emb384_123";

// 2. Import OpenAI
const OpenAI = require('openai');

// 3. Instantiate Client
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// 4. Attempt API Call in an async IIFE
(async () => {
    console.log("Attempting to call OpenAI embeddings API with text-embedding-3-small and dimensions: 384");
    try {
        const embeddingParams = {
            model: 'text-embedding-3-small',
            input: 'Sample event text for 384-dimensional embedding.',
            dimensions: 384
        };
        console.log("Using params:", JSON.stringify(embeddingParams));
        const response = await openai.embeddings.create(embeddingParams);
        console.log("OpenAI API call supposedly succeeded (unexpected with placeholder key):", response);
    } catch (error) {
        console.error("OpenAI API call failed (expected with placeholder key):");
        if (error instanceof OpenAI.APIError) {
            console.error("Error Name:", error.name);
            console.error("Error Status Code:", error.status);
            console.error("Error Message:", error.message);
            console.error("Error Type:", error.type);
            // console.error("Error Code:", error.code); // Also useful
            // console.error("Error Param:", error.param);
        } else {
            console.error("Non-OpenAI API Error:", error.message);
        }
    } finally {
        console.log("Test script finished.");
    }
})();
