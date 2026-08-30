import hmac
import logging

from fastmcp.server.auth.auth import TokenVerifier
from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)


class StaticBearerVerifier(TokenVerifier):
    """Constant-time shared-secret bearer verification for service-to-service calls.

    Mirrors the AI Learning Assistant's ``X-Internal-Key`` / ``hmac.compare_digest``
    pattern. The single valid token is the deployment secret shared with the
    assistant (its ``MCP_SERVER_AUTH_TOKEN``). Transport security (TLS) is the
    gateway's / mesh's responsibility.
    """

    def __init__(self, token: str, *, client_id: str = "ai-learning-assistant-service") -> None:
        super().__init__()
        self._token = token
        self._client_id = client_id

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not hmac.compare_digest(token, self._token):
            logger.warning("Rejected MCP request: missing or invalid bearer token")
            return None

        return AccessToken(
            token=token,
            client_id=self._client_id,
            scopes=[],
        )
