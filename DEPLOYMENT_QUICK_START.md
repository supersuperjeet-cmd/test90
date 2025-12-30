# Deploy to Render (2 minutes setup)

## Step 1: Push Code to GitHub
```bash
git add .
git commit -m "Jeet AI ready for deployment"
git push origin main
```

## Step 2: Create Web Service on Render
1. Go to https://render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub
4. Select your repo

## Step 3: Add Environment Variables (copy-paste these)
```
OWNER_ID=your_user_id
GROQ_API_KEY=your_groq_api_key
WEB_PASSWORD=love u
SESSION_SECRET=random_string_123
DATABASE_URL=postgresql://user:pass@host:5432/db
```

That's it! Render will:
- Read `Procfile` (gunicorn)
- Install from `requirements.txt`
- Start on port 5000
- Auto-restart on crashes

## Features Ready
✅ AI Chat with Groq/Gemini/OpenAI
✅ Memory system (safe from deletion)
✅ Delete messages by time range (all/7days/1day/session)
✅ Admin dashboard
✅ Music library
✅ Diary notes
✅ PostgreSQL backup

## Admin Access
- Password: `admin`

## User Access  
- Password: `love u` (or your WEB_PASSWORD)

## Notes
- No database needed initially (uses TinyDB)
- PostgreSQL optional (set DATABASE_URL for persistence)
- All data backed up in memory.json
- Very simple - no complex setup needed

Done! Your app will be live in 2 minutes.
