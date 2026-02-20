# FFmpeg Creative Tools Setup Guide

This guide explains how to set up and use the FFmpeg creative tools in Atom Personal Edition.

## Quick Start

1. **Start the Personal Edition**:
   ```bash
   docker-compose -f docker-compose-personal.yml up -d
   ```

2. **Verify FFmpeg is installed**:
   ```bash
   docker exec atom-personal-backend which ffmpeg
   ```
   Expected output: `/usr/bin/ffmpeg`

3. **Create media directories**:
   ```bash
   mkdir -p data/media/input data/media/output data/exports
   ```

## Directory Structure

```
data/
├── media/
│   ├── input/     # Source video/audio files for processing
│   └── output/    # Processed video/audio files
└── exports/       # Extracted audio, normalized audio, thumbnails
```

## API Endpoints

### Video Operations

#### Trim Video
```bash
curl -X POST http://localhost:8000/creative/video/trim \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/media/input/screencast.mp4",
    "output_path": "/app/data/media/output/screencast_trimmed.mp4",
    "start_time": "00:00:10",
    "duration": "00:02:00"
  }'
```

#### Convert Format
```bash
curl -X POST http://localhost:8000/creative/video/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/media/input/video.mov",
    "output_path": "/app/data/media/output/video.mp4",
    "format": "mp4",
    "quality": "medium"
  }'
```

#### Generate Thumbnail
```bash
curl -X POST http://localhost:8000/creative/video/thumbnail \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/app/data/media/input/video.mp4",
    "thumbnail_path": "/app/data/exports/thumbnail.jpg",
    "timestamp": "00:00:30"
  }'
```

### Audio Operations

#### Extract Audio
```bash
curl -X POST http://localhost:8000/creative/audio/extract \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/app/data/media/input/meeting.mp4",
    "audio_path": "/app/data/exports/meeting_audio.mp3",
    "format": "mp3"
  }'
```

#### Normalize Audio
```bash
curl -X POST http://localhost:8000/creative/audio/normalize \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/exports/audio.mp3",
    "output_path": "/app/data/exports/audio_normalized.mp3",
    "target_lufs": -16.0
  }'
```

### Job Management

#### Check Job Status
```bash
curl http://localhost:8000/creative/jobs/{job_id}
```

Response:
```json
{
  "job_id": "abc123",
  "status": "completed",
  "progress": 100,
  "operation": "trim_video",
  "input_path": "/app/data/media/input/video.mp4",
  "output_path": "/app/data/media/output/video_trimmed.mp4",
  "created_at": "2026-02-20T19:00:00Z",
  "started_at": "2026-02-20T19:00:01Z",
  "completed_at": "2026-02-20T19:00:15Z",
  "error": null,
  "result": {
    "success": true,
    "output_path": "/app/data/media/output/video_trimmed.mp4"
  }
}
```

#### List User Jobs
```bash
curl "http://localhost:8000/creative/jobs?status=completed&limit=10"
```

### File Management

#### List Files
```bash
curl "http://localhost:8000/creative/files?directory=/app/data/media/input"
```

#### Delete File
```bash
curl -X DELETE http://localhost:8000/creative/files//app/data/media/output/old_video.mp4
```

## Security

- **AUTONOMOUS maturity required**: Only AUTONOMOUS agents can use FFmpeg tools
- **Path validation**: All file paths must be within allowed directories (`/app/data/media`, `/app/data/exports`)
- **Audit trail**: All operations are logged in the `ffmpeg_job` database table

## Common Use Cases

### 1. Trim Screencast
"Trim the screencast from 5 minutes to 10 minutes"
```bash
# Agent would execute:
curl -X POST http://localhost:8000/creative/video/trim \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/media/input/screencast.mp4",
    "output_path": "/app/data/media/output/screencast_5-10min.mp4",
    "start_time": "00:05:00",
    "duration": "00:05:00"
  }'
```

### 2. Extract Meeting Audio
"Extract the audio from the recorded meeting"
```bash
curl -X POST http://localhost:8000/creative/audio/extract \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "/app/data/media/input/meeting_recording.mp4",
    "audio_path": "/app/data/exports/meeting_audio.mp3",
    "format": "mp3"
  }'
```

### 3. Generate Video Thumbnails
"Create thumbnails at 30 seconds for each video"
```bash
for video in /app/data/media/input/*.mp4; do
  filename=$(basename "$video" .mp4)
  curl -X POST http://localhost:8000/creative/video/thumbnail \
    -H "Content-Type: application/json" \
    -d "{
      \"video_path\": \"$video\",
      \"thumbnail_path\": \"/app/data/exports/${filename}_thumb.jpg\",
      \"timestamp\": \"00:00:30\"
    }"
done
```

### 4. Normalize Audio Volume
"Normalize the audio volume to -16 LUFS"
```bash
curl -X POST http://localhost:8000/creative/audio/normalize \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "/app/data/exports/audio.mp3",
    "output_path": "/app/data/exports/audio_normalized.mp3",
    "target_lufs": -16.0
  }'
```

## Troubleshooting

### FFmpeg Not Found
```bash
# Verify FFmpeg is installed in the container
docker exec atom-personal-backend which ffmpeg

# If not found, rebuild the container
docker-compose -f docker-compose-personal.yml up -d --build
```

### Path Validation Errors
Ensure file paths are within allowed directories:
- `/app/data/media/input`
- `/app/data/media/output`
- `/app/data/exports`

### Job Timeout
FFmpeg operations have a 5-minute timeout. For longer operations:
1. Process shorter segments
2. Use format conversion with codec copy (faster)
3. Check disk space

## Performance Tips

- **Use codec copy for trimming**: Faster than re-encoding
- **Generate thumbnails in batch**: Process multiple videos in parallel
- **Lower quality for preview**: Use `quality: "low"` for faster processing

## Next Steps

- Integrate with agent workflow automation
- Add video compression for large files
- Support batch processing workflows
- Add watermarking capabilities
