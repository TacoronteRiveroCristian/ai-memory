import argparse
import asyncio
import os
import subprocess
from pathlib import Path

import httpx

API_URL = os.getenv("MEMORY_API_URL", "http://127.0.0.1:8050")
API_KEY = os.getenv("MEMORY_API_KEY", "")

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".pytest_cache"}
IGNORE_EXTS = {".pyc", ".pyo", ".min.js", ".lock", ".sum"}


async def post_memory(client: httpx.AsyncClient, content: str, project: str, memory_type: str, tags: str = "", importance: float = 0.85):
    response = await client.post(
        f"{API_URL}/api/memories",
        headers={"X-API-Key": API_KEY},
        json={
            "content": content,
            "project": project,
            "memory_type": memory_type,
            "tags": tags,
            "importance": importance,
            "agent_id": "ingest-codebase",
        },
    )
    response.raise_for_status()


async def ingest_repo(repo_path: str, project: str):
    repo = Path(repo_path)
    async with httpx.AsyncClient(timeout=90) as client:
        for readme in repo.glob("README*"):
            content = readme.read_text(errors="ignore")
            await post_memory(client, f"README DEL PROYECTO:\n{content[:2000]}", project, "architecture", importance=0.95)

        tree = subprocess.run(
            ["find", repo_path, "-type", "f", "-not", "-path", "*/.git/*"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        filtered = [
            line.replace(repo_path, "").lstrip("/")
            for line in tree.strip().split("\n")
            if line
            and not any(part in line for part in IGNORE_DIRS)
            and not any(line.endswith(ext) for ext in IGNORE_EXTS)
        ]
        structure = "\n".join(sorted(filtered))
        await post_memory(client, f"ESTRUCTURA DEL PROYECTO {project}:\n{structure[:3000]}", project, "architecture", tags="structure,config", importance=0.9)

        for config_name in ["docker-compose.yml", "Dockerfile", "pyproject.toml", "package.json", "requirements.txt", ".env.example"]:
            path = repo / config_name
            if path.exists():
                content = path.read_text(errors="ignore")[:1500]
                await post_memory(client, f"CONFIG [{config_name}]:\n{content}", project, "architecture", tags="config,infrastructure", importance=0.85)
                await asyncio.sleep(0.2)

    print(f"Repositorio '{project}' ingestado")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    asyncio.run(ingest_repo(args.repo, args.project))
