// atom/src/websocket-server.js
// Real localhost WebSocket server for ATOM desktop clients

const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "http://localhost:1420",
    methods: ["GET", "POST"]
  }
});

// Real build tracking
const buildStates = new Map();

// Real-time build updates
io.on('connection', (socket) => {
  console.log('Desktop client connected:', socket.id);

  socket.on('start_build', (projectData) => {
    const { projectId, instruction, repoName } = projectData;

    // Start actual GitHub Actions workflow
    fetch('https://api.github.com/repos/rush86999/atom/dispatches', {
      method: 'POST',
+      headers: {
+        'Authorization': `Bearer ${process.env.GITHUB_TOKEN}`,
+        'Accept': 'application/vnd.github.v3+json'
+      },
+      body: JSON.stringify({
+        event_type: 'start_build',
+        client_payload: {
+          projectId,
+          instruction,
+          repoName
+        }
+      })
+    });
+
+    console.log(`Build started for ${projectId}: ${instruction}`);
+
+    // Track this build
+    buildStates.set(projectId, {
+      status: 'queued',
+      instruction,
+      startTime: new Date(),
+      log: ['Build queued...'],
+      progress: 0
+    });
+
+    // Emit initial state
+    socket.emit('build_status', {
+      projectId,
+      ...buildStates.get(projectId)
+    });
+  });

+  socket.on('get_build_status', (projectId) => {
+    const status = buildStates.get(projectId) || {
+      status: 'not_found',
+      log: ['No build found']
+    };
+    socket.emit('build_status', { projectId, ...status });
+  });

+  socket.on('disconnect', () => {
+    console.log('Desktop client disconnected:', socket.id);
+  });
+});

+// Real GitHub Actions webhooks
+app.use(cors());
+app.use(express.json());

+// Real webhook endpoint from GitHub Actions
+app.post('/webhook/build-status', (req, res) => {
+  const { projectId, status, log, url, progress } = req.body;
+
+  buildStates.set(projectId, {
+    ...buildStates.get(projectId),
+    status,
+    log: [...(buildStates.get(projectId)?.log || []), log],
+    url,
+    progress,
+    lastUpdate: new Date()
+  });

+  // Broadcast to all connected desktop clients
+  io.emit('build_status', { projectId, ...buildStates.get(projectId) });
+
+  res.json({ received: true });
+});

+// Real status endpoint for polling fallback
+app.get('/status/:projectId', (req, res) => {
+  const projectId = req.params.projectId;
+  const status = buildStates.get(projectId) || { status: 'not_found' };
+  res.json(status);
});

// Serve static files (optional)
app.use('/builds', express.static('./builds'));

// Real localhost server
const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`🚀 WebSocket server running on http://localhost:${PORT}`);
  console.log(`📡 WebSocket endpoint: ws://localhost:${PORT}`);
  console.log(`✅ Ready for desktop connections`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('Shutting down WebSocket server...');
  server.close(() => {
    console.log('✅ Server closed');
  });
});
