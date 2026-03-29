"""Build a reviewed source archive from an explicit allowlist, without Git."""

import hashlib
import io
import json
import os
import re
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
    "manage.py",
    "Dockerfile",
    ".dockerignore",
    ".gitignore",
    "compose.yaml",
    "compose.airflow.yaml",
    "compose.check.yaml",
}
DIRECTORIES = {
    ".github",
    "noticeboard",
    "procurement",
    "frontend",
    "tests",
    "scripts",
    "dags",
    "docs",
    "evaluation",
}
SUFFIXES = {
    ".py",
    ".xml",
    ".md",
    ".json",
    ".tsx",
    ".ts",
    ".css",
    ".html",
    ".svg",
    ".txt",
    ".toml",
    ".lock",
    ".yaml",
    ".yml",
    ".png",
}
EXCLUDED = {
    "node_modules",
    "dist-demo",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "private",
    "archive",
    "runtime",
}


def public_files():
    paths = [ROOT / name for name in FILES]
    for directory in DIRECTORIES:
        for base, dirs, names in os.walk(ROOT / directory):
            dirs[:] = [name for name in dirs if name not in EXCLUDED]
            paths.extend(Path(base) / name for name in names if Path(name).suffix in SUFFIXES)
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Invalid public file: {path.relative_to(ROOT)}")
        yield path


def main():
    secrets = []
    environment = ROOT / "runtime/local.env"
    if environment.exists():
        for line in environment.read_text().splitlines():
            key, _, value = line.partition("=")
            if any(word in key for word in ["TOKEN", "KEY", "SECRET"]) and value:
                secrets.append(value.encode())
    credentials = ROOT / "private/LOCAL_ACCESS.txt"
    if credentials.exists():
        secrets += [
            line.partition(": ")[2].encode()
            for line in credentials.read_text().splitlines()
            if line.startswith("Password: ")
        ]
    contents = {}
    for path in public_files():
        data = path.read_bytes()
        name = path.relative_to(ROOT).as_posix()
        if any(secret in data for secret in secrets) or re.search(
            rb"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", data
        ):
            raise ValueError(f"Possible credential in public file: {name}")
        contents[name] = data
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    contents["MANIFEST.json"] = json.dumps(manifest, indent=2, sort_keys=True).encode()
    output = ROOT / "dist/noticeboard-source.tar.gz"
    output.parent.mkdir(exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        for name, data in contents.items():
            info = tarfile.TarInfo("noticeboard/" + name)
            info.size, info.mode = len(data), 0o644
            info.mtime = int(time.time())
            archive.addfile(info, io.BytesIO(data))
    with tarfile.open(output) as archive:
        assert len(archive.getmembers()) == len(contents)
        for name, expected in manifest.items():
            assert (
                hashlib.sha256(archive.extractfile("noticeboard/" + name).read()).hexdigest()
                == expected
            )
    print(f"Exported and verified {len(manifest)} public files: {output}")


if __name__ == "__main__":
    main()
