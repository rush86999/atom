// IMPORTANT: The OpenTelemetry SDK must be initialized BEFORE any other modules that need to be instrumented.
// This is typically handled by NODE_OPTIONS="--require ./opentelemetry.js" in the container environment.
// Ensure `opentelemetry.js` is in the same directory as this `server.ts` or adjust path.

import path from 'path';
import express, { Request, Response, NextFunction } from 'express'; // Added Response, NextFunction
import glob from 'glob';
import { WebSocketServer, WebSocket } from 'ws';
import qs from 'qs';
import * as jose from 'jose';
import http from 'http';
import winston from 'winston';
import expressWinston from 'express-winston';
import { trace, context as otelContext, SpanStatusCode, Attributes } from '@opentelemetry/api'; // For manual span attributes

// Import custom metrics from opentelemetry.js
import {
  httpServerRequestsTotal,
  httpServerRequestDurationSeconds,
  activeWebsocketConnections,
  websocketMessagesReceivedTotal,
} from './opentelemetry'; // Assuming opentelemetry.js is in the same directory

// Agenda imports
import { startAgenda, stopAgenda } from '../../project/functions/agendaService';
import { _internalHandleMessage } from '../../project/functions/atom-agent/handler';
import type { InterfaceType } from '../../project/functions/atom-agent/conversationState';

const PORT = process.env.PORT || 3000; // Standardized PORT usage
const PORT2 = process.env.PORT2 || 3030; // Standardized PORT2 usage

const serviceName = process.env.OTEL_SERVICE_NAME || 'functions-service';
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';

// Configure Winston Logger
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json(), // Output logs in JSON format
    winston.format((info) => { // Custom formatter to add standard fields
      info.service_name = serviceName;
      info.version = serviceVersion;
      // trace_id and span_id should be added by WinstonInstrumentation logHook
      // If not, or for logs outside spans, add them manually here if possible:
      const currentSpan = trace.getSpan(otelContext.active());
      if (currentSpan) {
        const spanContext = currentSpan.spanContext();
        if (spanContext && spanContext.traceId) {
          info.trace_id = spanContext.traceId;
          info.span_id = spanContext.spanId;
        }
      }
      return info;
    })()
  ),
  transports: [
    new winston.transports.Console(), // Log to console (stdout/stderr)
  ],
  exitOnError: false, // Do not exit on handled exceptions
});

function onSocketError(err: Error) { // Typed error
  logger.error({ message: 'WebSocket socket error', error: err.message, stack_trace: err.stack });
}

const JWKS = jose.createRemoteJWKSet(new URL(`${process.env.APP_CLIENT_URL}/api/auth/jwt/jwks.json`));

const connectedClients = new Map<string, WebSocket>();

interface AgentClientCommand {
  command_id: string;
  action: 'START_RECORDING_SESSION' | 'STOP_RECORDING_SESSION' | 'CANCEL_RECORDING_SESSION';
  payload?: {
    suggestedTitle?: string;
    linkedEventId?: string;
  };
}

export async function sendCommandToUser(userId: string, command: AgentClientCommand): Promise<boolean> {
  const clientSocket = connectedClients.get(userId);
  const operation_name = 'SendCommandToUser';
  if (clientSocket && clientSocket.readyState === WebSocket.OPEN) {
    const messageToSend = { type: 'AGENT_COMMAND', payload: command };
    try {
      clientSocket.send(JSON.stringify(messageToSend));
      logger.info({ operation_name, user_id: userId, command_action: command.action, success: true }, 'Sent command to user');
      return true;
    } catch (error: any) {
      logger.error({ operation_name, user_id: userId, command_action: command.action, success: false, error_message: error.message, stack_trace: error.stack }, 'Error sending command to user');
      return false;
    }
  } else {
    logger.warn({ operation_name, user_id: userId, command_action: command.action, success: false, reason: 'No active WebSocket or socket not open' }, 'Failed to send command to user');
    return false;
  }
}

