from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from google.cloud import firestore

from app.core.security import get_current_user
from app.core.config import PROJECT_ID, LOCATION, GCS_BUCKET, INDEX_ENDPOINT_ID, DEPLOYED_INDEX_ID
from app.services.ingestion import PitchDeckIngestionPipeline

router = APIRouter()
db = firestore.Client(project=PROJECT_ID)
ingestion_pipeline = PitchDeckIngestionPipeline(PROJECT_ID, LOCATION, GCS_BUCKET, INDEX_ENDPOINT_ID, DEPLOYED_INDEX_ID)

@router.post("/user/upload-reference-deck")
async def upload_reference_deck(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    ALLOWED_EXTENSIONS = (".pdf", ".doc", ".docx", ".ppt", ".pptx")
    if not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Only PDF, DOC, DOCX, PPT, and PPTX files are supported")
    try:
        content = await file.read()
        metadata = ingestion_pipeline.ingest_user_reference_deck(current_user["uid"], file.filename, content)
        return metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest reference PDF: {str(e)}")

@router.get("/user/reference-decks")
def list_user_reference_decks(current_user: dict = Depends(get_current_user)):
    docs = db.collection("users").document(current_user["uid"]).collection("reference_decks").stream()
    return [doc.to_dict() for doc in docs]