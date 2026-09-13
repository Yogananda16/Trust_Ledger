# Backend image for Hugging Face Spaces (Docker SDK). The frontend is deployed separately on Vercel.
FROM python:3.10-slim

# Spaces run containers as user 1000, so the app directory must belong to that user.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

# CPU-only PyTorch first: the default build bundles GPU libraries that add gigabytes.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "torch==2.14.0+cpu" --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user api.py warm_cache.py ./
COPY --chown=user pipeline ./pipeline
COPY --chown=user data ./data

# Download the embedding model during the build so the first request doesn't wait for it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 7860
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
