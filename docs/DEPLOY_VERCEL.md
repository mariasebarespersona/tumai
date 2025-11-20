# Deploying RAMA AI to Vercel

This guide covers deploying the RAMA Agentic AI application with the **frontend on Vercel** and **backend on Render** (or Railway).

## Architecture Overview

- **Frontend**: Next.js → Vercel (serverless, edge-optimized)
- **Backend**: FastAPI + LangGraph → Render/Railway (long-running server required)
- **Database**: Supabase (PostgreSQL + Storage)
- **AI**: OpenAI GPT-4o

> **Why not backend on Vercel?** The FastAPI backend uses stateful LangGraph checkpointer, WebSocket support, and long-running processes that require a traditional server environment, not serverless functions.

---

## Step 1: Deploy Backend to Render

### Option A: Deploy via Render Blueprint (Recommended)

1. **Click Deploy Button**:
   [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/mariasebarespersona/tumai)

2. **Configure Environment Variables** in Render dashboard:
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `SUPABASE_URL` - Your Supabase project URL
   - `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
   - `LOGFIRE_TOKEN` - (Optional) Logfire observability token
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM` - (Optional) Email sending
   - `ALLOW_ALL_CORS=1` - Enable CORS for frontend access

3. **Wait for Deployment**: Render will build and deploy the backend service.

4. **Copy Backend URL**: After deployment, copy the backend URL (e.g., `https://rama-api-xxxx.onrender.com`)

### Option B: Deploy via Render Dashboard Manually

