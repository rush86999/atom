import winston from 'winston';
export declare const LOG_LEVEL: string;
export declare const logger: winston.Logger;
/**
 * Logger for non 5xx, non suspicious requests e.g. 200, 204, 400...
 * - Requests are logged as info, expect for /healthz et and /change-env which are logged as debug
 * - No additional meta is logged
 * */
export declare const httpLogger: import("express").Handler;
export declare const uncaughtErrorLogger: import("express").ErrorRequestHandler<import("express-serve-static-core").ParamsDictionary, any, any, import("qs").ParsedQs, Record<string, any>>;
