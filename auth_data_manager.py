# auth_data_manager.py
from supabase import create_client, Client
import os
from typing import Optional, Dict, Any
from datetime import datetime

class SupabaseAuthManager:
    def __init__(self):
        """Initialize Supabase client"""
        self.url: str = os.environ.get("SUPABASE_URL")
        self.key: str = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = create_client(self.url, self.key)
        
    # Authentication Methods
    def sign_up(self, email: str, password: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a new user with email/password
        Args:
            email: User email
            password: User password
            user_data: Dictionary containing user profile data
        Returns:
            Dictionary with user data
        """
        try:
            # Create auth user
            auth_response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": user_data.get("full_name"),
                        "avatar_url": user_data.get("avatar_url", ""),
                        "learning_preferences": user_data.get("preferences", {})
                    }
                }
            })
            
            if auth_response.user is None:
                raise Exception("User creation failed")
            
            # Create profile in public.users table
            profile_data = {
                "user_id": auth_response.user.id,
                "email": email,
                "full_name": user_data.get("full_name"),
                "learning_level": user_data.get("learning_level", "beginner"),
                "preferences": user_data.get("preferences", {}),
                "created_at": datetime.now().isoformat()
            }
            
            profile_response = self.supabase.table("users").insert(profile_data).execute()
            
            if profile_response.error:
                raise Exception(profile_response.error.message)
            
            return {
                "user": auth_response.user,
                "profile": profile_response.data[0] if profile_response.data else None
            }
            
        except Exception as e:
            print(f"[Signup Error] {str(e)}")
            raise

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate a user with email/password
        Args:
            email: User email
            password: User password
        Returns:
            Dictionary with session data
        """
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user is None:
                raise Exception("Authentication failed")
            
            # Update last login
            update_response = self.supabase.table("users").update({
                "last_login": datetime.now().isoformat()
            }).eq("user_id", response.user.id).execute()
            
            if update_response.error:
                print(f"[Update Last Login Error] {update_response.error.message}")
            
            return {
                "user": response.user,
                "session": response.session
            }
            
        except Exception as e:
            print(f"[Signin Error] {str(e)}")
            raise

    def sign_out(self) -> bool:
        """Sign out the current user"""
        try:
            response = self.supabase.auth.sign_out()
            return True
        except Exception as e:
            print(f"[Signout Error] {str(e)}")
            return False

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get the currently authenticated user"""
        try:
            response = self.supabase.auth.get_user()
            return response.user
        except Exception as e:
            print(f"[Get User Error] {str(e)}")
            return None

    # Data Management Methods
    def save_learning_progress(self, user_id: str, course_id: str, progress: float, metadata: Dict[str, Any] = {}) -> bool:
        """
        Save user's learning progress
        Args:
            user_id: User ID
            course_id: Course identifier
            progress: Completion percentage (0-100)
            metadata: Additional progress data
        Returns:
            True if successful
        """
        try:
            response = self.supabase.table("learning_progress").upsert({
                "user_id": user_id,
                "course_id": course_id,
                "completion_percentage": progress,
                "last_accessed": datetime.now().isoformat(),
                "data": metadata
            }).execute()
            
            if response.error:
                raise Exception(response.error.message)
            
            return True
        except Exception as e:
            print(f"[Save Progress Error] {str(e)}")
            return False

    def get_learning_progress(self, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user's learning progress
        Args:
            user_id: User ID
            course_id: Course identifier
        Returns:
            Dictionary with progress data or None
        """
        try:
            response = self.supabase.table("learning_progress")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("course_id", course_id)\
                .single()\
                .execute()
            
            return response.data
        except Exception as e:
            print(f"[Get Progress Error] {str(e)}")
            return None

    def save_chat_interaction(self, user_id: str, session_id: str, message: str, response: str, metadata: Dict[str, Any] = {}) -> bool:
        """
        Store chatbot interaction
        Args:
            user_id: User ID
            session_id: Chat session identifier
            message: User message
            response: Bot response
            metadata: Additional interaction data
        Returns:
            True if successful
        """
        try:
            chat_data = {
                "user_id": user_id,
                "session_id": session_id,
                "message": message,
                "response": response,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata
            }
            
            result = self.supabase.table("chat_interactions").insert(chat_data).execute()
            
            if result.error:
                raise Exception(result.error.message)
            
            return True
        except Exception as e:
            print(f"[Save Chat Error] {str(e)}")
            return False

    def get_chat_history(self, user_id: str, session_id: str, limit: int = 100) -> Optional[list]:
        """
        Retrieve chat history
        Args:
            user_id: User ID
            session_id: Chat session identifier
            limit: Maximum number of messages to return
        Returns:
            List of chat messages or None
        """
        try:
            response = self.supabase.table("chat_interactions")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("session_id", session_id)\
                .order("timestamp", desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data
        except Exception as e:
            print(f"[Get Chat History Error] {str(e)}")
            return None

    # OAuth Methods (Bonus)
    def get_oauth_providers(self) -> list:
        """Get available OAuth providers"""
        return ['google', 'github', 'gitlab', 'bitbucket']  # Supabase supported providers

    def sign_in_with_oauth(self, provider: str, redirect_url: str = None) -> str:
        """
        Initiate OAuth sign-in
        Args:
            provider: OAuth provider name
            redirect_url: Callback URL
        Returns:
            Authentication URL
        """
        try:
            if redirect_url is None:
                redirect_url = f"{os.environ.get('BASE_URL')}/auth/callback"
                
            response = self.supabase.auth.sign_in_with_oauth({
                "provider": provider,
                "options": {
                    "redirect_to": redirect_url
                }
            })
            
            return response.url
        except Exception as e:
            print(f"[OAuth Error] {str(e)}")
            raise

    # Helper Methods
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.get_current_user() is not None

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile data"""
        try:
            response = self.supabase.table("users")\
                .select("*")\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            return response.data
        except Exception as e:
            print(f"[Get Profile Error] {str(e)}")
            return None

# Example Usage
if __name__ == "__main__":
    # Initialize environment variables (in production, use .env or config)
    # os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    os.environ["SUPABASE_URL"] = "your-supabase-url"
    os.environ["SUPABASE_KEY"] = "your-supabase-key"
    os.environ["BASE_URL"] = "http://localhost:8000"
    
    auth_manager = SupabaseAuthManager()
    
    # Example sign up
    try:
        new_user = auth_manager.sign_up(
            email="test@example.com",
            password="securepassword123",
            user_data={
                "full_name": "Test User",
                "learning_level": "beginner",
                "preferences": {"theme": "dark", "language": "en"}
            }
        )
        print("Sign up successful:", new_user)
    except Exception as e:
        print("Sign up failed:", str(e))
    
    # Example sign in
    try:
        user_session = auth_manager.sign_in(
            email="test@example.com",
            password="securepassword123"
        )
        print("Sign in successful:", user_session)
    except Exception as e:
        print("Sign in failed:", str(e))
    
    # Example data operations
    if auth_manager.is_authenticated():
        current_user = auth_manager.get_current_user()
        print("Current user:", current_user)
        
        # Save learning progress
        auth_manager.save_learning_progress(
            user_id=current_user.id,
            course_id="python101",
            progress=25.5,
            metadata={"last_lesson": "variables"}
        )
        
        # Save chat interaction
        auth_manager.save_chat_interaction(
            user_id=current_user.id,
            session_id="session123",
            message="How do I use functions?",
            response="Here's how functions work...",
            metadata={"context": "python_functions"}
        )
        
        # Sign out
        auth_manager.sign_out()
        print("User signed out")