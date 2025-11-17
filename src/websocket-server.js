// atom/src/websocket-server.js
// Real localhost WebSocket server for ATOM desktop clients

const express = require("express");
const http = require("http");
const socketIo = require("socket.io");
const cors = require("cors");
const fs = require("fs").promises;
const path = require("path");

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: ["http://localhost:1420", "http://localhost:3002"],
    methods: ["GET", "POST"],
    credentials: true,
  },
});

// Optional socket auth middleware. Set WS_SECRET to enable token-based socket auth.
io.use((socket, next) => {
  try {
    const token = socket.handshake.auth && socket.handshake.auth.token;
    if (!process.env.WS_SECRET) return next(); // auth disabled when no secret
    if (token && token === process.env.WS_SECRET) return next();
    const err = new Error('Authentication error');
    // @ts-ignore
    err.data = { message: 'Invalid token' };
    return next(err);
  } catch (err) {
    return next(err);
  }
});

// Real build tracking
const buildStates = new Map();
const projectStates = new Map();
const connectedClients = new Map();

// Presence tracking and lightweight metrics
const presenceMap = new Map(); // socketId -> { userId, username, room }
const metrics = {
  totalConnections: 0,
  currentConnections: 0,
  messagesReceived: 0,
  messagesSent: 0,
};

// Middleware
app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.static(path.join(__dirname, "..", "public")));

// Real health check endpoint
app.get("/health", (req, res) => {
  res.json({
    status: "healthy",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    activeBuilds: buildStates.size,
    activeProjects: projectStates.size,
    connectedClients: connectedClients.size,
  });
});

// Metrics endpoint: connection and message stats
app.get('/metrics', (req, res) => {
  const rooms = {};
  try {
    for (const [name] of Object.entries(io.sockets.adapter.rooms || {})) {
      rooms[name] = io.sockets.adapter.rooms.get(name)?.size || 0;
    }
  } catch (e) {
    // adapter shape may vary; ignore
  }

  res.json({
    totalConnections: metrics.totalConnections,
    currentConnections: metrics.currentConnections,
    messagesReceived: metrics.messagesReceived,
    messagesSent: metrics.messagesSent,
    rooms,
  });
});

