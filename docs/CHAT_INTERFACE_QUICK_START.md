# ATOM Chat Interface - Quick Start Guide

## 🚀 Overview

The ATOM Chat Interface provides real-time communication capabilities with workflow automation integration. This guide will help you get started quickly with the chat interface components.

## 📋 Prerequisites

- Python 3.8+
- pip3 package manager
- FastAPI and WebSocket libraries

## ⚡ Quick Start

### 1. Deploy Chat Services

```bash
# Make deployment script executable
chmod +x deploy_chat_interface.sh

# Deploy all chat services
./deploy_chat_interface.sh
```

This will:
- Install dependencies
- Start Chat Interface Server (port 8000)
- Start WebSocket Server (port 5060)
- Run health checks
- Execute integration tests

### 2. Verify Deployment

```bash
# Check service health
curl http://localhost:8000/health
curl http://localhost:5060/health

# Test WebSocket connection
python3 -c "import websocket; ws = websocket.create_connection('ws://localhost:5060/ws/test_user'); print('Connected!'); ws.close()"
```

### 3. Start Monitoring

```bash
# Make monitoring script executable
chmod +x monitor_chat_services.sh

# Start continuous monitoring
./monitor_chat_services.sh --continuous
```

## 🎯 Core Components

### Chat Interface Server (Port 8000)
- HTTP API for chat message processing
- Integration with workflow engine
- Context management and conversation history
- AI response generation

### WebSocket Server (Port 5060)
- Real-time bidirectional communication
- Room-based messaging
- Typing indicators
- Connection health monitoring

## 🔧 API Usage Examples

### Send Chat Message (HTTP)

```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, create a task in Asana",
    "user_id": "user_123",
    "message_type": "text",
    "metadata": {"priority": "high"}
  }'
```

### Get User Context

```bash
curl http://localhost:8000/api/v1/chat/users/user_123/context
```

### WebSocket Communication (Python)

```python
import websocket
import json

# Connect to WebSocket
ws = websocket.create_connection('ws://localhost:5060/ws/user_123')

# Join a room
ws.send(json.dumps({
    "type": "join_room",
    "room_id": "general"
}))

# Send chat message
ws.send(json.dumps({
    "type": "chat_message",
    "room_id": "general",
    "message": "Hello everyone!"
}))

# Close connection
ws.close()
```

## 🛠️ Development

### Manual Service Startup

```bash
# Start Chat Interface Server
cd atom/backend
python3 chat_interface_server.py

# Start WebSocket Server (new terminal)
cd atom/backend
python3 websocket_server.py
```

### Run Integration Tests

```bash
# Run comprehensive tests
python3 test_chat_integration.py
```

### Check Logs

```bash
# View chat interface logs
tail -f logs/chat_interface.log

# View WebSocket logs
tail -f logs/websocket_server.log
```

## 🔍 Monitoring & Debugging

### Service Status

```bash
# Check if services are running
./monitor_chat_services.sh --status

# Run single health check
./monitor_chat_services.sh --single
```

### Common Issues

1. **Port Conflicts**: Ensure ports 8000 and 5060 are available
2. **Dependencies**: Run `pip3 install -r backend/requirements.txt`
3. **Permissions**: Make scripts executable with `chmod +x *.sh`

### Performance Testing

```bash
# Test with multiple concurrent users
python3 -c "
import threading
import websocket
def test_user(user_id):
    ws = websocket.create_connection('ws://localhost:5060/ws/' + user_id)
    ws.send('{\"type\": \"ping\"}')
    print(ws.recv())
    ws.close()

threads = [threading.Thread(target=test_user, args=(f'user_{i}',)) for i in range(10)]
[t.start() for t in threads]
[t.join() for t in threads]
"
```

## 📊 Configuration

### Environment Variables

Create `.env` file in backend directory:

```env
CHAT_API_PORT=8000
WEBSOCKET_PORT=5060
DATABASE_URL=postgresql://user:pass@localhost/atom
OPENAI_API_KEY=your_key_here
```

### Service Configuration

Modify ports and settings in:
- `backend/chat_interface_server.py`
- `backend/websocket_server.py`

## 🎨 Frontend Integration

### React Example

```javascript
import { useEffect, useState } from 'react';

function ChatComponent() {
  const [ws, setWs] = useState(null);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    const websocket = new WebSocket('ws://localhost:5060/ws/user_123');
    
    websocket.onopen = () => {
      console.log('WebSocket connected');
      // Join room
      websocket.send(JSON.stringify({
        type: 'join_room',
        room_id: 'general'
      }));
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'chat_message') {
        setMessages(prev => [...prev, data]);
      }
    };

    setWs(websocket);

    return () => websocket.close();
  }, []);

  const sendMessage = (message) => {
    if (ws) {
      ws.send(JSON.stringify({
        type: 'chat_message',
        room_id: 'general',
        message: message
      }));
    }
  };

  return (
    <div>
      {/* Chat UI implementation */}
    </div>
  );
}
```

## 🔒 Security Considerations

- Use HTTPS/WSS in production
- Implement JWT authentication
- Validate user input
- Set up rate limiting
- Enable CORS for your domains

## 📞 Support

### Troubleshooting

1. **Services not starting**: Check Python version and dependencies
2. **Connection refused**: Verify ports and firewall settings
3. **Messages not delivering**: Check WebSocket connection status

### Log Files

- `logs/chat_interface.log` - Chat API logs
- `logs/websocket_server.log` - WebSocket logs
- `logs/monitoring_report_*.json` - Monitoring reports

### Next Steps

After successful deployment:
1. Integrate with your frontend application
2. Configure user authentication
3. Set up production monitoring
4. Implement backup procedures

---

**Need Help?** Check the comprehensive documentation or contact the development team.

*Last Updated: November 8, 2025*