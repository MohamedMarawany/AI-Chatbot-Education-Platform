# python -m venv venv
# venv\Scripts\activate
# deactivate

# app.py

import streamlit as st
from rag_pipeline import RAGPipeline  # Import your RAG pipeline
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
import tempfile
import logging  # Added for logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Supabase client and store in session state
def init_supabase():
    if 'supabase' not in st.session_state:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            st.error("Supabase credentials not found in environment variables")
            return None
        st.session_state.supabase = create_client(url, key)
    return st.session_state.supabase

# Initialize Supabase client
supabase = init_supabase()
if not supabase:
    st.error("Supabase connection failed")
    st.stop()

# Reapply session on every rerun if the user is signed in
if 'auth' in st.session_state and st.session_state.auth.get('access_token'):
    try:
        supabase.auth.set_session(
            access_token=st.session_state.auth['access_token'],
            refresh_token=st.session_state.auth['refresh_token']
        )
        current_user = supabase.auth.get_user()
        logger.info(f"Current authenticated user: {current_user.user.email if current_user.user else 'None'}")
    except Exception as e:
        st.error(f"Failed to reapply session: {str(e)}")

# Session state management
def init_session_state():
    if 'auth' not in st.session_state:
        st.session_state.auth = {
            'access_token': None,
            'refresh_token': None,
            'user': None,
            'user_data': None
        }
    if 'page' not in st.session_state:
        st.session_state.page = "Sign In"

init_session_state()

# Test Supabase connection
response = supabase.table("courses").select("*").limit(5).execute()
logger.info(f"Initial Supabase test query response: {response.data}")

def check_admin_status():
    if not st.session_state.auth.get('user'):
        st.write("Debug: No user in session state")
        return False
    user_email = st.session_state.auth['user'].email
    user_id = st.session_state.auth['user'].id
    # st.write(f"Debug: User email: {user_email}, User ID: {user_id}")
    try:
        user_data = supabase.table("users").select("role").eq("email", user_email).execute()
        # st.write(f"Debug: Supabase response: {user_data.data}")
        if not user_data.data:
            st.write("Debug: No user data found in Supabase for this email")
            return False
        role = user_data.data[0].get("role")
        st.write(f"Debug: User role: {role}")
        return role == "admin"
    except Exception as e:
        st.write(f"Debug: Supabase query error: {str(e)}")
        return False

# Authentication Functions
def handle_sign_up(email, password, full_name=None):
    try:
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name or email.split('@')[0]
                }
            }
        })
        
        if not auth_response.user:
            st.error("User creation failed")
            return False
            
        profile_data = {
            "id": auth_response.user.id,
            "email": email,
            "full_name": full_name or email.split('@')[0],
            "created_at": datetime.now().isoformat(),
            "role": "user"
        }
        
        profile_response = supabase.table("users").insert(profile_data).execute()
        
        if not profile_response.data:
            st.error("Profile creation failed")
            return False
            
        return True
        
    except Exception as e:
        st.error(f"Sign up error: {str(e)}")
        return False

