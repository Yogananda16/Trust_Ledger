"""Upload the backend to a Hugging Face Space.

Usage (log in once first with `hf auth login`):
    python deploy_space.py <username>/trustledger

Only backend files are uploaded. The Space keeps the README that Hugging Face
created, which holds its Docker settings.
"""
import sys

from huggingface_hub import HfApi

BACKEND_FILES = [
    "Dockerfile",
    "requirements.txt",
    "api.py",
    "warm_cache.py",
    "pipeline/*.py",
    "data/*.json",
]

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python deploy_space.py <username>/<space-name>")

    space_id = sys.argv[1]
    HfApi().upload_folder(
        repo_id=space_id,
        repo_type="space",
        folder_path=".",
        allow_patterns=BACKEND_FILES,
        commit_message="Deploy TrustLedger backend",
    )
    print(f"Uploaded. Watch the build at https://huggingface.co/spaces/{space_id}")
