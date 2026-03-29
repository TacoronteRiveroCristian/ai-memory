import argparse
import asyncio
import os
import re
from pathlib import Path

import httpx

API_URL = os.getenv("MEMORY_API_URL", "http://127.0.0.1:8050")
API_KEY = os.getenv("MEMORY_API_KEY", "")


async def store_memory(client: httpx.AsyncClient, content: str, project: str, memory_type: str, tags: list[str]):
    response = await client.post(
        f"{API_URL}/api/memories",
        headers={"X-API-Key": API_KEY},
        json={
            "content": content,
            "project": project,
            "memory_type": memory_type,
            "tags": ", ".join(tags),
            "importance": 0.7,
            "agent_id": "ingest-markdown",
        },
    )
    response.raise_for_status()
    return response.json()


def extract_obsidian_tags(content: str) -> list[str]:
    tags = re.findall(r"#([a-zA-Z0-9_/-]+)", content)
    match = re.search(r"^tags:\s*\[(.*?)\]", content, re.MULTILINE)
    if match:
        tags.extend([item.strip().strip("\"'") for item in match.group(1).split(",") if item.strip()])
    return sorted(set(tags))


def chunk_document(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 50:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


async def ingest_vault(vault_path: str, project: str):
    vault = Path(vault_path)
    files = list(vault.rglob("*.md")) + list(vault.rglob("*.txt"))
    print(f"Encontrados {len(files)} archivos en {vault_path}")

    async with httpx.AsyncClient(timeout=60) as client:
        ingested = 0
        for file_path in files:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if len(content.strip()) < 50:
                continue
            tags = extract_obsidian_tags(content)
            tags.append(file_path.parent.name)
            name_lower = str(file_path).lower()
            memory_type = "general"
            if any(token in name_lower for token in ["decision", "adr", "architecture"]):
                memory_type = "decision"
            elif any(token in name_lower for token in ["error", "bug", "fix", "troubleshoot"]):
                memory_type = "error"
            elif any(token in name_lower for token in ["readme", "overview", "intro"]):
                memory_type = "architecture"
            for index, chunk in enumerate(chunk_document(content)):
                prefix = f"[{file_path.name}{'#' + str(index) if index else ''}]"
                await store_memory(client, f"{prefix}\n{chunk}", project, memory_type, tags)
                await asyncio.sleep(0.1)
            ingested += 1
            if ingested % 10 == 0:
                print(f"Procesados {ingested}/{len(files)}")

    print(f"Ingesta completada: {ingested} archivos -> proyecto '{project}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    asyncio.run(ingest_vault(args.vault, args.project))
