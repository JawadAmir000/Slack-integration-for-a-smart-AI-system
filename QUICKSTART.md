# 🚀 Quick Start Guide

Your Slack Integration app is ready to run! Follow these steps to get started.

## ✅ Prerequisites Checked
- ✅ Slack App credentials configured
- ✅ Django project structure created
- ✅ Environment variables set

## 🏃‍♂️ Quick Setup (3 steps)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup Database
```bash
python setup.py
```
*This will run migrations, test configuration, and collect static files*

### 3. Start the Server
```bash
python manage.py runserver
```

## 🌐 Access Your App

- **Home Page**: http://localhost:8000/
- **Dashboard**: http://localhost:8000/dashboard/
- **Admin Panel**: http://localhost:8000/admin/

## 🔧 Slack App Configuration

Make sure your Slack app has this **Redirect URL**:
```
http://localhost:8000/api/slack/auth/callback/
```

### Required OAuth Scopes
Your Slack app needs these **Bot Token Scopes**:
- `channels:read` - View basic information about public channels
- `channels:write` - Manage public channels  
- `chat:write` - Send messages as the app
- `chat:write.customize` - Send messages with custom appearance
- `chat:write.public` - Send messages to any channel
- `files:read` - View files shared in channels
- `files:write` - Upload, edit, and delete files
- `reactions:read` - View emoji reactions
- `reactions:write` - Add emoji reactions
- `users:read` - View people in workspace

## 🎯 Testing the Integration

1. **Open**: http://localhost:8000/
2. **Login**: Create an admin user or use existing credentials
3. **Connect**: Click "Connect to Slack" button
4. **Authorize**: Complete OAuth flow in popup window
5. **Use**: Go to Dashboard to send messages, upload files, etc.

## 📋 Available Features

### ✅ What You Can Do
- ✅ **OAuth Connection**: Secure Slack workspace connection
- ✅ **Send Messages**: Post messages to any channel
- ✅ **Upload Files**: Share files with channels  
- ✅ **Manage Channels**: Create, join, and list channels
- ✅ **Add Reactions**: React to messages with emojis
- ✅ **User Info**: Get authenticated user details
- ✅ **Multi-Workspace**: Connect multiple Slack workspaces

### 🚧 Current Limitations (2025 Slack API)
- 🚧 **Rate Limits**: 1 message per second per channel
- 🚧 **History Access**: Limited for non-Marketplace apps
- 🚧 **Bulk Operations**: Restricted bulk data access

## 🛠️ API Endpoints

All API endpoints are available at `/api/slack/`:

- `GET /api/slack/auth/initiate/` - Start OAuth
- `POST /api/slack/auth/callback/` - Handle OAuth callback
- `GET /api/slack/workspaces/` - List workspaces
- `GET /api/slack/channels/` - List channels
- `POST /api/slack/messages/send/` - Send message
- `POST /api/slack/files/upload/` - Upload file

## 🔍 Troubleshooting

### Common Issues

**"OAuth failed"**
- Check Slack app redirect URL matches exactly
- Verify Client ID and Client Secret in .env

**"No Slack integration found"**  
- Complete OAuth flow first
- Check user is logged into Django admin

**"Channel not found"**
- Ensure bot is added to the channel
- Use channel ID instead of name

**Database errors**
- Run: `python manage.py migrate`
- Check database permissions

## 📞 Need Help?

- Check the full `README.md` for detailed documentation
- Review Django logs for error details  
- Verify Slack app configuration in developer portal
- Test API endpoints individually using Django admin or Postman

## 🎉 You're Ready!

Your Slack integration is now fully functional. Start by connecting your first workspace and exploring the features!