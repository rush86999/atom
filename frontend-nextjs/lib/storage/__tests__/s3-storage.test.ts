/**
 * Tests for S3 Storage Service
 *
 * Tests S3 client initialization, presigned URL generation, and configuration.
 */

import { StorageService } from '@lib/storage/s3-storage';
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

// Mock AWS SDK
jest.mock('@aws-sdk/client-s3');
jest.mock('@aws-sdk/s3-request-presigner');

describe('StorageService', () => {
  let storageService: StorageService;
  let mockS3Client: jest.Mocked<S3Client>;
  let mockGetSignedUrl: jest.MockedFunction<typeof getSignedUrl>;

  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.resetModules();

    // Set up environment variables
    process.env = {
      ...originalEnv,
      STORAGE_AWS_REGION: 'us-east-1',
      STORAGE_AWS_ACCESS_KEY_ID: 'test-access-key',
      STORAGE_AWS_SECRET_ACCESS_KEY: 'test-secret-key',
      AWS_S3_BUCKET: 'test-bucket',
      S3_ENDPOINT: 'https://s3.example.com'
    };

    // Create mock S3Client
    mockS3Client = new S3Client({}) as jest.Mocked<S3Client>;
    (S3Client as jest.MockedClass<typeof S3Client>).mockImplementation(() => mockS3Client);

    // Mock getSignedUrl
    mockGetSignedUrl = getSignedUrl as jest.MockedFunction<typeof getSignedUrl>;
    mockGetSignedUrl.mockResolvedValue('https://presigned-url.example.com');

    // Create service instance
    storageService = new StorageService();
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe('constructor', () => {
    it('should initialize S3Client with environment variables', () => {
      expect(S3Client).toHaveBeenCalledWith({
        region: 'us-east-1',
        endpoint: 'https://s3.example.com',
        credentials: {
          accessKeyId: 'test-access-key',
          secretAccessKey: 'test-secret-key',
        },
        forcePathStyle: true,
      });
    });

    it('should use STORAGE_AWS credentials over AWS credentials', () => {
      process.env.AWS_ACCESS_KEY_ID = 'aws-access-key';
      process.env.AWS_SECRET_ACCESS_KEY = 'aws-secret-key';
      process.env.STORAGE_AWS_ACCESS_KEY_ID = 'storage-access-key';
      process.env.STORAGE_AWS_SECRET_ACCESS_KEY = 'storage-secret-key';

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith({
        region: 'us-east-1',
        endpoint: 'https://s3.example.com',
        credentials: {
          accessKeyId: 'storage-access-key',
          secretAccessKey: 'storage-secret-key',
        },
        forcePathStyle: true,
      });
    });

    it('should fallback to AWS credentials if STORAGE credentials not set', () => {
      delete process.env.STORAGE_AWS_ACCESS_KEY_ID;
      delete process.env.STORAGE_AWS_SECRET_ACCESS_KEY;
      process.env.AWS_ACCESS_KEY_ID = 'aws-access-key';
      process.env.AWS_SECRET_ACCESS_KEY = 'aws-secret-key';

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith({
        region: 'us-east-1',
        endpoint: 'https://s3.example.com',
        credentials: {
          accessKeyId: 'aws-access-key',
          secretAccessKey: 'aws-secret-key',
        },
        forcePathStyle: true,
      });
    });

    it('should use STORAGE_AWS_REGION over AWS_S3_REGION', () => {
      process.env.STORAGE_AWS_REGION = 'us-west-2';
      process.env.AWS_S3_REGION = 'eu-west-1';

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith(
        expect.objectContaining({
          region: 'us-west-2',
        })
      );
    });

    it('should use S3_ENDPOINT over AWS_ENDPOINT_URL', () => {
      process.env.S3_ENDPOINT = 'https://s3.custom.com';
      process.env.AWS_ENDPOINT_URL = 'https://aws-endpoint.com';

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: 'https://s3.custom.com',
        })
      );
    });

    it('should default to us-east-1 if no region specified', () => {
      delete process.env.STORAGE_AWS_REGION;
      delete process.env.AWS_S3_REGION;

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith(
        expect.objectContaining({
          region: 'us-east-1',
        })
      );
    });

    it('should set forcePathStyle to true when endpoint is set', () => {
      process.env.S3_ENDPOINT = 'https://minio.example.com';

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith(
        expect.objectContaining({
          forcePathStyle: true,
        })
      );
    });

    it('should set forcePathStyle to false when endpoint is not set', () => {
      delete process.env.S3_ENDPOINT;
      delete process.env.AWS_ENDPOINT_URL;

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith(
        expect.objectContaining({
          forcePathStyle: false,
        })
      );
    });

    it('should warn when credentials are missing', () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      delete process.env.STORAGE_AWS_ACCESS_KEY_ID;
      delete process.env.STORAGE_AWS_SECRET_ACCESS_KEY;
      delete process.env.AWS_ACCESS_KEY_ID;
      delete process.env.AWS_SECRET_ACCESS_KEY;

      new StorageService();

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        '[StorageService] Missing AWS credentials. S3 uploads will fail.'
      );
      consoleWarnSpy.mockRestore();
    });

    it('should warn when bucket is not configured', () => {
      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
      delete process.env.AWS_S3_BUCKET;

      new StorageService();

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        '[StorageService] Missing AWS_S3_BUCKET. S3 uploads will fail.'
      );
      consoleWarnSpy.mockRestore();
    });
  });

  describe('getPresignedPutUrl', () => {
    it('should generate presigned PUT URL', async () => {
      mockGetSignedUrl.mockResolvedValue('https://presigned-put-url.example.com');

      const url = await storageService.getPresignedPutUrl('test-key.txt', 'text/plain');

      expect(url).toBe('https://presigned-put-url.example.com');
      expect(mockGetSignedUrl).toHaveBeenCalledWith(
        mockS3Client,
        expect.any(PutObjectCommand),
        { expiresIn: 300 }
      );
    });

    it('should use custom expiration time', async () => {
      await storageService.getPresignedPutUrl('test-key.txt', 'text/plain', 600);

      expect(mockGetSignedUrl).toHaveBeenCalledWith(
        mockS3Client,
        expect.any(PutObjectCommand),
        { expiresIn: 600 }
      );
    });

    it('should create PutObjectCommand with correct parameters', async () => {
      await storageService.getPresignedPutUrl('path/to/file.pdf', 'application/pdf');

      expect(PutObjectCommand).toHaveBeenCalledWith({
        Bucket: 'test-bucket',
        Key: 'path/to/file.pdf',
        ContentType: 'application/pdf',
      });
    });

    it('should throw error if bucket not configured', async () => {
      delete process.env.AWS_S3_BUCKET;
      const service = new StorageService();

      await expect(
        service.getPresignedPutUrl('test.txt', 'text/plain')
      ).rejects.toThrow('Storage bucket not configured');
    });

    it('should handle various content types', async () => {
      const contentTypes = [
        'text/plain',
        'application/json',
        'image/png',
        'video/mp4',
        'application/octet-stream'
      ];

      for (const contentType of contentTypes) {
        await storageService.getPresignedPutUrl('test.file', contentType);
        expect(PutObjectCommand).toHaveBeenCalledWith(
          expect.objectContaining({
            ContentType: contentType
          })
        );
      }
    });
  });

  describe('getPresignedGetUrl', () => {
    it('should generate presigned GET URL', async () => {
      mockGetSignedUrl.mockResolvedValue('https://presigned-get-url.example.com');

      const url = await storageService.getPresignedGetUrl('test-key.txt');

      expect(url).toBe('https://presigned-get-url.example.com');
      expect(mockGetSignedUrl).toHaveBeenCalledWith(
        mockS3Client,
        expect.any(GetObjectCommand),
        { expiresIn: 3600 }
      );
    });

    it('should use custom expiration time', async () => {
      await storageService.getPresignedGetUrl('test-key.txt', 1800);

      expect(mockGetSignedUrl).toHaveBeenCalledWith(
        mockS3Client,
        expect.any(GetObjectCommand),
        { expiresIn: 1800 }
      );
    });

    it('should create GetObjectCommand with correct parameters', async () => {
      await storageService.getPresignedGetUrl('path/to/file.pdf');

      expect(GetObjectCommand).toHaveBeenCalledWith({
        Bucket: 'test-bucket',
        Key: 'path/to/file.pdf',
      });
    });

    it('should strip s3://bucket/ prefix from key', async () => {
      await storageService.getPresignedGetUrl('s3://test-bucket/path/to/file.pdf');

      expect(GetObjectCommand).toHaveBeenCalledWith({
        Bucket: 'test-bucket',
        Key: 'path/to/file.pdf',
      });
    });

    it('should throw error if bucket not configured', async () => {
      delete process.env.AWS_S3_BUCKET;
      const service = new StorageService();

      await expect(
        service.getPresignedGetUrl('test.txt')
      ).rejects.toThrow('Storage bucket not configured');
    });

    it('should handle keys without prefix', async () => {
      await storageService.getPresignedGetUrl('simple-file.txt');

      expect(GetObjectCommand).toHaveBeenCalledWith({
        Bucket: 'test-bucket',
        Key: 'simple-file.txt',
      });
    });

    it('should handle nested paths', async () => {
      await storageService.getPresignedGetUrl('folder/subfolder/file.txt');

      expect(GetObjectCommand).toHaveBeenCalledWith({
        Bucket: 'test-bucket',
        Key: 'folder/subfolder/file.txt',
      });
    });
  });

  describe('endpoint handling', () => {
    it('should handle undefined endpoint (standard AWS)', () => {
      delete process.env.S3_ENDPOINT;
      delete process.env.AWS_ENDPOINT_URL;

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: undefined,
          forcePathStyle: false,
        })
      );
    });

    it('should handle S3_ENDPOINT', () => {
      process.env.S3_ENDPOINT = 'https://custom-s3.com';

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: 'https://custom-s3.com',
        })
      );
    });

    it('should handle AWS_ENDPOINT_URL', () => {
      delete process.env.S3_ENDPOINT;
      process.env.AWS_ENDPOINT_URL = 'https://aws-endpoint.com';

      const service = new StorageService();

      expect(S3Client).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: 'https://aws-endpoint.com',
        })
      );
    });
  });

  describe('error handling', () => {
    it('should propagate getSignedUrl errors', async () => {
      mockGetSignedUrl.mockRejectedValue(new Error('AWS SDK Error'));

      await expect(
        storageService.getPresignedPutUrl('test.txt', 'text/plain')
      ).rejects.toThrow('AWS SDK Error');
    });

    it('should handle S3Client initialization errors gracefully', () => {
      (S3Client as jest.MockedClass<typeof S3Client>).mockImplementation(() => {
        throw new Error('S3Client init error');
      });

      expect(() => new StorageService()).toThrow('S3Client init error');
    });
  });

  describe('default expiration times', () => {
    it('should use 300 seconds (5 minutes) for PUT URLs', async () => {
      await storageService.getPresignedPutUrl('test.txt', 'text/plain');

      expect(mockGetSignedUrl).toHaveBeenCalledWith(
        expect.any(Object),
        expect.any(PutObjectCommand),
        { expiresIn: 300 }
      );
    });

    it('should use 3600 seconds (1 hour) for GET URLs', async () => {
      await storageService.getPresignedGetUrl('test.txt');

      expect(mockGetSignedUrl).toHaveBeenCalledWith(
        expect.any(Object),
        expect.any(GetObjectCommand),
        { expiresIn: 3600 }
      );
    });
  });

  describe('singleton export', () => {
    it('should export storageService singleton', () => {
      const { storageService: singleton } = require('../s3-storage');

      expect(singleton).toBeInstanceOf(StorageService);
    });
  });
});
