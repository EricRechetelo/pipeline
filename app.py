from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status, Form
import pymysql
import pymysql.cursors
import secrets
import os


def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "app_user"),
        password=os.getenv("DB_PASSWORD", "app_pass"),
        database=os.getenv("DB_NAME", "secure_api"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )


def reset_metrics():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE metrics
                SET requests = 0,
                    errors = 0,
                    failed_logins = 0
                WHERE id = 1
            """)
        connection.commit()
    finally:
        connection.close()


def get_metrics_from_db():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT requests, errors, failed_logins
                FROM metrics
                WHERE id = 1
            """)
            result = cursor.fetchone()

            if not result:
                return {
                    "requests": 0,
                    "errors": 0,
                    "failed_logins": 0
                }

            return result
    finally:
        connection.close()


def increment_requests():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE metrics
                SET requests = requests + 1
                WHERE id = 1
            """)
        connection.commit()
    finally:
        connection.close()


def increment_errors():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE metrics
                SET errors = errors + 1
                WHERE id = 1
            """)
        connection.commit()
    finally:
        connection.close()


def increment_failed_logins():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE metrics
                SET failed_logins = failed_logins + 1
                WHERE id = 1
            """)
        connection.commit()
    finally:
        connection.close()


def get_user_from_db(username: str):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, username, password
                FROM users
                WHERE username = %s
            """, (username,))
            return cursor.fetchone()
    finally:
        connection.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_metrics()
    yield


API = FastAPI(lifespan=lifespan)


@API.middleware("http")
async def count_requests_and_errors(request: Request, call_next):
    counted_paths = {"/health", "/login", "/metrics"}

    if request.url.path in counted_paths:
        increment_requests()

    try:
        response = await call_next(request)

        if request.url.path in counted_paths and response.status_code >= 500:
            increment_errors()

        return response

    except Exception:
        if request.url.path in counted_paths:
            increment_errors()
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
    user = get_user_from_db(username)

    if not user:
        increment_failed_logins()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    valid_user = secrets.compare_digest(username, user["username"])
    valid_password = secrets.compare_digest(password, user["password"])

    if not (valid_user and valid_password):
        increment_failed_logins()
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
    return get_metrics_from_db()