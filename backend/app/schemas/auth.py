from pydantic import BaseModel


class AccessTokenOnly(BaseModel):
    """What login and refresh return. The refresh token never appears in a body:
    it is set as an httpOnly cookie, out of reach of page scripts."""

    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Fallback for non-browser clients that cannot hold the cookie."""

    refresh_token: str
