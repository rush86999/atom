# Desktop Backend Integration

## Overview

This directory contains the Python backend service for the Atom desktop application. It provides the same backend functionality as the NextJS frontend, including voice processing, audio handling, wake word detection, and all API services.

## Architecture

The desktop app uses a hybrid architecture:
- **Tauri Frontend**: Rust-based desktop UI
- **Python Backend**: Flask-based API service running locally
- **Shared Backend Code**: Reuses the same Python modules as the web backend

## Features

### ✅ Voice & Audio Processing
- Wake word detection using OpenWakeWord
- Real-time audio processing
- Voice command transcription
- Audio stream handling

### ✅ Backend Services
- Meeting transcript search (LanceDB integration)
- Audio processing utilities
- API endpoints matching web backend functionality
- Secure storage and settings management

### ✅ Integration
- RESTful API endpoints
- WebSocket support for real-time communication
- Health monitoring and status endpoints
- Automatic dependency management

## Quick Start

### 1. Install Dependencies
```bash
cd desktop/tauri/src-tauri/python-backend
pip install -r requirements.txt
```

### 2. Start the Backend Service
```bash
# Method 1: Using the startup script
python start_backend.py start

# Method 2: Direct execution
python main.py
```

### 3. Verify Service Health
```bash
curl http://localhost:8083/health
```

## API Endpoints

### Wake Word Detection
- `POST /api/wake-word/start` - Start wake word listening
- `POST /api/wake-word/stop` - Stop wake word listening  
- `GET /api/wake-word/status` - Get detection status

### Audio Processing
- `POST /api/audio/process` - Process audio commands
- `POST /api/voice/transcribe` - Transcribe audio to text

### Search & Data
- `POST /api/search/meetings` - Search meeting transcripts
- Various other endpoints matching web backend functionality

## File Structure

```
python-backend/
├── main.py                 # Main Flask application
├── start_backend.py        # Service manager and startup script
├── requirements.txt        # Python dependencies
├── atom_wake_word.onnx     # Wake word model (copied during sync)
└── backend/                # Shared backend code (synced from main project)
    └── python-api-service/
        ├── _utils/         # Shared utilities
        ├── wake_word_detector/  # Wake word detection
        └── ...             # Other service modules
```

## Synchronization with Main Backend

The desktop backend stays in sync with the main backend using the sync script:

```bash
# Run from project root
./scripts/sync-desktop-backend.sh
```

This script:
- Copies backend Python modules
- Updates requirements
- Ensures wake word model is available
- Maintains consistency with web backend

## Protection Mechanisms

The desktop backend is protected from accidental deletion:

```bash
# Check protection status
./scripts/protect-desktop-backend.sh --delete /path/to/file

# Force operation (not recommended)
./scripts/protect-desktop-backend.sh --delete --force /path/to/file
```

## Development

### Adding New Endpoints
1. Add route handler in `main.py`
2. Import shared functionality from backend modules
3. Test with local requests
4. Update Tauri Rust backend for frontend integration

### Testing
```bash
# Test wake word detection
curl -X POST http://localhost:8083/api/wake-word/start

# Test audio processing
curl -X POST http://localhost:8083/api/voice/transcribe -H "Content-Type: application/json" -d '{"audio_data": "base64_encoded_audio"}'

# Test meeting search
curl -X POST http://localhost:8083/api/search/meetings -H "Content-Type: application/json" -d '{"query": "project discussion", "user_id": "test_user"}'
```

## Dependencies

Core dependencies include:
- `flask`, `flask-cors` - Web framework
- `pyaudio` - Audio processing
- `openwakeword` - Wake word detection
- `numpy` - Numerical processing
- `lancedb` - Vector search
- `requests` - HTTP client

## Troubleshooting

### Common Issues

1. **Port 8083 already in use**
   ```bash
   # Find and kill process
   lsof -ti:8083 | xargs kill -9
   ```

2. **Missing dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Wake word model not found**
   ```bash
   # Ensure model file exists
   cp ../atom_wake_word.onnx ./
   ```

4. **Import errors**
   ```bash
   # Add project to Python path
   export PYTHONPATH=/path/to/project/root:$PYTHONPATH
   ```

## Monitoring

Logs are available in:
- `desktop-backend.log` - Application logs
- `desktop-backend-startup.log` - Startup process logs
- `logs/desktop-backend-protection.log` - Protection events

## Security Notes

- Service runs on localhost (127.0.0.1) only
- No external network access required
- All sensitive operations require authentication
- Backups created before critical operations

## Performance

The backend is optimized for desktop use:
- Low memory footprint
- Efficient wake word detection
- Local processing minimizes latency
- Automatic resource cleanup

## Support

For issues with the desktop backend:
1. Check logs in `desktop-backend.log`
2. Verify dependencies with `pip list`
3. Test basic functionality with health endpoint
4. Consult main backend documentation for shared modules