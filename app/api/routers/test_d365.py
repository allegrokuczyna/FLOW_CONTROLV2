from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
import httpx

from app.core.config import settings

from app.core.auth import get_d365_access_token 

router = APIRouter(prefix="/test-d365", tags=["Testowanie D365 (Raw Data)"])

# testowe æadanie, dowolny endpoint w kurde
class D365TestRequest(BaseModel):
    endpoint_param_name: str = "SalesWithoutShippingType"
    query_values: Optional[List[Any]] = []

@router.post("/get-rows")
async def test_get_rows_from_d365(request_data: D365TestRequest):
    """
    testowe pobieranie danych z kurde
    """
    try:
        # 1. pobranie tokenu
        token = await get_d365_access_token()

        # 2. ednpoint 
        base_url = settings.D365_URL.rstrip('/')
        d365_endpoint = f"{base_url}/api/services/IWSQRDE/QRDE/GetRows"

        # 3. payload z n8n
        payload = {
            "_request": {
                "Message": {
                    "RequestID": "fastapi-sandbox-test",
                    "RequestType": "GetRows",
                    "RequestService": "QRDE",
                    "RequestSource": "FastAPI-Test"
                },
                "EndpointParamName": request_data.endpoint_param_name,
                "QueryValues": request_data.query_values
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(d365_endpoint, json=payload, headers=headers)
            
            
            response.raise_for_status() 
            
            
            return response.json()

    except httpx.HTTPStatusError as exc:
        
        raise HTTPException(
            status_code=exc.response.status_code, 
            detail=f"Błąd silnika D365: {exc.response.text}"
        )
    except Exception as e:
       
        raise HTTPException(status_code=500, detail=str(e))