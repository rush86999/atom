// DISABLED: Temporarily disabled for build optimization - 2025-09-03T14:38:43.013Z
// import { NextApiRequest, NextApiResponse } from "next";
// import { LlamaCPPBackend } from "../../../src/llm/llamaCPPBackend";
// 
// const llama = new LlamaCPPBackend({
//   serverPort: 8080,
//   gpuLayers: 28,
//   contextSize: 4096,
// });
// 
// export default async function handler(
//   req: NextApiRequest,
//   res: NextApiResponse,
// ) {
//   if (req.method === "POST") {
//     try {
//       const { prompt, model, max_tokens = 512, temperature = 0.7 } = req.body;
// 
//       if (!prompt) {
//         return res.status(400).json({ error: "Prompt is required" });
//       }
// 
//       // Start llama.cpp server if not running
//       if (!llama.isRunning()) {
//         await llama.startServer();
//       }
// 
//       const response = await llama.generate({
//         prompt,
//         model: model || "llama-3-8b",
//         max_tokens,
//         temperature,
//       });
// 
//       res.status(200).json(response);
//     } catch (error) {
//       res.status(500).json({ error: error.message || "Internal server error" });
//     }
//   } else if (req.method === "GET") {
//     // Return available models and server status
//     try {
//       const models = await llama.listModels();
//       res.status(200).json({
//         models,
//         isRunning: llama.isRunning(),
//         serverPort: llama.getPort(),
//       });
//     } catch (error) {
//       res.status(500).json({ error: error.message || "Failed to get models" });
//     }
//   } else {
//     res.setHeader("Allow", ["GET", "POST"]);
//     res.status(405).end(`Method ${req.method} Not Allowed`);
//   }
// }
// 