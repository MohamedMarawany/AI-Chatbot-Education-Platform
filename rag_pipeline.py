# rag_pipeline.py

from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from qdrant_client import QdrantClient
from crewai import Agent, Task, Crew
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
import logging  # Added for logging

# Suppress litellm provider list warnings
logging.getLogger("litellm").setLevel(logging.WARNING)

# Load environment variables
load_dotenv()

class RAGPipeline:
    def __init__(self, supabase_client=None):
        try:
            self.qdrant = QdrantClient("http://localhost:6333")
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-pro",
                temperature=0.3,
                google_api_key=os.getenv("GOOGLE_API_KEY")
            )
            if supabase_client:
                self.supabase = supabase_client
            else:
                self.supabase = create_client(
                    os.getenv("SUPABASE_URL"),
                    os.getenv("SUPABASE_KEY")
                )
            self.embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            self.loaders = {
                ".pdf": PyPDFLoader,
                ".txt": TextLoader
            }
            print("✅ Components initialized successfully")
        except Exception as e:
            print(f"❌ Initialization failed: {str(e)}")
            raise

    def setup_agents(self):
        try:
            self.intent_agent = Agent(
                role="Intent Classifier",
                goal="Determine user intent (course_recommendation/course_qa/career_advice/summarization)",
                backstory="Expert in understanding educational queries",
                llm=self.llm,
                verbose=False
            )
            
            self.context_agent = Agent(
                role="Quality Assurance",
                goal="Review responses for accuracy",
                backstory="Specialist in educational content verification",
                llm=self.llm,
                verbose=False
            )

            classify_task = Task(
                description="Classify: {query}",
                agent=self.intent_agent,
                expected_output="Intent classification"
            )
            
            review_task = Task(
                description="Verify: {response}",
                agent=self.context_agent,
                expected_output="Improved response"
            )

            self.crew = Crew(
                agents=[self.intent_agent, self.context_agent],
                tasks=[classify_task, review_task],
                verbose=False
            )
            print("✅ Agents setup complete")
        except Exception as e:
            print(f"❌ Agent setup failed: {str(e)}")
            raise

    def add_documents(self, documents: List, user_id: str) -> bool:
        try:
            if not self.qdrant.collection_exists(collection_name="user_documents"):
                self.qdrant.create_collection(
                    collection_name="user_documents",
                    vectors_config={"size": 384, "distance": "Cosine"}
                )
            
            embeddings = self.embedder.embed_documents([doc.page_content for doc in documents])
            
            points = [
                {
                    "id": f"{user_id}_{i}_{int(datetime.now().timestamp())}",
                    "vector": embedding,
                    "payload": {
                        "content": doc.page_content,
                        "user_id": user_id,
                        "source": doc.metadata.get("source", "uploaded_file"),
                        "uploaded_at": datetime.now().isoformat()
                    }
                }
                for i, (doc, embedding) in enumerate(zip(documents, embeddings))
            ]
            
            self.qdrant.upsert(
                collection_name="user_documents",
                points=points
            )
            print(f"✅ Added {len(documents)} documents for user {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding documents: {str(e)}")
            return False

    def fetch_courses(self, query: str = None, limit: int = 5) -> List[dict]:
        try:
            select_query = self.supabase.table("courses").select("*")
            
            if query:
                query_lower = query.lower()
                select_query = select_query.ilike("title", f"%{query_lower}%")\
                    .or_(f"subject.ilike.%{query_lower}%")\
                    .or_(f"description.ilike.%{query_lower}%")
            
            response = select_query.limit(limit).execute()
            
            if not response.data:
                print("⚠️ No courses found in Supabase. Check table data, RLS policies, or connection.")
            
            courses = response.data if response.data else []
            print(f"📚 Fetched {len(courses)} courses from Supabase")
            return courses
        except Exception as e:
            print(f"❌ Error fetching courses: {str(e)}")
            return []

    def basic_rag_chain(self, query: str, user_id: str = "unknown") -> str:
        try:
            print(f"🔍 Processing query: {query}")
            parts = query.split("\n\nQuestion: ")
            context_part = parts[0] if len(parts) > 1 else ""
            question = parts[-1]
            print(f"📝 Question: {question}")
            print(f"📝 Context part: {context_part}")
            print(f"👤 User ID: {user_id}")
            
            user_doc_results = []
            if user_id != "unknown":
                print("🔎 Searching Qdrant for user documents...")
                try:
                    user_doc_results = self.qdrant.search(
                        collection_name="user_documents",
                        query_vector=self.embedder.embed_query(question),
                        limit=3,
                        query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]}
                    )
                    print(f"📚 Found {len(user_doc_results)} user documents")
                except Exception as e:
                    print(f"❌ Qdrant search failed: {str(e)}")
            
            print("🔎 Fetching relevant courses from Supabase...")
            course_results = self.fetch_courses(query=question, limit=5)
            
            user_doc_context = "\n\n".join([f"User Document: {hit.payload['content'][:200]}..." for hit in user_doc_results]) if user_doc_results else "No relevant user documents found."
            course_context = "\n\n".join([
                f"Course: {course['title']}\n"
                f"Subject: {course['subject']}\n"
                f"Level: {course['level']}\n"
                f"Description: {course.get('description', 'N/A')}\n"
                f"Price: ${course['price']}\n"
                f"Subscribers: {course['subscribers']:,}"
                for course in course_results
            ]) if course_results else "No relevant courses found."
            
            full_context = f"{context_part}\n\nUser Uploaded Documents:\n{user_doc_context}\n\nAvailable Courses:\n{course_context}"
            print(f"📑 Full context prepared:\n{full_context[:500]}...")
            
            is_child_friendly = "six-year-old" in question.lower() or "child" in question.lower()
            
            print("📝 Building prompt...")
            if is_child_friendly:
                prompt = ChatPromptTemplate.from_template("""
                You're a friendly teacher talking to a six-year-old. Use this context to answer:
                {context}
                
                Question: {question}
                Explain it in a super simple way, like you're telling a story with toys, animals, or fun games a six-year-old would love:""")
            else:
                prompt = ChatPromptTemplate.from_template("""
                You're an educational assistant. Use this context to answer:
                {context}
                
                Question: {question}
                Provide a detailed response incorporating user-uploaded materials and course information:""")
            
            print("🔗 Creating chain...")
            chain = (
                {"context": RunnablePassthrough(), "question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
            )
            
            print("🤖 Invoking chain...")
            response = chain.invoke({"context": full_context, "question": question})
            print(f"✅ Generated response: {response[:200]}...")
            return response
            
        except Exception as e:
            print(f"❌ RAG error: {str(e)}")
            return f"I couldn't process that request. Please try again. (Error: {str(e)})"

if __name__ == "__main__":
    try:
        print("🚀 Initializing RAG pipeline...")
        pipeline = RAGPipeline()
        pipeline.setup_agents()
        
        test_query = "User's enrolled courses:\nNo enrolled courses yet.\n\nQuestion: What is financial analysis?"
        print(f"\n🔍 Testing with query: '{test_query}'")
        
        response = pipeline.basic_rag_chain(test_query)
        print(f"\n🤖 Response:\n{response}")
        
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")