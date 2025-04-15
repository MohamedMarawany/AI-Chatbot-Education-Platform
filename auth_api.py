# pip install fastapi supabase python-jose[cryptography] passlib python-dotenv uvicorn
# python auth_api.py

# File: auth_api.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from typing import Optional

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def setup_database():
    try:
        supabase.postgrest.rpc("execute_sql", {
            "query": """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    created_at TIMESTAMP NOT NULL,
                    last_login TIMESTAMP
                );
            """
        }).execute()

        supabase.postgrest.rpc("execute_sql", {
            "query": "ALTER TABLE users ENABLE ROW LEVEL SECURITY;"
        }).execute()

        try:
            supabase.postgrest.rpc("execute_sql", {
                "query": """
                    CREATE POLICY "Users can only access their own data" ON users
                    FOR ALL TO authenticated
                    USING (auth.uid() = id);
                """
            }).execute()
        except Exception as e:
            if 'already exists' in str(e):
                print("⚠️ Policy already exists, skipping.")
            else:
                raise e

        print("✅ Database schema and policies set up successfully")
    except Exception as e:
        print(f"❌ Database setup error: {str(e)}")
        raise


setup_database()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class UserInDB(UserCreate):
    id: str
    created_at: datetime
    last_login: Optional[datetime] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = supabase.table("users").select("*").eq("email", token_data.email).execute()
    if not user.data:
        raise credentials_exception
    return UserInDB(**user.data[0])

@app.post("/signup", response_model=Token)
async def signup(user: UserCreate):
    try:
        existing_user = supabase.table("users").select("*").eq("email", user.email).execute()
        if existing_user.data:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = get_password_hash(user.password)
        new_user = {
            "email": user.email,
            "password_hash": hashed_password,
            "full_name": user.full_name,
            "created_at": datetime.utcnow().isoformat()  # Convert to ISO 8601 format string
        }
        result = supabase.table("users").insert(new_user).execute()
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
        
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = supabase.table("users").select("*").eq("email", form_data.username).execute()
    if not user.data or not verify_password(form_data.password, user.data[0]["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_data = user.data[0]
    supabase.table("users").update({"last_login": datetime.utcnow().isoformat()}).eq("email", form_data.username).execute()
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_data["email"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserInDB)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    return current_user

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)