import asyncio
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Awaitable, Callable

from .config import ROOT_DIR


GitRunner = Callable[..., Awaitable[str]]
MAX_FILE_SIZE = 1024 * 1024
BLOCKED_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif",
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
}
BLOCKED_PARTS = {".env", "logs", "storage", "__pycache__", "node_modules"}
SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("provider-token", re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])-[_A-Za-z0-9-]{16,}\b")),
    ("credential-assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*"
        r"['\"]?[A-Za-z0-9_./+=-]{8,}"
    )),
)
SECRET_REMEDIATION = (
    "Remove the credential from the change, rotate it if it was real, and load it "
    "from an approved environment or secret store."
)


@dataclass(frozen=True)
class PreflightFinding:
    id: str
    rule: str
    file: str
    line: int
    detected_text: str
    remediation: str
    ignorable: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "rule": self.rule,
            "file": self.file,
            "line": self.line,
            "detected_text": self.detected_text,
            "remediation": self.remediation,
            "ignorable": self.ignorable,
        }


@dataclass(frozen=True)
class GitPreflight:
    ok: bool
    blockers: list[str]
    files: list[str]
    summary: str
    commit_message: str
    head: str
    branch: str
    upstream: str
    snapshot: str
    findings: list[PreflightFinding]

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "blockers": self.blockers,
            "files": self.files,
            "summary": self.summary,
            "commit_message": self.commit_message,
            "head": self.head,
            "branch": self.branch,
            "upstream": self.upstream,
            "snapshot": self.snapshot,
            "findings": [finding.as_dict() for finding in self.findings],
        }


