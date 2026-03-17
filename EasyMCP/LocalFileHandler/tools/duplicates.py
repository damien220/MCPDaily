"""DuplicatesTool — find exact and near-duplicate files in the workspace.

Phase 4.3:
- **Exact duplicates**: group files that share the same MD5 hash.
- **Near-duplicate names**: group files whose stems are very similar
  (Levenshtein ratio ≥ 0.80), helping catch typo-variants and versioned copies
  like ``report.md`` / ``report-v2.md`` / ``report-final.md``.

No LLM is needed for this tool — all logic is deterministic.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

_SKIP_DIRS = {".history", ".trash"}
_HASH_CHUNK = 65_536     # 64 KB read chunks for MD5


# ── Levenshtein similarity (pure Python, no dependencies) ────────────────────

def _levenshtein(a: str, b: str) -> int:
    """Return the Levenshtein edit distance between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def _similarity(a: str, b: str) -> float:
    """Normalised similarity in [0, 1] (1 = identical)."""
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    return 1.0 - _levenshtein(a, b) / max_len


# ── MD5 hashing ──────────────────────────────────────────────────────────────

def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


class DuplicatesTool(BaseTool):
    """Find exact and near-duplicate files across the workspace.

    Payload:
        ``path``        (str, optional, default ".")  — sub-directory to scan.
        ``mode``        (str, optional, default "all") — "exact", "similar", or "all".
        ``threshold``   (float, optional, default 0.80) — name-similarity ratio
                        for near-duplicates (0–1).

    Result (success):
        ``exact``       — list of groups; each group is a list of file-info dicts
                          for files with the same MD5.
        ``similar``     — list of groups; each group is a list of file-info dicts
                          for files whose stems are name-similar.
        ``total_wasted_bytes`` — sum of redundant file sizes (all copies minus one).
        ``scanned``     — number of files examined.
    """

    def __init__(self, workspace: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.workspace = workspace

    def handle(self, request: MCPRequest) -> MCPResponse:
        rel   = request.payload.get("path", ".").strip() or "."
        mode  = request.payload.get("mode", "all").lower()
        thr   = float(request.payload.get("threshold", 0.80))

        scan_root = (self.workspace / rel).resolve()
        if not str(scan_root).startswith(str(self.workspace.resolve())):
            return MCPResponse.failure(request, "Path escapes workspace.")
        if not scan_root.exists():
            return MCPResponse.failure(request, f"Path not found: {rel}")

        # ── Collect all files ─────────────────────────────────────────────
        files: list[Path] = []
        for p in scan_root.rglob("*"):
            if p.is_file() and not any(part in _SKIP_DIRS for part in p.parts):
                files.append(p)

        def _info(p: Path) -> dict:
            stat = p.stat()
            return {
                "path":     str(p.relative_to(self.workspace)),
                "name":     p.name,
                "size":     stat.st_size,
                "modified": p.stat().st_mtime,
            }

        exact_groups:   list[list[dict]] = []
        similar_groups: list[list[dict]] = []
        wasted = 0

        # ── Exact duplicates (MD5) ────────────────────────────────────────
        if mode in ("exact", "all"):
            hash_map: dict[str, list[Path]] = {}
            for p in files:
                try:
                    h = _md5(p)
                    hash_map.setdefault(h, []).append(p)
                except OSError:
                    continue
            for group in hash_map.values():
                if len(group) > 1:
                    infos = [_info(p) for p in group]
                    exact_groups.append(infos)
                    # Wasted = all copies minus the largest one
                    sizes = sorted(f["size"] for f in infos)
                    wasted += sum(sizes[:-1])

        # ── Near-duplicate names ──────────────────────────────────────────
        if mode in ("similar", "all"):
            visited: set[int] = set()
            for i, pi in enumerate(files):
                if i in visited:
                    continue
                group_paths = [pi]
                stem_i = pi.stem.lower()
                for j, pj in enumerate(files):
                    if j <= i or j in visited:
                        continue
                    stem_j = pj.stem.lower()
                    if _similarity(stem_i, stem_j) >= thr and pi.suffix == pj.suffix:
                        group_paths.append(pj)
                        visited.add(j)
                if len(group_paths) > 1:
                    visited.add(i)
                    similar_groups.append([_info(p) for p in group_paths])

        return MCPResponse.success(request, {
            "exact":               exact_groups,
            "similar":             similar_groups,
            "total_wasted_bytes":  wasted,
            "scanned":             len(files),
        })
