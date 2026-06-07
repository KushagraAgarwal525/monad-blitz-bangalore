from eth_account import Account
from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/address")
async def wallet_address():
    """Return the backend signer address derived from PRIVATE_KEY (never returns the key)."""
    key = settings.private_key.strip()
    if not key:
        raise HTTPException(400, "PRIVATE_KEY is not set in server .env")
    if not key.startswith("0x"):
        key = "0x" + key
    account = Account.from_key(key)
    return {"address": account.address}
