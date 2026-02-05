"""GitHub API tools with retry handling."""

import asyncio
import base64
import httpx
from typing import Any, Dict
from config import settings
from schemas import ToolResult


# Errors worth retrying
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GitHubTools:
    """GitHub API client with retry logic."""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.max_retries = settings.max_retries
    
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make request with retry and backoff."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
                    r = await client.request(method, url, **kwargs)
                    
                    # Success
                    if r.status_code < 400:
                        return r
                    
                    # Rate limited - wait and retry
                    if r.status_code == 429:
                        wait = int(r.headers.get("Retry-After", 60))
                        await asyncio.sleep(min(wait, 60))
                        continue
                    
                    # Retryable server error
                    if r.status_code in RETRYABLE_STATUS:
                        await asyncio.sleep(2 ** attempt)  # 1, 2, 4 seconds
                        continue
                    
                    # Non-retryable error (4xx except 429)
                    return r
                    
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                await asyncio.sleep(2 ** attempt)
                continue
        
        # All retries failed
        raise last_error or Exception("Max retries exceeded")
    
    async def execute(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """Route tool call to appropriate method."""
        methods = {
            "github_get_repo": self._get_repo,
            "github_search_repos": self._search_repos,
            "github_list_my_repos": self._list_my_repos,
            "github_get_file": self._get_file,
            "github_list_files": self._list_files,
            "github_create_issue": self._create_issue,
            "github_list_issues": self._list_issues,
        }
        
        method = methods.get(tool_name)
        if not method:
            return ToolResult(tool_name=tool_name, success=False, error=f"Unknown: {tool_name}")
        
        try:
            return await method(params)
        except Exception as e:
            return ToolResult(tool_name=tool_name, success=False, error=str(e))
    
    async def _get_repo(self, p: Dict) -> ToolResult:
        r = await self._request("GET", f"{self.base_url}/repos/{p['owner']}/{p['repo']}")
        if r.status_code == 200:
            d = r.json()
            return ToolResult(tool_name="github_get_repo", success=True, data={
                "name": d["name"], "description": d.get("description"),
                "stars": d["stargazers_count"], "forks": d["forks_count"],
                "language": d.get("language"), "url": d["html_url"],
            })
        return ToolResult(tool_name="github_get_repo", success=False, error=f"HTTP {r.status_code}")
    
    async def _search_repos(self, p: Dict) -> ToolResult:
        r = await self._request("GET", f"{self.base_url}/search/repositories", params={"q": p["query"], "per_page": p.get("limit", 5)})
        if r.status_code == 200:
            items = r.json().get("items", [])
            repos = [{"name": x["full_name"], "stars": x["stargazers_count"], "url": x["html_url"]} for x in items]
            return ToolResult(tool_name="github_search_repos", success=True, data={"repos": repos})
        return ToolResult(tool_name="github_search_repos", success=False, error=f"HTTP {r.status_code}")

    async def _list_my_repos(self, p: Dict) -> ToolResult:
        """List repositories for the authenticated user (GitHub token)."""
        params = {"per_page": p.get("limit", 30), "sort": p.get("sort", "updated")}
        r = await self._request("GET", f"{self.base_url}/user/repos", params=params)
        if r.status_code == 200:
            items = r.json()
            repos = [{"full_name": x["full_name"], "name": x["name"], "owner": x["owner"]["login"], "private": x.get("private", False), "url": x["html_url"]} for x in items]
            return ToolResult(tool_name="github_list_my_repos", success=True, data={"repos": repos})
        return ToolResult(tool_name="github_list_my_repos", success=False, error=f"HTTP {r.status_code}")
    
    async def _get_file(self, p: Dict) -> ToolResult:
        r = await self._request("GET", f"{self.base_url}/repos/{p['owner']}/{p['repo']}/contents/{p['path']}")
        if r.status_code == 200:
            d = r.json()
            content = base64.b64decode(d.get("content", "")).decode() if d.get("content") else ""
            return ToolResult(tool_name="github_get_file", success=True, data={"path": d["path"], "content": content, "sha": d["sha"]})
        return ToolResult(tool_name="github_get_file", success=False, error=f"HTTP {r.status_code}")
    
    async def _list_files(self, p: Dict) -> ToolResult:
        r = await self._request("GET", f"{self.base_url}/repos/{p['owner']}/{p['repo']}/contents/{p.get('path', '')}")
        if r.status_code == 200:
            d = r.json()
            files = [{"name": f["name"], "type": f["type"]} for f in d] if isinstance(d, list) else []
            return ToolResult(tool_name="github_list_files", success=True, data={"files": files})
        return ToolResult(tool_name="github_list_files", success=False, error=f"HTTP {r.status_code}")
    
    async def _create_issue(self, p: Dict) -> ToolResult:
        r = await self._request("POST", f"{self.base_url}/repos/{p['owner']}/{p['repo']}/issues", json={"title": p["title"], "body": p.get("body", "")})
        if r.status_code == 201:
            d = r.json()
            return ToolResult(tool_name="github_create_issue", success=True, data={"number": d["number"], "url": d["html_url"]})
        return ToolResult(tool_name="github_create_issue", success=False, error=f"HTTP {r.status_code}")
    
    async def _list_issues(self, p: Dict) -> ToolResult:
        r = await self._request("GET", f"{self.base_url}/repos/{p['owner']}/{p['repo']}/issues", params={"state": p.get("state", "open"), "per_page": p.get("limit", 10)})
        if r.status_code == 200:
            issues = [{"number": i["number"], "title": i["title"], "state": i["state"]} for i in r.json()]
            return ToolResult(tool_name="github_list_issues", success=True, data={"issues": issues})
        return ToolResult(tool_name="github_list_issues", success=False, error=f"HTTP {r.status_code}")


github_tools = GitHubTools()
