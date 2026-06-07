import uvicorn
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, EmailStr

app = FastAPI(
    title="Demo API - API Sentinel",
    description="A simple mock API to test API Sentinel health checks and contract validation.",
    version="1.0.0"
)

class LoginRequest(BaseModel):
    email: str
    password: str

@app.get("/health")
def health_check():
    """Returns a simple health status."""
    return {"status": "ok"}

@app.get("/users")
def get_users():
    """Returns a list of mock users."""
    return {
        "users": [
            {"id": 1, "name": "Ege"},
            {"id": 2, "name": "Derin"}
        ]
    }

@app.post("/login")
def login(payload: LoginRequest):
    """
    Accepts credentials and returns a dummy access token 
    along with user metadata.
    """
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
        
    return {
        "token": "demo-token-xyz-123456789",
        "user": {
            "email": payload.email,
            "role": "admin"
        }
    }

if __name__ == "__main__":
    # Runs the uvicorn server directly if executed
    uvicorn.run("demo_api:app", host="127.0.0.1", port=8000, reload=True)