class GitWorkflow:
    def __init__(self, runner: GitRunner, root: Path = ROOT_DIR) -> None:
        self._git = runner
        self._root = root.resolve()
        self._lock = asyncio.Lock()

    async def preflight(self) -> GitPreflight:
        status = await self._git("status", "--short")
        diff_check = await self._git("diff", "--check", check=False)
        staged_diff_check = await self._git("diff", "--cached", "--check", check=False)
        head = (await self._git("rev-parse", "HEAD", check=False)).strip()
        branch = (await self._git("branch", "--show-current", check=False)).strip()
        upstream = (
            await self._git(
                "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}",
                check=False,
            )
        ).strip()
        entries = _parse_status(status)
        files = [path for _, path in entries]
        blockers: list[str] = []

        if not entries:
            blockers.append("No changes to commit.")
        if diff_check.strip() or staged_diff_check.strip():
            blockers.append("git diff --check failed; fix whitespace errors first.")
        if not head or _git_lookup_failed(head):
            blockers.append("Current HEAD could not be resolved.")
        if not branch:
            blockers.append("Detached HEAD is not allowed.")
        if not upstream or _git_lookup_failed(upstream):
            blockers.append("The current branch has no configured upstream.")

        for code, path in entries:
            blockers.extend(self._inspect_path(code, path))

        diff = await self._combined_diff(files)
        findings = await self._secret_findings(files, diff)
        if findings:
            blockers.append("A possible secret was detected in the diff.")

        stat = await self._git("diff", "--stat", "HEAD", check=False)
        summary = f"{len(files)} changed file(s)"
        if stat.strip():
            summary = f"{summary}\n{stat.strip()}"
        message = _generate_commit_message(entries)
        snapshot = _snapshot(status, head, diff)
        return GitPreflight(
            ok=not blockers,
            blockers=_unique(blockers),
            files=files,
            summary=summary,
            commit_message=message,
            head=head,
            branch=branch,
            upstream=upstream,
            snapshot=snapshot,
            findings=findings,
        )

    async def commit_push(
        self, expected_snapshot: str, ignored_finding_ids: list[str] | None = None
    ) -> dict[str, object]:
        async with self._lock:
            report = await self.preflight()
            ignored = set(ignored_finding_ids or [])
            valid_ignored = {finding.id for finding in report.findings if finding.ignorable}
            remaining_blockers = list(report.blockers)
            if report.findings and ignored and ignored <= valid_ignored:
                if {finding.id for finding in report.findings} <= ignored:
                    remaining_blockers = [
                        blocker for blocker in remaining_blockers
                        if blocker != "A possible secret was detected in the diff."
                    ]
            if ignored - valid_ignored:
                remaining_blockers.append("Ignore Once contained an invalid or stale finding.")
            if remaining_blockers:
                return {
                    **report.as_dict(),
                    "ok": False,
                    "blockers": _unique(remaining_blockers),
                    "committed": False,
                    "pushed": False,
                }
            if not expected_snapshot or expected_snapshot != report.snapshot:
                return {
                    **report.as_dict(),
                    "ok": False,
                    "blockers": ["Changes or HEAD changed after preflight; run preflight again."],
                    "committed": False,
                    "pushed": False,
                }

            await self._git("add", "--", *report.files)
            staged = await self._git("diff", "--cached", "--name-only", "-z")
            if sorted(_parse_nul_paths(staged)) != sorted(report.files):
                return {
                    **report.as_dict(),
                    "ok": False,
                    "blockers": ["The staged file set did not match the approved preflight."],
                    "committed": False,
                    "pushed": False,
                }
            staged_check = await self._git("diff", "--cached", "--check", check=False)
            if staged_check.strip():
                return {
                    **report.as_dict(),
                    "ok": False,
                    "blockers": ["Staged diff failed git diff --check."],
                    "committed": False,
                    "pushed": False,
                }

            current_head = (await self._git("rev-parse", "HEAD", check=False)).strip()
            staged_diff = await self._git("diff", "--cached", "--", *report.files, check=False)
            post_stage_blockers: list[str] = []
            for code, path in _parse_status(await self._git("status", "--short")):
                if path in report.files:
                    post_stage_blockers.extend(self._inspect_path(code, path))
            if current_head != report.head:
                post_stage_blockers.append("HEAD changed while preparing the commit.")
            staged_findings = _find_secrets_in_diff(staged_diff)
            if staged_findings and not {finding.id for finding in staged_findings} <= ignored:
                post_stage_blockers.append("A possible secret was detected in the staged diff.")
            if post_stage_blockers:
                return {
                    **report.as_dict(),
                    "ok": False,
                    "blockers": _unique(post_stage_blockers),
                    "committed": False,
                    "pushed": False,
                }

            await self._git("commit", "-m", report.commit_message)
            commit_hash = (await self._git("rev-parse", "HEAD")).strip()
            commit_parent = (await self._git("rev-parse", "HEAD^", check=False)).strip()
            if not commit_hash or commit_hash == report.head or commit_parent != report.head:
                return {
                    **report.as_dict(),
                    "ok": False,
                    "blockers": ["Commit verification failed; push was not attempted."],
                    "committed": True,
                    "pushed": False,
                    "commit_hash": commit_hash,
                }

            push_output = await self._git("push", "--porcelain")
            return {
                **report.as_dict(),
                "ok": True,
                "blockers": [],
                "committed": True,
                "pushed": True,
                "commit_hash": commit_hash,
                "push_output": push_output.strip(),
            }

    def _inspect_path(self, code: str, path: str) -> list[str]:
        blockers: list[str] = []
        pure = PurePosixPath(path)
        if path.startswith("/") or ".." in pure.parts:
            return [f"Unsafe repository path: {path}"]
        if "D" in code:
            blockers.append(f"Deleted files require separate review: {path}")
        if any(part == ".env" or part.startswith(".env.") for part in pure.parts):
            blockers.append(f"Environment files cannot be committed: {path}")
        if set(pure.parts) & BLOCKED_PARTS:
            blockers.append(f"Generated, log, or storage content is blocked: {path}")
        if pure.suffix.lower() in BLOCKED_SUFFIXES:
            blockers.append(f"Database or media files cannot be committed: {path}")

        raw_candidate = self._root / path
        candidate = raw_candidate.resolve()
        if self._root not in candidate.parents and candidate != self._root:
            blockers.append(f"Path resolves outside the repository: {path}")
        elif raw_candidate.is_symlink():
            blockers.append(f"Symbolic links require separate review: {path}")
        elif candidate.is_file() and candidate.stat().st_size > MAX_FILE_SIZE:
            blockers.append(f"File exceeds the 1 MiB safety limit: {path}")
        elif candidate.is_file():
            try:
                candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                blockers.append(f"Binary files require separate review: {path}")
        return blockers

    async def _combined_diff(self, files: list[str]) -> str:
        if not files:
            return ""
        tracked = await self._git("diff", "HEAD", "--", *files, check=False)
        untracked_parts: list[str] = []
        for path in files:
            candidate = self._root / path
            if candidate.is_file() and not candidate.is_symlink():
                listed = await self._git("ls-files", "--error-unmatch", "--", path, check=False)
                if not listed.strip() and candidate.stat().st_size <= MAX_FILE_SIZE:
                    try:
                        untracked_parts.append(candidate.read_text(encoding="utf-8"))
                    except UnicodeDecodeError:
                        untracked_parts.append("[binary file]")
        return tracked + "\n".join(untracked_parts)

    async def _secret_findings(
        self, files: list[str], combined_diff: str
    ) -> list[PreflightFinding]:
        findings = _find_secrets_in_diff(combined_diff)
        tracked_findings = {(item.file, item.line, item.rule) for item in findings}
        for path in files:
            candidate = self._root / path
            if not candidate.is_file() or candidate.is_symlink():
                continue
            listed = await self._git("ls-files", "--error-unmatch", "--", path, check=False)
            if listed.strip():
                continue
            try:
                lines = candidate.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, 1):
                for finding in _find_secrets_in_line(path, line_number, line):
                    key = (finding.file, finding.line, finding.rule)
                    if key not in tracked_findings:
                        findings.append(finding)
                        tracked_findings.add(key)
        return findings


