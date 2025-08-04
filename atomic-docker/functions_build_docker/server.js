// IMPORTANT: The OpenTelemetry SDK must be initialized BEFORE any other modules that need to be instrumented.
// This is typically handled by NODE_OPTIONS="--require ./opentelemetry.js" in the container environment.
// Ensure `opentelemetry.js` is in the same directory as this `server.ts` or adjust path.
import path from 'path';
import express from 'express'; // Added Response, NextFunction
import glob from 'glob';
import { WebSocketServer, WebSocket } from 'ws';
import qs from 'qs';
import * as jose from 'jose';
import http from 'http';
import winston from 'winston';
import expressWinston from 'express-winston';
import { trace, context as otelContext, SpanStatusCode, } from '@opentelemetry/api'; // For manual span attributes
// Import custom metrics from opentelemetry.js
import { httpServerRequestsTotal, httpServerRequestDurationSeconds, activeWebsocketConnections, websocketMessagesReceivedTotal, } from './opentelemetry'; // Assuming opentelemetry.js is in the same directory
// Agenda imports
import { startAgenda, stopAgenda } from '../../project/functions/agendaService';
import { _internalHandleMessage } from '../../project/functions/atom-agent/handler';
const PORT = process.env.PORT || 3000; // Standardized PORT usage
const PORT2 = process.env.PORT2 || 3030; // Standardized PORT2 usage
const serviceName = process.env.OTEL_SERVICE_NAME || 'functions-service';
const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';
// Configure Winston Logger
const logger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: winston.format.combine(winston.format.timestamp(), winston.format.json(), // Output logs in JSON format
    winston.format((info) => {
        // Custom formatter to add standard fields
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
    })()),
    transports: [
        new winston.transports.Console(), // Log to console (stdout/stderr)
    ],
    exitOnError: false, // Do not exit on handled exceptions
});
function onSocketError(err) {
    // Typed error
    logger.error({
        message: 'WebSocket socket error',
        error: err.message,
        stack_trace: err.stack,
    });
}
const JWKS = jose.createRemoteJWKSet(new URL(`${process.env.APP_CLIENT_URL}/api/auth/jwt/jwks.json`));
const connectedClients = new Map();
export async function sendCommandToUser(userId, command) {
    const clientSocket = connectedClients.get(userId);
    const operation_name = 'SendCommandToUser';
    if (clientSocket && clientSocket.readyState === WebSocket.OPEN) {
        const messageToSend = { type: 'AGENT_COMMAND', payload: command };
        try {
            clientSocket.send(JSON.stringify(messageToSend));
            logger.info({
                operation_name,
                user_id: userId,
                command_action: command.action,
                success: true,
            }, 'Sent command to user');
            return true;
        }
        catch (error) {
            logger.error({
                operation_name,
                user_id: userId,
                command_action: command.action,
                success: false,
                error_message: error.message,
                stack_trace: error.stack,
            }, 'Error sending command to user');
            return false;
        }
    }
    else {
        logger.warn({
            operation_name,
            user_id: userId,
            command_action: command.action,
            success: false,
            reason: 'No active WebSocket or socket not open',
        }, 'Failed to send command to user');
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
        msg: 'HTTP {{req.method}} {{req.url}} {{res.statusCode}} {{res.responseTime}}ms',
        expressFormat: false, // Use winston's format, not morgan's
        colorize: false, // JSON logs should not be colorized
        skip: (req, _res) => req.path === '/healthz', // Skip health checks
        dynamicMeta: (req, res) => {
            // Add custom attributes to request logs
            const meta = {};
            if (req) {
                meta.http_method = req.method;
                meta.http_path = req.originalUrl || req.url;
                // meta.user_id = req.user?.id; // If user context is available
            }
            if (res) {
                meta.http_status_code = res.statusCode;
            }
            return meta;
        },
    }));
    app2.use(expressWinston.logger({
        // Apply to app2 as well
        winstonInstance: logger,
        meta: true,
        msg: 'HTTP {{req.method}} {{req.url}} {{res.statusCode}} {{res.responseTime}}ms (app2)',
        expressFormat: false,
        colorize: false,
        skip: (req, _res) => req.path === '/healthz',
        dynamicMeta: (req, res) => {
            const meta = {};
            if (req) {
                meta.http_method = req.method;
                meta.http_path = req.originalUrl || req.url;
            }
            if (res) {
                meta.http_status_code = res.statusCode;
            }
            return meta;
        },
    }));
    // Middleware for custom metrics for all requests
    const recordHttpMetrics = (req, res, next) => {
        const startEpoch = Date.now();
        res.on('finish', () => {
            const endEpoch = Date.now();
            const durationSeconds = (endEpoch - startEpoch) / 1000;
            const attributes = {
                http_route: req.route
                    ? req.route.path
                    : (req.originalUrl || req.url).split('?')[0], // Use route path if available, else full path
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
    app.use(express.json({
        limit: '6MB',
        verify: (req, _res, buf) => {
            req.rawBody = buf.toString();
        },
    }));
    app2.use(express.json({
        limit: '6MB',
        verify: (req, _res, buf) => {
            req.rawBody = buf.toString();
        },
    }));
    app.use(express.urlencoded({ extended: true }));
    app2.use(express.urlencoded({ extended: true }));
    // Authentication middleware (app)
    app.use(async (req, res, next) => {
        // Typed req, res, next
        const operation_name = `AuthMiddlewareApp1`;
        if (req.path.match(/\/public/) || req.path.match(/\-public$/)) {
            return next();
        }
        if (req.path.match(/\-admin$/)) {
            const authorizationToken = req.headers.authorization;
            if (!authorizationToken || !authorizationToken.startsWith('Basic ')) {
                logger.warn({
                    operation_name,
                    path: req.path,
                    reason: 'Missing or malformed Basic auth for admin path',
                });
                return res.status(401).send('Unauthorized');
            }
            const encodedCreds = authorizationToken.split(' ')[1];
            const verifyToken = Buffer.from(encodedCreds, 'base64')
                .toString()
                .split(':')[1];
            if (verifyToken !== process.env.BASIC_AUTH) {
                logger.warn({
                    operation_name,
                    path: req.path,
                    reason: 'Invalid Basic auth token for admin path',
                });
                return res.status(401).send('Unauthorized');
            }
            return next();
        }
        const authHeader = req.headers.authorization;
        if (authHeader && authHeader.startsWith('Bearer ')) {
            const token = authHeader.split(' ')[1];
            try {
                const result = await jose.jwtVerify(token, JWKS);
                logger.debug({ operation_name, path: req.path, user_id: result.payload.sub }, 'JWT verified successfully');
                req.user = result.payload; // Attach user payload to request
                next();
            }
            catch (e) {
                logger.warn({
                    operation_name,
                    path: req.path,
                    error_message: e.message,
                    reason: 'JWT verification failed',
                });
                return res.sendStatus(403);
            }
        }
        else {
            logger.warn({
                operation_name,
                path: req.path,
                reason: 'Missing Bearer token',
            });
            res.sendStatus(401);
        }
    });
    // Authentication middleware (app2) - DRY principle violation, consider refactoring to a shared function
    app2.use(async (req, res, next) => {
        const operation_name = `AuthMiddlewareApp2`;
        if (req.path.match(/\/public/) || req.path.match(/\-public$/)) {
            return next();
        }
        if (req.path.match(/\-admin$/)) {
            const authorizationToken = req.headers.authorization;
            if (!authorizationToken || !authorizationToken.startsWith('Basic ')) {
                logger.warn({
                    operation_name,
                    path: req.path,
                    reason: 'Missing or malformed Basic auth for admin path on app2',
                });
                return res.status(401).send('Unauthorized');
            }
            const encodedCreds = authorizationToken.split(' ')[1];
            const verifyToken = Buffer.from(encodedCreds, 'base64')
                .toString()
                .split(':')[1];
            if (verifyToken !== process.env.BASIC_AUTH) {
                logger.warn({
                    operation_name,
                    path: req.path,
                    reason: 'Invalid Basic auth token for admin path on app2',
                });
                return res.status(401).send('Unauthorized');
            }
            return next();
        }
        const authHeader = req.headers.authorization;
        if (authHeader && authHeader.startsWith('Bearer ')) {
            const token = authHeader.split(' ')[1];
            try {
                const result = await jose.jwtVerify(token, JWKS);
                logger.debug({ operation_name, path: req.path, user_id: result.payload.sub }, 'JWT verified successfully for app2');
                req.user = result.payload;
                next();
            }
            catch (e) {
                logger.warn({
                    operation_name,
                    path: req.path,
                    error_message: e.message,
                    reason: 'JWT verification failed for app2',
                });
                return res.sendStatus(403);
            }
        }
        else {
            logger.warn({
                operation_name,
                path: req.path,
                reason: 'Missing Bearer token for app2',
            });
            res.sendStatus(401);
        }
    });
    app.disable('x-powered-by');
    app2.disable('x-powered-by');
    app.get('/healthz', (_req, res) => {
        // Typed req, res
        res.status(200).send('ok');
    });
    app2.get('/healthz', (_req, res) => {
        // Typed req, res
        res.status(200).send('ok');
    });
    const functionsPath = path.join(process.cwd(), process.env.FUNCTIONS_RELATIVE_PATH); // Added non-null assertion
    const files = glob.sync('**/*.@(js|ts)', {
        cwd: functionsPath,
        ignore: ['**/node_modules/**', '**/_*/**', '**/_*'],
    });
    for (const file of files) {
        const operation_name = `LoadRouteHandler`;
        try {
            const { default: handler } = await import(path.join(functionsPath, file));
            const relativePath = path.relative(process.env.NHOST_PROJECT_PATH, file); // Added non-null assertion
            if (handler) {
                const route = `/${file}`
                    .replace(/(\.ts|\.js)$/, '')
                    .replace(/\/index$/, '/');
                app.all(route, handler);
                app2.all(route, handler);
                logger.info({ operation_name, route, file: relativePath }, `Loaded route from file`);
            }
            else {
                logger.warn({
                    operation_name,
                    file: relativePath,
                    reason: 'No default export',
                });
            }
        }
        catch (error) {
            logger.error({
                operation_name,
                file,
                error_message: error.message,
                stack_trace: error.stack,
            }, `Unable to load file as a Serverless Function`);
            continue;
        }
    }
    const httpServer = http.createServer(app);
    const httpServer2 = http.createServer(app2);
    const wss = new WebSocketServer({ clientTracking: false, noServer: true });
    const wss2 = new WebSocketServer({ clientTracking: false, noServer: true });
    const wsFiles = glob.sync('**/_chat/chat_brain/handler.ts', {
        // This seems very specific, ensure it's correct
        cwd: functionsPath,
        ignore: ['**/node_modules/**'],
    });
    // Common WebSocket upgrade logic
    async function handleWebSocketUpgrade(wssInstance, request, socket, // http.IncomingMessage uses stream.Duplex, but WebSocketServer expects NodeJS.Socket
    head, serverName) {
        const operation_name = `WebSocketUpgrade_${serverName}`;
        socket.on('error', onSocketError); // onSocketError now uses logger
        logger.info({ operation_name, url: request.url }, `Attempting WebSocket upgrade`);
        const string2Parse = request.url?.slice(2); // Assuming URL like "/?Auth=Bearer%20token"
        const queryParams = qs.parse(string2Parse || '');
        const authHeader = queryParams.Auth;
        if (authHeader && authHeader.startsWith('Bearer ')) {
            const token = authHeader.split(' ')[1];
            try {
                const result = await jose.jwtVerify(token, JWKS);
                if (result.payload.sub && typeof result.payload.sub === 'string') {
                    request.userId = result.payload.sub;
                    logger.info({ operation_name, user_id: result.payload.sub }, `WebSocket JWT verified`);
                }
                else {
                    logger.error({
                        operation_name,
                        reason: 'User ID (sub) not found or invalid in JWT payload',
                    });
                    socket.write('HTTP/1.1 401 Unauthorized (Invalid Token Payload)\r\n\r\n');
                    socket.destroy();
                    return;
                }
            }
            catch (e) {
                logger.error({
                    operation_name,
                    error_message: e.message,
                    reason: 'WebSocket JWT verification failed',
                });
                socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
                socket.destroy();
                return;
            }
        }
        else {
            logger.warn({
                operation_name,
                reason: 'Missing or malformed Auth query parameter for WebSocket',
            });
            socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
            socket.destroy();
            return;
        }
        socket.removeListener('error', onSocketError);
        wssInstance.handleUpgrade(request, socket, head, function done(ws) {
            wssInstance.emit('connection', ws, request);
        });
    }
    httpServer.on('upgrade', (req, socket, head) => handleWebSocketUpgrade(wss, req, socket, head, 'httpServer1'));
    httpServer2.on('upgrade', (req, socket, head) => handleWebSocketUpgrade(wss2, req, socket, head, 'httpServer2'));
    const keepAlivePeriod = 50000;
    // Common WebSocket connection logic
    async function onWebSocketConnection(ws, request, serverName) {
        const userId = request.userId;
        const operation_name = `WebSocketConnect_${serverName}`;
        if (userId) {
            activeWebsocketConnections.add(1, { server: serverName });
            logger.info({ operation_name, user_id: userId }, `WebSocket connection established`);
            connectedClients.set(userId, ws);
            ws.on('error', (error) => {
                // Typed error
                logger.error({
                    operation_name,
                    user_id: userId,
                    error_message: error.message,
                    stack_trace: error.stack,
                }, `WebSocket error`);
            });
            const keepAliveId = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'ping' })); // Send JSON ping
                }
            }, keepAlivePeriod);
            ws.on('message', async function incoming(messageBuffer) {
                const messageOpName = `WebSocketMessage_${serverName}`;
                websocketMessagesReceivedTotal.add(1, { server: serverName });
                const message = messageBuffer.toString();
                logger.debug({
                    messageOpName,
                    user_id: userId,
                    received_message_length: message.length,
                }, `Received message`);
                try {
                    if (wsFiles.length === 0) {
                        logger.error({
                            messageOpName,
                            user_id: userId,
                            reason: 'No WebSocket message handler file found (wsFiles empty)',
                        });
                        return;
                    }
                    // Assuming wsFiles[0] is the correct chat_brain handler
                    const { default: handler } = await import(path.join(functionsPath, wsFiles[0]));
                    const replyMessage = await handler(message, userId, request, sendCommandToUser);
                    if (replyMessage && ws.readyState === WebSocket.OPEN) {
                        ws.send(replyMessage); // replyMessage is expected to be stringified JSON or string
                    }
                }
                catch (e) {
                    logger.error({
                        messageOpName,
                        user_id: userId,
                        error_message: e.message,
                        stack_trace: e.stack,
                    }, `Error processing message`);
                }
            });
            ws.on('close', (code, reason) => {
                activeWebsocketConnections.add(-1, { server: serverName });
                logger.info({
                    operation_name: `WebSocketClose_${serverName}`,
                    user_id: userId,
                    code,
                    reason: reason.toString(),
                }, `WebSocket connection closed`);
                connectedClients.delete(userId);
                clearInterval(keepAliveId);
            });
        }
        else {
            logger.error({
                operation_name,
                reason: 'WebSocket connection established without a userId. Closing.',
            });
            ws.close(1008, 'User ID not available after upgrade');
        }
    }
    wss.on('connection', (ws, req) => onWebSocketConnection(ws, req, 'wss1'));
    wss2.on('connection', (ws, req) => onWebSocketConnection(ws, req, 'wss2'));
    const workerFiles = glob.sync('**/*_/*.@(js|ts)', {
        // e.g. _dayScheduleWorker_
        cwd: functionsPath,
        ignore: ['**/node_modules/**'],
    });
    const workerHandlers = []; // Typed array
    for (const workerFile of workerFiles) {
        const opName = `LoadWorkerHandler`;
        try {
            const { default: handler } = await import(path.join(functionsPath, workerFile));
            if (typeof handler === 'function') {
                workerHandlers.push(handler);
                logger.info({ opName, file: workerFile }, `Loaded worker handler`);
            }
            else {
                logger.warn({
                    opName,
                    file: workerFile,
                    reason: 'No default export function found',
                });
            }
        }
        catch (error) {
            logger.error({
                opName,
                file: workerFile,
                error_message: error.message,
                stack_trace: error.stack,
            }, `Error loading worker handler`);
        }
    }
    if (workerHandlers.length > 0) {
        logger.info({ operation_name: 'InitializeWorkers', count: workerHandlers.length }, 'Initializing Kafka consumer workers...');
        await Promise.all(workerHandlers.map((handler) => handler())).catch((err) => {
            logger.error({
                operation_name: 'InitializeWorkers',
                error_message: err.message,
                stack_trace: err.stack,
            }, 'Error during worker initialization');
        });
    }
    else {
        logger.info({ operation_name: 'InitializeWorkers' }, 'No Kafka consumer workers found to initialize.');
    }
    await startAgenda().catch((error) => {
        logger.error({
            operation_name: 'StartAgenda',
            error_message: error.message,
            stack_trace: error.stack,
        }, 'Failed to start Agenda');
    });
    app.post('/api/agent-handler', async (req, res) => {
        // Typed req, res
        const operation_name = 'AgentHandlerScheduledTask';
        logger.info({ operation_name }, 'Received request from Agenda job runner');
        const { message, userId, intentName, entities, requestSource, conversationId, } = req.body;
        if (!userId ||
            !intentName ||
            !requestSource ||
            requestSource !== 'ScheduledJobExecutor') {
            logger.warn({ operation_name, error_code: 'VALIDATION_001', payload: req.body }, 'Invalid payload for scheduled task');
            return res
                .status(400)
                .json({ error: 'Invalid payload for scheduled task' });
        }
        try {
            const interfaceType = 'text';
            const options = { requestSource, intentName, entities, conversationId };
            const result = await _internalHandleMessage(interfaceType, message, userId, options);
            logger.info({
                operation_name,
                user_id: userId,
                intent: intentName,
                success: true,
                result_text_length: result.text?.length,
            }, 'Scheduled task processed successfully');
            return res
                .status(200)
                .json({
                success: true,
                message: 'Task processed',
                details: result.text,
            });
        }
        catch (error) {
            logger.error({
                operation_name,
                user_id: userId,
                intent: intentName,
                success: false,
                error_message: error.message,
                stack_trace: error.stack,
            }, 'Error processing scheduled task');
            return res
                .status(500)
                .json({
                success: false,
                error: error.message || 'Internal server error',
            });
        }
    });
    httpServer.listen(PORT, () => {
        logger.info({ operation_name: 'HttpServerStart', port: PORT }, `HTTP Server with Agent Handler listening`);
    });
    httpServer2.listen(PORT2, () => {
        logger.info({ operation_name: 'HttpServer2Start', port: PORT2 }, `HTTP Server 2 listening`);
    });
    // Centralized Error Handling Middleware for 'app'
    // This MUST be the last middleware added to the app stack.
    app.use((err, req, res, next) => {
        const traceId = trace.getSpan(otelContext.active())?.spanContext().traceId;
        logger.error({
            // Standard log fields will be added by Winston format (service_name, version, timestamp)
            // trace_id, span_id should be added by WinstonInstrumentation logHook
            error_message: err.message,
            error_stack: err.stack, // Be cautious about logging full stacks in prod depending on sensitivity
            error_name: err.name,
            error_code_property: err.code, // e.g., from opossum EOPENBREAKER or other libs
            http_method: req.method,
            http_path: req.originalUrl || req.url,
            // trace_id: traceId, // Explicitly adding for clarity, though hook should do it.
        }, `Unhandled error caught by central error handler for app1: ${err.message}`);
        // Set OpenTelemetry Span Status to error
        const currentSpan = trace.getSpan(otelContext.active());
        if (currentSpan) {
            currentSpan.recordException(err); // Records error details on the span
            currentSpan.setStatus({
                code: SpanStatusCode.ERROR,
                message: err.message,
            });
        }
        if (!res.headersSent) {
            let statusCode = err.status || err.statusCode || 500;
            if (typeof statusCode !== 'number' ||
                statusCode < 400 ||
                statusCode > 599) {
                statusCode = 500; // Ensure it's a valid HTTP error status
            }
            let errorCode = 'UNEXPECTED_ERROR';
            if (err.code) {
                // From opossum (EOPENBREAKER) or other libs
                errorCode = err.code;
            }
            else {
                switch (statusCode) {
                    case 400:
                        errorCode = 'BAD_REQUEST';
                        break;
                    case 401:
                        errorCode = 'UNAUTHORIZED';
                        break;
                    case 403:
                        errorCode = 'FORBIDDEN';
                        break;
                    case 404:
                        errorCode = 'NOT_FOUND';
                        break;
                    case 500:
                        errorCode = 'INTERNAL_SERVER_ERROR';
                        break;
                    case 502:
                        errorCode = 'BAD_GATEWAY';
                        break;
                    case 503:
                        errorCode = 'SERVICE_UNAVAILABLE';
                        break;
                    case 504:
                        errorCode = 'GATEWAY_TIMEOUT';
                        break;
                }
            }
            const responseMessage = statusCode >= 500 && process.env.NODE_ENV === 'production'
                ? 'An internal server error occurred. Please try again later.'
                : err.message || 'An unexpected error occurred.';
            res.status(statusCode).json({
                success: false,
                error: {
                    code: errorCode,
                    message: responseMessage,
                },
            });
        }
        else {
            next(err); // Delegate to default Express error handler if headers already sent
        }
    });
    // Centralized Error Handling Middleware for 'app2'
    app2.use((err, req, res, next) => {
        // Re-get traceId for app2's context, though it should be same if one request flows to both.
        // const traceId = trace.getSpan(otelContext.active())?.spanContext().traceId;
        // Logging and OTel span status already handled above this section in the previous diff.
        logger.error(
        // This log was already added and is good.
        {
            error_message: err.message,
            error_stack: err.stack,
            error_name: err.name,
            error_code_property: err.code,
            http_method: req.method,
            http_path: req.originalUrl || req.url,
            app_instance: 'app2',
        }, `Unhandled error caught by central error handler for app2: ${err.message}`);
        const currentSpanApp2 = trace.getSpan(otelContext.active());
        if (currentSpanApp2) {
            // Ensure to use a potentially different span if app2 has its own root span for some reason
            currentSpanApp2.recordException(err);
            currentSpanApp2.setStatus({
                code: SpanStatusCode.ERROR,
                message: err.message,
            });
        }
        if (!res.headersSent) {
            let statusCode = err.status || err.statusCode || 500;
            if (typeof statusCode !== 'number' ||
                statusCode < 400 ||
                statusCode > 599) {
                statusCode = 500;
            }
            let errorCode = 'UNEXPECTED_ERROR_APP2';
            if (err.code) {
                errorCode = err.code;
            }
            else {
                switch (statusCode) {
                    case 400:
                        errorCode = 'BAD_REQUEST_APP2';
                        break;
                    case 401:
                        errorCode = 'UNAUTHORIZED_APP2';
                        break;
                    case 403:
                        errorCode = 'FORBIDDEN_APP2';
                        break;
                    case 404:
                        errorCode = 'NOT_FOUND_APP2';
                        break;
                    case 500:
                        errorCode = 'INTERNAL_SERVER_ERROR_APP2';
                        break;
                    case 502:
                        errorCode = 'BAD_GATEWAY_APP2';
                        break;
                    case 503:
                        errorCode = 'SERVICE_UNAVAILABLE_APP2';
                        break;
                    case 504:
                        errorCode = 'GATEWAY_TIMEOUT_APP2';
                        break;
                }
            }
            const responseMessage = statusCode >= 500 && process.env.NODE_ENV === 'production'
                ? 'An internal server error occurred on app2. Please try again later.'
                : err.message || 'An unexpected error occurred on app2.';
            res.status(statusCode).json({
                success: false,
                error: {
                    code: errorCode,
                    message: responseMessage,
                },
            });
        }
        else {
            next(err);
        }
    });
    const shutdown = async (signal) => {
        logger.info({ operation_name: 'ShutdownProcess', signal }, `Received signal. Shutting down...`);
        await stopAgenda();
        // Add any other cleanup here (e.g. wss.close(), sdk.shutdown() - though sdk handles SIGTERM/SIGINT)
        httpServer.close(() => {
            logger.info({ operation_name: 'HttpServerStop' }, 'HTTP server closed.');
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
main().catch((error) => {
    logger.fatal({
        operation_name: 'MainExecutionError',
        error_message: error.message,
        stack_trace: error.stack,
    }, 'Fatal error during main execution, exiting.');
    process.exit(1);
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VydmVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic2VydmVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLDhHQUE4RztBQUM5Ryx5R0FBeUc7QUFDekcseUZBQXlGO0FBRXpGLE9BQU8sSUFBSSxNQUFNLE1BQU0sQ0FBQztBQUN4QixPQUFPLE9BQTRDLE1BQU0sU0FBUyxDQUFDLENBQUMsK0JBQStCO0FBQ25HLE9BQU8sSUFBSSxNQUFNLE1BQU0sQ0FBQztBQUN4QixPQUFPLEVBQUUsZUFBZSxFQUFFLFNBQVMsRUFBRSxNQUFNLElBQUksQ0FBQztBQUNoRCxPQUFPLEVBQUUsTUFBTSxJQUFJLENBQUM7QUFDcEIsT0FBTyxLQUFLLElBQUksTUFBTSxNQUFNLENBQUM7QUFDN0IsT0FBTyxJQUFJLE1BQU0sTUFBTSxDQUFDO0FBQ3hCLE9BQU8sT0FBTyxNQUFNLFNBQVMsQ0FBQztBQUM5QixPQUFPLGNBQWMsTUFBTSxpQkFBaUIsQ0FBQztBQUM3QyxPQUFPLEVBQ0wsS0FBSyxFQUNMLE9BQU8sSUFBSSxXQUFXLEVBQ3RCLGNBQWMsR0FFZixNQUFNLG9CQUFvQixDQUFDLENBQUMsNkJBQTZCO0FBRTFELDhDQUE4QztBQUM5QyxPQUFPLEVBQ0wsdUJBQXVCLEVBQ3ZCLGdDQUFnQyxFQUNoQywwQkFBMEIsRUFDMUIsOEJBQThCLEdBQy9CLE1BQU0saUJBQWlCLENBQUMsQ0FBQyxxREFBcUQ7QUFFL0UsaUJBQWlCO0FBQ2pCLE9BQU8sRUFBRSxXQUFXLEVBQUUsVUFBVSxFQUFFLE1BQU0sdUNBQXVDLENBQUM7QUFDaEYsT0FBTyxFQUFFLHNCQUFzQixFQUFFLE1BQU0sNENBQTRDLENBQUM7QUFHcEYsTUFBTSxJQUFJLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxJQUFJLElBQUksSUFBSSxDQUFDLENBQUMsMEJBQTBCO0FBQ2pFLE1BQU0sS0FBSyxHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsS0FBSyxJQUFJLElBQUksQ0FBQyxDQUFDLDJC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QkFBb0I7UUFDcEMsYUFBYSxFQUFFLEtBQUssQ0FBQyxPQUFPO1FBQzVCLFdBQVcsRUFBRSxLQUFLLENBQUMsS0FBSztLQUN6QixFQUNELDZDQUE2QyxDQUM5QyxDQUFDO0lBQ0YsT0FBTyxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQztBQUNsQixDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIElNUE9SVEFOVDogVGhlIE9wZW5UZWxlbWV0cnkgU0RLIG11c3QgYmUgaW5pdGlhbGl6ZWQgQkVGT1JFIGFueSBvdGhlciBtb2R1bGVzIHRoYXQgbmVlZCB0byBiZSBpbnN0cnVtZW50ZWQuXG4vLyBUaGlzIGlzIHR5cGljYWxseSBoYW5kbGVkIGJ5IE5PREVfT1BUSU9OUz1cIi0tcmVxdWlyZSAuL29wZW50ZWxlbWV0cnkuanNcIiBpbiB0aGUgY29udGFpbmVyIGVudmlyb25tZW50LlxuLy8gRW5zdXJlIGBvcGVudGVsZW1ldHJ5LmpzYCBpcyBpbiB0aGUgc2FtZSBkaXJlY3RvcnkgYXMgdGhpcyBgc2VydmVyLnRzYCBvciBhZGp1c3QgcGF0aC5cblxuaW1wb3J0IHBhdGggZnJvbSAncGF0aCc7XG5pbXBvcnQgZXhwcmVzcywgeyBSZXF1ZXN0LCBSZXNwb25zZSwgTmV4dEZ1bmN0aW9uIH0gZnJvbSAnZXhwcmVzcyc7IC8vIEFkZGVkIFJlc3BvbnNlLCBOZXh0RnVuY3Rpb25cbmltcG9ydCBnbG9iIGZyb20gJ2dsb2InO1xuaW1wb3J0IHsgV2ViU29ja2V0U2VydmVyLCBXZWJTb2NrZXQgfSBmcm9tICd3cyc7XG5pbXBvcnQgcXMgZnJvbSAncXMnO1xuaW1wb3J0ICogYXMgam9zZSBmcm9tICdqb3NlJztcbmltcG9ydCBodHRwIGZyb20gJ2h0dHAnO1xuaW1wb3J0IHdpbnN0b24gZnJvbSAnd2luc3Rvbic7XG5pbXBvcnQgZXhwcmVzc1dpbnN0b24gZnJvbSAnZXhwcmVzcy13aW5zdG9uJztcbmltcG9ydCB7XG4gIHRyYWNlLFxuICBjb250ZXh0IGFzIG90ZWxDb250ZXh0LFxuICBTcGFuU3RhdHVzQ29kZSxcbiAgQXR0cmlidXRlcyxcbn0gZnJvbSAnQG9wZW50ZWxlbWV0cnkvYXBpJzsgLy8gRm9yIG1hbnVhbCBzcGFuIGF0dHJpYnV0ZXNcblxuLy8gSW1wb3J0IGN1c3RvbSBtZXRyaWNzIGZyb20gb3BlbnRlbGVtZXRyeS5qc1xuaW1wb3J0IHtcbiAgaHR0cFNlcnZlclJlcXVlc3RzVG90YWwsXG4gIGh0dHBTZXJ2ZXJSZXF1ZXN0RHVyYXRpb25TZWNvbmRzLFxuICBhY3RpdmVXZWJzb2NrZXRDb25uZWN0aW9ucyxcbiAgd2Vic29ja2V0TWVzc2FnZXNSZWNlaXZlZFRvdGFsLFxufSBmcm9tICcuL29wZW50ZWxlbWV0cnknOyAvLyBBc3N1bWluZyBvcGVudGVsZW1ldHJ5LmpzIGlzIGluIHRoZSBzYW1lIGRpcmVjdG9yeVxuXG4vLyBBZ2VuZGEgaW1wb3J0c1xuaW1wb3J0IHsgc3RhcnRBZ2VuZGEsIHN0b3BBZ2VuZGEgfSBmcm9tICcuLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9hZ2VuZGFTZXJ2aWNlJztcbmltcG9ydCB7IF9pbnRlcm5hbEhhbmRsZU1lc3NhZ2UgfSBmcm9tICcuLi8uLi9wcm9qZWN0L2Z1bmN0aW9ucy9hdG9tLWFnZW50L2hhbmRsZXInO1xuaW1wb3J0IHR5cGUgeyBJbnRlcmZhY2VUeXBlIH0gZnJvbSAnLi4vLi4vcHJvamVjdC9mdW5jdGlvbnMvYXRvbS1hZ2VudC9jb252ZXJzYXRpb25TdGF0ZSc7XG5cbmNvbnN0IFBPUlQgPSBwcm9jZXNzLmVudi5QT1JUIHx8IDMwMDA7IC8vIFN0YW5kYXJkaXplZCBQT1JUIHVzYWdlXG5jb25zdCBQT1JUMiA9IHByb2Nlc3MuZW52LlBPUlQyIHx8IDMwMzA7IC8vIFN0YW5kYXJkaXplZCBQT1JUMiB1c2FnZVxuXG5jb25zdCBzZXJ2aWNlTmFtZSA9IHByb2Nlc3MuZW52Lk9URUxfU0VSVklDRV9OQU1FIHx8ICdmdW5jdGlvbnMtc2VydmljZSc7XG5jb25zdCBzZXJ2aWNlVmVyc2lvbiA9IHByb2Nlc3MuZW52Lk9URUxfU0VSVklDRV9WRVJTSU9OIHx8ICcxLjAuMCc7XG5cbi8vIENvbmZpZ3VyZSBXaW5zdG9uIExvZ2dlclxuY29uc3QgbG9nZ2VyID0gd2luc3Rvbi5jcmVhdGVMb2dnZXIoe1xuICBsZXZlbDogcHJvY2Vzcy5lbnYuTE9HX0xFVkVMIHx8ICdpbmZvJyxcbiAgZm9ybWF0OiB3aW5zdG9uLmZvcm1hdC5jb21iaW5lKFxuICAgIHdpbnN0b24uZm9ybWF0LnRpbWVzdGFtcCgpLFxuICAgIHdpbnN0b24uZm9ybWF0Lmpzb24oKSwgLy8gT3V0cHV0IGxvZ3MgaW4gSlNPTiBmb3JtYXRcbiAgICB3aW5zdG9uLmZvcm1hdCgoaW5mbykgPT4ge1xuICAgICAgLy8gQ3VzdG9tIGZvcm1hdHRlciB0byBhZGQgc3RhbmRhcmQgZmllbGRzXG4gICAgICBpbmZvLnNlcnZpY2VfbmFtZSA9IHNlcnZpY2VOYW1lO1xuICAgICAgaW5mby52ZXJzaW9uID0gc2VydmljZVZlcnNpb247XG4gICAgICAvLyB0cmFjZV9pZCBhbmQgc3Bhbl9pZCBzaG91bGQgYmUgYWRkZWQgYnkgV2luc3Rvbkluc3RydW1lbnRhdGlvbiBsb2dIb29rXG4gICAgICAvLyBJZiBub3QsIG9yIGZvciBsb2dzIG91dHNpZGUgc3BhbnMsIGFkZCB0aGVtIG1hbnVhbGx5IGhlcmUgaWYgcG9zc2libGU6XG4gICAgICBjb25zdCBjdXJyZW50U3BhbiA9IHRyYWNlLmdldFNwYW4ob3RlbENvbnRleHQuYWN0aXZlKCkpO1xuICAgICAgaWYgKGN1cnJlbnRTcGFuKSB7XG4gICAgICAgIGNvbnN0IHNwYW5Db250ZXh0ID0gY3VycmVudFNwYW4uc3BhbkNvbnRleHQoKTtcbiAgICAgICAgaWYgKHNwYW5Db250ZXh0ICYmIHNwYW5Db250ZXh0LnRyYWNlSWQpIHtcbiAgICAgICAgICBpbmZvLnRyYWNlX2lkID0gc3BhbkNvbnRleHQudHJhY2VJZDtcbiAgICAgICAgICBpbmZvLnNwYW5faWQgPSBzcGFuQ29udGV4dC5zcGFuSWQ7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICAgIHJldHVybiBpbmZvO1xuICAgIH0pKClcbiAgKSxcbiAgdHJhbnNwb3J0czogW1xuICAgIG5ldyB3aW5zdG9uLnRyYW5zcG9ydHMuQ29uc29sZSgpLCAvLyBMb2cgdG8gY29uc29sZSAoc3Rkb3V0L3N0ZGVycilcbiAgXSxcbiAgZXhpdE9uRXJyb3I6IGZhbHNlLCAvLyBEbyBub3QgZXhpdCBvbiBoYW5kbGVkIGV4Y2VwdGlvbnNcbn0pO1xuXG5mdW5jdGlvbiBvblNvY2tldEVycm9yKGVycjogRXJyb3IpIHtcbiAgLy8gVHlwZWQgZXJyb3JcbiAgbG9nZ2VyLmVycm9yKHtcbiAgICBtZXNzYWdlOiAnV2ViU29ja2V0IHNvY2tldCBlcnJvcicsXG4gICAgZXJyb3I6IGVyci5tZXNzYWdlLFxuICAgIHN0YWNrX3RyYWNlOiBlcnIuc3RhY2ssXG4gIH0pO1xufVxuXG5jb25zdCBKV0tTID0gam9zZS5jcmVhdGVSZW1vdGVKV0tTZXQoXG4gIG5ldyBVUkwoYCR7cHJvY2Vzcy5lbnYuQVBQX0NMSUVOVF9VUkx9L2FwaS9hdXRoL2p3dC9qd2tzLmpzb25gKVxuKTtcblxuY29uc3QgY29ubmVjdGVkQ2xpZW50cyA9IG5ldyBNYXA8c3RyaW5nLCBXZWJTb2NrZXQ+KCk7XG5cbmludGVyZmFjZSBBZ2VudENsaWVudENvbW1hbmQge1xuICBjb21tYW5kX2lkOiBzdHJpbmc7XG4gIGFjdGlvbjpcbiAgICB8ICdTVEFSVF9SRUNPUkRJTkdfU0VTU0lPTidcbiAgICB8ICdTVE9QX1JFQ09SRElOR19TRVNTSU9OJ1xuICAgIHwgJ0NBTkNFTF9SRUNPUkRJTkdfU0VTU0lPTic7XG4gIHBheWxvYWQ/OiB7XG4gICAgc3VnZ2VzdGVkVGl0bGU/OiBzdHJpbmc7XG4gICAgbGlua2VkRXZlbnRJZD86IHN0cmluZztcbiAgfTtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHNlbmRDb21tYW5kVG9Vc2VyKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY29tbWFuZDogQWdlbnRDbGllbnRDb21tYW5kXG4pOiBQcm9taXNlPGJvb2xlYW4+IHtcbiAgY29uc3QgY2xpZW50U29ja2V0ID0gY29ubmVjdGVkQ2xpZW50cy5nZXQodXNlcklkKTtcbiAgY29uc3Qgb3BlcmF0aW9uX25hbWUgPSAnU2VuZENvbW1hbmRUb1VzZXInO1xuICBpZiAoY2xpZW50U29ja2V0ICYmIGNsaWVudFNvY2tldC5yZWFkeVN0YXRlID09PSBXZWJTb2NrZXQuT1BFTikge1xuICAgIGNvbnN0IG1lc3NhZ2VUb1NlbmQgPSB7IHR5cGU6ICdBR0VOVF9DT01NQU5EJywgcGF5bG9hZDogY29tbWFuZCB9O1xuICAgIHRyeSB7XG4gICAgICBjbGllbnRTb2NrZXQuc2VuZChKU09OLnN0cmluZ2lmeShtZXNzYWdlVG9TZW5kKSk7XG4gICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAge1xuICAgICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgICAgICBjb21tYW5kX2FjdGlvbjogY29tbWFuZC5hY3Rpb24sXG4gICAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgICAgfSxcbiAgICAgICAgJ1NlbnQgY29tbWFuZCB0byB1c2VyJ1xuICAgICAgKTtcbiAgICAgIHJldHVybiB0cnVlO1xuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAge1xuICAgICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgICAgICBjb21tYW5kX2FjdGlvbjogY29tbWFuZC5hY3Rpb24sXG4gICAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgICAgZXJyb3JfbWVzc2FnZTogZXJyb3IubWVzc2FnZSxcbiAgICAgICAgICBzdGFja190cmFjZTogZXJyb3Iuc3RhY2ssXG4gICAgICAgIH0sXG4gICAgICAgICdFcnJvciBzZW5kaW5nIGNvbW1hbmQgdG8gdXNlcidcbiAgICAgICk7XG4gICAgICByZXR1cm4gZmFsc2U7XG4gICAgfVxuICB9IGVsc2Uge1xuICAgIGxvZ2dlci53YXJuKFxuICAgICAge1xuICAgICAgICBvcGVyYXRpb25fbmFtZSxcbiAgICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgICBjb21tYW5kX2FjdGlvbjogY29tbWFuZC5hY3Rpb24sXG4gICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICByZWFzb246ICdObyBhY3RpdmUgV2ViU29ja2V0IG9yIHNvY2tldCBub3Qgb3BlbicsXG4gICAgICB9LFxuICAgICAgJ0ZhaWxlZCB0byBzZW5kIGNvbW1hbmQgdG8gdXNlcidcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxufVxuXG5jb25zdCBtYWluID0gYXN5bmMgKCkgPT4ge1xuICBjb25zdCBhcHAgPSBleHByZXNzKCk7XG4gIGNvbnN0IGFwcDIgPSBleHByZXNzKCk7XG5cbiAgLy8gUmVwbGFjZSBNb3JnYW4gd2l0aCBleHByZXNzLXdpbnN0b24gZm9yIHN0cnVjdHVyZWQgcmVxdWVzdCBsb2dnaW5nXG4gIGFwcC51c2UoXG4gICAgZXhwcmVzc1dpbnN0b24ubG9nZ2VyKHtcbiAgICAgIHdpbnN0b25JbnN0YW5jZTogbG9nZ2VyLFxuICAgICAgbWV0YTogdHJ1ZSwgLy8gTG9nIG1ldGFkYXRhIHN1Y2ggYXMgcmVxLnVybCwgcmVxLm1ldGhvZCwgZXRjLlxuICAgICAgbXNnOiAnSFRUUCB7e3JlcS5tZXRob2R9fSB7e3JlcS51cmx9fSB7e3Jlcy5zdGF0dXNDb2RlfX0ge3tyZXMucmVzcG9uc2VUaW1lfX1tcycsXG4gICAgICBleHByZXNzRm9ybWF0OiBmYWxzZSwgLy8gVXNlIHdpbnN0b24ncyBmb3JtYXQsIG5vdCBtb3JnYW4nc1xuICAgICAgY29sb3JpemU6IGZhbHNlLCAvLyBKU09OIGxvZ3Mgc2hvdWxkIG5vdCBiZSBjb2xvcml6ZWRcbiAgICAgIHNraXA6IChyZXEsIF9yZXMpID0+IHJlcS5wYXRoID09PSAnL2hlYWx0aHonLCAvLyBTa2lwIGhlYWx0aCBjaGVja3NcbiAgICAgIGR5bmFtaWNNZXRhOiAocmVxLCByZXMpID0+IHtcbiAgICAgICAgLy8gQWRkIGN1c3RvbSBhdHRyaWJ1dGVzIHRvIHJlcXVlc3QgbG9nc1xuICAgICAgICBjb25zdCBtZXRhOiBBdHRyaWJ1dGVzID0ge307XG4gICAgICAgIGlmIChyZXEpIHtcbiAgICAgICAgICBtZXRhLmh0dHBfbWV0aG9kID0gcmVxLm1ldGhvZDtcbiAgICAgICAgICBtZXRhLmh0dHBfcGF0aCA9IHJlcS5vcmlnaW5hbFVybCB8fCByZXEudXJsO1xuICAgICAgICAgIC8vIG1ldGEudXNlcl9pZCA9IHJlcS51c2VyPy5pZDsgLy8gSWYgdXNlciBjb250ZXh0IGlzIGF2YWlsYWJsZVxuICAgICAgICB9XG4gICAgICAgIGlmIChyZXMpIHtcbiAgICAgICAgICBtZXRhLmh0dHBfc3RhdHVzX2NvZGUgPSByZXMuc3RhdHVzQ29kZTtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4gbWV0YTtcbiAgICAgIH0sXG4gICAgfSlcbiAgKTtcbiAgYXBwMi51c2UoXG4gICAgZXhwcmVzc1dpbnN0b24ubG9nZ2VyKHtcbiAgICAgIC8vIEFwcGx5IHRvIGFwcDIgYXMgd2VsbFxuICAgICAgd2luc3Rvbkluc3RhbmNlOiBsb2dnZXIsXG4gICAgICBtZXRhOiB0cnVlLFxuICAgICAgbXNnOiAnSFRUUCB7e3JlcS5tZXRob2R9fSB7e3JlcS51cmx9fSB7e3Jlcy5zdGF0dXNDb2RlfX0ge3tyZXMucmVzcG9uc2VUaW1lfX1tcyAoYXBwMiknLFxuICAgICAgZXhwcmVzc0Zvcm1hdDogZmFsc2UsXG4gICAgICBjb2xvcml6ZTogZmFsc2UsXG4gICAgICBza2lwOiAocmVxLCBfcmVzKSA9PiByZXEucGF0aCA9PT0gJy9oZWFsdGh6JyxcbiAgICAgIGR5bmFtaWNNZXRhOiAocmVxLCByZXMpID0+IHtcbiAgICAgICAgY29uc3QgbWV0YTogQXR0cmlidXRlcyA9IHt9O1xuICAgICAgICBpZiAocmVxKSB7XG4gICAgICAgICAgbWV0YS5odHRwX21ldGhvZCA9IHJlcS5tZXRob2Q7XG4gICAgICAgICAgbWV0YS5odHRwX3BhdGggPSByZXEub3JpZ2luYWxVcmwgfHwgcmVxLnVybDtcbiAgICAgICAgfVxuICAgICAgICBpZiAocmVzKSB7XG4gICAgICAgICAgbWV0YS5odHRwX3N0YXR1c19jb2RlID0gcmVzLnN0YXR1c0NvZGU7XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIG1ldGE7XG4gICAgICB9LFxuICAgIH0pXG4gICk7XG5cbiAgLy8gTWlkZGxld2FyZSBmb3IgY3VzdG9tIG1ldHJpY3MgZm9yIGFsbCByZXF1ZXN0c1xuICBjb25zdCByZWNvcmRIdHRwTWV0cmljcyA9IChcbiAgICByZXE6IFJlcXVlc3QsXG4gICAgcmVzOiBSZXNwb25zZSxcbiAgICBuZXh0OiBOZXh0RnVuY3Rpb25cbiAgKSA9PiB7XG4gICAgY29uc3Qgc3RhcnRFcG9jaCA9IERhdGUubm93KCk7XG4gICAgcmVzLm9uKCdmaW5pc2gnLCAoKSA9PiB7XG4gICAgICBjb25zdCBlbmRFcG9jaCA9IERhdGUubm93KCk7XG4gICAgICBjb25zdCBkdXJhdGlvblNlY29uZHMgPSAoZW5kRXBvY2ggLSBzdGFydEVwb2NoKSAvIDEwMDA7XG5cbiAgICAgIGNvbnN0IGF0dHJpYnV0ZXMgPSB7XG4gICAgICAgIGh0dHBfcm91dGU6IHJlcS5yb3V0ZVxuICAgICAgICAgID8gcmVxLnJvdXRlLnBhdGhcbiAgICAgICAgICA6IChyZXEub3JpZ2luYWxVcmwgfHwgcmVxLnVybCkuc3BsaXQoJz8nKVswXSwgLy8gVXNlIHJvdXRlIHBhdGggaWYgYXZhaWxhYmxlLCBlbHNlIGZ1bGwgcGF0aFxuICAgICAgICBodHRwX21ldGhvZDogcmVxLm1ldGhvZCxcbiAgICAgICAgc3RhdHVzX2NvZGU6IHJlcy5zdGF0dXNDb2RlLFxuICAgICAgfTtcbiAgICAgIGh0dHBTZXJ2ZXJSZXF1ZXN0c1RvdGFsLmFkZCgxLCBhdHRyaWJ1dGVzKTtcbiAgICAgIGh0dHBTZXJ2ZXJSZXF1ZXN0RHVyYXRpb25TZWNvbmRzLnJlY29yZChkdXJhdGlvblNlY29uZHMsIGF0dHJpYnV0ZXMpO1xuICAgIH0pO1xuICAgIG5leHQoKTtcbiAgfTtcbiAgYXBwLnVzZShyZWNvcmRIdHRwTWV0cmljcyk7XG4gIGFwcDIudXNlKHJlY29yZEh0dHBNZXRyaWNzKTsgLy8gQXBwbHkgdG8gYXBwMiBhcyB3ZWxsXG5cbiAgYXBwLnVzZShcbiAgICBleHByZXNzLmpzb24oe1xuICAgICAgbGltaXQ6ICc2TUInLFxuICAgICAgdmVyaWZ5OiAocmVxLCBfcmVzLCBidWYpID0+IHtcbiAgICAgICAgKHJlcSBhcyBhbnkpLnJhd0JvZHkgPSBidWYudG9TdHJpbmcoKTtcbiAgICAgIH0sXG4gICAgfSlcbiAgKTtcbiAgYXBwMi51c2UoXG4gICAgZXhwcmVzcy5qc29uKHtcbiAgICAgIGxpbWl0OiAnNk1CJyxcbiAgICAgIHZlcmlmeTogKHJlcSwgX3JlcywgYnVmKSA9PiB7XG4gICAgICAgIChyZXEgYXMgYW55KS5yYXdCb2R5ID0gYnVmLnRvU3RyaW5nKCk7XG4gICAgICB9LFxuICAgIH0pXG4gICk7XG5cbiAgYXBwLnVzZShleHByZXNzLnVybGVuY29kZWQoeyBleHRlbmRlZDogdHJ1ZSB9KSk7XG4gIGFwcDIudXNlKGV4cHJlc3MudXJsZW5jb2RlZCh7IGV4dGVuZGVkOiB0cnVlIH0pKTtcblxuICAvLyBBdXRoZW50aWNhdGlvbiBtaWRkbGV3YXJlIChhcHApXG4gIGFwcC51c2UoYXN5bmMgKHJlcTogUmVxdWVzdCwgcmVzOiBSZXNwb25zZSwgbmV4dDogTmV4dEZ1bmN0aW9uKSA9PiB7XG4gICAgLy8gVHlwZWQgcmVxLCByZXMsIG5leHRcbiAgICBjb25zdCBvcGVyYXRpb25fbmFtZSA9IGBBdXRoTWlkZGxld2FyZUFwcDFgO1xuICAgIGlmIChyZXEucGF0aC5tYXRjaCgvXFwvcHVibGljLykgfHwgcmVxLnBhdGgubWF0Y2goL1xcLXB1YmxpYyQvKSkge1xuICAgICAgcmV0dXJuIG5leHQoKTtcbiAgICB9XG4gICAgaWYgKHJlcS5wYXRoLm1hdGNoKC9cXC1hZG1pbiQvKSkge1xuICAgICAgY29uc3QgYXV0aG9yaXphdGlvblRva2VuID0gcmVxLmhlYWRlcnMuYXV0aG9yaXphdGlvbjtcbiAgICAgIGlmICghYXV0aG9yaXphdGlvblRva2VuIHx8ICFhdXRob3JpemF0aW9uVG9rZW4uc3RhcnRzV2l0aCgnQmFzaWMgJykpIHtcbiAgICAgICAgbG9nZ2VyLndhcm4oe1xuICAgICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICAgIHBhdGg6IHJlcS5wYXRoLFxuICAgICAgICAgIHJlYXNvbjogJ01pc3Npbmcgb3IgbWFsZm9ybWVkIEJhc2ljIGF1dGggZm9yIGFkbWluIHBhdGgnLFxuICAgICAgICB9KTtcbiAgICAgICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAxKS5zZW5kKCdVbmF1dGhvcml6ZWQnKTtcbiAgICAgIH1cbiAgICAgIGNvbnN0IGVuY29kZWRDcmVkcyA9IGF1dGhvcml6YXRpb25Ub2tlbi5zcGxpdCgnICcpWzFdO1xuICAgICAgY29uc3QgdmVyaWZ5VG9rZW4gPSBCdWZmZXIuZnJvbShlbmNvZGVkQ3JlZHMsICdiYXNlNjQnKVxuICAgICAgICAudG9TdHJpbmcoKVxuICAgICAgICAuc3BsaXQoJzonKVsxXTtcbiAgICAgIGlmICh2ZXJpZnlUb2tlbiAhPT0gcHJvY2Vzcy5lbnYuQkFTSUNfQVVUSCkge1xuICAgICAgICBsb2dnZXIud2Fybih7XG4gICAgICAgICAgb3BlcmF0aW9uX25hbWUsXG4gICAgICAgICAgcGF0aDogcmVxLnBhdGgsXG4gICAgICAgICAgcmVhc29uOiAnSW52YWxpZCBCYXNpYyBhdXRoIHRva2VuIGZvciBhZG1pbiBwYXRoJyxcbiAgICAgICAgfSk7XG4gICAgICAgIHJldHVybiByZXMuc3RhdHVzKDQwMSkuc2VuZCgnVW5hdXRob3JpemVkJyk7XG4gICAgICB9XG4gICAgICByZXR1cm4gbmV4dCgpO1xuICAgIH1cbiAgICBjb25zdCBhdXRoSGVhZGVyID0gcmVxLmhlYWRlcnMuYXV0aG9yaXphdGlvbjtcbiAgICBpZiAoYXV0aEhlYWRlciAmJiBhdXRoSGVhZGVyLnN0YXJ0c1dpdGgoJ0JlYXJlciAnKSkge1xuICAgICAgY29uc3QgdG9rZW4gPSBhdXRoSGVhZGVyLnNwbGl0KCcgJylbMV07XG4gICAgICB0cnkge1xuICAgICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBqb3NlLmp3dFZlcmlmeSh0b2tlbiwgSldLUyk7XG4gICAgICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgICAgICB7IG9wZXJhdGlvbl9uYW1lLCBwYXRoOiByZXEucGF0aCwgdXNlcl9pZDogcmVzdWx0LnBheWxvYWQuc3ViIH0sXG4gICAgICAgICAgJ0pXVCB2ZXJpZmllZCBzdWNjZXNzZnVsbHknXG4gICAgICAgICk7XG4gICAgICAgIChyZXEgYXMgYW55KS51c2VyID0gcmVzdWx0LnBheWxvYWQ7IC8vIEF0dGFjaCB1c2VyIHBheWxvYWQgdG8gcmVxdWVzdFxuICAgICAgICBuZXh0KCk7XG4gICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgbG9nZ2VyLndhcm4oe1xuICAgICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICAgIHBhdGg6IHJlcS5wYXRoLFxuICAgICAgICAgIGVycm9yX21lc3NhZ2U6IGUubWVzc2FnZSxcbiAgICAgICAgICByZWFzb246ICdKV1QgdmVyaWZpY2F0aW9uIGZhaWxlZCcsXG4gICAgICAgIH0pO1xuICAgICAgICByZXR1cm4gcmVzLnNlbmRTdGF0dXMoNDAzKTtcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgbG9nZ2VyLndhcm4oe1xuICAgICAgICBvcGVyYXRpb25fbmFtZSxcbiAgICAgICAgcGF0aDogcmVxLnBhdGgsXG4gICAgICAgIHJlYXNvbjogJ01pc3NpbmcgQmVhcmVyIHRva2VuJyxcbiAgICAgIH0pO1xuICAgICAgcmVzLnNlbmRTdGF0dXMoNDAxKTtcbiAgICB9XG4gIH0pO1xuXG4gIC8vIEF1dGhlbnRpY2F0aW9uIG1pZGRsZXdhcmUgKGFwcDIpIC0gRFJZIHByaW5jaXBsZSB2aW9sYXRpb24sIGNvbnNpZGVyIHJlZmFjdG9yaW5nIHRvIGEgc2hhcmVkIGZ1bmN0aW9uXG4gIGFwcDIudXNlKGFzeW5jIChyZXE6IFJlcXVlc3QsIHJlczogUmVzcG9uc2UsIG5leHQ6IE5leHRGdW5jdGlvbikgPT4ge1xuICAgIGNvbnN0IG9wZXJhdGlvbl9uYW1lID0gYEF1dGhNaWRkbGV3YXJlQXBwMmA7XG4gICAgaWYgKHJlcS5wYXRoLm1hdGNoKC9cXC9wdWJsaWMvKSB8fCByZXEucGF0aC5tYXRjaCgvXFwtcHVibGljJC8pKSB7XG4gICAgICByZXR1cm4gbmV4dCgpO1xuICAgIH1cbiAgICBpZiAocmVxLnBhdGgubWF0Y2goL1xcLWFkbWluJC8pKSB7XG4gICAgICBjb25zdCBhdXRob3JpemF0aW9uVG9rZW4gPSByZXEuaGVhZGVycy5hdXRob3JpemF0aW9uO1xuICAgICAgaWYgKCFhdXRob3JpemF0aW9uVG9rZW4gfHwgIWF1dGhvcml6YXRpb25Ub2tlbi5zdGFydHNXaXRoKCdCYXNpYyAnKSkge1xuICAgICAgICBsb2dnZXIud2Fybih7XG4gICAgICAgICAgb3BlcmF0aW9uX25hbWUsXG4gICAgICAgICAgcGF0aDogcmVxLnBhdGgsXG4gICAgICAgICAgcmVhc29uOiAnTWlzc2luZyBvciBtYWxmb3JtZWQgQmFzaWMgYXV0aCBmb3IgYWRtaW4gcGF0aCBvbiBhcHAyJyxcbiAgICAgICAgfSk7XG4gICAgICAgIHJldHVybiByZXMuc3RhdHVzKDQwMSkuc2VuZCgnVW5hdXRob3JpemVkJyk7XG4gICAgICB9XG4gICAgICBjb25zdCBlbmNvZGVkQ3JlZHMgPSBhdXRob3JpemF0aW9uVG9rZW4uc3BsaXQoJyAnKVsxXTtcbiAgICAgIGNvbnN0IHZlcmlmeVRva2VuID0gQnVmZmVyLmZyb20oZW5jb2RlZENyZWRzLCAnYmFzZTY0JylcbiAgICAgICAgLnRvU3RyaW5nKClcbiAgICAgICAgLnNwbGl0KCc6JylbMV07XG4gICAgICBpZiAodmVyaWZ5VG9rZW4gIT09IHByb2Nlc3MuZW52LkJBU0lDX0FVVEgpIHtcbiAgICAgICAgbG9nZ2VyLndhcm4oe1xuICAgICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICAgIHBhdGg6IHJlcS5wYXRoLFxuICAgICAgICAgIHJlYXNvbjogJ0ludmFsaWQgQmFzaWMgYXV0aCB0b2tlbiBmb3IgYWRtaW4gcGF0aCBvbiBhcHAyJyxcbiAgICAgICAgfSk7XG4gICAgICAgIHJldHVybiByZXMuc3RhdHVzKDQwMSkuc2VuZCgnVW5hdXRob3JpemVkJyk7XG4gICAgICB9XG4gICAgICByZXR1cm4gbmV4dCgpO1xuICAgIH1cbiAgICBjb25zdCBhdXRoSGVhZGVyID0gcmVxLmhlYWRlcnMuYXV0aG9yaXphdGlvbjtcbiAgICBpZiAoYXV0aEhlYWRlciAmJiBhdXRoSGVhZGVyLnN0YXJ0c1dpdGgoJ0JlYXJlciAnKSkge1xuICAgICAgY29uc3QgdG9rZW4gPSBhdXRoSGVhZGVyLnNwbGl0KCcgJylbMV07XG4gICAgICB0cnkge1xuICAgICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBqb3NlLmp3dFZlcmlmeSh0b2tlbiwgSldLUyk7XG4gICAgICAgIGxvZ2dlci5kZWJ1ZyhcbiAgICAgICAgICB7IG9wZXJhdGlvbl9uYW1lLCBwYXRoOiByZXEucGF0aCwgdXNlcl9pZDogcmVzdWx0LnBheWxvYWQuc3ViIH0sXG4gICAgICAgICAgJ0pXVCB2ZXJpZmllZCBzdWNjZXNzZnVsbHkgZm9yIGFwcDInXG4gICAgICAgICk7XG4gICAgICAgIChyZXEgYXMgYW55KS51c2VyID0gcmVzdWx0LnBheWxvYWQ7XG4gICAgICAgIG5leHQoKTtcbiAgICAgIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgICAgICBsb2dnZXIud2Fybih7XG4gICAgICAgICAgb3BlcmF0aW9uX25hbWUsXG4gICAgICAgICAgcGF0aDogcmVxLnBhdGgsXG4gICAgICAgICAgZXJyb3JfbWVzc2FnZTogZS5tZXNzYWdlLFxuICAgICAgICAgIHJlYXNvbjogJ0pXVCB2ZXJpZmljYXRpb24gZmFpbGVkIGZvciBhcHAyJyxcbiAgICAgICAgfSk7XG4gICAgICAgIHJldHVybiByZXMuc2VuZFN0YXR1cyg0MDMpO1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICBsb2dnZXIud2Fybih7XG4gICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICBwYXRoOiByZXEucGF0aCxcbiAgICAgICAgcmVhc29uOiAnTWlzc2luZyBCZWFyZXIgdG9rZW4gZm9yIGFwcDInLFxuICAgICAgfSk7XG4gICAgICByZXMuc2VuZFN0YXR1cyg0MDEpO1xuICAgIH1cbiAgfSk7XG5cbiAgYXBwLmRpc2FibGUoJ3gtcG93ZXJlZC1ieScpO1xuICBhcHAyLmRpc2FibGUoJ3gtcG93ZXJlZC1ieScpO1xuXG4gIGFwcC5nZXQoJy9oZWFsdGh6JywgKF9yZXE6IFJlcXVlc3QsIHJlczogUmVzcG9uc2UpID0+IHtcbiAgICAvLyBUeXBlZCByZXEsIHJlc1xuICAgIHJlcy5zdGF0dXMoMjAwKS5zZW5kKCdvaycpO1xuICB9KTtcbiAgYXBwMi5nZXQoJy9oZWFsdGh6JywgKF9yZXE6IFJlcXVlc3QsIHJlczogUmVzcG9uc2UpID0+IHtcbiAgICAvLyBUeXBlZCByZXEsIHJlc1xuICAgIHJlcy5zdGF0dXMoMjAwKS5zZW5kKCdvaycpO1xuICB9KTtcblxuICBjb25zdCBmdW5jdGlvbnNQYXRoID0gcGF0aC5qb2luKFxuICAgIHByb2Nlc3MuY3dkKCksXG4gICAgcHJvY2Vzcy5lbnYuRlVOQ1RJT05TX1JFTEFUSVZFX1BBVEghXG4gICk7IC8vIEFkZGVkIG5vbi1udWxsIGFzc2VydGlvblxuICBjb25zdCBmaWxlcyA9IGdsb2Iuc3luYygnKiovKi5AKGpzfHRzKScsIHtcbiAgICBjd2Q6IGZ1bmN0aW9uc1BhdGgsXG4gICAgaWdub3JlOiBbJyoqL25vZGVfbW9kdWxlcy8qKicsICcqKi9fKi8qKicsICcqKi9fKiddLFxuICB9KTtcblxuICBmb3IgKGNvbnN0IGZpbGUgb2YgZmlsZXMpIHtcbiAgICBjb25zdCBvcGVyYXRpb25fbmFtZSA9IGBMb2FkUm91dGVIYW5kbGVyYDtcbiAgICB0cnkge1xuICAgICAgY29uc3QgeyBkZWZhdWx0OiBoYW5kbGVyIH0gPSBhd2FpdCBpbXBvcnQocGF0aC5qb2luKGZ1bmN0aW9uc1BhdGgsIGZpbGUpKTtcbiAgICAgIGNvbnN0IHJlbGF0aXZlUGF0aCA9IHBhdGgucmVsYXRpdmUocHJvY2Vzcy5lbnYuTkhPU1RfUFJPSkVDVF9QQVRIISwgZmlsZSk7IC8vIEFkZGVkIG5vbi1udWxsIGFzc2VydGlvblxuXG4gICAgICBpZiAoaGFuZGxlcikge1xuICAgICAgICBjb25zdCByb3V0ZSA9IGAvJHtmaWxlfWBcbiAgICAgICAgICAucmVwbGFjZSgvKFxcLnRzfFxcLmpzKSQvLCAnJylcbiAgICAgICAgICAucmVwbGFjZSgvXFwvaW5kZXgkLywgJy8nKTtcbiAgICAgICAgYXBwLmFsbChyb3V0ZSwgaGFuZGxlcik7XG4gICAgICAgIGFwcDIuYWxsKHJvdXRlLCBoYW5kbGVyKTtcbiAgICAgICAgbG9nZ2VyLmluZm8oXG4gICAgICAgICAgeyBvcGVyYXRpb25fbmFtZSwgcm91dGUsIGZpbGU6IHJlbGF0aXZlUGF0aCB9LFxuICAgICAgICAgIGBMb2FkZWQgcm91dGUgZnJvbSBmaWxlYFxuICAgICAgICApO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbG9nZ2VyLndhcm4oe1xuICAgICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICAgIGZpbGU6IHJlbGF0aXZlUGF0aCxcbiAgICAgICAgICByZWFzb246ICdObyBkZWZhdWx0IGV4cG9ydCcsXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAge1xuICAgICAgICAgIG9wZXJhdGlvbl9uYW1lLFxuICAgICAgICAgIGZpbGUsXG4gICAgICAgICAgZXJyb3JfbWVzc2FnZTogZXJyb3IubWVzc2FnZSxcbiAgICAgICAgICBzdGFja190cmFjZTogZXJyb3Iuc3RhY2ssXG4gICAgICAgIH0sXG4gICAgICAgIGBVbmFibGUgdG8gbG9hZCBmaWxlIGFzIGEgU2VydmVybGVzcyBGdW5jdGlvbmBcbiAgICAgICk7XG4gICAgICBjb250aW51ZTtcbiAgICB9XG4gIH1cblxuICBjb25zdCBodHRwU2VydmVyID0gaHR0cC5jcmVhdGVTZXJ2ZXIoYXBwKTtcbiAgY29uc3QgaHR0cFNlcnZlcjIgPSBodHRwLmNyZWF0ZVNlcnZlcihhcHAyKTtcblxuICBjb25zdCB3c3MgPSBuZXcgV2ViU29ja2V0U2VydmVyKHsgY2xpZW50VHJhY2tpbmc6IGZhbHNlLCBub1NlcnZlcjogdHJ1ZSB9KTtcbiAgY29uc3Qgd3NzMiA9IG5ldyBXZWJTb2NrZXRTZXJ2ZXIoeyBjbGllbnRUcmFja2luZzogZmFsc2UsIG5vU2VydmVyOiB0cnVlIH0pO1xuXG4gIGNvbnN0IHdzRmlsZXMgPSBnbG9iLnN5bmMoJyoqL19jaGF0L2NoYXRfYnJhaW4vaGFuZGxlci50cycsIHtcbiAgICAvLyBUaGlzIHNlZW1zIHZlcnkgc3BlY2lmaWMsIGVuc3VyZSBpdCdzIGNvcnJlY3RcbiAgICBjd2Q6IGZ1bmN0aW9uc1BhdGgsXG4gICAgaWdub3JlOiBbJyoqL25vZGVfbW9kdWxlcy8qKiddLFxuICB9KTtcblxuICAvLyBDb21tb24gV2ViU29ja2V0IHVwZ3JhZGUgbG9naWNcbiAgYXN5bmMgZnVuY3Rpb24gaGFuZGxlV2ViU29ja2V0VXBncmFkZShcbiAgICB3c3NJbnN0YW5jZTogV2ViU29ja2V0U2VydmVyLFxuICAgIHJlcXVlc3Q6IFJlcXVlc3QsXG4gICAgc29ja2V0OiBOb2RlSlMuU29ja2V0LCAvLyBodHRwLkluY29taW5nTWVzc2FnZSB1c2VzIHN0cmVhbS5EdXBsZXgsIGJ1dCBXZWJTb2NrZXRTZXJ2ZXIgZXhwZWN0cyBOb2RlSlMuU29ja2V0XG4gICAgaGVhZDogQnVmZmVyLFxuICAgIHNlcnZlck5hbWU6IHN0cmluZ1xuICApIHtcbiAgICBjb25zdCBvcGVyYXRpb25fbmFtZSA9IGBXZWJTb2NrZXRVcGdyYWRlXyR7c2VydmVyTmFtZX1gO1xuICAgIHNvY2tldC5vbignZXJyb3InLCBvblNvY2tldEVycm9yKTsgLy8gb25Tb2NrZXRFcnJvciBub3cgdXNlcyBsb2dnZXJcblxuICAgIGxvZ2dlci5pbmZvKFxuICAgICAgeyBvcGVyYXRpb25fbmFtZSwgdXJsOiByZXF1ZXN0LnVybCB9LFxuICAgICAgYEF0dGVtcHRpbmcgV2ViU29ja2V0IHVwZ3JhZGVgXG4gICAgKTtcblxuICAgIGNvbnN0IHN0cmluZzJQYXJzZSA9IHJlcXVlc3QudXJsPy5zbGljZSgyKTsgLy8gQXNzdW1pbmcgVVJMIGxpa2UgXCIvP0F1dGg9QmVhcmVyJTIwdG9rZW5cIlxuICAgIGNvbnN0IHF1ZXJ5UGFyYW1zID0gcXMucGFyc2Uoc3RyaW5nMlBhcnNlIHx8ICcnKTtcbiAgICBjb25zdCBhdXRoSGVhZGVyID0gcXVlcnlQYXJhbXMuQXV0aCBhcyBzdHJpbmc7XG5cbiAgICBpZiAoYXV0aEhlYWRlciAmJiBhdXRoSGVhZGVyLnN0YXJ0c1dpdGgoJ0JlYXJlciAnKSkge1xuICAgICAgY29uc3QgdG9rZW4gPSBhdXRoSGVhZGVyLnNwbGl0KCcgJylbMV07XG4gICAgICB0cnkge1xuICAgICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBqb3NlLmp3dFZlcmlmeSh0b2tlbiwgSldLUyk7XG4gICAgICAgIGlmIChyZXN1bHQucGF5bG9hZC5zdWIgJiYgdHlwZW9mIHJlc3VsdC5wYXlsb2FkLnN1YiA9PT0gJ3N0cmluZycpIHtcbiAgICAgICAgICAocmVxdWVzdCBhcyBhbnkpLnVzZXJJZCA9IHJlc3VsdC5wYXlsb2FkLnN1YjtcbiAgICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICAgIHsgb3BlcmF0aW9uX25hbWUsIHVzZXJfaWQ6IHJlc3VsdC5wYXlsb2FkLnN1YiB9LFxuICAgICAgICAgICAgYFdlYlNvY2tldCBKV1QgdmVyaWZpZWRgXG4gICAgICAgICAgKTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBsb2dnZXIuZXJyb3Ioe1xuICAgICAgICAgICAgb3BlcmF0aW9uX25hbWUsXG4gICAgICAgICAgICByZWFzb246ICdVc2VyIElEIChzdWIpIG5vdCBmb3VuZCBvciBpbnZhbGlkIGluIEpXVCBwYXlsb2FkJyxcbiAgICAgICAgICB9KTtcbiAgICAgICAgICBzb2NrZXQud3JpdGUoXG4gICAgICAgICAgICAnSFRUUC8xLjEgNDAxIFVuYXV0aG9yaXplZCAoSW52YWxpZCBUb2tlbiBQYXlsb2FkKVxcclxcblxcclxcbidcbiAgICAgICAgICApO1xuICAgICAgICAgIHNvY2tldC5kZXN0cm95KCk7XG4gICAgICAgICAgcmV0dXJuO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgbG9nZ2VyLmVycm9yKHtcbiAgICAgICAgICBvcGVyYXRpb25fbmFtZSxcbiAgICAgICAgICBlcnJvcl9tZXNzYWdlOiBlLm1lc3NhZ2UsXG4gICAgICAgICAgcmVhc29uOiAnV2ViU29ja2V0IEpXVCB2ZXJpZmljYXRpb24gZmFpbGVkJyxcbiAgICAgICAgfSk7XG4gICAgICAgIHNvY2tldC53cml0ZSgnSFRUUC8xLjEgNDAxIFVuYXV0aG9yaXplZFxcclxcblxcclxcbicpO1xuICAgICAgICBzb2NrZXQuZGVzdHJveSgpO1xuICAgICAgICByZXR1cm47XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGxvZ2dlci53YXJuKHtcbiAgICAgICAgb3BlcmF0aW9uX25hbWUsXG4gICAgICAgIHJlYXNvbjogJ01pc3Npbmcgb3IgbWFsZm9ybWVkIEF1dGggcXVlcnkgcGFyYW1ldGVyIGZvciBXZWJTb2NrZXQnLFxuICAgICAgfSk7XG4gICAgICBzb2NrZXQud3JpdGUoJ0hUVFAvMS4xIDQwMSBVbmF1dGhvcml6ZWRcXHJcXG5cXHJcXG4nKTtcbiAgICAgIHNvY2tldC5kZXN0cm95KCk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgc29ja2V0LnJlbW92ZUxpc3RlbmVyKCdlcnJvcicsIG9uU29ja2V0RXJyb3IpO1xuICAgIHdzc0luc3RhbmNlLmhhbmRsZVVwZ3JhZGUoXG4gICAgICByZXF1ZXN0IGFzIGh0dHAuSW5jb21pbmdNZXNzYWdlLFxuICAgICAgc29ja2V0LFxuICAgICAgaGVhZCxcbiAgICAgIGZ1bmN0aW9uIGRvbmUod3MpIHtcbiAgICAgICAgd3NzSW5zdGFuY2UuZW1pdCgnY29ubmVjdGlvbicsIHdzLCByZXF1ZXN0KTtcbiAgICAgIH1cbiAgICApO1xuICB9XG5cbiAgaHR0cFNlcnZlci5vbigndXBncmFkZScsIChyZXEsIHNvY2tldCwgaGVhZCkgPT5cbiAgICBoYW5kbGVXZWJTb2NrZXRVcGdyYWRlKHdzcywgcmVxIGFzIFJlcXVlc3QsIHNvY2tldCwgaGVhZCwgJ2h0dHBTZXJ2ZXIxJylcbiAgKTtcbiAgaHR0cFNlcnZlcjIub24oJ3VwZ3JhZGUnLCAocmVxLCBzb2NrZXQsIGhlYWQpID0+XG4gICAgaGFuZGxlV2ViU29ja2V0VXBncmFkZSh3c3MyLCByZXEgYXMgUmVxdWVzdCwgc29ja2V0LCBoZWFkLCAnaHR0cFNlcnZlcjInKVxuICApO1xuXG4gIGNvbnN0IGtlZXBBbGl2ZVBlcmlvZCA9IDUwMDAwO1xuXG4gIC8vIENvbW1vbiBXZWJTb2NrZXQgY29ubmVjdGlvbiBsb2dpY1xuICBhc3luYyBmdW5jdGlvbiBvbldlYlNvY2tldENvbm5lY3Rpb24oXG4gICAgd3M6IFdlYlNvY2tldCxcbiAgICByZXF1ZXN0OiBSZXF1ZXN0ICYgeyB1c2VySWQ/OiBzdHJpbmcgfSxcbiAgICBzZXJ2ZXJOYW1lOiBzdHJpbmdcbiAgKSB7XG4gICAgY29uc3QgdXNlcklkID0gcmVxdWVzdC51c2VySWQ7XG4gICAgY29uc3Qgb3BlcmF0aW9uX25hbWUgPSBgV2ViU29ja2V0Q29ubmVjdF8ke3NlcnZlck5hbWV9YDtcblxuICAgIGlmICh1c2VySWQpIHtcbiAgICAgIGFjdGl2ZVdlYnNvY2tldENvbm5lY3Rpb25zLmFkZCgxLCB7IHNlcnZlcjogc2VydmVyTmFtZSB9KTtcbiAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICB7IG9wZXJhdGlvbl9uYW1lLCB1c2VyX2lkOiB1c2VySWQgfSxcbiAgICAgICAgYFdlYlNvY2tldCBjb25uZWN0aW9uIGVzdGFibGlzaGVkYFxuICAgICAgKTtcbiAgICAgIGNvbm5lY3RlZENsaWVudHMuc2V0KHVzZXJJZCwgd3MpO1xuXG4gICAgICB3cy5vbignZXJyb3InLCAoZXJyb3I6IEVycm9yKSA9PiB7XG4gICAgICAgIC8vIFR5cGVkIGVycm9yXG4gICAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgICB7XG4gICAgICAgICAgICBvcGVyYXRpb25fbmFtZSxcbiAgICAgICAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgICAgICAgIGVycm9yX21lc3NhZ2U6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgICAgICBzdGFja190cmFjZTogZXJyb3Iuc3RhY2ssXG4gICAgICAgICAgfSxcbiAgICAgICAgICBgV2ViU29ja2V0IGVycm9yYFxuICAgICAgICApO1xuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IGtlZXBBbGl2ZUlkID0gc2V0SW50ZXJ2YWwoKCkgPT4ge1xuICAgICAgICBpZiAod3MucmVhZHlTdGF0ZSA9PT0gV2ViU29ja2V0Lk9QRU4pIHtcbiAgICAgICAgICB3cy5zZW5kKEpTT04uc3RyaW5naWZ5KHsgdHlwZTogJ3BpbmcnIH0pKTsgLy8gU2VuZCBKU09OIHBpbmdcbiAgICAgICAgfVxuICAgICAgfSwga2VlcEFsaXZlUGVyaW9kKTtcblxuICAgICAgd3Mub24oJ21lc3NhZ2UnLCBhc3luYyBmdW5jdGlvbiBpbmNvbWluZyhtZXNzYWdlQnVmZmVyKSB7XG4gICAgICAgIGNvbnN0IG1lc3NhZ2VPcE5hbWUgPSBgV2ViU29ja2V0TWVzc2FnZV8ke3NlcnZlck5hbWV9YDtcbiAgICAgICAgd2Vic29ja2V0TWVzc2FnZXNSZWNlaXZlZFRvdGFsLmFkZCgxLCB7IHNlcnZlcjogc2VydmVyTmFtZSB9KTtcbiAgICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VCdWZmZXIudG9TdHJpbmcoKTtcbiAgICAgICAgbG9nZ2VyLmRlYnVnKFxuICAgICAgICAgIHtcbiAgICAgICAgICAgIG1lc3NhZ2VPcE5hbWUsXG4gICAgICAgICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICAgICAgICByZWNlaXZlZF9tZXNzYWdlX2xlbmd0aDogbWVzc2FnZS5sZW5ndGgsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBgUmVjZWl2ZWQgbWVzc2FnZWBcbiAgICAgICAgKTtcblxuICAgICAgICB0cnkge1xuICAgICAgICAgIGlmICh3c0ZpbGVzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgICAgICAgbG9nZ2VyLmVycm9yKHtcbiAgICAgICAgICAgICAgbWVzc2FnZU9wTmFtZSxcbiAgICAgICAgICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgICAgICAgICByZWFzb246ICdObyBXZWJTb2NrZXQgbWVzc2FnZSBoYW5kbGVyIGZpbGUgZm91bmQgKHdzRmlsZXMgZW1wdHkpJyxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgcmV0dXJuO1xuICAgICAgICAgIH1cbiAgICAgICAgICAvLyBBc3N1bWluZyB3c0ZpbGVzWzBdIGlzIHRoZSBjb3JyZWN0IGNoYXRfYnJhaW4gaGFuZGxlclxuICAgICAgICAgIGNvbnN0IHsgZGVmYXVsdDogaGFuZGxlciB9ID0gYXdhaXQgaW1wb3J0KFxuICAgICAgICAgICAgcGF0aC5qb2luKGZ1bmN0aW9uc1BhdGgsIHdzRmlsZXNbMF0pXG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb25zdCByZXBseU1lc3NhZ2UgPSBhd2FpdCBoYW5kbGVyKFxuICAgICAgICAgICAgbWVzc2FnZSxcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIHJlcXVlc3QsXG4gICAgICAgICAgICBzZW5kQ29tbWFuZFRvVXNlclxuICAgICAgICAgICk7XG5cbiAgICAgICAgICBpZiAocmVwbHlNZXNzYWdlICYmIHdzLnJlYWR5U3RhdGUgPT09IFdlYlNvY2tldC5PUEVOKSB7XG4gICAgICAgICAgICB3cy5zZW5kKHJlcGx5TWVzc2FnZSk7IC8vIHJlcGx5TWVzc2FnZSBpcyBleHBlY3RlZCB0byBiZSBzdHJpbmdpZmllZCBKU09OIG9yIHN0cmluZ1xuICAgICAgICAgIH1cbiAgICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICAgICAge1xuICAgICAgICAgICAgICBtZXNzYWdlT3BOYW1lLFxuICAgICAgICAgICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICAgICAgICAgIGVycm9yX21lc3NhZ2U6IGUubWVzc2FnZSxcbiAgICAgICAgICAgICAgc3RhY2tfdHJhY2U6IGUuc3RhY2ssXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgYEVycm9yIHByb2Nlc3NpbmcgbWVzc2FnZWBcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9KTtcblxuICAgICAgd3Mub24oJ2Nsb3NlJywgKGNvZGUsIHJlYXNvbikgPT4ge1xuICAgICAgICBhY3RpdmVXZWJzb2NrZXRDb25uZWN0aW9ucy5hZGQoLTEsIHsgc2VydmVyOiBzZXJ2ZXJOYW1lIH0pO1xuICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICB7XG4gICAgICAgICAgICBvcGVyYXRpb25fbmFtZTogYFdlYlNvY2tldENsb3NlXyR7c2VydmVyTmFtZX1gLFxuICAgICAgICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgICAgICAgY29kZSxcbiAgICAgICAgICAgIHJlYXNvbjogcmVhc29uLnRvU3RyaW5nKCksXG4gICAgICAgICAgfSxcbiAgICAgICAgICBgV2ViU29ja2V0IGNvbm5lY3Rpb24gY2xvc2VkYFxuICAgICAgICApO1xuICAgICAgICBjb25uZWN0ZWRDbGllbnRzLmRlbGV0ZSh1c2VySWQpO1xuICAgICAgICBjbGVhckludGVydmFsKGtlZXBBbGl2ZUlkKTtcbiAgICAgIH0pO1xuICAgIH0gZWxzZSB7XG4gICAgICBsb2dnZXIuZXJyb3Ioe1xuICAgICAgICBvcGVyYXRpb25fbmFtZSxcbiAgICAgICAgcmVhc29uOiAnV2ViU29ja2V0IGNvbm5lY3Rpb24gZXN0YWJsaXNoZWQgd2l0aG91dCBhIHVzZXJJZC4gQ2xvc2luZy4nLFxuICAgICAgfSk7XG4gICAgICB3cy5jbG9zZSgxMDA4LCAnVXNlciBJRCBub3QgYXZhaWxhYmxlIGFmdGVyIHVwZ3JhZGUnKTtcbiAgICB9XG4gIH1cblxuICB3c3Mub24oJ2Nvbm5lY3Rpb24nLCAod3MsIHJlcSkgPT5cbiAgICBvbldlYlNvY2tldENvbm5lY3Rpb24od3MsIHJlcSBhcyBSZXF1ZXN0ICYgeyB1c2VySWQ/OiBzdHJpbmcgfSwgJ3dzczEnKVxuICApO1xuICB3c3MyLm9uKCdjb25uZWN0aW9uJywgKHdzLCByZXEpID0+XG4gICAgb25XZWJTb2NrZXRDb25uZWN0aW9uKHdzLCByZXEgYXMgUmVxdWVzdCAmIHsgdXNlcklkPzogc3RyaW5nIH0sICd3c3MyJylcbiAgKTtcblxuICBjb25zdCB3b3JrZXJGaWxlcyA9IGdsb2Iuc3luYygnKiovKl8vKi5AKGpzfHRzKScsIHtcbiAgICAvLyBlLmcuIF9kYXlTY2hlZHVsZVdvcmtlcl9cbiAgICBjd2Q6IGZ1bmN0aW9uc1BhdGgsXG4gICAgaWdub3JlOiBbJyoqL25vZGVfbW9kdWxlcy8qKiddLFxuICB9KTtcblxuICBjb25zdCB3b3JrZXJIYW5kbGVyczogKCgpID0+IFByb21pc2U8YW55PilbXSA9IFtdOyAvLyBUeXBlZCBhcnJheVxuICBmb3IgKGNvbnN0IHdvcmtlckZpbGUgb2Ygd29ya2VyRmlsZXMpIHtcbiAgICBjb25zdCBvcE5hbWUgPSBgTG9hZFdvcmtlckhhbmRsZXJgO1xuICAgIHRyeSB7XG4gICAgICBjb25zdCB7IGRlZmF1bHQ6IGhhbmRsZXIgfSA9IGF3YWl0IGltcG9ydChcbiAgICAgICAgcGF0aC5qb2luKGZ1bmN0aW9uc1BhdGgsIHdvcmtlckZpbGUpXG4gICAgICApO1xuICAgICAgaWYgKHR5cGVvZiBoYW5kbGVyID09PSAnZnVuY3Rpb24nKSB7XG4gICAgICAgIHdvcmtlckhhbmRsZXJzLnB1c2goaGFuZGxlcik7XG4gICAgICAgIGxvZ2dlci5pbmZvKHsgb3BOYW1lLCBmaWxlOiB3b3JrZXJGaWxlIH0sIGBMb2FkZWQgd29ya2VyIGhhbmRsZXJgKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGxvZ2dlci53YXJuKHtcbiAgICAgICAgICBvcE5hbWUsXG4gICAgICAgICAgZmlsZTogd29ya2VyRmlsZSxcbiAgICAgICAgICByZWFzb246ICdObyBkZWZhdWx0IGV4cG9ydCBmdW5jdGlvbiBmb3VuZCcsXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAge1xuICAgICAgICAgIG9wTmFtZSxcbiAgICAgICAgICBmaWxlOiB3b3JrZXJGaWxlLFxuICAgICAgICAgIGVycm9yX21lc3NhZ2U6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgICAgc3RhY2tfdHJhY2U6IGVycm9yLnN0YWNrLFxuICAgICAgICB9LFxuICAgICAgICBgRXJyb3IgbG9hZGluZyB3b3JrZXIgaGFuZGxlcmBcbiAgICAgICk7XG4gICAgfVxuICB9XG5cbiAgaWYgKHdvcmtlckhhbmRsZXJzLmxlbmd0aCA+IDApIHtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIHsgb3BlcmF0aW9uX25hbWU6ICdJbml0aWFsaXplV29ya2VycycsIGNvdW50OiB3b3JrZXJIYW5kbGVycy5sZW5ndGggfSxcbiAgICAgICdJbml0aWFsaXppbmcgS2Fma2EgY29uc3VtZXIgd29ya2Vycy4uLidcbiAgICApO1xuICAgIGF3YWl0IFByb21pc2UuYWxsKHdvcmtlckhhbmRsZXJzLm1hcCgoaGFuZGxlcikgPT4gaGFuZGxlcigpKSkuY2F0Y2goXG4gICAgICAoZXJyKSA9PiB7XG4gICAgICAgIGxvZ2dlci5lcnJvcihcbiAgICAgICAgICB7XG4gICAgICAgICAgICBvcGVyYXRpb25fbmFtZTogJ0luaXRpYWxpemVXb3JrZXJzJyxcbiAgICAgICAgICAgIGVycm9yX21lc3NhZ2U6IGVyci5tZXNzYWdlLFxuICAgICAgICAgICAgc3RhY2tfdHJhY2U6IGVyci5zdGFjayxcbiAgICAgICAgICB9LFxuICAgICAgICAgICdFcnJvciBkdXJpbmcgd29ya2VyIGluaXRpYWxpemF0aW9uJ1xuICAgICAgICApO1xuICAgICAgfVxuICAgICk7XG4gIH0gZWxzZSB7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICB7IG9wZXJhdGlvbl9uYW1lOiAnSW5pdGlhbGl6ZVdvcmtlcnMnIH0sXG4gICAgICAnTm8gS2Fma2EgY29uc3VtZXIgd29ya2VycyBmb3VuZCB0byBpbml0aWFsaXplLidcbiAgICApO1xuICB9XG5cbiAgYXdhaXQgc3RhcnRBZ2VuZGEoKS5jYXRjaCgoZXJyb3IpID0+IHtcbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICB7XG4gICAgICAgIG9wZXJhdGlvbl9uYW1lOiAnU3RhcnRBZ2VuZGEnLFxuICAgICAgICBlcnJvcl9tZXNzYWdlOiBlcnJvci5tZXNzYWdlLFxuICAgICAgICBzdGFja190cmFjZTogZXJyb3Iuc3RhY2ssXG4gICAgICB9LFxuICAgICAgJ0ZhaWxlZCB0byBzdGFydCBBZ2VuZGEnXG4gICAgKTtcbiAgfSk7XG5cbiAgYXBwLnBvc3QoJy9hcGkvYWdlbnQtaGFuZGxlcicsIGFzeW5jIChyZXE6IFJlcXVlc3QsIHJlczogUmVzcG9uc2UpID0+IHtcbiAgICAvLyBUeXBlZCByZXEsIHJlc1xuICAgIGNvbnN0IG9wZXJhdGlvbl9uYW1lID0gJ0FnZW50SGFuZGxlclNjaGVkdWxlZFRhc2snO1xuICAgIGxvZ2dlci5pbmZvKHsgb3BlcmF0aW9uX25hbWUgfSwgJ1JlY2VpdmVkIHJlcXVlc3QgZnJvbSBBZ2VuZGEgam9iIHJ1bm5lcicpO1xuICAgIGNvbnN0IHtcbiAgICAgIG1lc3NhZ2UsXG4gICAgICB1c2VySWQsXG4gICAgICBpbnRlbnROYW1lLFxuICAgICAgZW50aXRpZXMsXG4gICAgICByZXF1ZXN0U291cmNlLFxuICAgICAgY29udmVyc2F0aW9uSWQsXG4gICAgfSA9IHJlcS5ib2R5O1xuXG4gICAgaWYgKFxuICAgICAgIXVzZXJJZCB8fFxuICAgICAgIWludGVudE5hbWUgfHxcbiAgICAgICFyZXF1ZXN0U291cmNlIHx8XG4gICAgICByZXF1ZXN0U291cmNlICE9PSAnU2NoZWR1bGVkSm9iRXhlY3V0b3InXG4gICAgKSB7XG4gICAgICBsb2dnZXIud2FybihcbiAgICAgICAgeyBvcGVyYXRpb25fbmFtZSwgZXJyb3JfY29kZTogJ1ZBTElEQVRJT05fMDAxJywgcGF5bG9hZDogcmVxLmJvZHkgfSxcbiAgICAgICAgJ0ludmFsaWQgcGF5bG9hZCBmb3Igc2NoZWR1bGVkIHRhc2snXG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgLmpzb24oeyBlcnJvcjogJ0ludmFsaWQgcGF5bG9hZCBmb3Igc2NoZWR1bGVkIHRhc2snIH0pO1xuICAgIH1cblxuICAgIHRyeSB7XG4gICAgICBjb25zdCBpbnRlcmZhY2VUeXBlOiBJbnRlcmZhY2VUeXBlID0gJ3RleHQnO1xuICAgICAgY29uc3Qgb3B0aW9ucyA9IHsgcmVxdWVzdFNvdXJjZSwgaW50ZW50TmFtZSwgZW50aXRpZXMsIGNvbnZlcnNhdGlvbklkIH07XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlKFxuICAgICAgICBpbnRlcmZhY2VUeXBlLFxuICAgICAgICBtZXNzYWdlLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIG9wdGlvbnNcbiAgICAgICk7XG5cbiAgICAgIGxvZ2dlci5pbmZvKFxuICAgICAgICB7XG4gICAgICAgICAgb3BlcmF0aW9uX25hbWUsXG4gICAgICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgICAgIGludGVudDogaW50ZW50TmFtZSxcbiAgICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICAgIHJlc3VsdF90ZXh0X2xlbmd0aDogcmVzdWx0LnRleHQ/Lmxlbmd0aCxcbiAgICAgICAgfSxcbiAgICAgICAgJ1NjaGVkdWxlZCB0YXNrIHByb2Nlc3NlZCBzdWNjZXNzZnVsbHknXG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDIwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICAgICAgbWVzc2FnZTogJ1Rhc2sgcHJvY2Vzc2VkJyxcbiAgICAgICAgICBkZXRhaWxzOiByZXN1bHQudGV4dCxcbiAgICAgICAgfSk7XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgbG9nZ2VyLmVycm9yKFxuICAgICAgICB7XG4gICAgICAgICAgb3BlcmF0aW9uX25hbWUsXG4gICAgICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgICAgIGludGVudDogaW50ZW50TmFtZSxcbiAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcl9tZXNzYWdlOiBlcnJvci5tZXNzYWdlLFxuICAgICAgICAgIHN0YWNrX3RyYWNlOiBlcnJvci5zdGFjayxcbiAgICAgICAgfSxcbiAgICAgICAgJ0Vycm9yIHByb2Nlc3Npbmcgc2NoZWR1bGVkIHRhc2snXG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICAgIGVycm9yOiBlcnJvci5tZXNzYWdlIHx8ICdJbnRlcm5hbCBzZXJ2ZXIgZXJyb3InLFxuICAgICAgICB9KTtcbiAgICB9XG4gIH0pO1xuXG4gIGh0dHBTZXJ2ZXIubGlzdGVuKFBPUlQsICgpID0+IHtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIHsgb3BlcmF0aW9uX25hbWU6ICdIdHRwU2VydmVyU3RhcnQnLCBwb3J0OiBQT1JUIH0sXG4gICAgICBgSFRUUCBTZXJ2ZXIgd2l0aCBBZ2VudCBIYW5kbGVyIGxpc3RlbmluZ2BcbiAgICApO1xuICB9KTtcbiAgaHR0cFNlcnZlcjIubGlzdGVuKFBPUlQyLCAoKSA9PiB7XG4gICAgbG9nZ2VyLmluZm8oXG4gICAgICB7IG9wZXJhdGlvbl9uYW1lOiAnSHR0cFNlcnZlcjJTdGFydCcsIHBvcnQ6IFBPUlQyIH0sXG4gICAgICBgSFRUUCBTZXJ2ZXIgMiBsaXN0ZW5pbmdgXG4gICAgKTtcbiAgfSk7XG5cbiAgLy8gQ2VudHJhbGl6ZWQgRXJyb3IgSGFuZGxpbmcgTWlkZGxld2FyZSBmb3IgJ2FwcCdcbiAgLy8gVGhpcyBNVVNUIGJlIHRoZSBsYXN0IG1pZGRsZXdhcmUgYWRkZWQgdG8gdGhlIGFwcCBzdGFjay5cbiAgYXBwLnVzZSgoZXJyOiBhbnksIHJlcTogUmVxdWVzdCwgcmVzOiBSZXNwb25zZSwgbmV4dDogTmV4dEZ1bmN0aW9uKSA9PiB7XG4gICAgY29uc3QgdHJhY2VJZCA9IHRyYWNlLmdldFNwYW4ob3RlbENvbnRleHQuYWN0aXZlKCkpPy5zcGFuQ29udGV4dCgpLnRyYWNlSWQ7XG5cbiAgICBsb2dnZXIuZXJyb3IoXG4gICAgICB7XG4gICAgICAgIC8vIFN0YW5kYXJkIGxvZyBmaWVsZHMgd2lsbCBiZSBhZGRlZCBieSBXaW5zdG9uIGZvcm1hdCAoc2VydmljZV9uYW1lLCB2ZXJzaW9uLCB0aW1lc3RhbXApXG4gICAgICAgIC8vIHRyYWNlX2lkLCBzcGFuX2lkIHNob3VsZCBiZSBhZGRlZCBieSBXaW5zdG9uSW5zdHJ1bWVudGF0aW9uIGxvZ0hvb2tcbiAgICAgICAgZXJyb3JfbWVzc2FnZTogZXJyLm1lc3NhZ2UsXG4gICAgICAgIGVycm9yX3N0YWNrOiBlcnIuc3RhY2ssIC8vIEJlIGNhdXRpb3VzIGFib3V0IGxvZ2dpbmcgZnVsbCBzdGFja3MgaW4gcHJvZCBkZXBlbmRpbmcgb24gc2Vuc2l0aXZpdHlcbiAgICAgICAgZXJyb3JfbmFtZTogZXJyLm5hbWUsXG4gICAgICAgIGVycm9yX2NvZGVfcHJvcGVydHk6IGVyci5jb2RlLCAvLyBlLmcuLCBmcm9tIG9wb3NzdW0gRU9QRU5CUkVBS0VSIG9yIG90aGVyIGxpYnNcbiAgICAgICAgaHR0cF9tZXRob2Q6IHJlcS5tZXRob2QsXG4gICAgICAgIGh0dHBfcGF0aDogcmVxLm9yaWdpbmFsVXJsIHx8IHJlcS51cmwsXG4gICAgICAgIC8vIHRyYWNlX2lkOiB0cmFjZUlkLCAvLyBFeHBsaWNpdGx5IGFkZGluZyBmb3IgY2xhcml0eSwgdGhvdWdoIGhvb2sgc2hvdWxkIGRvIGl0LlxuICAgICAgfSxcbiAgICAgIGBVbmhhbmRsZWQgZXJyb3IgY2F1Z2h0IGJ5IGNlbnRyYWwgZXJyb3IgaGFuZGxlciBmb3IgYXBwMTogJHtlcnIubWVzc2FnZX1gXG4gICAgKTtcblxuICAgIC8vIFNldCBPcGVuVGVsZW1ldHJ5IFNwYW4gU3RhdHVzIHRvIGVycm9yXG4gICAgY29uc3QgY3VycmVudFNwYW4gPSB0cmFjZS5nZXRTcGFuKG90ZWxDb250ZXh0LmFjdGl2ZSgpKTtcbiAgICBpZiAoY3VycmVudFNwYW4pIHtcbiAgICAgIGN1cnJlbnRTcGFuLnJlY29yZEV4Y2VwdGlvbihlcnIpOyAvLyBSZWNvcmRzIGVycm9yIGRldGFpbHMgb24gdGhlIHNwYW5cbiAgICAgIGN1cnJlbnRTcGFuLnNldFN0YXR1cyh7XG4gICAgICAgIGNvZGU6IFNwYW5TdGF0dXNDb2RlLkVSUk9SLFxuICAgICAgICBtZXNzYWdlOiBlcnIubWVzc2FnZSxcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIGlmICghcmVzLmhlYWRlcnNTZW50KSB7XG4gICAgICBsZXQgc3RhdHVzQ29kZSA9IGVyci5zdGF0dXMgfHwgZXJyLnN0YXR1c0NvZGUgfHwgNTAwO1xuICAgICAgaWYgKFxuICAgICAgICB0eXBlb2Ygc3RhdHVzQ29kZSAhPT0gJ251bWJlcicgfHxcbiAgICAgICAgc3RhdHVzQ29kZSA8IDQwMCB8fFxuICAgICAgICBzdGF0dXNDb2RlID4gNTk5XG4gICAgICApIHtcbiAgICAgICAgc3RhdHVzQ29kZSA9IDUwMDsgLy8gRW5zdXJlIGl0J3MgYSB2YWxpZCBIVFRQIGVycm9yIHN0YXR1c1xuICAgICAgfVxuXG4gICAgICBsZXQgZXJyb3JDb2RlID0gJ1VORVhQRUNURURfRVJST1InO1xuICAgICAgaWYgKGVyci5jb2RlKSB7XG4gICAgICAgIC8vIEZyb20gb3Bvc3N1bSAoRU9QRU5CUkVBS0VSKSBvciBvdGhlciBsaWJzXG4gICAgICAgIGVycm9yQ29kZSA9IGVyci5jb2RlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgc3dpdGNoIChzdGF0dXNDb2RlKSB7XG4gICAgICAgICAgY2FzZSA0MDA6XG4gICAgICAgICAgICBlcnJvckNvZGUgPSAnQkFEX1JFUVVFU1QnO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgY2FzZSA0MDE6XG4gICAgICAgICAgICBlcnJvckNvZGUgPSAnVU5BVVRIT1JJWkVEJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNDAzOlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ0ZPUkJJRERFTic7XG4gICAgICAgICAgICBicmVhaztcbiAgICAgICAgICBjYXNlIDQwNDpcbiAgICAgICAgICAgIGVycm9yQ29kZSA9ICdOT1RfRk9VTkQnO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgY2FzZSA1MDA6XG4gICAgICAgICAgICBlcnJvckNvZGUgPSAnSU5URVJOQUxfU0VSVkVSX0VSUk9SJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNTAyOlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ0JBRF9HQVRFV0FZJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNTAzOlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ1NFUlZJQ0VfVU5BVkFJTEFCTEUnO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgY2FzZSA1MDQ6XG4gICAgICAgICAgICBlcnJvckNvZGUgPSAnR0FURVdBWV9USU1FT1VUJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlTWVzc2FnZSA9XG4gICAgICAgIHN0YXR1c0NvZGUgPj0gNTAwICYmIHByb2Nlc3MuZW52Lk5PREVfRU5WID09PSAncHJvZHVjdGlvbidcbiAgICAgICAgICA/ICdBbiBpbnRlcm5hbCBzZXJ2ZXIgZXJyb3Igb2NjdXJyZWQuIFBsZWFzZSB0cnkgYWdhaW4gbGF0ZXIuJ1xuICAgICAgICAgIDogZXJyLm1lc3NhZ2UgfHwgJ0FuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQuJztcblxuICAgICAgcmVzLnN0YXR1cyhzdGF0dXNDb2RlKS5qc29uKHtcbiAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogZXJyb3JDb2RlLFxuICAgICAgICAgIG1lc3NhZ2U6IHJlc3BvbnNlTWVzc2FnZSxcbiAgICAgICAgfSxcbiAgICAgIH0pO1xuICAgIH0gZWxzZSB7XG4gICAgICBuZXh0KGVycik7IC8vIERlbGVnYXRlIHRvIGRlZmF1bHQgRXhwcmVzcyBlcnJvciBoYW5kbGVyIGlmIGhlYWRlcnMgYWxyZWFkeSBzZW50XG4gICAgfVxuICB9KTtcblxuICAvLyBDZW50cmFsaXplZCBFcnJvciBIYW5kbGluZyBNaWRkbGV3YXJlIGZvciAnYXBwMidcbiAgYXBwMi51c2UoKGVycjogYW55LCByZXE6IFJlcXVlc3QsIHJlczogUmVzcG9uc2UsIG5leHQ6IE5leHRGdW5jdGlvbikgPT4ge1xuICAgIC8vIFJlLWdldCB0cmFjZUlkIGZvciBhcHAyJ3MgY29udGV4dCwgdGhvdWdoIGl0IHNob3VsZCBiZSBzYW1lIGlmIG9uZSByZXF1ZXN0IGZsb3dzIHRvIGJvdGguXG4gICAgLy8gY29uc3QgdHJhY2VJZCA9IHRyYWNlLmdldFNwYW4ob3RlbENvbnRleHQuYWN0aXZlKCkpPy5zcGFuQ29udGV4dCgpLnRyYWNlSWQ7XG4gICAgLy8gTG9nZ2luZyBhbmQgT1RlbCBzcGFuIHN0YXR1cyBhbHJlYWR5IGhhbmRsZWQgYWJvdmUgdGhpcyBzZWN0aW9uIGluIHRoZSBwcmV2aW91cyBkaWZmLlxuXG4gICAgbG9nZ2VyLmVycm9yKFxuICAgICAgLy8gVGhpcyBsb2cgd2FzIGFscmVhZHkgYWRkZWQgYW5kIGlzIGdvb2QuXG4gICAgICB7XG4gICAgICAgIGVycm9yX21lc3NhZ2U6IGVyci5tZXNzYWdlLFxuICAgICAgICBlcnJvcl9zdGFjazogZXJyLnN0YWNrLFxuICAgICAgICBlcnJvcl9uYW1lOiBlcnIubmFtZSxcbiAgICAgICAgZXJyb3JfY29kZV9wcm9wZXJ0eTogZXJyLmNvZGUsXG4gICAgICAgIGh0dHBfbWV0aG9kOiByZXEubWV0aG9kLFxuICAgICAgICBodHRwX3BhdGg6IHJlcS5vcmlnaW5hbFVybCB8fCByZXEudXJsLFxuICAgICAgICBhcHBfaW5zdGFuY2U6ICdhcHAyJyxcbiAgICAgIH0sXG4gICAgICBgVW5oYW5kbGVkIGVycm9yIGNhdWdodCBieSBjZW50cmFsIGVycm9yIGhhbmRsZXIgZm9yIGFwcDI6ICR7ZXJyLm1lc3NhZ2V9YFxuICAgICk7XG5cbiAgICBjb25zdCBjdXJyZW50U3BhbkFwcDIgPSB0cmFjZS5nZXRTcGFuKG90ZWxDb250ZXh0LmFjdGl2ZSgpKTtcbiAgICBpZiAoY3VycmVudFNwYW5BcHAyKSB7XG4gICAgICAvLyBFbnN1cmUgdG8gdXNlIGEgcG90ZW50aWFsbHkgZGlmZmVyZW50IHNwYW4gaWYgYXBwMiBoYXMgaXRzIG93biByb290IHNwYW4gZm9yIHNvbWUgcmVhc29uXG4gICAgICBjdXJyZW50U3BhbkFwcDIucmVjb3JkRXhjZXB0aW9uKGVycik7XG4gICAgICBjdXJyZW50U3BhbkFwcDIuc2V0U3RhdHVzKHtcbiAgICAgICAgY29kZTogU3BhblN0YXR1c0NvZGUuRVJST1IsXG4gICAgICAgIG1lc3NhZ2U6IGVyci5tZXNzYWdlLFxuICAgICAgfSk7XG4gICAgfVxuXG4gICAgaWYgKCFyZXMuaGVhZGVyc1NlbnQpIHtcbiAgICAgIGxldCBzdGF0dXNDb2RlID0gZXJyLnN0YXR1cyB8fCBlcnIuc3RhdHVzQ29kZSB8fCA1MDA7XG4gICAgICBpZiAoXG4gICAgICAgIHR5cGVvZiBzdGF0dXNDb2RlICE9PSAnbnVtYmVyJyB8fFxuICAgICAgICBzdGF0dXNDb2RlIDwgNDAwIHx8XG4gICAgICAgIHN0YXR1c0NvZGUgPiA1OTlcbiAgICAgICkge1xuICAgICAgICBzdGF0dXNDb2RlID0gNTAwO1xuICAgICAgfVxuXG4gICAgICBsZXQgZXJyb3JDb2RlID0gJ1VORVhQRUNURURfRVJST1JfQVBQMic7XG4gICAgICBpZiAoZXJyLmNvZGUpIHtcbiAgICAgICAgZXJyb3JDb2RlID0gZXJyLmNvZGU7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzd2l0Y2ggKHN0YXR1c0NvZGUpIHtcbiAgICAgICAgICBjYXNlIDQwMDpcbiAgICAgICAgICAgIGVycm9yQ29kZSA9ICdCQURfUkVRVUVTVF9BUFAyJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNDAxOlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ1VOQVVUSE9SSVpFRF9BUFAyJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNDAzOlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ0ZPUkJJRERFTl9BUFAyJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNDA0OlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ05PVF9GT1VORF9BUFAyJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNTAwOlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ0lOVEVSTkFMX1NFUlZFUl9FUlJPUl9BUFAyJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNTAyOlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ0JBRF9HQVRFV0FZX0FQUDInO1xuICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgY2FzZSA1MDM6XG4gICAgICAgICAgICBlcnJvckNvZGUgPSAnU0VSVklDRV9VTkFWQUlMQUJMRV9BUFAyJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGNhc2UgNTA0OlxuICAgICAgICAgICAgZXJyb3JDb2RlID0gJ0dBVEVXQVlfVElNRU9VVF9BUFAyJztcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHJlc3BvbnNlTWVzc2FnZSA9XG4gICAgICAgIHN0YXR1c0NvZGUgPj0gNTAwICYmIHByb2Nlc3MuZW52Lk5PREVfRU5WID09PSAncHJvZHVjdGlvbidcbiAgICAgICAgICA/ICdBbiBpbnRlcm5hbCBzZXJ2ZXIgZXJyb3Igb2NjdXJyZWQgb24gYXBwMi4gUGxlYXNlIHRyeSBhZ2FpbiBsYXRlci4nXG4gICAgICAgICAgOiBlcnIubWVzc2FnZSB8fCAnQW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZCBvbiBhcHAyLic7XG5cbiAgICAgIHJlcy5zdGF0dXMoc3RhdHVzQ29kZSkuanNvbih7XG4gICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6IGVycm9yQ29kZSxcbiAgICAgICAgICBtZXNzYWdlOiByZXNwb25zZU1lc3NhZ2UsXG4gICAgICAgIH0sXG4gICAgICB9KTtcbiAgICB9IGVsc2Uge1xuICAgICAgbmV4dChlcnIpO1xuICAgIH1cbiAgfSk7XG5cbiAgY29uc3Qgc2h1dGRvd24gPSBhc3luYyAoc2lnbmFsOiBzdHJpbmcpID0+IHtcbiAgICBsb2dnZXIuaW5mbyhcbiAgICAgIHsgb3BlcmF0aW9uX25hbWU6ICdTaHV0ZG93blByb2Nlc3MnLCBzaWduYWwgfSxcbiAgICAgIGBSZWNlaXZlZCBzaWduYWwuIFNodXR0aW5nIGRvd24uLi5gXG4gICAgKTtcbiAgICBhd2FpdCBzdG9wQWdlbmRhKCk7XG4gICAgLy8gQWRkIGFueSBvdGhlciBjbGVhbnVwIGhlcmUgKGUuZy4gd3NzLmNsb3NlKCksIHNkay5zaHV0ZG93bigpIC0gdGhvdWdoIHNkayBoYW5kbGVzIFNJR1RFUk0vU0lHSU5UKVxuICAgIGh0dHBTZXJ2ZXIuY2xvc2UoKCkgPT4ge1xuICAgICAgbG9nZ2VyLmluZm8oeyBvcGVyYXRpb25fbmFtZTogJ0h0dHBTZXJ2ZXJTdG9wJyB9LCAnSFRUUCBzZXJ2ZXIgY2xvc2VkLicpO1xuICAgICAgaHR0cFNlcnZlcjIuY2xvc2UoKCkgPT4ge1xuICAgICAgICBsb2dnZXIuaW5mbyhcbiAgICAgICAgICB7IG9wZXJhdGlvbl9uYW1lOiAnSHR0cFNlcnZlcjJTdG9wJyB9LFxuICAgICAgICAgICdIVFRQIHNlcnZlciAyIGNsb3NlZC4nXG4gICAgICAgICk7XG4gICAgICAgIC8vIHByb2Nlc3MuZXhpdCgwKSB3aWxsIGJlIGhhbmRsZWQgYnkgT3BlblRlbGVtZXRyeSBTREsncyBzaHV0ZG93biBob29rcyBpZiBpdCdzIHJlZ2lzdGVyZWQgZm9yIHRoZSBzaWduYWxcbiAgICAgIH0pO1xuICAgIH0pO1xuICB9O1xuXG4gIC8vIFNJR0lOVCBhbmQgU0lHVEVSTSBhcmUgaGFuZGxlZCBieSBPcGVuVGVsZW1ldHJ5IFNESydzIHNodXRkb3duIGhvb2tzIGluIG9wZW50ZWxlbWV0cnkuanNcbiAgLy8gSWYgYWRkaXRpb25hbCBjbGVhbnVwIHNwZWNpZmljIHRvIHRoaXMgc2VydmVyIGlzIG5lZWRlZCBiZXlvbmQgd2hhdCBPVGVsIFNESyBkb2VzLFxuICAvLyBpdCBjYW4gYmUgYWRkZWQgaGVyZSwgYnV0IGVuc3VyZSBpdCBkb2Vzbid0IGNvbmZsaWN0IHdpdGggU0RLJ3MgcHJvY2Vzcy5leGl0KCkuXG4gIC8vIEZvciBpbnN0YW5jZSwgT1RlbCBTREsgY2FsbHMgcHJvY2Vzcy5leGl0KDApIGFmdGVyIGl0cyBzaHV0ZG93bi5cbn07XG5cbm1haW4oKS5jYXRjaCgoZXJyb3IpID0+IHtcbiAgbG9nZ2VyLmZhdGFsKFxuICAgIHtcbiAgICAgIG9wZXJhdGlvbl9uYW1lOiAnTWFpbkV4ZWN1dGlvbkVycm9yJyxcbiAgICAgIGVycm9yX21lc3NhZ2U6IGVycm9yLm1lc3NhZ2UsXG4gICAgICBzdGFja190cmFjZTogZXJyb3Iuc3RhY2ssXG4gICAgfSxcbiAgICAnRmF0YWwgZXJyb3IgZHVyaW5nIG1haW4gZXhlY3V0aW9uLCBleGl0aW5nLidcbiAgKTtcbiAgcHJvY2Vzcy5leGl0KDEpO1xufSk7XG4iXX0=