from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from typing import Optional
from shared.auth import AuthUtils

app = FastAPI(title="API Gateway", description="Unified API Gateway for Autosalon microservices")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs from environment
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8002")
FINANCING_SERVICE_URL = os.getenv("FINANCING_SERVICE_URL", "http://localhost:8003")
INSURANCE_SERVICE_URL = os.getenv("INSURANCE_SERVICE_URL", "http://localhost:8004")

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    "", # Root path for API Gateway
    "auth/",
    "auth/register",
    "auth/token",
    "auth/refresh",
    "auth/health",
    "auth/stats",
    "payment/",
    "payment/health",
    "payment/stats",
    "financing/",
    "financing/health",
    "financing/stats",
    "insurance/",
    "insurance/health",
    "insurance/stats",
    "health"
]

@app.get("/")
async def read_root():
    """Get API Gateway status with statistics from all services"""
    stats = {
        "message": "API Gateway is running",
        "version": "1.0.0",
        "services": {}
    }

    # Collect statistics from all services
    services = [
        ("auth", AUTH_SERVICE_URL),
        ("payment", PAYMENT_SERVICE_URL),
        ("financing", FINANCING_SERVICE_URL),
        ("insurance", INSURANCE_SERVICE_URL)
    ]

    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, service_url in services:
            try:
                response = await client.get(f"{service_url}/stats")
                if response.status_code == 200:
                    stats["services"][service_name] = response.json()
                else:
                    stats["services"][service_name] = {"error": f"HTTP {response.status_code}"}
            except Exception as e:
                stats["services"][service_name] = {"error": str(e)}

    return stats

async def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token"""
    return AuthUtils.verify_token(token)

async def authenticate_request(request: Request) -> Optional[dict]:
    """Extract and verify authentication token from request"""
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ")[1]
    return await verify_token(token)

async def check_permissions(user_data: dict, required_roles: list = None) -> bool:
    """Check if user has required permissions"""
    if not user_data:
        return False

    if not required_roles:
        return True

    user_role = user_data.get("role")
    return user_role in required_roles

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway_handler(request: Request, path: str):
    """Main gateway handler that routes requests to appropriate services"""

    # Normalize path - remove leading slash
    path = path.lstrip("/")

    # Health check
    if path == "health":
        return {"status": "healthy", "service": "api-gateway"}

    # Authenticate request if not public endpoint
    user_data = None
    
    is_public_endpoint_match = False
    for endpoint in PUBLIC_ENDPOINTS:
        if path == endpoint or path.startswith(endpoint + "/"):
            is_public_endpoint_match = True
            break

    if not is_public_endpoint_match:
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )

        token = authorization.split(" ")[1]
        user_data = AuthUtils.verify_token(token)
        if not user_data:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"}
            )
    else:
        # If it's a public endpoint, we still need to initialize user_data for permission checks in downstream services
        # For health checks, user_data is not strictly needed, but for other public endpoints that might require
        # some user context (e.g., getting public user profiles), we'd get it here if a token is present.
        # For now, if it's public and no token, user_data remains None.
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_data = AuthUtils.verify_token(token)

    # Route to appropriate service
    service_url = None
    forward_path = ""

    if path.startswith("auth/"):
        service_url = AUTH_SERVICE_URL
        forward_path = path[len("auth/"):]
    elif path.startswith("payment/"):
        service_url = PAYMENT_SERVICE_URL
        forward_path = path[len("payment/"):]
        # Check permissions for payment operations, skip for health checks and root path
        if forward_path not in ["health", ""] and not await check_permissions(user_data, ["client", "manager", "admin"]):
            return JSONResponse(
                status_code=403,
                content={"detail": "Insufficient permissions"}
            )
    elif path.startswith("financing/"):
        service_url = FINANCING_SERVICE_URL
        forward_path = path[len("financing/"):]
        # Skip permissions check for health endpoint and root path
        if forward_path not in ["health", ""] and not await check_permissions(user_data, ["client", "manager", "admin"]):
            return JSONResponse(
                status_code=403,
                content={"detail": "Insufficient permissions"}
            )
    elif path.startswith("insurance/"):
        service_url = INSURANCE_SERVICE_URL
        forward_path = path[len("insurance/"):]
        # Skip permissions check for health endpoint and root path
        if forward_path not in ["health", ""] and not await check_permissions(user_data, ["client", "manager", "admin"]):
            return JSONResponse(
                status_code=403,
                content={"detail": "Insufficient permissions"}
            )
    else:
        return JSONResponse(
            status_code=404,
            content={"detail": "Service not found"}
        )

    # Forward request to service
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{service_url}/{forward_path}"

            # Prepare request data
            headers = dict(request.headers)
            # Remove host header to avoid conflicts
            headers.pop("host", None)

            # Forward the request
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
                params=request.query_params
            )

            # Return response from service
            return JSONResponse(
                status_code=response.status_code,
                content=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
            )

    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"detail": "Service timeout"}
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Service unavailable: {str(e)}"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal error: {str(e)}"}
        )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "api-gateway"}