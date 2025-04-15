import pandas as pd
from datetime import datetime

# Path to your CSV file
file_path = r'data\cleaned_data.csv'

# Load the CSV file with a specific encoding
try:
    df = pd.read_csv(file_path, encoding='latin1')  # Try 'latin1' or 'cp1252'
except Exception as e:
    print(f"Error reading CSV: {str(e)}")
    exit(1)

# Fix title
df['title'] = df['title'].replace({
    'Ultimate in': 'Ultimate Investment Banking Course',
    'Complete <': 'Complete GST Course & Certification'
})

# Add created_by (replace with a valid UUID from your users table)
df['created_by'] = 'f43f8ba4-4c8a-4758-b9a4-ca3b03501148'

# Add description (placeholder)
df['description'] = df['title'].apply(lambda x: f"Learn about {x.lower()}" if isinstance(x, str) else "No description available")

# Fix url (placeholder, replace with actual URLs if available)
df['url'] = df['url'].apply(lambda x: 'https://www.example.com/course' if x == 'https://www' else x)

# Fix subject
df['subject'] = df['subject'].replace('Business F', 'Business Finance')

# Fix level
df['level'] = df['level'].replace('ALLLevels', 'All Levels')

# Transform published_at to published (boolean)
df['published'] = df['published_at'].notnull()
df = df.drop(columns=['published_at'])

# Add created_at
df['created_at'] = datetime.now().isoformat()

# Ensure data types
df['price'] = df['price'].astype(float)
df['subscribers'] = df['subscribers'].astype(int)
df['is_paid'] = df['is_paid'].astype(bool)

# Reorder columns to match schema
columns = [
    'course_id', 'title', 'description', 'subject', 'level', 'created_by',
    'url', 'price', 'duration', 'is_paid', 'published', 'subscribers', 'created_at'
]
df = df[columns]

# Save the fixed data
output_file = 'courses_fixed.csv'
df.to_csv(output_file, index=False, encoding='utf-8')
print(f"Data fixed and saved to {output_file}")