def handle_sign_in(email, password):
    try:
        logger.info(f"Attempting to sign in user with email: {email}")
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if not auth_response or not auth_response.session:
            logger.error("Sign-in failed: Invalid credentials or authentication failed")
            st.error("Invalid credentials or authentication failed")
            return False
            
        user_id = auth_response.user.id
        logger.info(f"User signed in successfully, user_id: {user_id}")
        
        # Check if user exists in the users table
        user_data_response = supabase.table("users") \
            .select("*") \
            .eq("id", user_id) \
            .execute()
        
        user_metadata = auth_response.user.user_metadata if auth_response.user.user_metadata else {}
        if user_data_response.data:
            user_data = user_data_response.data[0]
            logger.info(f"User found in users table: {user_data}")
        else:
            # User not found in users table, create a new profile
            logger.info(f"User not found in users table, creating profile for user_id: {user_id}")
            user_data = {
                "id": user_id,
                "email": email,
                "full_name": user_metadata.get('full_name', email.split('@')[0]),
                "created_at": datetime.now().isoformat(),
                "role": "user",  # Default role
                "last_login": datetime.now().isoformat()
                # Do not include password_hash since it's not needed
            }
            try:
                insert_response = supabase.table("users").insert(user_data).execute()
                if insert_response.data:
                    logger.info(f"Successfully created user profile: {insert_response.data}")
                    user_data = insert_response.data[0]
                else:
                    logger.error(f"Failed to create user profile, response: {insert_response}")
                    st.error("Failed to create user profile in database")
                    return False
            except Exception as e:
                logger.error(f"Error creating user profile: {str(e)}")
                st.error(f"Error creating user profile: {str(e)}")
                return False
        
        st.session_state.auth = {
            'access_token': auth_response.session.access_token,
            'refresh_token': auth_response.session.refresh_token,
            'user': auth_response.user,
            'user_data': user_data
        }
        
        supabase.auth.set_session(
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token
        )
        
        try:
            update_response = supabase.table("users").update({
                "last_login": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            logger.info(f"Updated last_login for user_id: {user_id}, response: {update_response.data}")
        except Exception as e:
            logger.error(f"Error updating last_login: {str(e)}")
        
        logger.info("Sign-in completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Sign in error: {str(e)}")
        st.error(f"Sign in error: {str(e)}")
        return False

def handle_sign_out():
    try:
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Sign out error: {str(e)}")

# Course Functions
def get_all_courses(page=1, page_size=10):
    try:
        offset = (page - 1) * page_size
        logger.info(f"Fetching courses: page={page}, page_size={page_size}, offset={offset}")
        response = supabase.table("courses")\
            .select("*")\
            .range(offset, offset + page_size - 1)\
            .execute()
        logger.info(f"Supabase response: {response}")
        courses = response.data if response.data else []
        logger.info(f"Retrieved {len(courses)} courses")
        return courses
    except Exception as e:
        logger.error(f"Error loading courses: {str(e)}")
        st.error(f"Error loading courses: {str(e)}")
        return []

def add_course_page():
    st.subheader("📝 Add New Course")
    
    if not check_admin_status():
        st.error("Only admins can add courses")
        return
    
    with st.form("add_course_form"):
        course_title = st.text_input("Course Title*", placeholder="e.g., HTML & CSS")
        description = st.text_area("Description*", placeholder="Enter course description")
        subject = st.text_input("Subject*", placeholder="e.g., Web Development")
        level = st.selectbox("Level*", ["All Levels", "Beginner Level", "Intermediate Level", "Expert Level"])
        
        submit_button = st.form_submit_button("Add Course")
        
        if submit_button:
            if not (course_title and description and subject):
                st.error("Please fill in all required fields")
            else:
                try:
                    course_data = {
                        "title": course_title,
                        "description": description,
                        "subject": subject,
                        "level": level,
                        "created_by": st.session_state.auth['user'].id
                    }
                    response = supabase.table("courses").insert(course_data).execute()
                    if response.data:
                        st.success(f"Course '{course_title}' added successfully!")
                    else:
                        st.error("Failed to add course")
                except Exception as e:
                    st.error(f"Failed to add course: {str(e)}")

def get_user_courses(user_id):
    try:
        res = supabase.table("user_courses")\
            .select("*, courses!inner(*)")\
            .eq("user_id", user_id)\
            .execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error fetching user courses: {str(e)}")
        return []

def handle_enroll_course(course_id):
    try:
        if not st.session_state.get('auth') or not st.session_state.auth.get('user'):
            st.warning("Please sign in to enroll")
            return
        
        user_id = st.session_state.auth['user'].id
        
        try:
            course_id_int = int(course_id)
        except ValueError:
            st.error(f"Invalid course ID: {course_id}. Must be an integer.")
            return
        
        existing = supabase.table("user_courses")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("course_id", course_id_int)\
            .execute()
        
        if existing.data:
            st.warning("You're already enrolled in this course")
            return
        
        response = supabase.table("user_courses").insert({
            "user_id": user_id,
            "course_id": course_id_int,
            "progress": 0
        }).execute()
        
        if response.data:
            st.success("Successfully enrolled!")
            st.rerun()
        else:
            st.error("Enrollment failed")
    except Exception as e:
        st.error(f"Enrollment error: {str(e)}")

# Admin Functions
def admin_add_user(email, password, full_name, role="user"):
    try:
        if st.session_state.auth['user_data'].get('role') != 'admin':
            st.error("Only admins can add users")
            return False
        
        auth_response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": full_name
            }
        })
        
        if not auth_response.user:
            st.error("User creation failed")
            return False
        
        profile_data = {
            "id": auth_response.user.id,
            "email": email,
            "full_name": full_name,
            "created_at": datetime.now().isoformat(),
            "role": role
        }
        
        profile_response = supabase.table("users").insert(profile_data).execute()
        
        if not profile_response.data:
            st.error("Profile creation failed")
            return False
        
        st.success(f"User {email} added successfully!")
        return True
        
    except Exception as e:
        st.error(f"Error adding user: {str(e)}")
        return False

