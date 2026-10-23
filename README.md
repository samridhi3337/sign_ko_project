# SignBridge

Shareable Flask web app for text-to-sign references, a word dictionary, and 3D sign animation.

## Deploy on Render

1. Push this repository to GitHub.
2. In Render, select **New → Blueprint** and choose the repository. Render reads `render.yaml` and creates the web service.
3. Wait for the health check at `/healthz` to pass, then share the generated `onrender.com` URL.

The deployment uses `gunicorn`, respects the platform `PORT`, runs without Flask debug mode, and keeps local camera processes disabled. The animation, word dictionary, text-to-sign pages, and static assets remain available publicly.

## Run locally

For the shareable web experience:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

For webcam recognition and model-training tools, install the extra local packages and explicitly opt in to server-camera processes:

```bash
pip install -r requirements-local.txt
ENABLE_LOCAL_RECOGNITION=true python app.py
```

Open `http://127.0.0.1:5001`. On a hosted deployment, webcam recognition intentionally stays disabled because the cloud server cannot access a visitor's camera.

## Notes for hosting

The repository contains a substantial sign-video dataset. Leave it in the repository if the public Word Dictionary reference videos are required; moving it to object storage/CDN is the next scaling step if the selected host has a source or build-size limit.
