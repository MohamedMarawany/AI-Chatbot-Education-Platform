# AI Chatbot Education Platform 🎓🤖

An intelligent and interactive education platform powered by AI and chatbot capabilities. Designed for students to explore AI-related courses, track their learning progress, and get assistance from a smart chatbot trained on custom knowledge.

---

## 🚀 Features

- 🔐 User Authentication (Sign up / Sign in)
- 📘 Add & View Courses
- 📊 Personalized Student Dashboard
- 🤖 AI Chatbot (Prompt + Knowledge File Upload)
- 📂 File Upload Support for Custom Knowledge
- 🔧 Backend with FastAPI & Supabase Integration

---

## 🧪 Tech Stack

- **Frontend**: Streamlit
- **Backend**: FastAPI
- **Database**: Supabase
- **AI/ML**: OpenAI API, RAG (Retrieval-Augmented Generation)
- **Data Processing**: Pandas, Langchain
- **Chatbot Memory**: FAISS Vector Store

---

## 🛠️ How to Run Locally

 🔹 Streamlit Frontend

```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

🔹 FastAPI Backend

```bash
uvicorn fastapi:app --reload
# Or
python fastapi.py
```


### 🔐 Environment Variables

**Create a .env file and add the following:**

SUPABASE_URL=your_supabase_url

SUPABASE_KEY=your_supabase_anon_key

OPENAI_API_KEY=your_openai_key


### 📹 Project Video & Demo
Check out our demo video (not included in repo) or contact us for a walkthrough!

### 👨‍💻 Authors
Mohamed Marawany – AI Developer & Streamlit App Engineer

Project Team – Graduation Project | Sprints


