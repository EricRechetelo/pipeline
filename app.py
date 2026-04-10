from fastapi import FastAPI, HTTPException, Request, status, Form
import secrets

API = FastAPI()


metrics = {
    "requests": 0,
    "errors": 0,
    "failed_logins": 0
}


@API.middleware("http")
async def count_requests_and_errors(request: Request, call_next):
    metrics["requests"] += 1

    try:
        response = await call_next(request)

        if response.status_code >= 500:
            metrics["errors"] += 1

        return response

    except Exception:
        metrics["errors"] += 1
        raise


@API.get("/health")
def health():
    return {"status": "OK"}


@API.post(
    "/login",
    responses={
        200: {"description": "Successful Response"},
        401: {"description": "Invalid credentials"}
    }
)
def login(
    username: str = Form(...),
    password: str = Form(...)
):
    expected_username = "admin"
    expected_password = "admin123"

    valid_user = secrets.compare_digest(username, expected_username)
    valid_password = secrets.compare_digest(password, expected_password)

    if not (valid_user and valid_password):
        metrics["failed_logins"] += 1
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    return {
        "message": "Login successful",
        "access_token": secrets.token_urlsafe(32),
        "token_type": "bearer"
    }


@API.get("/metrics")
def get_metrics():
    return metrics