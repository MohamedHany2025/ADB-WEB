# Deployment Guide for ADB Web Control

## Railway Deployment

### Prerequisites
- GitHub account with repository
- Railway account (railway.app)
- Git installed locally

### Deployment Steps

1. **Push to GitHub:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/adb-web-control.git
git push -u origin main
```

2. **Connect to Railway:**
- Go to [Railway.app](https://railway.app)
- Click "New Project"
- Select "Deploy from GitHub"
- Authorize and select your repository
- Railway auto-detects Python and `Procfile`

3. **Set Environment Variables (Optional):**
In Railway Dashboard → Project → Variables:
- `PORT`: 8000 (default)
- `DEBUG`: False (default)
- `FLASK_ENV`: production (default)

4. **Deploy:**
Push changes to GitHub branch, Railway auto-deploys:
```bash
git push origin main
```

### Health Check
Access the deployed app:
```
https://your-project.up.railway.app/health
```

Returns:
```json
{
  "status": "ok",
  "adb": true,
  "scrcpy": true
}
```

---

## Local Docker Testing

### Build Image
```bash
docker build -t adb-web:latest .
```

### Run Container
```bash
docker run -p 8000:8000 \
  -e PORT=8000 \
  -e DEBUG=False \
  -e FLASK_ENV=production \
  adb-web:latest
```

### Using Docker Compose
```bash
docker-compose up --build
```

Access at: `http://localhost:8000`

---

## System Requirements

The Dockerfile includes:
- ✅ Python 3.9
- ✅ ADB (Android Debug Bridge)
- ✅ Scrcpy (Android screen mirroring)
- ✅ Java 11 JDK
- ✅ libusb (USB support)
- ✅ Git, wget, curl, unzip utilities

---

## Troubleshooting

### ADB not found
Check status endpoint:
```bash
curl https://your-project.up.railway.app/health
```

If `"adb": false`, the Docker image wasn't rebuilt with new Dockerfile. 
Trigger rebuild:
```bash
git commit --allow-empty -m "Trigger Railway rebuild"
git push
```

### Scrcpy not found
Same as ADB above - requires Docker image rebuild.

### Health check fails
Ensure `/health` endpoint is accessible:
```bash
curl http://localhost:8000/health
```

### Container logs
```bash
# Railway
railway logs

# Docker
docker logs <container_id>
```

---

## Production Notes

- Application runs on port 8000 in production
- Debug mode disabled by default
- All system dependencies pre-installed in Docker image
- Health check validates ADB and Scrcpy availability every 30 seconds

