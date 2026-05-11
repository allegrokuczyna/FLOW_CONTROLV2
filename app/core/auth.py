import httpx
from app.core.config import settings

async def get_d365_access_token() -> str:
    auth_url = f"https://login.microsoftonline.com/{settings.D365_TENANT_ID}/oauth2/v2.0/token"
    
    scope = f"{settings.D365_URL.rstrip('/')}/.default"
    
    payload = {
        "grant_type": "client_credentials",
        "client_id": settings.D365_CLIENT_ID,
        "client_secret": settings.D365_CLIENT_SECRET,
        "scope": scope
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(auth_url, data=payload)
        response.raise_for_status()  # Rzuci błędem, jeśli logowanie się nie powiedzie
        return response.json().get("access_token")