def admin_delete_user(user_id):
    try:
        if st.session_state.auth['user_data'].get('role') != 'admin':
            st.error("Only admins can delete users")
            return False
        
        supabase.auth.admin.delete_user(user_id)
        
        supabase.table("users").delete().eq("id", user_id).execute()
        
        supabase.table("user_courses").delete().eq("user_id", user_id).execute()
        
        st.success("User deleted successfully!")
        return True
        
    except Exception as e:
        st.error(f"Error deleting user: {str(e)}")
        return False

def admin_delete_course(course_id):
    try:
        if st.session_state.auth['user_data'].get('role') != 'admin':
            st.error("Only admins can delete courses")
            return False
        
        try:
            course_id_int = int(course_id)
        except ValueError:
            st.error(f"Invalid course ID: {course_id}")
            return False
        
        supabase.table("courses").delete().eq("course_id", course_id_int).execute()
        
        supabase.table("user_courses").delete().eq("course_id", course_id_int).execute()
        
        st.success("Course deleted successfully!")
        return True
        
    except Exception as e:
        st.error(f"Error deleting course: {str(e)}")
        return False

# UI Components
def show_sidebar():
    with st.sidebar:
        st.title("Learning Platform")
        
        if st.session_state.auth.get('user'):
            full_name = st.session_state.auth['user_data'].get('full_name', 'User')
            st.write(f"Welcome, {full_name}")
            
            pages = ["Dashboard", "View Courses", "My Courses", "Chat Assistant"]
            if check_admin_status():
                pages.append("Admin Panel")
            else:
                pages.append("Add Course")
            st.session_state.page = st.radio("Menu", pages)
            
            if st.button("Sign Out"):
                handle_sign_out()
            
            if st.button("Clear Session (Debug)"):
                st.session_state.clear()
                st.rerun()
        else:
            st.session_state.page = st.radio("Menu", ["Sign In", "Sign Up"])

def show_chat_assistant():
    st.title("Chat Assistant")
    
    if not st.session_state.auth.get('user'):
        st.warning("Please sign in to use the Chat Assistant")
        return
    
    user_id = st.session_state.auth['user'].id
    
    # Display available courses
    st.subheader("Available Courses")
    courses = get_all_courses(page=1, page_size=5)
    if courses:
        for course in courses:
            st.write(f"- **{course['title']}** ({course['subject']}, {course['level']})")
    else:
        st.info("No courses available yet.")
    
    # Initialize RAG Pipeline
    if 'rag_pipeline' not in st.session_state:
        try:
            st.session_state.rag_pipeline = RAGPipeline(supabase_client=supabase)
            st.session_state.rag_pipeline.setup_agents()
            st.success("Chat Assistant initialized successfully!")
        except Exception as e:
            logger.error(f"Failed to initialize Chat Assistant: {str(e)}")
            st.error(f"Failed to initialize Chat Assistant: {str(e)}")
            return

    # Chat interface
    st.subheader("Talk to Your Learning Assistant")
    user_input = st.text_input(
        "Ask anything, from course topics to general knowledge!",
        placeholder="E.g., 'Explain Artificial Intelligence to a six-year-old'",
        key="chat_assistant_input"
    )

    if user_input:
        with st.spinner("Thinking..."):
            try:
                user_courses = get_user_courses(user_id)
                course_context = "\n".join([
                    f"Course: {course['courses']['title']}\n"
                    f"Subject: {course['courses']['subject']}\n"
                    f"Description: {course['courses']['description']}"
                    for course in user_courses
                ]) if user_courses else "The user has not enrolled in any courses yet."
                
                full_query = f"User's enrolled courses:\n{course_context}\n\nQuestion: {user_input}"
                
                response = st.session_state.rag_pipeline.basic_rag_chain(full_query, user_id=user_id)
                st.write(f"**Chat Assistant**: {response}")
                
                with st.expander("Provide Feedback"):
                    feedback = st.radio(
                        "Was this answer helpful?",
                        ("Yes", "No"),
                        key=f"feedback_{user_input}"
                    )
                    if feedback == "No":
                        feedback_text = st.text_area(
                            "Please tell us how we can improve:",
                            key=f"feedback_text_{user_input}"
                        )
                        if st.button("Submit Feedback", key=f"submit_feedback_{user_input}"):
                            if len(feedback_text) > 1000:
                                st.error("Feedback is too long (max 1000 characters)")
                            else:
                                supabase.table("feedback").insert({
                                    "user_id": user_id,
                                    "query": user_input[:500],
                                    "response": response[:2000],
                                    "feedback": feedback_text,
                                    "created_at": datetime.now().isoformat()
                                }).execute()
                                st.success("Thank you for your feedback!")
            except Exception as e:
                logger.error(f"Error processing question: {str(e)}")
                st.error(f"Error processing question: {str(e)}")

