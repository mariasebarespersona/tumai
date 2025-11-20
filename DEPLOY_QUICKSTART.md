# Quick Start: Deploy to Vercel

Get your RAMA AI app running on Vercel in 5 minutes!

## Prerequisites

- [Vercel account](https://vercel.com/signup) (free)
- [Render account](https://render.com/register) (free) or alternative backend host
- [Supabase account](https://supabase.com) (free)
- OpenAI API key

---

## 🚀 5-Minute Deployment

### Step 1: Deploy Backend (2 minutes)

Click this button to deploy the FastAPI backend to Render:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/mariasebarespersona/tumai)

When prompted, add these **required** environment variables:
```
OPENAI_API_KEY=sk-...your-key...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres.xxx:xxx@aws-0-region.pooler.supabase.com:6543/postgres
ALLOW_ALL_CORS=1
```

**Copy the backend URL** after deployment (e.g., `https://rama-api-xxx.onrender.com`)

---

### Step 2: Deploy Frontend to Vercel (2 minutes)

#### Option A: One-Click Deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/mariasebarespersona/tumai&env=NEXT_PUBLIC_API_URL&envDescription=Backend%20API%20URL%20from%20Step%201&project-name=rama-agentic-ai&repository-name=rama-agentic-ai&root-directory=web)

When prompted:
1. **Repository name**: `rama-agentic-ai` (or your choice)
2. **Root Directory**: `web`
3. **Environment Variable**:
   - `NEXT_PUBLIC_API_URL` = your backend URL from Step 1

#### Option B: Import via Vercel Dashboard

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repository
3. Configure:
   - **Root Directory**: `web`
   - **Framework**: Next.js (auto-detected)
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = backend URL from Step 1
5. Click **Deploy**

---

### Step 3: Test Your Deployment (1 minute)

1. Visit your Vercel URL: `https://your-project.vercel.app`
2. You should see the RAMA AI chat interface
3. Test the connection:
   - Type: "Show me the list of properties"
   - You should get a response (empty list if no properties yet)
4. Create a test property:
   - Type: "Create a property named Test House at 123 Main St"

**Done! ✅** Your app is live.

---

## 🔧 Configuration (Optional)

### Update Backend CORS for Production

Once frontend is deployed, update backend for security:

1. Go to Render Dashboard → Your Backend Service → Environment
2. Replace `ALLOW_ALL_CORS=1` with:
   ```
   WEB_BASE=https://your-project.vercel.app
   ```
3. Restart service

### Add Custom Domain

**Frontend (Vercel)**:
1. Vercel Dashboard → Your Project → Settings → Domains
2. Add domain (e.g., `app.yourdomain.com`)
3. Follow DNS instructions

**Backend (Render)**:
1. Render Dashboard → Your Service → Settings → Custom Domain
2. Add domain (e.g., `api.yourdomain.com`)
3. Update `NEXT_PUBLIC_API_URL` in Vercel to new backend domain

---

## 📊 Monitor Your Deployment

### Vercel
- **Dashboard**: [vercel.com/dashboard](https://vercel.com/dashboard)
- **Logs**: Your Project → Deployments → View Function Logs
- **Analytics**: Your Project → Analytics (Pro plan)

### Render
- **Dashboard**: [dashboard.render.com](https://dashboard.render.com/)
- **Logs**: Your Service → Logs (real-time)
- **Metrics**: Your Service → Metrics (CPU, memory, requests)

### Logfire (Optional - Advanced)
1. Sign up: [logfire.pydantic.dev](https://logfire.pydantic.dev)
2. Create project and copy token
3. Add to backend env vars:
   ```
   LOGFIRE_TOKEN=your_token_here
   ```
4. View LLM calls, traces, and errors in real-time

---

## 🐛 Troubleshooting

### "Cannot connect to backend"
- Check backend is running: Visit backend URL in browser (should show FastAPI docs)
- Verify `NEXT_PUBLIC_API_URL` in Vercel environment variables
- Check CORS settings on backend

### "Database connection error"
- Verify `DATABASE_URL` is correct in backend env vars
- Check Supabase is running (dashboard.supabase.com)
- Run migrations in Supabase SQL Editor (see `/migrations` folder)

### "Build failed on Vercel"
- Check build logs in Vercel Dashboard → Deployments
- Verify `web/` directory contains valid Next.js app
- Try manual deploy: `cd web && vercel --prod`

### Backend sleeps after inactivity (Render Free Tier)
- Expected behavior on free tier (sleeps after 15 min)
- First request after sleep takes ~30 seconds to wake up
- Upgrade to Render Starter ($7/mo) for always-on
- Or use cron job to ping every 10 minutes

---

## 💰 Costs

**Free Tier** (Good for development/MVP):
- Vercel: Free (Hobby plan)
- Render: Free (with sleep after 15min inactive)
- Supabase: Free (500MB DB, 1GB storage)
- OpenAI: ~$10-50/month (pay-as-you-go)

**Production** (Recommended):
- Vercel Pro: $20/month
- Render Starter: $7-14/month
- Supabase Pro: $25/month
- OpenAI: $50-200/month

---

## 📚 Full Documentation

For detailed guides:
- **Complete Deployment Guide**: [docs/DEPLOY_VERCEL.md](docs/DEPLOY_VERCEL.md)
- **Operational Guide**: [docs/OPS.md](docs/OPS.md)
- **Feature Documentation**: [README.md](README.md)

---

## 🆘 Need Help?

- Check the [full deployment guide](docs/DEPLOY_VERCEL.md)
- Review Vercel logs and Render logs
- Verify all environment variables are set correctly
- Test backend directly (visit backend URL `/docs` for FastAPI Swagger)

---

**Questions? Issues?** Open an issue on GitHub or check the documentation.

**Happy deploying! 🎉**

