from __future__ import annotations

from urllib.robotparser import RobotFileParser

import httpx


class RobotsPolicy:
    def __init__(self, user_agent: str, client: httpx.AsyncClient):
        self.user_agent = user_agent
        self.client = client
        self._parsers: dict[str, RobotFileParser | None] = {}

    async def allowed(self, url: str) -> bool:
        origin = "/".join(url.split("/", 3)[:3])
        if origin not in self._parsers:
            parser = RobotFileParser(f"{origin}/robots.txt")
            try:
                response = await self.client.get(f"{origin}/robots.txt")
                if response.status_code == 404:
                    parser.parse([])
                    self._parsers[origin] = parser
                elif response.status_code >= 400:
                    self._parsers[origin] = None
                else:
                    parser.parse(response.text.splitlines())
                    self._parsers[origin] = parser
            except httpx.HTTPError:
                # A failed robots request is treated as disallow-all.
                self._parsers[origin] = None
        parser = self._parsers[origin]
        return parser is not None and parser.can_fetch(self.user_agent, url)
