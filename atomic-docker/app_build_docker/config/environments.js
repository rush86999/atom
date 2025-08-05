/**
 * Environment-Specific Configuration Handler
 * Separates local development from cloud-hosted environments
 */

const path = require('path');

// Environment detection
const getEnvironment = () => {
  const nodeEnv = process.env.NODE_ENV || 'development';

  // Check if running in cloud environment
  const isCloudHosted = !!(
    process.env.FLY_APP_NAME ||         // Fly.io
    process.env.RAILWAY_PROJECT_ID ||   // Railway
    process.env.HEROKU_APP_NAME ||      // Heroku
    process.env.K_SERVICE ||            // Google Cloud Run
    process.env.AWS_LAMBDA_FUNCTION_NAME // AWS Lambda
  );

  return {
    isLocal: !isCloudHosted,
    isCloudHosted,
    isDevelopment: nodeEnv === 'development',
    isProduction: nodeEnv === 'production',
    isTest: nodeEnv === 'test',
  };
};

// Database Configuration based on environment
const getDatabaseConfig = () => {
  const { isCloudHosted } = getEnvironment();

  // Cloud-hosted uses DATABASE_URL exclusively
  if (isCloudHosted) {
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl) {
      throw new Error('DATABASE_URL environment variable is required for cloud hosting');
    }

    return {
      url: databaseUrl,
      ssl: {
        rejectUnauthorized: false // Required for managed databases like Supabase, AWS RDS
      },
      pool: {
        min: 1,
        max: 10,
        acquireTimeoutMillis: 60000,
        createTimeoutMillis: 30000,
        destroyTimeoutMillis: 5000,
        idleTimeoutMillis: 10000,
        reapIntervalMillis: 1000,
        createRetryIntervalMillis: 1000,
      }
    };
  }

  // Local development uses individual variables
  return {
    host: process.env.POSTGRES_HOST || 'localhost',
    port: parseInt(process.env.POSTGRES_PORT || '5432'),
    database: process.env.POSTGRES_DB || 'atom_local',
    user: process.env.POSTGRES_USER || process.env.USER,
    password: process.env.POSTGRES_PASSWORD || '',
    ssl: false, // Local development typically doesn't use SSL
    pool: {
      min: 1,
      max: 5,
    }
  };
};

// Redis Configuration
const getRedisConfig = () => {
  const { isCloudHosted } = getEnvironment();

  if (isCloudHosted) {
    return {
      url: process.env.REDIS_URL,
      ssl: false,
      family: 4,
    };
  }

  return {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
    password: process.env.REDIS_PASSWORD,
    ssl: false,
  };
};

// Server Configuration
const getServerConfig = () => {
  const { isCloudHosted, isProduction } = getEnvironment();

  return {
    port: parseInt(process.env.PORT || '3000'),
    baseUrl: isCloudHosted
      ? process.env.APP_URL || process.env.NEXT_PUBLIC_APP_URL
      : `http://localhost:${process.env.PORT || '3000'}`,
    cors: {
      origin: isCloudHosted
        ? [process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, '') || '*']
        : ['http://localhost:3000', 'http://localhost:3001', 'http://localhost:3002', '*'],
      credentials: true,
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      allowedHeaders: '*',
    }
  };
};

// Security Configuration
const getSecurityConfig = () => {
  const { isCloudHosted, isProduction } = getEnvironment();

  return {
    jwt: {
      secret: process.env.JWT_SECRET,
      expiration: '7d',
      algorithm: 'HS256'
    },
    encryption: {
      key: process.env.ENCRYPTION_KEY,
    },
    session: {
      secure: isCloudHosted || isProduction, // HTTPS only
      httpOnly: true,
      sameSite: isCloudHosted ? 'none' : 'lax',
      maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
    }
  };
};

// Storage Configuration
const getStorageConfig = () => {
  const { isCloudHosted } = getEnvironment();

  if (isCloudHosted) {
    return {
      type: 'cloud',
      s3: {
        region: process.env.AWS_REGION || 'us-east-1',
        bucket: process.env.S3_BUCKET_NAME,
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      },
      cdn: process.env.CDN_URL,
    };
  }

  return {
+    type: 'local',
+    uploadPath: path.join(process.cwd(), 'public', 'uploads'),
+    maxFileSize: 10 * 1024 * 1024, // 10MB
+  };
+};
+
+// Database Migration Configuration
+const getMigrationConfig = () => {
+  const { isCloudHosted } = getEnvironment();
+
+  return {
+    directory: path.join(__dirname, '..', 'migrations'),
+    localMigrations: !isCloudHosted,
+    autoMigration: isCloudHosted, // Auto-migrate in cloud
+  };
+};
+
+// Logging Configuration
+const getLoggingConfig = () => {
+  const { isCloudHosted, isProduction } = getEnvironment();
+
+  return {
+    level: isProduction ? 'info' : 'debug',
+    cloudLogging: isCloudHosted,
+    localFile: isCloudHosted ? false : path.join(process.cwd(), 'logs', 'app.log'),
+  };
+};
+
+// Monitoring Configuration
+const getMonitoringConfig = () => {
+  const { isCloudHosted, isProduction } = getEnvironment();
+
+  return {
+    datadog: {
+      apiKey: process.env.DATADOG_API_KEY,
+      service: 'atom-app',
+      env: isProduction ? 'production' : 'development',
+    },
+    sentry: {
+      dsn: process.env.SENTRY_DSN,
+      debug: !isProduction,
+    },
+    newRelic: {
+      licenseKey: process.env.NEW_RELIC_LICENSE_KEY,
+    }
+  };
+};
+
+// Combine all configurations
+const getConfig = () => {
+  return {
+    environment: getEnvironment(),
+    database: getDatabaseConfig(),
+    redis: getRedisConfig(),
+    server: getServerConfig(),
+    security: getSecurityConfig(),
+    storage: getStorageConfig(),
+    migration: getMigrationConfig(),
+    logging: getLoggingConfig(),
+    monitoring: getMonitoringConfig(),
+
+    // Helper methods
+    isLocal: () => getEnvironment().isLocal,
+    isCloudHosted: () => getEnvironment().isCloudHosted,
+    isProduction: () => getEnvironment().isProduction,
+    isDevelopment: () => getEnvironment().isDevelopment,
+
+    // Validation
+    validateCriticalEnvVars: () => {
+      const missing = [];
+      const { isCloudHosted } = getEnvironment();
+
+      // Always required
+      if (!process.env.JWT_SECRET) missing.push('JWT_SECRET');
+      if (!process.env.OPENAI_API_KEY) missing.push('OPENAI_API_KEY');
+
+      if (isCloudHosted) {
+        if (!process.env.DATABASE_URL) missing.push('DATABASE_URL');
+      } else {
+        if (!process.env.POSTGRES_PASSWORD) missing.push('POSTGRES_PASSWORD');
+      }
+
+      return {
+        valid: missing.length === 0,
+        missing,
+      };
+    }
+  };
+};
+
+module.exports = {
+  getConfig,
+  ...getConfig()
+};
