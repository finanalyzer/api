import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
import httpx
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

proxy_router = APIRouter()


@proxy_router.api_route("/proxy", methods=["GET", "POST"])
async def generic_proxy(
    request: Request,
    url: str = Query(..., description="Target URL to proxy request to"),
    method: Optional[str] = Query(None, description="HTTP method (GET or POST, defaults to request method)"),
):
    """
    Generic proxy endpoint that forwards requests to any URL.
    This bypasses CORS restrictions by making requests server-side.
    
    Query Parameters:
    - url: The target URL to proxy to (required)
    - method: HTTP method to use (GET or POST, optional - defaults to actual method)
    
    For GET requests: All other query params are forwarded as query string parameters
    For POST requests: Body should be JSON with optional 'body' and 'headers' fields
    """
    try:
        # Determine the HTTP method
        http_method = method.upper() if method else request.method
        if http_method not in ("GET", "POST"):
            raise HTTPException(
                status_code=400,
                detail="Only GET and POST methods are supported"
            )
        
        # Validate URL
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail="URL must start with http:// or https://"
            )
        
        headers = {
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            if http_method == "GET":
                # For GET requests, forward query parameters from the incoming request
                query_params = dict(request.query_params)
                # Remove 'url' and 'method' from query params as they're not part of the target URL
                query_params.pop("url", None)
                query_params.pop("method", None)
                
                # Build the full URL for logging
                full_url = f"{url}?{urlencode(query_params)}" if query_params else url
                logger.info(f"[PROXY DEBUG] GET request to: {full_url}")
                logger.info(f"[PROXY DEBUG] Headers: {headers}")
                
                response = await client.get(
                    url,
                    headers=headers,
                    params=query_params if query_params else None,
                )
            else:  # POST
                # For POST requests, try to get body from JSON
                body = await request.json()
                
                # Extract body content and custom headers
                body_content = body.get("body")
                custom_headers = body.get("headers", {})
                
                # Merge custom headers
                headers.update(custom_headers)
                
                logger.info(f"[PROXY DEBUG] POST request to: {url}")
                logger.info(f"[PROXY DEBUG] Body: {body}")
                
                response = await client.post(
                    url,
                    headers=headers,
                    json=body_content if body_content else body,
                )
            
            logger.info(f"[PROXY DEBUG] Response status: {response.status_code}")
            logger.info(f"[PROXY DEBUG] Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            # Try to return JSON if possible, otherwise return text
            content_type = response.headers.get("content-type", "")
            response_text = response.text
            
            # Check if response looks like HTML (error page)
            if "<html" in response_text.lower() or "<!doctype" in response_text.lower():
                logger.warning(f"[PROXY DEBUG] Response appears to be HTML, not JSON. First 500 chars: {response_text[:500]}")
                return JSONResponse(
                    content={
                        "content": response_text,
                        "contentType": content_type,
                        "warning": "Response appears to be HTML, not JSON",
                        "requestedUrl": url,
                        "statusCode": response.status_code
                    },
                    status_code=response.status_code,
                )
            
            # Try to parse as JSON regardless of content-type (East Money returns text/plain)
            try:
                json_data = response.json()
                logger.info(f"[PROXY] Successfully parsed JSON, type: {type(json_data)}")
                if isinstance(json_data, dict):
                    logger.info(f"[PROXY] Response keys: {json_data.keys()}")
                
                # Handle OpenBB wrapper structure: extract body.result.data
                # If response has type="RESPONSE" with body containing result.data, extract only data
                if isinstance(json_data, dict):
                    if json_data.get("type") == "RESPONSE" and "body" in json_data:
                        body = json_data["body"]
                        logger.info("[PROXY] Found OpenBB wrapper structure, extracting body")
                        if isinstance(body, dict) and "result" in body:
                            result = body["result"]
                            logger.info(f"[PROXY] Found result, keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
                            if isinstance(result, dict) and "data" in result:
                                data = result["data"]
                                logger.info(f"[PROXY] Extracted data, type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
                                return data
                        # If body exists but no result.data, return body
                        logger.info("[PROXY] Returning body without result.data extraction")
                        return body
                    elif "result" in json_data and "data" in json_data.get("result", {}):
                        # East Money API format: {"version": "...", "result": {"pages": 1, "data": [...]}}
                        result = json_data["result"]
                        data = result.get("data", [])
                        logger.info(f"[PROXY] Extracted East Money data, type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
                        return data
                
                logger.info(f"[PROXY] Returning raw JSON, type: {type(json_data)}")
                return json_data
            except Exception as json_error:
                logger.warning(f"[PROXY] Failed to parse JSON: {json_error}")
                return JSONResponse(
                    content={"content": response_text, "contentType": content_type},
                    status_code=response.status_code,
                )
                
    except httpx.TimeoutException:
        logger.error(f"Proxy timeout for URL: {url}")
        raise HTTPException(status_code=504, detail="Request timed out")
    except httpx.HTTPStatusError as e:
        logger.error(f"Proxy HTTP error for URL {url}: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Error from target server: {e.response.text}")
    except Exception as e:
        logger.error(f"Proxy error for URL {url}: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")