def show_sign_in():
    st.title("Sign In")
    with st.form("sign_in_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Sign In"):
            if handle_sign_in(email, password):
                st.success("Signed in successfully!")
                st.session_state.page = "Dashboard"
                st.rerun()
            else:
                st.error("Invalid credentials")

def show_sign_up():
    st.title("Sign Up")
    with st.form("sign_up_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        full_name = st.text_input("Full Name (optional)")
        
        if st.form_submit_button("Create Account"):
            if handle_sign_up(email, password, full_name):
                st.success("Account created! Please sign in.")
                st.session_state.page = "Sign In"
                st.rerun()
            else:
                st.error("Account creation failed")

def show_add_course():
    st.subheader("📝 Add New Course")
    
    if not check_admin_status():
        st.error("Only admins can add courses")
        return
    
    with st.form("add_course_form"):
        course_title = st.text_input("Course Title*", placeholder="e.g., HTML & CSS")
        description = st.text_area("Description*", placeholder="Enter course description")
        subject = st.text_input("Subject*", placeholder="e.g., Web Development")
        level = st.selectbox("Level*", ["All Levels", "Beginner Level", "Intermediate Level", "Expert Level"])
        
        url = st.text_input("Course URL", placeholder="e.g., https://example.com/course")
        price = st.number_input("Price", min_value=0.0, value=0.0, step=0.01)
        duration = st.text_input("Duration", placeholder="e.g., 4 weeks")
        is_paid = st.checkbox("Is Paid Course?", value=True)
        published = st.checkbox("Publish Now?", value=False)
        
        submit_button = st.form_submit_button("Add Course")
        
        if submit_button:
            if not (course_title and description and subject):
                st.error("Please fill in all required fields")
            else:
                try:
                    course_data = {
                        "title": course_title,
                        "description": description,
                        "subject": subject,
                        "level": level,
                        "created_by": st.session_state.auth['user'].id,
                        "url": url if url else None,
                        "price": price if price > 0 else None,
                        "duration": duration if duration else None,
                        "is_paid": is_paid,
                        "published": published,
                        "subscribers": 0,
                        "created_at": datetime.now().isoformat()
                    }
                    response = supabase.table("courses").insert(course_data).execute()
                    if response.data:
                        st.success(f"Course '{course_title}' added successfully!")
                    else:
                        st.error("Failed to add course: No data returned from Supabase")
                except Exception as e:
                    st.error(f"Failed to add course: {str(e)}")

def show_view_courses():
    st.title("Available Courses")
    
    try:
        courses = get_all_courses()
    except Exception as e:
        st.error(f"Failed to fetch courses: {str(e)}")
        return
    
    if not courses:
        st.info("No courses available yet.")
        return
    
    raw_subjects = []
    for course in courses:
        subject = course.get('subject', course.get('Subject', course.get('SUBJECT', None)))
        if subject is None or (isinstance(subject, str) and subject.strip() == ""):
            subject = 'Missing'
        raw_subjects.append(subject)
    
    unique_subjects = sorted({subject for subject in raw_subjects if subject != 'Missing'})
    
    items_per_page = 10
    page_number = st.number_input(
        "Page Number", min_value=1, value=1, step=1, key="course_page"
    )
    start_idx = (page_number - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_courses = courses[start_idx:end_idx]
    
    st.write(f"Showing courses {start_idx + 1} to {min(end_idx, len(courses))} of {len(courses)}")
    
    col1, col2 = st.columns(2)
    with col1:
        subjects = ["All"] + unique_subjects
        category_filter = st.selectbox("Filter by Subject", subjects, key="subject_filter")
    
    with col2:
        levels = ["All"] + sorted(
            {course.get('level', 'N/A') for course in courses if course.get('level')}
        )
        level_filter = st.selectbox("Filter by Level", levels, key="level_filter")
    
    filtered_courses = paginated_courses
    if category_filter != "All":
        filtered_courses = [
            c for c in filtered_courses 
            if c.get('subject', c.get('Subject', c.get('SUBJECT'))) == category_filter
        ]
    if level_filter != "All":
        filtered_courses = [
            c for c in filtered_courses if c.get('level') == level_filter
        ]
    
    if not filtered_courses:
        st.warning("No courses match the selected filters.")
        return
    
    for idx, course in enumerate(filtered_courses):
        try:
            expander_label = f"{course.get('title', 'Untitled Course')} - {course.get('level', 'N/A')}"
            with st.expander(expander_label):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"Duration: {course.get('duration', 'Not specified')}")
                    st.caption(f"Subject: {course.get('subject', course.get('Subject', course.get('SUBJECT', 'General')))})")
                    st.write(course.get('description', 'No description available'))
                with col2:
                    st.metric("Subscribers", course.get('subscribers', 0))
                    course_id = course.get('course_id', course.get('id', f"missing_id_{idx}"))
                    try:
                        course_id_int = int(course_id)
                    except ValueError:
                        course_id_int = f"missing_id_{idx}"
                    button_key = f"enroll_{course_id}_{idx}"
                    if st.button("Enroll", key=button_key):
                        if course_id in (None, "", f"missing_id_{idx}"):
                            st.error("Cannot enroll: Course ID is missing.")
                        else:
                            handle_enroll_course(course_id_int)
                
                if course.get('url'):
                    st.markdown(f"[View Course]({course.get('url')})")
        except Exception as e:
            st.error(f"Error displaying course: {str(e)}")

def show_my_courses():
    st.title("My Courses")
    
    if not st.session_state.auth.get('user'):
        st.warning("Please sign in to view your courses")
        return
    
    user_id = st.session_state.auth['user'].id
    user_courses = get_user_courses(user_id)
    
    if not user_courses:
        st.info("You haven't enrolled in any courses yet. Go to 'View Courses' to enroll!")
        return
    
    st.write(f"Number of Enrolled Courses: {len(user_courses)}")
    
    for idx, enrollment in enumerate(user_courses):
        try:
            course = enrollment.get('courses', {})
            if not course:
                st.warning(f"Course data missing for enrollment: {enrollment}")
                continue
                
            expander_label = f"{course.get('title', 'Untitled Course')} - {course.get('level', 'N/A')}"
            with st.expander(expander_label):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"Duration: {course.get('duration', 'Not specified')}")
                    st.caption(f"Subject: {course.get('subject', course.get('Subject', course.get('SUBJECT', 'General')))})")
                    st.write(course.get('description', 'No description available'))
                    st.progress(enrollment.get('progress', 0) / 100.0)
                    st.write(f"Progress: {enrollment.get('progress', 0)}%")
                with col2:
                    st.metric("Subscribers", course.get('subscribers', 0))
                
                if course.get('url'):
                    st.markdown(f"[View Course]({course.get('url')})")
        except Exception as e:
            st.error(f"Error displaying course: {str(e)}")

