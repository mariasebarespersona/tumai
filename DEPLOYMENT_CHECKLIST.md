# Deployment Checklist for Vercel

Quick checklist to ensure successful deployment.

## Pre-Deployment

### Backend (Render/Railway)
- [ ] Supabase project created and configured
- [ ] Database migrations run in Supabase SQL Editor
- [ ] OpenAI API key obtained
- [ ] Backend environment variables ready:
  - [ ] `OPENAI_API_KEY`
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_SERVICE_ROLE_KEY`
  - [ ] `DATABASE_URL`
  - [ ] `ALLOW_ALL_CORS=1` (for initial testing)
- [ ] Code pushed to GitHub repository

### Frontend (Vercel)
- [ ] Backend URL noted (will be available after backend deployment)
- [ ] Vercel account created
- [ ] Repository connected to Vercel

---

## Deployment Steps

### 1. Deploy Backend First
- [ ] Click Render deploy button or create service manually
- [ ] Add all required environment variables
- [ ] Wait for build and deployment to complete
- [ ] Test backend: Visit `https://your-backend-url.onrender.com/docs`
- [ ] Copy backend URL for frontend configuration

### 2. Deploy Frontend to Vercel
- [ ] Import repository to Vercel
- [ ] Set root directory: `web`
- [ ] Add environment variable: `NEXT_PUBLIC_API_URL=https://your-backend-url.onrender.com`
- [ ] Deploy
- [ ] Visit frontend URL to test

### 3. Test Integration
- [ ] Frontend loads without errors
- [ ] Browser console shows no CORS errors
- [ ] Test chat: "Show me the list of properties"
- [ ] Create a test property
- [ ] Upload a document (if applicable)
- [ ] Set a number value
- [ ] Generate a summary

---

## Post-Deployment

### Security Hardening
- [ ] Update backend CORS:
  - [ ] Remove `ALLOW_ALL_CORS=1`
  - [ ] Add `WEB_BASE=https://your-project.vercel.app`
  - [ ] Restart backend service
- [ ] Verify CORS works with new settings
- [ ] Test all features again

### Optional Enhancements
- [ ] Add custom domain to Vercel
- [ ] Add custom domain to Render backend
- [ ] Update `NEXT_PUBLIC_API_URL` to custom domain
- [ ] Enable Vercel Analytics (Pro plan)
- [ ] Set up Logfire monitoring
  - [ ] Create Logfire account
  - [ ] Add `LOGFIRE_TOKEN` to backend
  - [ ] Verify logs appear in dashboard
- [ ] Configure Supabase backups
- [ ] Set up uptime monitoring (e.g., UptimeRobot)

### Documentation
- [ ] Update README with deployed URLs
- [ ] Document any custom configuration
- [ ] Note environment variables used
- [ ] Create runbook for common issues

---

## Verification Tests

Run through these scenarios to ensure everything works:

### Basic Functionality
- [ ] Chat interface loads
- [ ] Can send messages and receive responses
- [ ] Agent responds intelligently

### Property Management
- [ ] Create a new property
- [ ] List all properties
- [ ] Switch between properties
- [ ] Search for properties

### Document Framework
- [ ] List documents for a property
- [ ] Upload a document (test with dummy PDF)
- [ ] Propose document slots works
- [ ] List documents shows uploaded files
- [ ] Summarize document works (RAG)

### Numbers Framework
- [ ] Get numbers template
- [ ] Set a number value
- [ ] Calculate derived metrics
- [ ] Export to Excel (if email configured)
- [ ] View numbers in chat

### Summary Framework
- [ ] Generate property summary
- [ ] Download summary PDF
- [ ] Email summary (if SMTP configured)

### Email (Optional - requires SMTP)
- [ ] Send document link by email
- [ ] Send numbers Excel by email
- [ ] Send summary PDF by email

### Error Handling
- [ ] Invalid property name shows helpful error
- [ ] Missing document shows helpful message
- [ ] Network errors are handled gracefully
- [ ] Backend errors don't crash frontend

---

## Monitoring Setup

### Daily Checks (First Week)
- [ ] Check Vercel deployment status
- [ ] Check Render service status
- [ ] Review error logs
- [ ] Monitor OpenAI API usage
- [ ] Check Supabase database size

### Weekly Checks (After First Week)
- [ ] Review cost breakdown
- [ ] Check performance metrics
- [ ] Review user feedback (if applicable)
- [ ] Update dependencies if needed

### Tools to Set Up
- [ ] Vercel Dashboard notifications
- [ ] Render email alerts
- [ ] Supabase usage alerts
- [ ] OpenAI usage alerts
- [ ] Logfire dashboard (optional)

---

## Rollback Plan

If deployment fails or has critical issues:

### Frontend Rollback
1. Go to Vercel Dashboard → Deployments
2. Find last working deployment
3. Click "Promote to Production"

### Backend Rollback
1. Go to Render Dashboard → Your Service → Manual Deploy
2. Select previous commit from Git
3. Deploy

### Database Rollback
1. Use Supabase point-in-time recovery (Pro plan)
2. Or restore from manual backup

---

## Common Issues & Solutions

### Frontend can't reach backend
- Check `NEXT_PUBLIC_API_URL` is set in Vercel
- Redeploy frontend after env var changes
- Check CORS on backend

### Backend is slow to respond
- Render free tier sleeps after 15 min inactive
- First request takes ~30s to wake
- Consider upgrading to paid tier

### Database connection errors
- Verify `DATABASE_URL` format
- Check Supabase pooler is enabled
- Ensure migrations are run

### Build fails
- Check build logs for specific errors
- Verify all dependencies are in package.json
- Try local build first: `cd web && npm run build`

---

## Success Criteria

✅ **Deployment is successful when:**
- Frontend loads at Vercel URL
- Backend responds at Render URL
- Can create and list properties
- Chat interface works end-to-end
- No console errors
- Performance is acceptable (<3s for most requests)

---

## Contact & Support

- **Vercel Support**: [vercel.com/support](https://vercel.com/support)
- **Render Support**: [render.com/docs](https://render.com/docs)
- **Supabase Support**: [supabase.com/docs](https://supabase.com/docs)
- **Project Docs**: See `docs/` folder

---

**Last Updated**: November 2025  
**Deployment Guide**: See [DEPLOY_QUICKSTART.md](DEPLOY_QUICKSTART.md) and [docs/DEPLOY_VERCEL.md](docs/DEPLOY_VERCEL.md)

