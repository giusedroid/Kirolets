import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
import re
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from kirolets_bot.config import Settings


@dataclass(frozen=True)
class PullRequestResult:
    branch_name: str
    pr_url: str | None
    changed: bool
    summary: str


class GitHubWorkflowError(RuntimeError):
    pass


class GitHubWorkflow:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def execute_request(self, request_text: str, user_label: str) -> PullRequestResult:
        async with _temporary_directory() as workspace:
            repo_dir = os.path.join(workspace, "repo")
            branch_name = self._branch_name(user_label)

            await self._git("clone", self._authenticated_repo_url(), repo_dir, cwd=workspace)
            await self._git("checkout", self._settings.github_base_branch, cwd=repo_dir)
            await self._git("checkout", "-b", branch_name, cwd=repo_dir)

            kiro_output = await self._run_kiro(repo_dir, request_text)
            changed = await self._has_changes(repo_dir)

            if not changed:
                return PullRequestResult(
                    branch_name=branch_name,
                    pr_url=None,
                    changed=False,
                    summary=self._summarize_output(kiro_output),
                )

            await self._git("add", "-A", cwd=repo_dir)
            await self._git("commit", "-m", self._commit_message(request_text), cwd=repo_dir)
            await self._git("push", "-u", "origin", branch_name, cwd=repo_dir)
            pr_url = await self._create_pull_request(branch_name, request_text, kiro_output)

            return PullRequestResult(
                branch_name=branch_name,
                pr_url=pr_url,
                changed=True,
                summary=self._summarize_output(kiro_output),
            )

    async def _run_kiro(self, repo_dir: str, request_text: str) -> str:
        env = os.environ.copy()
        env["KIRO_API_KEY"] = self._settings.kiro_api_key

        return await self._run_command(
            "kiro-cli",
            "chat",
            "--no-interactive",
            f"--trust-tools={self._settings.kiro_trust_tools}",
            request_text,
            cwd=repo_dir,
            env=env,
            timeout=self._settings.kiro_timeout_seconds,
        )

    async def _has_changes(self, repo_dir: str) -> bool:
        output = await self._git("status", "--porcelain", cwd=repo_dir)
        return bool(output.strip())

    async def _git(self, *args: str, cwd: str) -> str:
        return await self._run_command("git", *args, cwd=cwd, timeout=300)

    async def _run_command(
        self,
        *args: str,
        cwd: str,
        env: dict[str, str] | None = None,
        timeout: int,
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise GitHubWorkflowError(f"Command timed out: {args[0]}") from exc

        output = (stdout + stderr).decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise GitHubWorkflowError(self._redact(f"Command failed: {' '.join(args)}\n{output}"))

        return self._redact(output)

    async def _create_pull_request(self, branch_name: str, request_text: str, kiro_output: str) -> str:
        owner, repo = self._repository_owner_and_name()
        body = {
            "title": self._pr_title(request_text),
            "head": branch_name,
            "base": self._settings.github_base_branch,
            "body": self._pr_body(request_text, branch_name, kiro_output),
            "draft": False,
            "maintainer_can_modify": True,
        }

        request = Request(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._settings.github_token}",
                "Content-Type": "application/json",
                "User-Agent": "kirolets-bot",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )

        try:
            response_body = await asyncio.to_thread(self._open_json_request, request)
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise GitHubWorkflowError(f"Failed to create PR: {exc.code} {error_body}") from exc

        return response_body["html_url"]

    def _open_json_request(self, request: Request) -> dict:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _authenticated_repo_url(self) -> str:
        parsed = urlparse(self._settings.github_repository_url)
        if parsed.scheme != "https":
            raise GitHubWorkflowError("GITHUB_REPOSITORY_URL must be an HTTPS GitHub URL.")

        token = quote(self._settings.github_token, safe="")
        return parsed._replace(netloc=f"x-access-token:{token}@{parsed.netloc}").geturl()

    def _repository_owner_and_name(self) -> tuple[str, str]:
        parsed = urlparse(self._settings.github_repository_url)
        path_parts = parsed.path.strip("/").removesuffix(".git").split("/")
        if len(path_parts) != 2:
            raise GitHubWorkflowError("GITHUB_REPOSITORY_URL must look like https://github.com/owner/repo.git")

        return path_parts[0], path_parts[1]

    def _branch_name(self, user_label: str) -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        safe_user = re.sub(r"[^a-zA-Z0-9._-]+", "-", user_label).strip("-") or "user"
        return f"kirolets/{safe_user}/{timestamp}"

    def _commit_message(self, request_text: str) -> str:
        return f"Kirolets: {self._short_text(request_text, 60)}"

    def _pr_title(self, request_text: str) -> str:
        return f"Kirolets: {self._short_text(request_text, 80)}"

    def _pr_body(self, request_text: str, branch_name: str, kiro_output: str) -> str:
        summary = self._summarize_output(kiro_output)
        return (
            "## Request\n\n"
            f"{request_text}\n\n"
            "## Branch\n\n"
            f"`{branch_name}`\n\n"
            "## Kiro Output Summary\n\n"
            f"```text\n{summary}\n```\n"
        )

    def _summarize_output(self, output: str) -> str:
        cleaned = output.strip()
        if len(cleaned) <= 2000:
            return cleaned

        return f"{cleaned[:2000]}\n...[truncated]"

    def _short_text(self, text: str, max_length: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= max_length:
            return normalized

        return normalized[: max_length - 3].rstrip() + "..."

    def _redact(self, text: str) -> str:
        return text.replace(self._settings.github_token, "***").replace(self._settings.kiro_api_key, "***")


class _temporary_directory:
    def __init__(self) -> None:
        self._manager = tempfile.TemporaryDirectory(prefix="kirolets-")

    async def __aenter__(self) -> str:
        return await asyncio.to_thread(self._manager.__enter__)

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await asyncio.to_thread(self._manager.__exit__, exc_type, exc, traceback)
