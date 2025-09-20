# Using ngrok for HTTPS Tunnel

## Step 1: Install ngrok
1. Go to https://ngrok.com/
2. Sign up for a free account
3. Download ngrok for Windows
4. Extract it to a folder (like C:\ngrok\)

## Step 2: Setup ngrok
1. Open command prompt
2. Navigate to ngrok folder: `cd C:\ngrok`
3. Authenticate: `ngrok config add-authtoken YOUR_TOKEN` (get token from ngrok dashboard)

## Step 3: Start tunnel
1. Run: `ngrok http 8000`
2. Copy the HTTPS URL (something like: https://abc123.ngrok-free.app)
3. Use this URL + "/api/slack/auth/callback" as your Slack redirect URL

## Step 4: Update your .env file
Replace localhost with the ngrok URL in SLACK_REDIRECT_URI