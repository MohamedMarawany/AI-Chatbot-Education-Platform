from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the .env file")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize FastAPI app
app = FastAPI()

# Security for JWT token validation
security = HTTPBearer()

# Pydantic models for request/response validation
class UserCreate(BaseModel):
    email: str
    full_name: str
    role: str = "user"

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None

class CourseCreate(BaseModel):
    title: str
    description: str
    subject: str
    level: str
    url: Optional[str] = None
    price: Optional[float] = None
    duration: Optional[str] = None
    is_paid: bool = True
    published: bool = False

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    level: Optional[str] = None
    url: Optional[str] = None
    price: Optional[float] = None
    duration: Optional[str] = None
    is_paid: Optional[bool] = None
    published: Optional[bool] = None

class ChatMessage(BaseModel):
    message: str

class UserCourse(BaseModel):
    user_id: str
    course_id: str

# Dependency to get the current user from JWT token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user = supabase.auth.get_user(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user.user.id
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

# Helper function to check admin status
def check_admin(user_id: str) -> bool:
    try:
        user = supabase.table("users").select("role").eq("id", user_id).execute()
        if not user.data:
            logger.warning(f"User not found: {user_id}")
            return False
        return user.data[0]["role"] == "admin"
    except Exception as e:
        logger.error(f"Error checking admin status for user {user_id}: {str(e)}")
        return False

# API Endpoints
@app.post("/users/", response_model=dict)
async def add_user(user: UserCreate):
    logger.info(f"Received request to add user: {user.email}")
    try:
        # Check if the email already exists in Supabase Auth
        existing_users = supabase.auth.admin.list_users()
        for u in existing_users:
            if u.email == user.email:
                logger.warning(f"Email already registered: {user.email}")
                raise HTTPException(status_code=400, detail=f"Email {user.email} is already registered")

        # Sign up the user with Supabase Auth
        data = user.dict()
        signup_response = supabase.auth.sign_up({"email": user.email, "password": "defaultpassword123"})
        if not signup_response.user:
            logger.error("Failed to sign up user with Supabase Auth")
            raise HTTPException(status_code=400, detail="Failed to sign up user with Supabase Auth")
        data["id"] = str(signup_response.user.id)
        logger.info(f"User signed up with ID: {data['id']}")

        # Insert into users table
        response = supabase.table("users").insert(data).execute()
        if not response.data:
            logger.error("Failed to insert user into Supabase")
            raise HTTPException(status_code=400, detail="Failed to insert user into Supabase")
        logger.info(f"User inserted into Supabase: {response.data[0]}")
        return response.data[0]
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error adding user: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@app.delete("/users/{user_id}")
async def remove_user(user_id: str, current_user_id: str = Depends(get_current_user)):
    if not check_admin(current_user_id):
        raise HTTPException(status_code=403, detail="Only admins can remove users")
    try:
        response = supabase.table("users").delete().eq("id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="User not found")
        # Also delete from Supabase Auth
        supabase.auth.admin.delete_user(user_id)
        return {"message": "User removed successfully"}
    except Exception as e:
        logger.error(f"Error removing user {user_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/users/{user_id}", response_model=dict)
async def get_user_data(user_id: str, current_user_id: str = Depends(get_current_user)):
    if user_id != current_user_id and not check_admin(current_user_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this user's data")
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found")
    return response.data[0]

@app.get("/users/", response_model=List[dict])
async def get_all_users(current_user_id: str = Depends(get_current_user)):
    if not check_admin(current_user_id):
        raise HTTPException(status_code=403, detail="Only admins can view all users")
    response = supabase.table("users").select("*").execute()
    return response.data

@app.post("/courses/", response_model=dict)
async def add_course(course: CourseCreate, current_user_id: str = Depends(get_current_user)):
    if not check_admin(current_user_id):
        raise HTTPException(status_code=403, detail="Only admins can add courses")
    try:
        data = course.dict()
        data["created_by"] = current_user_id
        data["created_at"] = datetime.now().isoformat()
        response = supabase.table("courses").insert(data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to add course")
        return response.data[0]
    except Exception as e:
        logger.error(f"Error adding course: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/courses/{course_id}", response_model=dict)
async def view_course_details(course_id: str):
    response = supabase.table("courses").select("*").eq("course_id", course_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Course not found")
    return response.data[0]

@app.get("/courses/", response_model=List[dict])
async def get_all_courses():
    response = supabase.table("courses").select("*").execute()
    return response.data

@app.put("/courses/{course_id}", response_model=dict)
async def rename_course(course_id: str, course: CourseUpdate, current_user_id: str = Depends(get_current_user)):
    if not check_admin(current_user_id):
        raise HTTPException(status_code=403, detail="Only admins can rename courses")
    data = {k: v for k, v in course.dict().items() if v is not None}
    response = supabase.table("courses").update(data).eq("course_id", course_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Course not found")
    return response.data[0]

@app.get("/courses/{course_id}/assets", response_model=dict)
async def get_course_assets(course_id: str):
    # Placeholder: Implement logic to retrieve course assets (e.g., from Supabase Storage)
    return {"course_id": course_id, "assets": []}

@app.delete("/courses/{course_id}")
async def delete_course(course_id: str, current_user_id: str = Depends(get_current_user)):
    if not check_admin(current_user_id):
        raise HTTPException(status_code=403, detail="Only admins can delete courses")
    response = supabase.table("courses").delete().eq("course_id", course_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Course not found")
    return {"message": "Course deleted successfully"}

@app.post("/user-courses/")
async def add_student_to_course(user_course: UserCourse, current_user_id: str = Depends(get_current_user)):
    if not check_admin(current_user_id):
        raise HTTPException(status_code=403, detail="Only admins can add students to courses")
    try:
        data = user_course.dict()
        data["enrolled_at"] = datetime.now().isoformat()
        response = supabase.table("user_courses").insert(data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to enroll student")
        return response.data[0]
    except Exception as e:
        logger.error(f"Error enrolling student: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chatbot/message/", response_model=dict)
async def post_message_to_chatbot(chat: ChatMessage, current_user_id: str = Depends(get_current_user)):
    try:
        data = {
            "user_id": current_user_id,
            "message": chat.message,
            "created_at": datetime.now().isoformat()
        }
        # Placeholder for chatbot response (you can integrate an AI model here)
        data["response"] = "This is a placeholder response from the chatbot."
        response = supabase.table("chatbot_messages").insert(data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to save message")
        return response.data[0]
    except Exception as e:
        logger.error(f"Error posting chatbot message: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/chatbot/messages/", response_model=List[dict])
async def get_messages_from_chatbot(current_user_id: str = Depends(get_current_user)):
    response = supabase.table("chatbot_messages").select("*").eq("user_id", current_user_id).execute()
    return response.data

# Bonus: Upload file as knowledge to chatbot
@app.post("/chatbot/upload/")
async def upload_file_to_chatbot(file: UploadFile = File(...), current_user_id: str = Depends(get_current_user)):
    try:
        contents = await file.read()
        file_name = f"{current_user_id}/{file.filename}"
        supabase.storage.from_("chatbot-files").upload(file_name, contents)
        return {"message": f"File {file.filename} uploaded successfully"}
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))