def show_dashboard():
    st.title("Learning Dashboard")
    
    if not st.session_state.auth.get('user'):
        st.warning("Please sign in to view dashboard")
        return
    
    user_id = st.session_state.auth['user'].id
    user_data = st.session_state.auth['user_data']
    
    st.subheader("Your Profile")
    with st.expander("View and Edit Profile"):
        st.write(f"Email: {user_data.get('email', 'N/A')}")
        st.write(f"Full Name: {user_data.get('full_name', 'N/A')}")
        st.write(f"Last Login: {user_data.get('last_login', 'Never')}")
        
        with st.form("update_profile_form"):
            new_full_name = st.text_input("Update Full Name", value=user_data.get('full_name', ''))
            if st.form_submit_button("Update Name"):
                try:
                    supabase.table("users").update({
                        "full_name": new_full_name
                    }).eq("id", user_id).execute()
                    supabase.auth.update_user({
                        "data": {"full_name": new_full_name}
                    })
                    st.session_state.auth['user_data']['full_name'] = new_full_name
                    st.success("Name updated successfully!")
                    st.rerun()
                except Exception as e:
                    logger.error(f"Error updating name: {str(e)}")
                    st.error(f"Error updating name: {str(e)}")
    
    user_courses = get_user_courses(user_id)
    st.subheader("Progress Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Courses Enrolled", len(user_courses))
    avg_progress = sum(course.get('progress', 0) for course in user_courses) / len(user_courses) if user_courses else 0
    col2.metric("Average Progress", f"{avg_progress:.1f}%")
    col3.metric("Last Active", user_data.get('last_login', 'Never'))
    
    if user_courses:
        st.subheader("Your Enrolled Courses")
        for enrollment in user_courses:
            course = enrollment.get('courses', {})
            if not course:
                continue
            with st.expander(f"{course.get('title', 'Untitled Course')} - {course.get('level', 'N/A')}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Subject**: {course.get('subject', 'General')}")
                    st.write(f"**Duration**: {course.get('duration', 'Not specified')}")
                    st.write(f"**Description**: {course.get('description', 'No description available')}")
                    st.progress(enrollment.get('progress', 0) / 100.0)
                    st.write(f"**Progress**: {enrollment.get('progress', 0)}%")
                with col2:
                    st.metric("Subscribers", course.get('subscribers', 0))
                    if course.get('url'):
                        st.markdown(f"[View Course]({course.get('url')})")
    else:
        st.info("You haven't enrolled in any courses yet. Go to 'View Courses' to enroll!")
    
    if user_courses:
        st.subheader("Progress Chart")
        progress_data = [
            {"Course": enrollment['courses'].get('title', 'Untitled'), "Progress": enrollment.get('progress', 0)}
            for enrollment in user_courses if enrollment.get('courses')
        ]
        if progress_data:
            df = pd.DataFrame(progress_data)
            st.bar_chart(df.set_index("Course"), height=300, use_container_width=True)

    if 'rag_pipeline' not in st.session_state:
        try:
            st.session_state.rag_pipeline = RAGPipeline(supabase_client=supabase)
            st.session_state.rag_pipeline.setup_agents()
            st.success("Learning Assistant initialized successfully!")
        except Exception as e:
            logger.error(f"Failed to initialize Learning Assistant: {str(e)}")
            st.error(f"Failed to initialize Learning Assistant: {str(e)}")
            return

    st.subheader("Learning Assistant")
    user_input = st.text_input(
        "Ask a question about your courses or general topics",
        placeholder="E.g., 'What is financial analysis?'",
        key="learning_assistant_input"
    )

    if user_input:
        with st.spinner("Processing your question..."):
            try:
                user_courses = get_user_courses(user_id)
                course_context = "\n".join([
                    f"Course: {course['courses']['title']}\nSubject: {course['courses']['subject']}\nDescription: {course['courses']['description']}"
                    for course in user_courses
                ]) if user_courses else "The user has not enrolled in any courses yet."
                
                full_query = f"User's enrolled courses:\n{course_context}\n\nQuestion: {user_input}"
                
                response = st.session_state.rag_pipeline.basic_rag_chain(full_query, user_id=user_id)
                st.write(f"**Learning Assistant**: {response}")
                
                with st.expander("Provide Feedback"):
                    feedback = st.radio("Was this answer helpful?", ("Yes", "No"), key=f"feedback_{user_input}")
                    if feedback == "No":
                        feedback_text = st.text_area("Please tell us how we can improve:", key=f"feedback_text_{user_input}")
                        if st.button("Submit Feedback", key=f"submit_feedback_{user_input}"):
                            if len(feedback_text) > 1000:
                                st.error("Feedback is too long (max 1000 characters)")
                            else:
                                supabase.table("feedback").insert({
                                    "user_id": user_id,
                                    "query": user_input[:500],
                                    "response": response[:2000],
                                    "feedback": feedback_text,
                                    "created_at": datetime.now().isoformat()
                                }).execute()
                                st.success("Thank you for your feedback!")
            except Exception as e:
                logger.error(f"Error processing question: {str(e)}")
                st.error(f"Error processing question: {str(e)}")

    st.subheader("Upload Study Materials")
    uploaded_file = st.file_uploader(
        "Upload study materials to enhance your learning",
        type=["pdf", "txt"],
        help="Limit 200MB per file • PDF, TXT",
        accept_multiple_files=False
    )

    if uploaded_file:
        with st.spinner(f"Processing '{uploaded_file.name}'..."):
            try:
                file_size_mb = uploaded_file.size / (1024 * 1024)
                if uploaded_file.size > 200 * 1024 * 1024:
                    st.error("File exceeds 200MB limit")
                    return
                st.write(f"**File**: {uploaded_file.name} ({file_size_mb:.2f} MB)")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_file_path = tmp_file.name
                
                file_extension = os.path.splitext(uploaded_file.name)[1].lower()
                loader_class = st.session_state.rag_pipeline.loaders.get(file_extension)
                if not loader_class:
                    st.error(f"Unsupported file type: {file_extension}")
                else:
                    loader = loader_class(tmp_file_path)
                    documents = loader.load()
                    success = st.session_state.rag_pipeline.add_documents(documents, user_id)
                    if success:
                        st.success(f"Successfully added '{uploaded_file.name}' to your knowledge base!")
                        with st.expander("View Uploaded File Content"):
                            for doc in documents[:1]:
                                preview = doc.page_content[:1000] + "..." if len(doc.page_content) > 1000 else doc.page_content
                                st.text(preview)
                    else:
                        st.warning("Failed to add file to knowledge base")
                os.unlink(tmp_file_path)
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                st.error(f"Error processing file: {str(e)}")
            finally:
                if 'tmp_file_path' in locals():
                    os.unlink(tmp_file_path)

