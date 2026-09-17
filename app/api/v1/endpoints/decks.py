import uuid
import base64
from fastapi import APIRouter, HTTPException, Depends
from google.cloud import firestore

from app.schemas.pitch_deck import BusinessConceptInput, PitchDeckResponse
from app.core.security import get_current_user
from app.core.config import PROJECT_ID, LOCATION, INDEX_ENDPOINT_ID, DEPLOYED_INDEX_ID
from app.services.rag_engine import PitchDeckRAGEngine

router = APIRouter()
db = firestore.Client(project=PROJECT_ID)
rag_engine = PitchDeckRAGEngine(PROJECT_ID, LOCATION, INDEX_ENDPOINT_ID, DEPLOYED_INDEX_ID)

@router.post("/generate-deck", response_model=PitchDeckResponse)
def generate_pitch_deck(concept: BusinessConceptInput, current_user: dict = Depends(get_current_user)):
    try:
        return rag_engine.generate_pitch_deck(concept, user_id=current_user["uid"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deck generation failed: {str(e)}")

@router.get("/user/decks")
def list_user_decks(current_user: dict = Depends(get_current_user)):
    docs = db.collection("users").document(current_user["uid"]).collection("generated_decks").stream()
    return [doc.to_dict() for doc in docs]

@router.put("/decks/{deck_id}")
def update_user_deck(deck_id: str, deck: PitchDeckResponse, current_user: dict = Depends(get_current_user)):
    deck.deck_id = deck_id

    for slide in deck.slides:
        if slide.image_url and slide.image_url.startswith("data:image/"):
            try:
                header, base64_data = slide.image_url.split(",", 1)
                mime_type = header.split(";")[0].split(":")[1]
                ext = mime_type.split("/")[1] if "/" in mime_type else "png"
                
                image_bytes = base64.b64decode(base64_data)
                destination_path = f"users/{current_user['uid']}/decks/{deck_id}/images/{uuid.uuid4()}.{ext}"
                
                gcs_image_url = rag_engine.upload_bytes_to_gcs(image_bytes, destination_path, content_type=mime_type)
                if gcs_image_url:
                    slide.image_url = gcs_image_url
            except Exception as e:
                print(f"Failed to process slide image base64: {e}")
                slide.image_url = None

    updated_pptx_url = rag_engine.upload_pptx_to_gcs(deck, current_user["uid"])
    if updated_pptx_url:
        deck.pptx_url = updated_pptx_url

    doc_ref = db.collection("users").document(current_user["uid"]).collection("generated_decks").document(deck_id)
    doc_ref.set({
        "deck_id": deck_id,
        "user_id": current_user["uid"],
        "generated_deck": deck.model_dump(mode="json"),
        "updated_at": firestore.SERVER_TIMESTAMP
    }, merge=True)

    return {"status": "success", "deck_id": deck_id, "pptx_url": deck.pptx_url}