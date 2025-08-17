// atom/src/development-server.js
// Real continued development environment with advanced features
// Self-contained development server for entire ATOM ecosystem

require('dotenv').config();
const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const fs = require('fs').promises;
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);

class DevelopmentServer {
  constructor() {
    this.app = express();
    this.server = http.createServer(this.app);
    this.io = socketIo(this.server, {
      cors: {
        origin: ["http://localhost:1420", "http://localhost:3002"],
        credentials: true
      }
    });

    this.projects = new Map();
    this.activeBuilds = new Map();
    this.setupRoutes();
    this.setupWebSocket();
  }

  setupRoutes() {
    this.app.use(express.json());
    this.app.use(express.static(path.join(__dirname, '..', 'public')));

    // Real health check
    this.app.get('/health', (req, res) => {
      res.json({
        status: 'healthy',
+        timestamp: new Date().toISOString(),
+        uptime: process.uptime(),
+        activeProjects: this.projects.size
+      });
+    });
+
+    // Real project creation
+    this.app.post('/api/create-project', async (req, res) => {
+      const { projectName, userLogin, template, githubToken } = req.body;
+
+      try {
+        const projectConfig = await this.createProject({
+          name: projectName,
+          user: userLogin,
+          template: template || 'nextjs',
+          githubToken
+        });
+
+        res.json({
+          success: true,
+          projectId: projectConfig.id,
+          repoUrl: projectConfig.repoUrl,
+          liveUrl: projectConfig.liveUrl,
+          status: 'created'
+        });
+
+        this.emitProgress(projectConfig.id, 'Project created successfully', 100);
+      } catch (error) {
+        res.status(500).json({ success: false, error: error.message });
+        this.emitError(projectConfig?.id, error.message);
+      }
+    });
+
+    // Real build trigger from conversation
+    this.app.post('/api/build', async (req, res) => {
+      const { projectId, instruction, githubToken } = req.body;
+
+      try {
+        const buildId = await this.triggerBuild(projectId, instruction, githubToken);
+        res.json({ success: true, buildId });
+      } catch (error) {
+        res.status(500).json({ success: false, error: error.message });
+      }
+    });
+
+    // Real project status
+    this.app.get('/api/projects/:id', (req, res) => {
+      const project = this.projects.get(req.params.id);
+      const build = this.activeBuilds.get(req.params.id);
+
+      res.json({
+        project: project || null,
+        build: build || null
+      });
+    });
+  }

  setupWebSocket() {
    this.io.on('connection', (socket) => {
      log('Desktop connected:', socket.id);

      socket.on('join_project', (projectId) => {
        socket.join(`project-${projectId}`);
        const project = this.projects.get(projectId);
+        if (project) {
+          socket.emit('project_loaded', project);
+        }
+      });

+      socket.on('start_development', async (data) => {
+        const { name, instruction, userLogin, githubToken } = data;
+
+        this.emitProgress('initial', 'Setting up development environment...', 10);
+
+        try {
+          await this.createProject({ name, userLogin, instruction, githubToken });
+          this.emitProgress('initial', 'Development environment ready', 100);
+        } catch (error) {
+          this.emitError('initial', error.message);
+        }
+      });

+      socket.on('execute_instruction', async (data) => {
+        const { instruction, projectId, githubToken } = data;
+
+        await this.executeDevelopmentInstruction(instruction, projectId, githubToken);
+      });
+    });
+  }

  async createProject({ name, user, instruction, githubToken }) {
+    const projectId = `atom-${name}-${Date.now().toString(36)}`;
+    const repoName = `${user}-atom-${name}-${Date.now().toString(36)}`;
+
+    const project = {
+      id