1. Create new **Web Service** on [Render](https://dashboard.render.com/)
2. Connect your GitHub repository
3. Configure:
   - **Name**: `rama-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free or Starter
4. Add environment variables (same as Option A)
5. Deploy

---

## Step 2: Deploy Frontend to Vercel

### Prerequisites

- [Vercel account](https://vercel.com/signup)
- [Vercel CLI](https://vercel.com/cli) (optional, for CLI deployment)

### Option A: Deploy via Vercel Dashboard (Easiest)

1. **Push to GitHub**: Ensure your code is pushed to a GitHub repository

2. **Import Project on Vercel**:
   - Go to [Vercel Dashboard](https://vercel.com/new)
   - Click **"Add New..."** → **"Project"**
   - Import your GitHub repository

3. **Configure Project Settings**:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `web`
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)

4. **Add Environment Variables**:
   Click **"Environment Variables"** and add:
   ```
   Name: NEXT_PUBLIC_API_URL
   Value: https://rama-api-xxxx.onrender.com
   ```
   (Use the backend URL from Step 1)

5. **Deploy**: Click **"Deploy"**

6. **Done!** Your frontend will be live at `https://your-project.vercel.app`

### Option B: Deploy via Vercel CLI

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Login**:
   ```bash
   vercel login
   ```

3. **Navigate to web directory**:
   ```bash
   cd web
   ```

4. **Deploy**:
   ```bash
   vercel
   ```

5. **Follow prompts**:
   - Set up and deploy: `Y`
   - Scope: (your account/team)
   - Link to existing project: `N`
   - Project name: `rama-agentic-ai`
   - Directory: `./` (already in web/)
   - Override settings: `N`

6. **Set Environment Variable**:
   ```bash
   vercel env add NEXT_PUBLIC_API_URL
   # Paste your backend URL when prompted
   ```

7. **Deploy to Production**:
   ```bash
   vercel --prod
   ```

---

## Step 3: Configure Backend CORS

Update your backend environment variables on Render to allow requests from your Vercel domain:

1. Go to Render Dashboard → Your Backend Service → Environment
2. Update or add:
   ```
   WEB_BASE=https://your-project.vercel.app
   ```
3. Remove `ALLOW_ALL_CORS` or set it to `0` for production security

The backend (`app.py`) should automatically configure CORS based on `WEB_BASE`.

---

## Step 4: Verify Deployment

1. **Visit Frontend**: `https://your-project.vercel.app`
2. **Test Connection**: Open browser console, check for API calls to backend
3. **Create a Property**: Try creating a test property to verify backend connection
4. **Check Logs**:
   - Frontend: Vercel Dashboard → Your Project → Deployments → Logs
   - Backend: Render Dashboard → Your Service → Logs

---

## Environment Variables Reference

### Frontend (Vercel)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | ✅ Yes | Backend API base URL | `https://rama-api.onrender.com` |
| `NEXT_PUBLIC_MCP_URL` | ❌ Optional | MCP server for Excel add-in | `http://localhost:4310/jsonrpc` |
| `NEXT_PUBLIC_EXCEL_EMBED_R2B` | ❌ Optional | Excel embed URLs | (leave empty unless using Office embeds) |

### Backend (Render)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | OpenAI API key |
| `SUPABASE_URL` | ✅ Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ Yes | Supabase service role key (not anon key) |
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string for LangGraph checkpointer |
| `LOGFIRE_TOKEN` | ❌ Optional | Logfire observability token |
| `ALLOW_ALL_CORS` | ⚠️ Dev only | Set to `1` for development, remove for production |
| `WEB_BASE` | ⚠️ Production | Frontend URL for CORS (e.g., `https://your-app.vercel.app`) |
| `SMTP_HOST` | ❌ Optional | SMTP server for email sending |
| `SMTP_PORT` | ❌ Optional | SMTP port (default: 587) |
| `SMTP_USER` | ❌ Optional | SMTP username |
| `SMTP_PASS` | ❌ Optional | SMTP password |
| `EMAIL_FROM` | ❌ Optional | From email address |

---

## Custom Domain (Optional)

### Add Custom Domain to Vercel

1. Go to Vercel Dashboard → Your Project → Settings → Domains
2. Add your domain (e.g., `app.yourdomain.com`)
3. Follow DNS configuration instructions
4. Update backend `WEB_BASE` to your custom domain

### Add Custom Domain to Render Backend

1. Go to Render Dashboard → Your Service → Settings → Custom Domains
2. Add your backend domain (e.g., `api.yourdomain.com`)
3. Configure DNS CNAME
4. Update frontend `NEXT_PUBLIC_API_URL` to your custom backend domain

---

## Troubleshooting

### Frontend can't connect to backend

**Symptoms**: Network errors, CORS errors in browser console

**Solutions**:
1. Verify `NEXT_PUBLIC_API_URL` is set correctly in Vercel environment variables
2. Redeploy frontend after changing env vars (Vercel → Deployments → Redeploy)
3. Check backend is running (visit backend URL in browser, should show FastAPI docs)
4. Verify CORS settings on backend (`WEB_BASE` or `ALLOW_ALL_CORS`)

### Backend deployment fails

**Symptoms**: Build errors on Render

**Solutions**:
1. Check Python version (should be 3.10+)
2. Verify `requirements.txt` is up to date
3. Check Render build logs for specific errors
4. Ensure all environment variables are set

### Database connection errors

**Symptoms**: Backend logs show PostgreSQL connection errors

**Solutions**:
1. Verify `DATABASE_URL` is correctly formatted:
   ```
   postgresql://user:password@host:port/database
   ```
2. Check Supabase connection pooler is enabled
3. Verify Supabase service role key has necessary permissions
4. Run migrations in Supabase SQL Editor (see `/migrations` folder)

### Build fails due to memory limits

**Symptoms**: Vercel build exceeds memory/time limits

**Solutions**:
1. Upgrade Vercel plan if needed
2. Check for large dependencies in `web/node_modules`
3. Consider splitting into multiple smaller deployments

---

## Production Checklist

Before going live:

- [ ] Backend deployed and accessible
- [ ] Frontend deployed on Vercel
- [ ] All environment variables configured
- [ ] Database migrations run on Supabase
- [ ] CORS configured properly (no `ALLOW_ALL_CORS` in production)
- [ ] Custom domains configured (optional)
- [ ] SSL/HTTPS enabled (automatic on Vercel and Render)
- [ ] Test full workflow:
  - [ ] Create property
  - [ ] Upload document
  - [ ] Set numbers
  - [ ] Generate summary
  - [ ] Send email
- [ ] Monitor logs for errors (first 24 hours)
- [ ] Set up Logfire dashboard for observability (optional)

---

## Cost Estimate

### Free Tier (Suitable for Development/MVP)

| Service | Plan | Cost | Limits |
|---------|------|------|--------|
| Vercel | Hobby | Free | 100GB bandwidth/month, 100 builds/month |
| Render | Free | Free | 750 hours/month (sleeps after 15min inactive) |
| Supabase | Free | Free | 500MB database, 1GB storage, 2GB bandwidth |
| OpenAI | Pay-as-you-go | ~$10-50/month | Depends on usage (GPT-4o costs ~$0.15/1M tokens) |

**Total**: ~$10-50/month (mostly OpenAI)

### Production Tier

| Service | Plan | Cost |
|---------|------|------|
| Vercel | Pro | $20/month/member |
| Render | Starter | $7/month (512MB RAM) or $14/month (1GB RAM) |
| Supabase | Pro | $25/month (8GB database, 100GB storage) |
| OpenAI | Pay-as-you-go | $50-200/month (depends on usage) |

**Total**: ~$102-259/month

---

## Alternative Backend Hosting Options

If you prefer not to use Render, here are alternatives:

### Railway
- Similar to Render, supports Python
- Generous free tier
- Deploy: `railway up`
- [Railway.app](https://railway.app)

### Fly.io
- Supports long-running Python apps
- Global edge deployment
- Free tier: 3 shared-CPU VMs
- [Fly.io](https://fly.io)

### Google Cloud Run
- Serverless containers
- Pay per request
- Supports WebSockets
- [Cloud Run](https://cloud.google.com/run)

### AWS Elastic Beanstalk
- Traditional PaaS
- More configuration required
- [AWS Elastic Beanstalk](https://aws.amazon.com/elasticbeanstalk/)

---

## Monitoring & Observability

### Logfire (Recommended)

The app is already instrumented with Logfire. To enable:

1. Sign up at [logfire.pydantic.dev](https://logfire.pydantic.dev)
2. Create a project
3. Copy your token
4. Add to backend environment variables:
   ```
   LOGFIRE_TOKEN=your_token_here
   ```
5. View real-time logs, traces, and LLM calls in Logfire dashboard

### Vercel Analytics

Enable in Vercel Dashboard → Your Project → Analytics (included in Pro plan)

### Render Metrics

View CPU, memory, and request metrics in Render Dashboard → Your Service → Metrics

---

## Next Steps

After successful deployment:

1. **Set up monitoring**: Configure Logfire for backend observability
2. **Add custom domains**: Professional URLs for production
3. **Configure backups**: Set up Supabase daily backups
4. **Scale as needed**: Upgrade plans based on traffic
5. **Add CI/CD**: Set up automated testing before deployment (optional)
6. **Security hardening**: 
   - Rotate API keys regularly
   - Enable Supabase RLS policies
   - Configure rate limiting
   - Set up WAF (Web Application Firewall) if needed

---

## Support

For issues:
- Check Vercel logs: Dashboard → Deployments → Function Logs
- Check Render logs: Dashboard → Logs
- Check Supabase logs: Dashboard → Logs
- Review `docs/OPS.md` for operational guidance

---

**Happy Deploying! 🚀**

