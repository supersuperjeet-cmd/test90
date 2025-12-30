# Jeet 💙 - Easy Render Deployment Guide (For Beginners)

Hello! I've made this guide super simple so you can get Jeet up and running on Render without any mistakes. Just follow these steps one by one.

## 1. Get Your "Ingredients" (Environment Variables)
Before you start, make sure you have these 5 things ready. You will need to paste them into Render later.

1.  **`GROQ_API_KEY`**: Get this from [Groq Console](https://console.groq.com/). This is Jeet's brain.
2.  **`DATABASE_URL`**: Create a free PostgreSQL database on [Neon.tech](https://neon.tech/) or [Render](https://render.com/). Copy the "Connection String".
3.  **`OWNER_ID`**: Your Telegram User ID. You can get this by messaging [@userinfobot](https://t.me/userinfobot) on Telegram.
4.  **`TG_TOKEN`**: Your Bot Token from [@BotFather](https://t.me/BotFather).
5.  **`WEB_PASSWORD`**: Any password you want to use to log into your Jeet website (e.g., `loveu123`).

---

## 2. Prepare Your Code
1.  **GitHub**: Make sure all these files are in your GitHub repository:
    *   `main.py` (The heart of Jeet)
    *   `requirements.txt` (The list of things Jeet needs to run)
    *   `Procfile` (Tells Render how to start the app)
    *   `templates/` folder (The website look)
    *   `static/` folder (The music and styles)

---

## 3. Deploy to Render 🚀
1.  Go to [Render.com](https://render.com/) and log in.
2.  Click **"New +"** and select **"Web Service"**.
3.  Connect your GitHub repository.
4.  **Settings**:
    *   **Name**: `jeet-bot` (or anything you like)
    *   **Region**: Pick the one closest to you (e.g., Singapore or US East)
    *   **Branch**: `main`
    *   **Root Directory**: (Leave blank)
    *   **Runtime**: `Python 3`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `gunicorn main:app`
5.  **Environment Variables**:
    *   Click **"Advanced"** -> **"Add Environment Variable"**.
    *   Add all 5 items from Step 1 here.
6.  Click **"Create Web Service"**.

---

## 4. Final Step: Connect to Telegram
Once Render says "Live", copy your website URL (e.g., `https://jeet-bot.onrender.com`).
Go to your Telegram Bot and send a message. If you set up everything correctly, Jeet will reply!

### 💡 Pro Tips for Noobs:
*   **Database**: If you use Neon.tech, make sure the URL starts with `postgres://` (not `postgresql://`).
*   **Wait**: Render can take 2-5 minutes to build your app for the first time. Be patient!
*   **Logs**: If something goes wrong, click the "Logs" tab in Render to see what Jeet is "complaining" about.

You did it! Jeet is now live and waiting for you! 💙🌸
