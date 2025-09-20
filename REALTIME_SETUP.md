# 🚀 Slack Real-Time Messaging Setup Guide

Your Slack integration now supports **real-time message delivery** using Django Channels and WebSocket connections!

## 📋 What's New

✅ **Real-time message reception** from Slack channels and DMs
✅ **WebSocket consumers** for live message broadcasting
✅ **Slack Events API** integration with webhook validation
✅ **Multi-tenant support** with client-specific configurations
✅ **Redis-backed channel layers** for scalable message broadcasting
✅ **Test client** for development and debugging

---

## 🔧 Setup Requirements

### 1. Install Dependencies
Your `requirements.txt` has been updated with:
```
channels>=4.0.0
channels-redis>=4.1.0
daphne>=4.0.0
```

Install with:
```bash
pip install -r requirements.txt
```

### 2. Redis Server
Start Redis server (required for channel layers):
```bash
# Windows with Redis installed
redis-server

# Or using Docker
docker run -d -p 6379:6379 redis:alpine
```

### 3. Environment Configuration
Add to your `.env` file:
```
REDIS_URL=redis://localhost:6379/0
```

---

## 🎯 How to Use

### Step 1: Configure Slack Events API

1. **Go to your Slack App configuration** at https://api.slack.com/apps
2. **Enable Events API** and set your webhook URL:
   ```
   https://yourdomain.com/api/slack/events/
   ```
   Or for specific clients:
   ```
   https://yourdomain.com/api/slack/events/your-client-id/
   ```

3. **Subscribe to Events**:
   - `message.channels` - Channel messages
   - `message.groups` - Private channel messages
   - `message.im` - Direct messages
   - `message.mpim` - Multi-person direct messages

4. **Save and verify** your webhook endpoint

### Step 2: Start the Server

Use Daphne (ASGI server) instead of Django's development server:
```bash
# Development
daphne -b 0.0.0.0 -p 8000 slack_integration.asgi:application

# Production
daphne -b 0.0.0.0 -p 8000 --proxy-headers slack_integration.asgi:application
```

### Step 3: Test Real-Time Messages

1. **Open the test client**: http://localhost:8000/api/slack/test/
2. **Click "Connect to Messages"**
3. **Send messages in Slack** - you'll see them appear live!

---

## 📡 WebSocket Endpoints

- **Messages**: `ws://localhost:8000/ws/slack/messages/`
- **Notifications**: `ws://localhost:8000/ws/slack/notifications/`

---

## 🧪 Testing

### Manual Test with Management Command
```bash
python manage.py test_realtime --message-type channel_message --count 5

# Options:
# --message-type: channel_message, dm, notification
# --count: Number of test messages
# --channel-id: Channel ID for messages
```

### Test WebSocket Connection
1. Open: http://localhost:8000/api/slack/test/
2. Click "Connect to Messages"
3. Use management command to send test messages
4. Watch messages appear in real-time!

---

## 🔧 Architecture Overview

```
Slack → Events API Webhook → Django View → WebSocket Broadcast → Frontend
```

**Components:**
- **`apps.realtime.views`** - Webhook endpoints for Slack events
- **`apps.realtime.consumers`** - WebSocket consumers for real-time delivery
- **`apps.realtime.events`** - Event processing and message handling
- **`apps.realtime.routing`** - WebSocket URL routing
- **Redis Channel Layers** - Message broadcasting infrastructure

---

## 📝 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/slack/events/` | POST | Slack Events API webhook |
| `/api/slack/events/{client}/` | POST | Client-specific webhook |
| `/api/slack/interactive/` | POST | Interactive components |
| `/api/slack/test/` | GET | WebSocket test client |

---

## 🔍 Message Types Received

**Channel Messages:**
```json
{
  "type": "slack_channel_message",
  "message": {
    "channel_id": "C1234567890",
    "channel_name": "general",
    "text": "Hello world!",
    "user_id": "U1234567890",
    "workspace_name": "My Workspace",
    "timestamp": "1234567890.123456"
  }
}
```

**Direct Messages:**
```json
{
  "type": "slack_dm",
  "message": {
    "text": "Private message",
    "user_id": "U1234567890",
    "is_dm": true,
    "workspace_name": "My Workspace"
  }
}
```

---

## 🛠️ Configuration

### Settings (added to `settings.py`):
```python
# Real-time messaging configuration
REALTIME_SETTINGS = {
    'SLACK_WEBHOOK_VERIFICATION': True,
    'MESSAGE_BROADCAST_ENABLED': True,
    'MAX_MESSAGE_HISTORY': 100,
    'WEBSOCKET_HEARTBEAT_INTERVAL': 30,
}
```

### Redis Configuration:
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [config('REDIS_URL', default='redis://localhost:6379/0')],
        },
    },
}
```

---

## 🔐 Security Features

✅ **Webhook signature verification** using Slack signing secrets
✅ **Request timestamp validation** to prevent replay attacks
✅ **Multi-tenant configuration** with client-specific credentials
✅ **User authentication** for WebSocket connections

---

## 🚀 Next Steps

1. **Set up your Slack App** Events API configuration
2. **Start Redis server** and your Django app with Daphne
3. **Test the connection** with the included test client
4. **Integrate WebSocket client** in your frontend application

---

## 📞 Support

- Test endpoint: http://localhost:8000/api/slack/test/
- Management command: `python manage.py test_realtime --help`
- WebSocket URL: `ws://localhost:8000/ws/slack/messages/`

Your Slack integration is now **real-time enabled**! 🎉