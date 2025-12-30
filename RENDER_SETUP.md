# Deploy to Render

This app is ready for production deployment on Render. It's designed to be simple and work smoothly without issues.

## Quick Setup (3 steps)

### 1. Push to GitHub
```bash
git push origin main
```

### 2. Connect to Render
- Go to https://render.com
- Click "New +" → "Web Service"
- Connect your GitHub repository
- Select this repository

### 3. Configure Environment Variables
In Render dashboard, add these variables:

```
OWNER_ID=<your_user_id>
WEB_PASSWORD=love u
GROQ_API_KEY=<your_groq_key>
DATABASE_URL=<postgres_url>
GEMINI_API_KEY=<optional_gemini_key>
OPENAI_API_KEY=<optional_openai_key>
TG_TOKEN=<optional_telegram_token>
SESSION_SECRET=<any_random_string>
```

That's it! Render will automatically:
- Read `Procfile` (gunicorn command)
- Install from `requirements.txt`
- Start the app on port 5000

## How It Works

- **No Database Needed Initially**: App uses TinyDB locally
- **Add PostgreSQL Later**: Set DATABASE_URL to enable PostgreSQL
- **Memory Persists**: memory.json auto-syncs to database
- **Survives Redeployments**: All data backed up in database

## Notes

- Don't change `Procfile` - it's already Render-optimized
- Don't add complex startup commands
- All settings via environment variables only
- To update AI instructions: Use `/admin/memory/set` endpoint

## Admin Login
- Password: `admin` (change in environment variables)

## User Login
- Password: `love u` (or your WEB_PASSWORD)

That's all! Push to GitHub and Render handles the rest automatically.
