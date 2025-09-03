import express from "express";
import cors from "cors";
import helmet from "helmet";
import morgan from "morgan";
import dotenv from "dotenv";
import { spawn } from "child_process";
import path from "path";

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(helmet());
app.use(cors());
app.use(morgan("combined"));
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true }));

// Health check endpoint
app.get("/healthz", (req, res) => {
  res.status(200).json({ status: "ok", timestamp: new Date().toISOString() });
});

// Root endpoint
app.get("/", (req, res) => {
  res.json({
    message: "Atom Functions Service",
    version: "1.0.0",
    status: "running",
  });
});

// Import and register function handlers
// Note: This is a placeholder - actual function routes should be imported here
// based on the existing function structure

// Example route structure for functions
app.use("/v1/functions", (req, res) => {
  res.status(501).json({
    error: "Function endpoints not yet implemented",
    message:
      "Function routes need to be configured based on existing function structure",
  });
});

// Proxy endpoints for Python functions
app.use("/v1/functions/audio-processor", (req, res) => {
  // Proxy to Python audio processor
  const pythonProcess = spawn("python3", [
    path.join(__dirname, "../audio_processor/handler.py"),
  ]);

  // Handle Python process communication
  // This is a placeholder - actual implementation would need proper request forwarding
  pythonProcess.stdout.on("data", (data) => {
    res.json(JSON.parse(data.toString()));
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`Python error: ${data}`);
    res.status(500).json({ error: "Python function error" });
  });
});

app.use("/v1/functions/personalized-learning", (req, res) => {
  // Proxy to Python personalized learning assistant
  const pythonProcess = spawn("uvicorn", [
    "personalized_learning_assistant.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8001",
  ]);

  // This is a placeholder - actual implementation would need proper request forwarding
  res.status(501).json({
    error: "Python function proxy not fully implemented",
    message: "Personalized learning assistant needs proper request forwarding",
  });
});

// Error handling middleware
app.use(
  (
    err: any,
    req: express.Request,
    res: express.Response,
    next: express.NextFunction,
  ) => {
    console.error("Error:", err);
    res.status(500).json({
      error: "Internal server error",
      message:
        process.env.NODE_ENV === "development"
          ? err.message
          : "Something went wrong",
    });
  },
);

// 404 handler
app.use("*", (req, res) => {
  res.status(404).json({ error: "Endpoint not found" });
});

// Start server
app.listen(PORT, () => {
  console.log(`Atom Functions Service running on port ${PORT}`);
  console.log(`Health check available at http://localhost:${PORT}/healthz`);

  // Start Python functions as subprocesses
  console.log("Starting Python function subprocesses...");

  // Start audio processor (Flask)
  const audioProcessor = spawn(
    "python3",
    [path.join(__dirname, "../audio_processor/handler.py")],
    {
      env: { ...process.env, FLASK_ENV: "production" },
    },
  );

  audioProcessor.stdout.on("data", (data) => {
    console.log(`Audio Processor: ${data}`);
  });

  audioProcessor.stderr.on("data", (data) => {
    console.error(`Audio Processor Error: ${data}`);
  });

  // Start personalized learning assistant (FastAPI)
  const learningAssistant = spawn(
    "uvicorn",
    [
      "personalized_learning_assistant.main:app",
      "--host",
      "0.0.0.0",
      "--port",
      "8001",
      "--workers",
      "1",
    ],
    {
      cwd: path.join(__dirname, ".."),
      env: process.env,
    },
  );

  learningAssistant.stdout.on("data", (data) => {
    console.log(`Learning Assistant: ${data}`);
  });

  learningAssistant.stderr.on("data", (data) => {
    console.error(`Learning Assistant Error: ${data}`);
  });
});

// Graceful shutdown
process.on("SIGTERM", () => {
  console.log("SIGTERM received, shutting down gracefully");
  process.exit(0);
});

process.on("SIGINT", () => {
  console.log("SIGINT received, shutting down gracefully");
  process.exit(0);
});

export default app;
