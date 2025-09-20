# Slack Integration Django REST Framework

A comprehensive Django REST Framework application for integrating with Slack API, allowing users to connect their Slack workspaces and interact with channels, messages, files, and more.

## Features

### 🔐 Authentication & OAuth
- Secure Slack OAuth 2.0 integration
- User authentication and token management
- Support for both user and bot tokens
- Automatic token refresh and validation

### 💬 Messaging Capabilities
- Send messages to channels and direct messages
- Rich text formatting and message attachments
- Threaded conversation support
- Message scheduling functionality
- Add emoji reactions to messages

### 🏢 Channel Management
- List all accessible channels
- Create new public and private channels
- Join existing channels
- Channel information and metadata

### 📁 File Operations
- Upload files to Slack channels (using 2025 updated API)
- Support for multiple file types
- File sharing with specific users or channels
- File metadata and permissions management

### 👥 User & Workspace Management
- Access user profile information
- Workspace details and settings
- Multiple workspace support
- User presence and status management

## Technology Stack

- **Backend**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL (with SQLite fallback for development)
- **Task Queue**: Celery with Redis
- **Authentication**: OAuth 2.0 with django-oauth-toolkit
- **API Client**: Slack SDK for Python
- **Frontend**: Bootstrap 5 with vanilla JavaScript

## Project Structure

```
slack_integration/
├── slack_integration/          # Django project settings
├── apps/
│   ├── authentication/        # User authentication
│   ├── core/                  # Core models and views
│   └── slack_api/             # Slack API integration
├── templates/                 # HTML templates
├── requirements.txt           # Python dependencies
├── manage.py                  # Django management script
└── README.md                  # This file
```

## Installation

### Prerequisites

- Python 3.8+
- PostgreSQL (optional, SQLite fallback available)
- Redis (for Celery tasks)
- Slack app with OAuth credentials

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd slack-integration
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Environment Variables**
   Configure the following variables in your `.env` file:
   ```
   SECRET_KEY=your-django-secret-key
   DEBUG=True
   
   # Database (optional, defaults to SQLite)
   DB_NAME=slack_integration
   DB_USER=postgres
   DB_PASSWORD=password
   DB_HOST=localhost
   DB_PORT=5432
   
   # Slack API Configuration
   SLACK_CLIENT_ID=your-slack-client-id
   SLACK_CLIENT_SECRET=your-slack-client-secret
   SLACK_SIGNING_SECRET=your-slack-signing-secret
   SLACK_REDIRECT_URI=http://localhost:8000/api/slack/auth/callback/
   
   # Redis Configuration
   REDIS_URL=redis://localhost:6379/0
   ```

6. **Database Setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

7. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

8. **Start Celery Worker** (Optional, for background tasks)
   ```bash
   celery -A slack_integration worker -l info
   ```

## Slack App Configuration

### Create Slack App

1. Go to [Slack API](https://api.slack.com/apps) and create a new app
2. Choose "From scratch" and select your workspace
3. Note down the **Client ID**, **Client Secret**, and **Signing Secret**

### OAuth & Permissions

Configure the following OAuth scopes:

**Bot Token Scopes:**
- `channels:read` - View basic information about public channels
- `channels:write` - Manage public channels
- `chat:write` - Send messages as the app
- `chat:write.customize` - Send messages with customized username and avatar
- `chat:write.public` - Send messages to channels the app isn't a member of
- `files:read` - View files shared in channels
- `files:write` - Upload, edit, and delete files
- `reactions:read` - View emoji reactions and their associated content
- `reactions:write` - Add and edit emoji reactions
- `users:read` - View people in a workspace

**Redirect URLs:**
- `http://localhost:8000/api/slack/auth/callback/` (development)
- `https://yourdomain.com/api/slack/auth/callback/` (production)

### Event Subscriptions (Optional)

If you want to receive real-time events:
- Enable Event Subscriptions
- Request URL: `https://yourdomain.com/api/slack/events/`
- Subscribe to bot events as needed

## API Endpoints

### Authentication
- `GET /api/slack/auth/initiate/` - Start OAuth flow
- `POST /api/slack/auth/callback/` - Handle OAuth callback

### Workspaces
- `GET /api/slack/workspaces/` - List connected workspaces

### Channels
- `GET /api/slack/channels/` - List all channels
- `GET /api/slack/channels/{workspace_id}/` - List channels for specific workspace
- `POST /api/slack/channels/` - Create new channel
- `POST /api/slack/channels/join/` - Join a channel

### Messages
- `POST /api/slack/messages/send/` - Send message to channel
- `POST /api/slack/messages/reaction/` - Add reaction to message

### Files
- `POST /api/slack/files/upload/` - Upload file to channel

### User
- `GET /api/slack/user/info/` - Get current user information

## Usage Examples

### Send a Message
```javascript
fetch('/api/slack/messages/send/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'Authorization': 'Token your-auth-token'
    },
    body: JSON.stringify({
        channel: 'C1234567890',
        text: 'Hello from Django!'
    })
});
```

### Upload a File
```javascript
const formData = new FormData();
formData.append('channels', 'C1234567890');
formData.append('file', fileInput.files[0]);
formData.append('title', 'My Document');

fetch('/api/slack/files/upload/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrfToken,
        'Authorization': 'Token your-auth-token'
    },
    body: formData
});
```

## Rate Limits & Limitations (2025)

### Important Restrictions
- **Non-Marketplace Apps**: Limited to 1 request per minute for conversation history
- **Message Rate**: Maximum 1 message per second per channel
- **File Upload**: Uses new 2025 API methods for better reliability
- **Bulk Data Access**: Prohibited for non-approved applications

### Best Practices
- Implement proper error handling and retry logic
- Respect rate limits to avoid API blocks
- Cache frequently accessed data locally
- Use webhooks for real-time updates instead of polling

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Security Considerations

- Store tokens securely and encrypted
- Use HTTPS in production
- Implement proper CORS settings
- Regularly rotate API credentials
- Follow OAuth 2.0 security best practices
- Never commit sensitive credentials to version control

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:
- Create an issue in the GitHub repository
- Check the [Slack API documentation](https://api.slack.com/)
- Review Django REST Framework [documentation](https://www.django-rest-framework.org/)

## Changelog

### v1.0.0 (2025)
- Initial release with full Slack OAuth integration
- Complete messaging and file upload functionality
- Channel management capabilities
- User and workspace management
- Comprehensive API documentation
- Bootstrap-based web interface