const main = async () => {
  const app = express();
  const app2 = express();

  // Replace Morgan with express-winston for structured request logging
  app.use(expressWinston.logger({
    winstonInstance: logger,
    meta: true, // Log metadata such as req.url, req.method, etc.
    msg: "HTTP {{req.method}} {{req.url}} {{res.statusCode}} {{res.responseTime}}ms",
    expressFormat: false, // Use winston's format, not morgan's
    colorize: false, // JSON logs should not be colorized
    skip: (req, _res) => req.path === '/healthz', // Skip health checks
    dynamicMeta: (req, res) => { // Add custom attributes to request logs
        const meta: Attributes = {};
        if (req) {
            meta.http_method = req.method;
            meta.http_path = req.originalUrl || req.url;
            // meta.user_id = req.user?.id; // If user context is available
        }
        if (res) {
            meta.http_status_code = res.statusCode;
        }
        return meta;
    }
  }));
  app2.use(expressWinston.logger({ // Apply to app2 as well
    winstonInstance: logger,
    meta: true,
    msg: "HTTP {{req.method}} {{req.url}} {{res.statusCode}} {{res.responseTime}}ms (app2)",
    expressFormat: false,
    colorize: false,
    skip: (req, _res) => req.path === '/healthz',
    dynamicMeta: (req, res) => {
        const meta: Attributes = {};
        if (req) {
            meta.http_method = req.method;
            meta.http_path = req.originalUrl || req.url;
        }
        if (res) {
            meta.http_status_code = res.statusCode;
        }
        return meta;
    }
  }));


  // Middleware for custom metrics for all requests
  const recordHttpMetrics = (req: Request, res: Response, next: NextFunction) => {
    const startEpoch = Date.now();
    res.on('finish', () => {
      const endEpoch = Date.now();
      const durationSeconds = (endEpoch - startEpoch) / 1000;

      const attributes = {
        http_route: req.route ? req.route.path : (req.originalUrl || req.url).split('?')[0], // Use route path if available, else full path
        http_method: req.method,
        status_code: res.statusCode,
      };
      httpServerRequestsTotal.add(1, attributes);
      httpServerRequestDurationSeconds.record(durationSeconds, attributes);
    });
    next();
  };
  app.use(recordHttpMetrics);
  app2.use(recordHttpMetrics); // Apply to app2 as well

  app.use(
    express.json({
      limit: '6MB',
      verify: (req, _res, buf) => {
        (req as any).rawBody = buf.toString();
      },
    })
  );
  app2.use(
    express.json({
      limit: '6MB',
      verify: (req, _res, buf) => {
        (req as any).rawBody = buf.toString();
      },
    })
  );

  app.use(express.urlencoded({ extended: true }));
  app2.use(express.urlencoded({ extended: true }));

  // Authentication middleware (app)
  app.use(async (req: Request, res: Response, next: NextFunction) => { // Typed req, res, next
    const operation_name = `AuthMiddlewareApp1`;
    if (req.path.match(/\/public/) || req.path.match(/\-public$/)) {
      return next();
    }
    if (req.path.match(/\-admin$/)) {
      const authorizationToken = req.headers.authorization;
      if (!authorizationToken || !authorizationToken.startsWith('Basic ')) {
        logger.warn({ operation_name, path: req.path, reason: 'Missing or malformed Basic auth for admin path' });
        return res.status(401).send("Unauthorized");
      }
      const encodedCreds = authorizationToken.split(' ')[1];
      const verifyToken = Buffer.from(encodedCreds, 'base64').toString().split(':')[1];
      if (verifyToken !== process.env.BASIC_AUTH) {
        logger.warn({ operation_name, path: req.path, reason: 'Invalid Basic auth token for admin path' });
        return res.status(401).send("Unauthorized");
      }
      return next();
    }
    const authHeader = req.headers.authorization;
    if (authHeader && authHeader.startsWith('Bearer ')) {
      const token = authHeader.split(' ')[1];
      try {
        const result = await jose.jwtVerify(token, JWKS);
        logger.debug({ operation_name, path: req.path, user_id: result.payload.sub }, 'JWT verified successfully');
        (req as any).user = result.payload; // Attach user payload to request
        next();
      } catch (e: any) {
        logger.warn({ operation_name, path: req.path, error_message: e.message, reason: 'JWT verification failed' });
        return res.sendStatus(403);
      }
    } else {
      logger.warn({ operation_name, path: req.path, reason: 'Missing Bearer token' });
      res.sendStatus(401);
    }
  });

  // Authentication middleware (app2) - DRY principle violation, consider refactoring to a shared function
  app2.use(async (req: Request, res: Response, next: NextFunction) => {
    const operation_name = `AuthMiddlewareApp2`;
    if (req.path.match(/\/public/) || req.path.match(/\-public$/)) {
      return next();
    }
    if (req.path.match(/\-admin$/)) {
      const authorizationToken = req.headers.authorization;
       if (!authorizationToken || !authorizationToken.startsWith('Basic ')) {
        logger.warn({ operation_name, path: req.path, reason: 'Missing or malformed Basic auth for admin path on app2' });
        return res.status(401).send("Unauthorized");
      }
      const encodedCreds = authorizationToken.split(' ')[1];
      const verifyToken = Buffer.from(encodedCreds, 'base64').toString().split(':')[1];
      if (verifyToken !== process.env.BASIC_AUTH) {
         logger.warn({ operation_name, path: req.path, reason: 'Invalid Basic auth token for admin path on app2' });
        return res.status(401).send("Unauthorized");
      }
      return next();
    }
    const authHeader = req.headers.authorization;
    if (authHeader && authHeader.startsWith('Bearer ')) {
      const token = authHeader.split(' ')[1];
      try {
        const result = await jose.jwtVerify(token, JWKS);
        logger.debug({ operation_name, path: req.path, user_id: result.payload.sub }, 'JWT verified successfully for app2');
        (req as any).user = result.payload;
        next();
      } catch (e: any) {
        logger.warn({ operation_name, path: req.path, error_message: e.message, reason: 'JWT verification failed for app2' });
        return res.sendStatus(403);
      }
    } else {
      logger.warn({ operation_name, path: req.path, reason: 'Missing Bearer token for app2' });
      res.sendStatus(401);
    }
  });

  app.disable('x-powered-by');
  app2.disable('x-powered-by');

  app.get('/healthz', (_req: Request, res: Response) => { // Typed req, res
    res.status(200).send('ok');
  });
  app2.get('/healthz', (_req: Request, res: Response) => { // Typed req, res
    res.status(200).send('ok');
  });

  const functionsPath = path.join(process.cwd(), process.env.FUNCTIONS_RELATIVE_PATH!); // Added non-null assertion
  const files = glob.sync('**/*.@(js|ts)', {
    cwd: functionsPath,
    ignore: [
      '**/node_modules/**',
      '**/_*/**',
      '**/_*',
    ],
  });

  for (const file of files) {
    const operation_name = `LoadRouteHandler`;
    try {
      const { default: handler } = await import(path.join(functionsPath, file));
      const relativePath = path.relative(process.env.NHOST_PROJECT_PATH!, file); // Added non-null assertion

      if (handler) {
        const route = `/${file}`.replace(/(\.ts|\.js)$/, '').replace(/\/index$/, '/');
        app.all(route, handler);
        app2.all(route, handler);
        logger.info({ operation_name, route, file: relativePath }, `Loaded route from file`);
      } else {
        logger.warn({ operation_name, file: relativePath, reason: 'No default export' });
      }
    } catch (error: any) {
      logger.error({ operation_name, file, error_message: error.message, stack_trace: error.stack }, `Unable to load file as a Serverless Function`);
      continue;
    }
  }

  const httpServer = http.createServer(app);
  const httpServer2 = http.createServer(app2);

  const wss = new WebSocketServer({ clientTracking: false, noServer: true });
  const wss2 = new WebSocketServer({ clientTracking: false, noServer: true });

  const wsFiles = glob.sync('**/_chat/chat_brain/handler.ts', { // This seems very specific, ensure it's correct
    cwd: functionsPath,
    ignore: ['**/node_modules/**'],
  });

  // Common WebSocket upgrade logic
  async function handleWebSocketUpgrade(
    wssInstance: WebSocketServer,
    request: Request,
    socket: NodeJS.Socket, // http.IncomingMessage uses stream.Duplex, but WebSocketServer expects NodeJS.Socket
    head: Buffer,
    serverName: string
  ) {
    const operation_name = `WebSocketUpgrade_${serverName}`;
    socket.on('error', onSocketError); // onSocketError now uses logger

    logger.info({ operation_name, url: request.url }, `Attempting WebSocket upgrade`);

    const string2Parse = request.url?.slice(2); // Assuming URL like "/?Auth=Bearer%20token"
    const queryParams = qs.parse(string2Parse || "");
    const authHeader = queryParams.Auth as string;

    if (authHeader && authHeader.startsWith('Bearer ')) {
      const token = authHeader.split(' ')[1];
      try {
        const result = await jose.jwtVerify(token, JWKS);
        if (result.payload.sub && typeof result.payload.sub === 'string') {
          (request as any).userId = result.payload.sub;
           logger.info({ operation_name, user_id: result.payload.sub }, `WebSocket JWT verified`);
        } else {
          logger.error({ operation_name, reason: "User ID (sub) not found or invalid in JWT payload" });
          socket.write('HTTP/1.1 401 Unauthorized (Invalid Token Payload)\r\n\r\n');
          socket.destroy();
          return;
        }
      } catch (e: any) {
        logger.error({ operation_name, error_message: e.message, reason: "WebSocket JWT verification failed" });
        socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
        socket.destroy();
        return;
      }
    } else {
      logger.warn({ operation_name, reason: "Missing or malformed Auth query parameter for WebSocket" });
      socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
      socket.destroy();
      return;
    }

    socket.removeListener('error', onSocketError);
    wssInstance.handleUpgrade(request as http.IncomingMessage, socket, head, function done(ws) {
      wssInstance.emit('connection', ws, request);
    });
  }

  httpServer.on('upgrade', (req, socket, head) =>
    handleWebSocketUpgrade(wss, req as Request, socket, head, 'httpServer1')
  );
  httpServer2.on('upgrade', (req, socket, head) =>
    handleWebSocketUpgrade(wss2, req as Request, socket, head, 'httpServer2')
  );

  const keepAlivePeriod = 50000;

  // Common WebSocket connection logic
  async function onWebSocketConnection(
    ws: WebSocket,
    request: Request & { userId?: string },
    serverName: string
  ) {
    const userId = request.userId;
    const operation_name = `WebSocketConnect_${serverName}`;

    if (userId) {
      activeWebsocketConnections.add(1, { server: serverName });
      logger.info({ operation_name, user_id: userId }, `WebSocket connection established`);
      connectedClients.set(userId, ws);

      ws.on('error', (error: Error) => { // Typed error
        logger.error({ operation_name, user_id: userId, error_message: error.message, stack_trace: error.stack }, `WebSocket error`);
      });

      const keepAliveId = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({type: 'ping'})); // Send JSON ping
        }
      }, keepAlivePeriod);

      ws.on('message', async function incoming(messageBuffer) {
        const messageOpName = `WebSocketMessage_${serverName}`;
        websocketMessagesReceivedTotal.add(1, { server: serverName });
        const message = messageBuffer.toString();
        logger.debug({ messageOpName, user_id: userId, received_message_length: message.length }, `Received message`);

        try {
          if (wsFiles.length === 0) {
            logger.error({ messageOpName, user_id: userId, reason: "No WebSocket message handler file found (wsFiles empty)"});
            return;
          }
          // Assuming wsFiles[0] is the correct chat_brain handler
          const { default: handler } = await import(path.join(functionsPath, wsFiles[0]));
          const replyMessage = await handler(message, userId, request, sendCommandToUser);

          if (replyMessage && ws.readyState === WebSocket.OPEN) {
            ws.send(replyMessage); // replyMessage is expected to be stringified JSON or string
          }
        } catch (e: any) {
          logger.error({ messageOpName, user_id: userId, error_message: e.message, stack_trace: e.stack }, `Error processing message`);
        }
      });

      ws.on('close', (code, reason) => {
        activeWebsocketConnections.add(-1, { server: serverName });
        logger.info({ operation_name: `WebSocketClose_${serverName}`, user_id: userId, code, reason: reason.toString() }, `WebSocket connection closed`);
        connectedClients.delete(userId);
        clearInterval(keepAliveId);
      });
    } else {
      logger.error({ operation_name, reason: "WebSocket connection established without a userId. Closing." });
      ws.close(1008, "User ID not available after upgrade");
    }
  }

  wss.on('connection', (ws, req) => onWebSocketConnection(ws, req as Request & { userId?: string }, 'wss1'));
  wss2.on('connection', (ws, req) => onWebSocketConnection(ws, req as Request & { userId?: string }, 'wss2'));
  
  const workerFiles = glob.sync('**/*_/*.@(js|ts)', { // e.g. _dayScheduleWorker_
    cwd: functionsPath,
    ignore: ['**/node_modules/**'],
  });

  const workerHandlers: (() => Promise<any>)[] = []; // Typed array
  for (const workerFile of workerFiles) {
    const opName = `LoadWorkerHandler`;
    try {
      const { default: handler } = await import(path.join(functionsPath, workerFile));
      if (typeof handler === 'function') {
        workerHandlers.push(handler);
        logger.info({ opName, file: workerFile }, `Loaded worker handler`);
      } else {
        logger.warn({ opName, file: workerFile, reason: 'No default export function found' });
      }
    } catch (error: any) {
       logger.error({ opName, file: workerFile, error_message: error.message, stack_trace: error.stack }, `Error loading worker handler`);
    }
  }

  if (workerHandlers.length > 0) {
    logger.info({ operation_name: "InitializeWorkers" , count: workerHandlers.length }, "Initializing Kafka consumer workers...");
    await Promise.all(workerHandlers.map(handler => handler())).catch(err => {
        logger.error({ operation_name: "InitializeWorkers", error_message: err.message, stack_trace: err.stack }, "Error during worker initialization");
    });
  } else {
     logger.info({ operation_name: "InitializeWorkers" }, "No Kafka consumer workers found to initialize.");
  }

  await startAgenda().catch(error => {
    logger.error({ operation_name: 'StartAgenda', error_message: error.message, stack_trace: error.stack }, 'Failed to start Agenda');
  });

  app.post('/api/agent-handler', async (req: Request, res: Response) => { // Typed req, res
    const operation_name = 'AgentHandlerScheduledTask';
    logger.info({ operation_name }, 'Received request from Agenda job runner');
    const { message, userId, intentName, entities, requestSource, conversationId } = req.body;

    if (!userId || !intentName || !requestSource || requestSource !== 'ScheduledJobExecutor') {
      logger.warn({ operation_name, error_code: 'VALIDATION_001', payload: req.body }, 'Invalid payload for scheduled task');
      return res.status(400).json({ error: 'Invalid payload for scheduled task' });
    }

    try {
      const interfaceType: InterfaceType = 'text';
      const options = { requestSource, intentName, entities, conversationId };
      const result = await _internalHandleMessage(interfaceType, message, userId, options);

      logger.info({ operation_name, user_id: userId, intent: intentName, success: true, result_text_length: result.text?.length }, 'Scheduled task processed successfully');
      return res.status(200).json({ success: true, message: "Task processed", details: result.text });
    } catch (error: any) {
      logger.error({ operation_name, user_id: userId, intent: intentName, success: false, error_message: error.message, stack_trace: error.stack }, 'Error processing scheduled task');
      return res.status(500).json({ success: false, error: error.message || 'Internal server error' });
    }
  });

  httpServer.listen(PORT, () => {
    logger.info({ operation_name: 'HttpServerStart', port: PORT }, `HTTP Server with Agent Handler listening`);
  });
  httpServer2.listen(PORT2, () => {
    logger.info({ operation_name: 'HttpServer2Start', port: PORT2 }, `HTTP Server 2 listening`);
  });

  const shutdown = async (signal: string) => {
    logger.info({ operation_name: 'ShutdownProcess', signal }, `Received signal. Shutting down...`);
    await stopAgenda();
    // Add any other cleanup here (e.g. wss.close(), sdk.shutdown() - though sdk handles SIGTERM/SIGINT)
    httpServer.close(() => {
      logger.info({ operation_name: 'HttpServerStop' },'HTTP server closed.');
      httpServer2.close(() => {
        logger.info({ operation_name: 'HttpServer2Stop' }, 'HTTP server 2 closed.');
        // process.exit(0) will be handled by OpenTelemetry SDK's shutdown hooks if it's registered for the signal
      });
    });
  };

  // SIGINT and SIGTERM are handled by OpenTelemetry SDK's shutdown hooks in opentelemetry.js
  // If additional cleanup specific to this server is needed beyond what OTel SDK does,
  // it can be added here, but ensure it doesn't conflict with SDK's process.exit().
  // For instance, OTel SDK calls process.exit(0) after its shutdown.
};

main().catch(error => {
  logger.fatal({ operation_name: 'MainExecutionError', error_message: error.message, stack_trace: error.stack }, "Fatal error during main execution, exiting.");
  process.exit(1);
});
