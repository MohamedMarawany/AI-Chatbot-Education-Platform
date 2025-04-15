# File: udemy_data_to_vector_db.py

# python -m venv venv
# venv\Scripts\activate
# deactivate

# pip install pandas nltk scikit-learn sentence-transformers qdrant-client spacy
# python -m spacy download en_core_web_sm

# data_path = r"data\udemy_course_data.csv"

# python udemy_data_to_vector_db.py

import pandas as pd
import re
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models
import spacy
import time
from tqdm import tqdm

# ----------------------------
# Initialize Components
# ----------------------------
print("\n🚀 Initializing components...")
start_time = time.time()

# NLP tools
nlp = spacy.load("en_core_web_sm")
lemmatizer = WordNetLemmatizer()

# ----------------------------
# 1. Data Loading & Cleaning
# ----------------------------
print("\n🔍 Step 1/5: Loading and cleaning data...")

try:
    df = pd.read_csv(r"data\udemy_course_data.csv")
    print(f"📊 Loaded {len(df)} courses")
    
    # Remove irrelevant columns
    cols_to_drop = ["url", "published_time", "course_id", "published_timestamp"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors="ignore")
    
    # Filter rows with missing critical fields
    initial_count = len(df)
    df = df.dropna(subset=["course_title", "subject", "content_duration"])
    print(f"🧹 Removed {initial_count - len(df)} rows with missing data")
    
except Exception as e:
    print(f"❌ Error loading data: {str(e)}")
    exit()

# ----------------------------
# 2. Text Normalization
# ----------------------------
print("\n📝 Step 2/5: Normalizing text...")

def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    tokens = word_tokenize(text)
    lemmas = [lemmatizer.lemmatize(token) for token in tokens]
    return " ".join(lemmas)

df["processed_text"] = df["course_title"].apply(normalize_text)

# ----------------------------
# 3. Data Enrichment
# ----------------------------
print("\n✨ Step 3/5: Enriching data...")

# Topic Modeling
print(" - Running topic modeling (LDA)...")
tfidf = TfidfVectorizer(max_features=1000)
X_tfidf = tfidf.fit_transform(df["processed_text"])
lda = LatentDirichletAllocation(n_components=5, random_state=42)
df["topic"] = lda.fit_transform(X_tfidf).argmax(axis=1)

# Named Entity Recognition
print(" - Extracting named entities...")
def extract_entities(text):
    try:
        return [ent.text for ent in nlp(text).ents]
    except:
        return []

df["entities"] = [extract_entities(title) for title in tqdm(df["course_title"], desc="Processing NER")]

# ----------------------------
# 4. Vectorization
# ----------------------------
print("\n🧮 Step 4/5: Generating embeddings...")
model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(df["processed_text"].tolist(), show_progress_bar=True)

# ----------------------------
# 5. Vector Database Integration
# ----------------------------
print("\n💾 Step 5/5: Storing in Qdrant...")
try:
    client = QdrantClient(":memory:")  # For production: QdrantClient(url="http://localhost:6333")
    
    # Create collection
    client.recreate_collection(
        collection_name="udemy_courses",
        vectors_config=models.VectorParams(
            size=384,
            distance=models.Distance.COSINE
        )
    )

    # Upload in batches
    batch_size = 100
    for i in tqdm(range(0, len(df), batch_size), desc="Uploading courses"):
        batch = df.iloc[i:i+batch_size]
        points = [
            models.PointStruct(
                id=idx,
                vector=embeddings[idx].tolist(),
                payload={
                    "title": row["course_title"],
                    "subject": row["subject"],
                    "level": row["level"],
                    "price": float(row["price"]),
                    "topic": int(row["topic"]),
                    "entities": row["entities"],
                    "duration": row["content_duration"],
                    "subscribers": int(row["num_subscribers"])
                }
            )
            for idx, row in batch.iterrows()
        ]
        client.upsert(
            collection_name="udemy_courses",
            points=points
        )

except Exception as e:
    print(f"❌ Qdrant Error: {str(e)}")
    exit()

# ----------------------------
# Verification
# ----------------------------
print("\n🔎 Testing retrieval...")
test_queries = [
    "Learn Python programming",
    "Advanced finance course",
    "Photoshop for beginners"
]

for query in test_queries:
    query_embedding = model.encode([normalize_text(query)])
    
    # Using the current recommended API
    results = client.search(
        collection_name="udemy_courses",
        query_vector=query_embedding[0].tolist(),
        limit=3,
        with_payload=True,
        with_vectors=False
    )
    
    print(f"\n🔍 Results for '{query}':")
    for i, hit in enumerate(results, 1):
        print(f"{i}. {hit.payload['title']} (Score: {hit.score:.2f})")
        print(f"   Subject: {hit.payload['subject']} | Price: ${hit.payload['price']}")
        print(f"   Subscribers: {hit.payload['subscribers']:,}")

print(f"\n✅ Phase 1 Complete! Processed {len(df)} courses in {time.time()-start_time:.1f} seconds")