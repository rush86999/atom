# Team Chat & Real-time Collaboration

## Quick Start

### 1. Start Backend
```bash
cd backend
uvicorn main_api_app:app --port 5061
```

### 2. Initialize Database
```bash
cd backend
python scripts/init_db.py
```

### 3. Access the Application
- Login/Register: `http://localhost:3000/login`
- Team Chat: `http://localhost:3000/team-chat`

## Features

### ✨ Real-time Messaging
- Instant message delivery via WebSockets
- Auto-scroll to latest messages
- Typing indicators (coming soon)

### 👥 Team Collaboration
- Multiple teams per workspace
- Team selection sidebar
- Member presence (coming soon)

### 🎯 Context-Aware Chat
Embed chat anywhere in your app:
```tsx
<TeamChatPanel 
  teamId="team-123"
  contextType="task"      // 'task' | 'workflow' | 'general'
  contextId="task-456"    // ID of the related item
/>
```

## Architecture

### Authentication Flow
1. User registers/logs in via `/api/auth/register` or `/api/auth/login`
2. JWT token stored in `localStorage`
3. WebSocket connection uses token: `ws://localhost:5061/ws?token={jwt}`

### Message Flow
1. User types message in `TeamChatPanel`
2. POST to `/api/teams/{team_id}/messages`
3. Backend broadcasts to `team:{team_id}` channel
4. All connected team members receive update instantly

### Channel System
- `user:{user_id}` - Personal notifications
- `team:{team_id}` - Team collaboration
- `workspace:{workspace_id}` - Organization-wide updates

## API Endpoints

### Authentication
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Login (OAuth2 password flow)

### Team Messaging
- `POST /api/teams/{team_id}/messages` - Send message
- `GET /api/teams/{team_id}/messages` - Get message history
  - Query params: `context_type`, `context_id`, `limit`

### WebSocket
- `GET /ws?token={jwt}` - Connect to real-time stream

## Environment Variables

Add to `.env`:
```bash
DATABASE_URL=sqlite:///./atom.db
SECRET_KEY=your-secret-key-here
```

## Development Tips

### Testing WebSocket Connection
```javascript
const token = localStorage.getItem('auth_token');
const ws = new WebSocket(`ws://localhost:5061/ws?token=${token}`);

ws.onopen = () => {
  // Subscribe to a channel
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'team:your-team-id'
  }));
};

ws.onmessage = (event) => {
  console.log('Received:', JSON.parse(event.data));
};
```

### Creating Teams
Currently teams must be created via backend API or database directly. UI for team creation is coming soon.

## Troubleshooting

### "Connection refused" error
- Ensure backend is running on correct port (5061)
- Check DATABASE_URL in .env

### Messages not appearing
- Verify WebSocket connection in browser DevTools (Network tab)
- Check that user is member of the team
- Ensure token is valid (not expired)

### "No teams" message
- Create a workspace and team via backend API
- Assign user to team using `/api/enterprise/teams/{team_id}/users/{user_id}`
