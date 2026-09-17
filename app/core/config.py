import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
LOCATION = os.getenv("GCP_LOCATION", "")
GCS_BUCKET = os.getenv("GCS_BUCKET_NAME", "")
INDEX_ENDPOINT_ID = os.getenv("VECTOR_SEARCH_ENDPOINT_ID","")
DEPLOYED_INDEX_ID = os.getenv("DEPLOYED_INDEX_ID", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")