def _parse_status(status: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        entries.append((line[:2], path.strip('"')))
    return entries


def _parse_nul_paths(value: str) -> list[str]:
    return [path for path in value.split("\0") if path]


def _find_secrets_in_diff(diff: str) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    path = ""
    new_line = 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        hunk = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk:
            new_line = int(hunk.group(1))
            continue
        if not path or line.startswith("---"):
            continue
        if line.startswith("+"):
            findings.extend(_find_secrets_in_line(path, new_line, line[1:]))
            new_line += 1
        elif not line.startswith("-"):
            new_line += 1
    return findings


def _find_secrets_in_line(path: str, line_number: int, line: str) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    for rule, pattern in SECRET_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        finding_id = hashlib.sha256(
            f"{rule}\0{path}\0{line_number}\0{match.group(0)}".encode()
        ).hexdigest()[:20]
        findings.append(PreflightFinding(
            id=finding_id,
            rule=rule,
            file=path,
            line=line_number,
            detected_text=_mask_secret(match.group(0)),
            remediation=SECRET_REMEDIATION,
            ignorable=True,
        ))
    return findings


def _mask_secret(value: str) -> str:
    label = re.match(r"(?i)^([^:=]{1,40}\s*[:=]\s*)", value)
    prefix = label.group(1) if label else ""
    return f"{prefix}[REDACTED]"


def redact_secrets(value: str) -> str:
    redacted = value
    for _, pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: _mask_secret(match.group(0)), redacted)
    return redacted


def _snapshot(status: str, head: str, diff: str) -> str:
    return hashlib.sha256(f"{head}\0{status}\0{diff}".encode()).hexdigest()


def _generate_commit_message(entries: list[tuple[str, str]]) -> str:
    paths = [path for _, path in entries]
    docs_only = bool(paths) and all(
        path == "AGENTS.md" or path == "README.md" or path.startswith(("docs/", "chatgpt_docs/"))
        for path in paths
    )
    kind = "docs" if docs_only else "feat"
    if any(path.startswith("backend/") for path in paths) and any(
        path.startswith("frontend/") for path in paths
    ):
        subject = "add safe commit and push workflow"
    elif docs_only:
        subject = "update project guidance"
    elif any(path.startswith("backend/") for path in paths):
        subject = "update developer backend workflow"
    elif any(path.startswith("frontend/") for path in paths):
        subject = "update developer interface"
    else:
        subject = "update Jarvis developer workflow"
    return f"{kind}: {subject}"


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _git_lookup_failed(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("fatal:") or lowered.startswith("error:")