// Simple admin broadcast (protected by WS_SECRET header when set)
app.post('/api/broadcast', async (req, res) => {
  try {
    const { room, event = 'broadcast', payload } = req.body || {};
    if (process.env.WS_SECRET && req.headers['x-admin-token'] !== process.env.WS_SECRET) {
      return res.status(403).json({ error: 'Unauthorized' });
    }

    if (room) {
      io.to(room).emit(event, payload);
    } else {
      io.emit(event, payload);
    }
    metrics.messagesSent += 1;
    res.json({ ok: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Real project status endpoint
app.get("/api/projects/:projectId", (req, res) => {
  const projectId = req.params.projectId;
  const project = projectStates.get(projectId);

  if (!project) {
    return res.status(404).json({ error: "Project not found" });
  }

  res.json(project);
});

// Real build status endpoint
app.get("/api/builds/:buildId", (req, res) => {
  const buildId = req.params.buildId;
  const build = buildStates.get(buildId);

  if (!build) {
    return res.status(404).json({ error: "Build not found" });
  }

  res.json(build);
});

// Real project list endpoint
app.get("/api/projects", (req, res) => {
  const projects = Array.from(projectStates.values());
  res.json({ projects });
});

// Real build list endpoint
app.get("/api/builds", (req, res) => {
  const builds = Array.from(buildStates.values());
  res.json({ builds });
});

// Real GitHub Actions webhook endpoint
app.post("/webhook/build-status", async (req, res) => {
  try {
    const { projectId, status, log, url, progress, buildId } = req.body;

    if (!buildId) {
      return res.status(400).json({ error: "buildId is required" });
    }

    let build = buildStates.get(buildId);
    if (!build) {
      build = {
        id: buildId,
        projectId,
        status: status || "unknown",
        progress: progress || 0,
        logs: [],
        startTime: new Date(),
        lastUpdate: new Date(),
      };
    }

    build.status = status || build.status;
    build.progress = progress || build.progress;
    build.url = url || build.url;
    build.lastUpdate = new Date();

    if (log) {
      build.logs.push({
        timestamp: new Date().toISOString(),
        message: log,
      });
    }

    buildStates.set(buildId, build);

    // Update project state if projectId is provided
    if (projectId) {
      let project = projectStates.get(projectId);
      if (project) {
        project.lastBuild = buildId;
        project.lastBuildStatus = status;
        project.lastUpdate = new Date();
        projectStates.set(projectId, project);
      }
    }

    // Broadcast to all connected desktop clients
    metrics.messagesSent += 1;
    io.emit("build_status", { buildId, build });
    metrics.messagesSent += 1;
    io.to(`project-${projectId}`).emit("project_update", { projectId, build });

    res.json({ received: true, buildId });
  } catch (error) {
    console.error("Webhook error:", error);
    res.status(500).json({ error: error.message });
  }
});

// Real-time build updates via WebSocket
io.on("connection", (socket) => {
  console.log("Desktop client connected:", socket.id);
  connectedClients.set(socket.id, { connectedAt: new Date() });
  metrics.totalConnections += 1;
  metrics.currentConnections = connectedClients.size;

  // Presence: join/leave
  socket.on('presence:join', (user) => {
    try {
      const { userId, username, room } = user || {};
      presenceMap.set(socket.id, { userId, username, room });
      const target = room ? `project-${room}` : null;
      if (target) {
        io.to(target).emit('presence:joined', { userId, username, socketId: socket.id, room });
      } else {
        io.emit('presence:joined', { userId, username, socketId: socket.id });
      }
      metrics.messagesSent += 1;
    } catch (e) {
      console.warn('presence:join handler error', e);
    }
  });

  socket.on('presence:leave', (user) => {
    try {
      const { userId, username, room } = user || {};
      presenceMap.delete(socket.id);
      const target = room ? `project-${room}` : null;
      if (target) {
        io.to(target).emit('presence:left', { userId, username, socketId: socket.id, room });
      } else {
        io.emit('presence:left', { userId, username, socketId: socket.id });
      }
      metrics.messagesSent += 1;
    } catch (e) {
      console.warn('presence:leave handler error', e);
    }
  });

  // Typing indicators (volatile - not critical)
  socket.on('typing:start', (data) => {
    try {
      const { channelId, userId, username } = data || {};
      socket.to(`project-${channelId}`).volatile.emit('typing:start', { channelId, userId, username });
      metrics.messagesSent += 1;
    } catch (e) {
      console.warn('typing:start error', e);
    }
  });

  socket.on('typing:stop', (data) => {
    try {
      const { channelId, userId, username } = data || {};
      socket.to(`project-${channelId}`).volatile.emit('typing:stop', { channelId, userId, username });
      metrics.messagesSent += 1;
    } catch (e) {
      console.warn('typing:stop error', e);
    }
  });

  // Count incoming messages for lightweight metrics
  if (typeof socket.onAny === 'function') {
    socket.onAny((event, ...args) => {
      try {
        metrics.messagesReceived += 1;
      } catch (e) {
        // ignore
      }
    });
  }

  socket.on("join_project", (projectId) => {
    socket.join(`project-${projectId}`);
    console.log(`Client ${socket.id} joined project ${projectId}`);

    const project = projectStates.get(projectId);
    if (project) {
      socket.emit("project_loaded", project);
    }
  });

  socket.on("leave_project", (projectId) => {
    socket.leave(`project-${projectId}`);
    console.log(`Client ${socket.id} left project ${projectId}`);
  });

  socket.on("start_build", async (projectData) => {
    const { projectId, instruction, repoName, githubToken } = projectData;

    console.log(`Build started for ${projectId}: ${instruction}`);

    const buildId = `build-${projectId}-${Date.now().toString(36)}`;

    // Initialize build state
    const build = {
      id: buildId,
      projectId,
      instruction,
      repoName,
      status: "queued",
      progress: 0,
      logs: ["Build queued..."],
      startTime: new Date(),
      lastUpdate: new Date(),
    };

    buildStates.set(buildId, build);

    // Initialize or update project state
    let project = projectStates.get(projectId);
    if (!project) {
      project = {
        id: projectId,
        name: repoName,
        repoName,
        status: "building",
        builds: [buildId],
        createdAt: new Date(),
        lastUpdate: new Date(),
      };
    } else {
      project.builds.push(buildId);
      project.status = "building";
      project.lastUpdate = new Date();
    }
    projectStates.set(projectId, project);

    // Emit initial state
    metrics.messagesSent += 1;
    socket.emit("build_status", { buildId, build });
    metrics.messagesSent += 1;
    io.to(`project-${projectId}`).emit("project_update", {
      projectId,
      project,
    });

    try {
      // Start actual GitHub Actions workflow
      const response = await fetch(
        "https://api.github.com/repos/rush86999/atom/dispatches",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${githubToken || process.env.GITHUB_TOKEN}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            event_type: "start_build",
            client_payload: {
              projectId,
              buildId,
              instruction,
              repoName,
            },
          }),
        },
      );

      if (!response.ok) {
        throw new Error(
          `GitHub API error: ${response.status} ${response.statusText}`,
        );
      }

      build.status = "dispatched";
      build.logs.push("Build dispatched to GitHub Actions");
      buildStates.set(buildId, build);

      metrics.messagesSent += 1;
      socket.emit("build_status", { buildId, build });
      metrics.messagesSent += 1;
      io.to(`project-${projectId}`).emit("project_update", {
        projectId,
        project,
      });
    } catch (error) {
      console.error("Build start error:", error);

      build.status = "failed";
      build.error = error.message;
      build.logs.push(`Build failed: ${error.message}`);
      buildStates.set(buildId, build);

      project.status = "failed";
      projectStates.set(projectId, project);

      metrics.messagesSent += 1;
      socket.emit("build_error", { buildId, error: error.message });
      metrics.messagesSent += 1;
      io.to(`project-${projectId}`).emit("project_error", {
        projectId,
        error: error.message,
      });
    }
  });

  socket.on("get_build_status", (buildId) => {
    const build = buildStates.get(buildId) || {
      status: "not_found",
      logs: ["No build found with this ID"],
    };
    socket.emit("build_status", { buildId, build });
  });

  socket.on("get_project_status", (projectId) => {
    const project = projectStates.get(projectId);
    if (!project) {
      socket.emit("project_error", { projectId, error: "Project not found" });
      return;
    }

    // Get latest build for this project
    const latestBuildId = project.builds?.[project.builds.length - 1];
    const latestBuild = latestBuildId ? buildStates.get(latestBuildId) : null;

    socket.emit("project_status", {
      projectId,
      project,
      latestBuild,
    });
  });

  socket.on("cancel_build", (buildId) => {
    const build = buildStates.get(buildId);
    if (build && build.status === "running") {
      build.status = "cancelled";
      build.logs.push("Build cancelled by user");
      build.endTime = new Date();
      buildStates.set(buildId, build);

      metrics.messagesSent += 1;
      socket.emit("build_status", { buildId, build });
      metrics.messagesSent += 1;
      io.to(`project-${build.projectId}`).emit("project_update", {
        projectId: build.projectId,
        project: projectStates.get(build.projectId),
      });
    }
  });

  socket.on("delete_project", async (projectId) => {
    try {
      const project = projectStates.get(projectId);
      if (!project) {
        socket.emit("project_error", { projectId, error: "Project not found" });
        return;
      }

      // Clean up build states
      if (project.builds) {
        project.builds.forEach((buildId) => buildStates.delete(buildId));
      }

      // Remove project
      projectStates.delete(projectId);

      metrics.messagesSent += 1;
      socket.emit("project_deleted", { projectId });
      metrics.messagesSent += 1;
      io.emit("project_removed", { projectId });
    } catch (error) {
      socket.emit("project_error", { projectId, error: error.message });
    }
  });

  socket.on("disconnect", () => {
    console.log("Desktop client disconnected:", socket.id);
    connectedClients.delete(socket.id);
    // Update metrics
    metrics.currentConnections = connectedClients.size;

    // Remove presence if it exists and broadcast leave
    const p = presenceMap.get(socket.id);
    if (p) {
      const { userId, username, room } = p;
      const target = room ? `project-${room}` : null;
      if (target) {
        io.to(target).emit('presence:left', { userId, username, socketId: socket.id, room });
      } else {
        io.emit('presence:left', { userId, username, socketId: socket.id });
      }
      presenceMap.delete(socket.id);
      metrics.messagesSent += 1;
    }
  });
});

// Real status endpoint for polling fallback
app.get("/status/:projectId", (req, res) => {
  const projectId = req.params.projectId;
  const project = projectStates.get(projectId);

  if (!project) {
    return res.status(404).json({ status: "not_found" });
  }

  const latestBuildId = project.builds?.[project.builds.length - 1];
  const latestBuild = latestBuildId ? buildStates.get(latestBuildId) : null;

  res.json({
    project,
    latestBuild,
  });
});

// Serve static files for build artifacts
app.use("/builds", express.static(path.join(__dirname, "..", "builds")));

// Real localhost server
const PORT = process.env.PORT || 3002;
server.listen(PORT, () => {
  console.log(`🚀 WebSocket server running on http://localhost:${PORT}`);
  console.log(`📡 WebSocket endpoint: ws://localhost:${PORT}`);
  console.log(`✅ Ready for desktop connections`);
  console.log(`🌐 Health check available at http://localhost:${PORT}/health`);
});

// Periodically broadcast metrics so clients can render live charts
setInterval(() => {
  try {
    io.emit('metrics:update', { ...metrics, timestamp: new Date().toISOString() });
  } catch (e) {
    // ignore
  }
}, 5000);

// Graceful shutdown
process.on("SIGTERM", () => {
  console.log("Shutting down WebSocket server...");
  server.close(() => {
    console.log("✅ Server closed");
    process.exit(0);
  });
});

process.on("SIGINT", () => {
  console.log("Shutting down WebSocket server...");
  server.close(() => {
    console.log("✅ Server closed");
    process.exit(0);
  });
});

// Export for testing
module.exports = { app, server, io, buildStates, projectStates };
