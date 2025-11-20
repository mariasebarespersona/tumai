# Fix: Vercel 250MB Serverless Function Error

## Problem

When deploying to Vercel, you get this error:

```
Error: A Serverless Function has exceeded the unzipped maximum size of 250 MB.
```

This happens because Vercel is trying to build the **entire repository** (including the Python backend with all dependencies) instead of just the Next.js frontend.

## Root Cause

Vercel sees `requirements.txt` in the root directory and tries to package the Python backend as a serverless function, which exceeds the 250MB limit.

## Solution

Configure Vercel to **only build the `web/` directory** (Next.js frontend).

---

## 🔧 Fix Method 1: Update Existing Project Settings

### Step 1: Update Root Directory

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project
3. Go to **Settings** → **General**
4. Scroll to **"Build & Development Settings"**
5. Find **"Root Directory"**
6. Click **"Edit"**
7. Enter: `web`
8. Click **"Save"**

### Step 2: Redeploy

1. Go to **Deployments** tab
2. Click on the three dots (•••) on the latest deployment
3. Click **"Redeploy"**
4. Wait for build to complete

✅ **This should work!** Vercel will now only build the Next.js app from `web/`.

---

## 🔧 Fix Method 2: Delete and Reimport

If you can't find the Root Directory setting or it doesn't work:

### Step 1: Delete Existing Project

1. Go to Vercel Dashboard → Your Project
2. Go to **Settings** → **General**
3. Scroll to bottom → **"Delete Project"**
4. Confirm deletion

### Step 2: Reimport with Correct Settings

1. Go to [vercel.com/new](https://vercel.com/new)
2. Click **"Import Project"**
3. Select your GitHub repository
4. **IMPORTANT**: Before clicking Deploy, configure:

   **Build and Output Settings**:
   - Click **"Edit"** next to "Root Directory"
   - Enter: `web`
   - Click **"Continue"**

   **Environment Variables**:
   - Click **"Add"**
   - Name: `NEXT_PUBLIC_API_URL`
   - Value: Your backend URL (e.g., `https://rama-api-xxx.onrender.com`)
   
5. Click **"Deploy"**

✅ **Done!** Vercel should now build successfully.

---

## 🔧 Fix Method 3: Use Vercel CLI

If you prefer command line:

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Navigate to web directory
cd web

# Deploy from web directory
vercel

# Follow prompts, then deploy to production
vercel --prod
```

By running `vercel` from inside the `web/` directory, Vercel automatically uses that as the root.

---

## 📋 Verification

After redeploying, you should see in the build logs:

```
✅ Building Next.js application...
✅ Collecting page data
✅ Generating static pages
✅ Build completed successfully
```

**NOT**:
```
❌ Installing required dependencies from requirements.txt...
❌ No Python version specified...
```

If you see Python/requirements.txt in the logs, the Root Directory is still wrong.

---

## 🎯 Expected Build Configuration

**Correct configuration for Vercel:**

| Setting | Value |
|---------|-------|
| Framework | Next.js |
| Root Directory | `web` |
| Build Command | `npm run build` |
| Output Directory | `.next` |
| Install Command | `npm install` |

**Environment Variables:**
- `NEXT_PUBLIC_API_URL` = Your Render backend URL

---

## 🔍 Why This Happens

Your repository structure is:

```
rama-agentic-ai/
├── requirements.txt      ← Python backend (FastAPI)
├── app.py               ← Python backend
├── agents/              ← Python backend
├── tools/               ← Python backend
└── web/                 ← Next.js frontend (THIS is what Vercel should build)
    ├── package.json
    ├── next.config.js
    └── src/
```

**Without Root Directory set to `web`:**
- Vercel sees `requirements.txt` at root
- Tries to build as Python serverless function
- Includes all Python dependencies (LangGraph, pandas, etc.)
- Exceeds 250MB limit ❌

**With Root Directory set to `web`:**
- Vercel only looks inside `web/`
- Sees `package.json` and `next.config.js`
- Builds as Next.js app
- Much smaller bundle (~50MB) ✅

---

## 🚨 Important Notes

1. **Backend should NOT be on Vercel**
   - The Python backend needs a long-running server
   - Vercel is for the Next.js frontend only
   - Deploy backend to Render/Railway instead

2. **Vercel Configuration Files**
   - `vercel.json` at root is only used if Root Directory is not set
   - When Root Directory = `web`, Vercel uses `web/vercel.json`
   - `.vercelignore` helps but Root Directory is more reliable

3. **After Successful Deploy**
   - Test frontend loads: `https://your-project.vercel.app`
   - Check browser console for API connection
   - Set `NEXT_PUBLIC_API_URL` to point to Render backend

---

## ✅ Success Criteria

Deployment is successful when:

- ✅ Build completes in <2 minutes
- ✅ No Python/requirements.txt in build logs
- ✅ See "Building Next.js application" in logs
- ✅ Frontend loads at Vercel URL
- ✅ Bundle size is ~30-50MB (not 250MB+)

---

## 🆘 Still Having Issues?

### Check Build Logs

1. Vercel Dashboard → Deployments
2. Click on failed deployment
3. Check **Build Logs**
4. Look for: "Root Directory: web" near the top

### Verify Settings

1. Vercel Dashboard → Settings → General
2. Confirm "Root Directory" shows `web`
3. If blank or `/`, update it

### Manual Deploy

Try deploying manually from CLI:

```bash
cd web
vercel --prod
```

This forces deployment from the `web` directory.

---

## 📞 Need More Help?

- **Vercel Documentation**: [vercel.com/docs/projects/project-configuration](https://vercel.com/docs/projects/project-configuration)
- **Root Directory Guide**: [vercel.com/docs/projects/overview#root-directory](https://vercel.com/docs/projects/overview#root-directory)
- **Contact**: Vercel Support in dashboard

---

**Quick Summary**: Set **Root Directory = `web`** in Vercel project settings, then redeploy. This tells Vercel to only build the Next.js frontend, not the Python backend.