def show_admin_panel():
    st.title("Admin Panel")
    
    if st.session_state.auth['user_data'].get('role') != 'admin':
        st.error("Access denied: Only admins can view this page")
        return
    
    st.subheader("Add New User")
    with st.form("add_user_form"):
        email = st.text_input("Email", key="admin_add_user_email")
        password = st.text_input("Password", type="password", key="admin_add_user_password")
        full_name = st.text_input("Full Name", key="admin_add_user_full_name")
        role = st.selectbox("Role", ["user", "admin"], key="admin_add_user_role")
        if st.form_submit_button("Add User"):
            admin_add_user(email, password, full_name, role)
    
    st.subheader("Delete User")
    users = supabase.table("users").select("id, email, full_name, role").execute().data
    if users:
        user_options = {f"{user['email']} ({user['full_name']})": user['id'] for user in users}
        user_to_delete = st.selectbox("Select User to Delete", list(user_options.keys()), key="delete_user_select")
        if st.button("Delete User", key="delete_user_button"):
            user_id = user_options[user_to_delete]
            admin_delete_user(user_id)
    else:
        st.info("No users found")
    
    st.subheader("Add New Course")
    show_add_course()
    
    st.subheader("Delete Course")
    courses = get_all_courses()
    if courses:
        course_options = {f"{course['title']} ({course['subject']})": course['course_id'] for course in courses}
        course_to_delete = st.selectbox("Select Course to Delete", list(course_options.keys()), key="delete_course_select")
        if st.button("Delete Course", key="delete_course_button"):
            course_id = course_options[course_to_delete]
            admin_delete_course(course_id)
    else:
        st.info("No courses found")

# Main App Flow
def main():
    # Add Content Security Policy to block external scripts
    st.markdown("""
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';">
    """, unsafe_allow_html=True)
    
    show_sidebar()
    
    if not st.session_state.auth.get('user'):
        if st.session_state.page == "Sign In":
            show_sign_in()
        elif st.session_state.page == "Sign Up":
            show_sign_up()
    else:
        if st.session_state.page == "Dashboard":
            show_dashboard()
        elif st.session_state.page == "View Courses":
            show_view_courses()
        elif st.session_state.page == "My Courses":
            show_my_courses()
        elif st.session_state.page == "Add Course":
            show_add_course()
        elif st.session_state.page == "Admin Panel":
            show_admin_panel()
        elif st.session_state.page == "Chat Assistant":
            show_chat_assistant()

if __name__ == "__main__":
    main()