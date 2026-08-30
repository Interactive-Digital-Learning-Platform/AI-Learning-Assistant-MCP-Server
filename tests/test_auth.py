import pytest

from app.auth import StaticBearerVerifier


async def test_valid_token_accepted():
    verifier = StaticBearerVerifier("s3cret")
    token = await verifier.verify_token("s3cret")
    assert token is not None
    assert token.client_id == "ai-learning-assistant-service"


@pytest.mark.parametrize("bad", ["", "wrong", "s3cre", "s3cret "])
async def test_invalid_token_rejected(bad):
    verifier = StaticBearerVerifier("s3cret")
    assert await verifier.verify_token(bad) is None
