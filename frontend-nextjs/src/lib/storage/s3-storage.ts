import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3'
import { getSignedUrl } from '@aws-sdk/s3-request-presigner'

export class StorageService {
    private client: S3Client
    private bucket: string

    constructor() {
        const region = process.env.STORAGE_AWS_REGION || process.env.AWS_S3_REGION || 'us-east-1'
        const accessKeyId = process.env.STORAGE_AWS_ACCESS_KEY_ID || process.env.AWS_ACCESS_KEY_ID
        const secretAccessKey = process.env.STORAGE_AWS_SECRET_ACCESS_KEY || process.env.AWS_SECRET_ACCESS_KEY
        // Support both standard AWS_ENDPOINT_URL (boto3/Fly compatible) and S3_ENDPOINT
        const endpoint = process.env.S3_ENDPOINT || process.env.AWS_ENDPOINT_URL

        if (!accessKeyId || !secretAccessKey) {
            console.warn('[StorageService] Missing AWS credentials. S3 uploads will fail.')
        }

        this.bucket = process.env.AWS_S3_BUCKET || ''
        if (!this.bucket) {
            console.warn('[StorageService] Missing AWS_S3_BUCKET. S3 uploads will fail.')
        }

        this.client = new S3Client({
            region,
            endpoint, // undefined is fine for standard AWS
            credentials: {
                accessKeyId: accessKeyId || '',
                secretAccessKey: secretAccessKey || '',
            },
            forcePathStyle: !!endpoint, // Necessary for MinIO/some S3 compatible services
        })
    }

    /**
     * Generate a presigned URL for uploading a file to S3
     * @param key The S3 key (path) where the file will be stored
     * @param contentType MIME type of the file
     * @param expiresInSeconds Duration before URL expires (default 300s / 5m)
     */
    async getPresignedPutUrl(key: string, contentType: string, expiresInSeconds: number = 300): Promise<string> {
        if (!this.bucket) throw new Error('Storage bucket not configured')

        const command = new PutObjectCommand({
            Bucket: this.bucket,
            Key: key,
            ContentType: contentType,
        })

        return await getSignedUrl(this.client, command, { expiresIn: expiresInSeconds })
    }

    /**
     * Generate a presigned URL for reading a file (if bucket is private)
     */
    /**
     * Generate a presigned URL for reading a file (if bucket is private)
     */
    async getPresignedGetUrl(key: string, expiresInSeconds: number = 3600): Promise<string> {
        if (!this.bucket) throw new Error('Storage bucket not configured')

        // Remove s3://bucket/ prefix if present
        const cleanKey = key.replace(`s3://${this.bucket}/`, '')

        const command = new GetObjectCommand({
            Bucket: this.bucket,
            Key: cleanKey,
        })

        return await getSignedUrl(this.client, command, { expiresIn: expiresInSeconds })
    }
}

export const storageService = new StorageService()
