import json
import base64
import os
import io
import datetime
import traceback
from typing import List, Optional
from PIL import Image
from google.cloud import firestore, storage
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from vertexai.language_models import TextEmbeddingModel

from app.schemas.pitch_deck import BusinessConceptInput, PitchDeckResponse, PitchDeckGenerationSchema
from app.services.pptx_generator import generate_pptx_from_deck

class PitchDeckRAGEngine:
    def __init__(self, project_id: str, location: str, index_endpoint_id: str, deployed_index_id: str):
        self.project_id = project_id
        self.location = location
        self.index_endpoint_id = index_endpoint_id
        self.deployed_index_id = deployed_index_id

        vertexai.init(project=project_id, location=location)
        self.db = firestore.Client(project=project_id)
        self.storage_client = storage.Client(project=project_id)
        self.gcs_bucket_name = os.getenv("GCS_BUCKET_NAME")
        
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        self.generative_model = GenerativeModel("gemini-2.5-pro")
        self.image_model = GenerativeModel("gemini-2.5-flash-image")

    def _optimize_image(self, image_bytes: bytes) -> bytes:
        img = Image.open(io.BytesIO(image_bytes))
        output = io.BytesIO()
        img.save(output, format="WEBP", quality=80, optimize=True)
        return output.getvalue()

    def _upload_to_gcs(self, image_bytes: bytes, deck_id: str, slide_number: int) -> Optional[str]:
        if not self.gcs_bucket_name:
            return None
        try:
            webp_bytes = self._optimize_image(image_bytes)
            bucket = self.storage_client.bucket(self.gcs_bucket_name)
            blob_path = f"generated_decks/{deck_id}/slide_{slide_number}.webp"
            blob = bucket.blob(blob_path)
            blob.cache_control = "public, max-age=31536000, immutable"
            blob.upload_from_string(webp_bytes, content_type="image/webp")

            return blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(days=7),
                method="GET"
            )
        except Exception as err:
            print(f"GCS Image Upload Error: {err}")
            return None

    def upload_pptx_to_gcs(self, deck: PitchDeckResponse, user_id: str) -> Optional[str]:
        if not self.gcs_bucket_name or not deck.deck_id:
            return None
        try:
            pptx_bytes = generate_pptx_from_deck(deck)
            bucket = self.storage_client.bucket(self.gcs_bucket_name)
            blob_path = f"generated_decks/{deck.deck_id}/presentation.pptx"
            blob = bucket.blob(blob_path)
            blob.upload_from_string(
                pptx_bytes,
                content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
            return blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(days=7),
                method="GET"
            )
        except Exception as err:
            print(f"GCS PPTX Upload Error: {err}")
            return None

    def generate_slide_image(self, image_prompt: str, deck_id: str, slide_number: int) -> Optional[str]:
        if not image_prompt:
            return None

        try:
            prompt = (
                f"{image_prompt}. Premium investor presentation visual, 16:9 aspect ratio, "
                "no text, no labels, no logos, no watermark, no fake UI copy."
            )
            
            response = self.image_model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    response_modalities=["IMAGE"],
                ),
            )

            image_bytes = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                        image_bytes = part.inline_data.data
                        break

            if not image_bytes:
                raise RuntimeError("Gemini 2.5 Flash Image returned no image data")

            gcs_url = self._upload_to_gcs(image_bytes, deck_id, slide_number)
            if gcs_url:
                return gcs_url

            webp_bytes = self._optimize_image(image_bytes)
            encoded_image = base64.b64encode(webp_bytes).decode("ascii")
            return f"data:image/webp;base64,{encoded_image}"
            
        except Exception as exc:
            print(f"Slide image generation failed for slide {slide_number}: {exc}")
            traceback.print_exc()
            return None

    def retrieve_benchmark_context(self, concept: BusinessConceptInput, user_id: Optional[str] = None, top_k: int = 5) -> List[str]:
        retrieved_texts = []
        try:
            if user_id:
                user_chunks = self.db.collection("reference_pitch_chunks")\
                    .where("user_id", "==", user_id)\
                    .limit(top_k).stream()
                for doc in user_chunks:
                    retrieved_texts.append(doc.to_dict().get("content", ""))

            if len(retrieved_texts) < top_k:
                global_chunks = self.db.collection("reference_pitch_chunks").limit(top_k - len(retrieved_texts)).stream()
                for doc in global_chunks:
                    retrieved_texts.append(doc.to_dict().get("content", ""))
        except Exception as e:
            print(f"Context Retrieval Exception: {e}")

        return retrieved_texts

    def upload_bytes_to_gcs(self, file_bytes: bytes, destination_blob_name: str, content_type: str = "image/png") -> Optional[str]:
        if not self.gcs_bucket_name:
            return None
        bucket = self.storage_client.bucket(self.gcs_bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(file_bytes, content_type=content_type)
        return blob.public_url

    def generate_pitch_deck(self, concept: BusinessConceptInput, user_id: str) -> PitchDeckResponse:
        retrieved_contexts = self.retrieve_benchmark_context(concept, user_id=user_id)
        context_str = "\n\n--- REFERENCE BENCHMARK SLIDE CONTENT ---\n" + "\n".join(retrieved_contexts) if retrieved_contexts else ""

        prompt = f"""
You are an expert venture capital investment partner and startup pitch architect.
Create a finished, institutional-grade 10-slide investor pitch deck for the specific venture below.

BUSINESS CONCEPT DETAILS:
- Company/Project Title: {concept.title}
- Industry Vertical: {concept.industry_vertical}
- Core Concept: {concept.business_idea}
- Target Audience/Customers: {concept.target_audience}

{context_str}

REQUIREMENTS:
1. You MUST generate EXACTLY 10 slides matching these slide titles:
   Slide 1: Problem
   Slide 2: Solution
   Slide 3: Market Size (TAM/SAM/SOM)
   Slide 4: Business Model
   Slide 5: Competitive Landscape
   Slide 6: Go-To-Market Strategy
   Slide 7: Team Composition
   Slide 8: Financial Projections
   Slide 9: Traction Metrics
   Slide 10: Funding Ask

2. Provide 3 to 5 concise, quantitative bullet points per slide.
3. Every claim must be specific to this company and customer segment.
4. Each slide must include an image_prompt for a clean 16:9 presentation visual with no text or fake UI copy.
"""

        generation_config = GenerationConfig(
            response_mime_type="application/json",
            response_schema=PitchDeckGenerationSchema.model_json_schema(),
            temperature=0.2,
        )

        response = self.generative_model.generate_content(
            prompt,
            generation_config=generation_config
        )

        raw_dict = json.loads(response.text)

        for slide_number, slide in enumerate(raw_dict.get("slides", []), start=1):
            slide["slide_number"] = slide_number
            slide.setdefault("key_takeaway", slide.get("headline", ""))
            bullet_points = slide.get("bullet_points", [])
            if len(bullet_points) > 5:
                slide["bullet_points"] = bullet_points[:5]

        deck_doc_ref = self.db.collection("users").document(user_id).collection("generated_decks").document()
        deck_id = deck_doc_ref.id

        validated_deck = PitchDeckResponse(
            deck_id=deck_id,
            **raw_dict
        )

        for slide in validated_deck.slides:
            if slide.image_prompt:
                slide.image_url = self.generate_slide_image(
                    image_prompt=slide.image_prompt,
                    deck_id=deck_id,
                    slide_number=slide.slide_number
                )

        validated_deck.pptx_url = self.upload_pptx_to_gcs(validated_deck, user_id)

        deck_doc_ref.set({
            "deck_id": deck_id,
            "user_id": user_id,
            "inputs": concept.model_dump(),
            "generated_deck": validated_deck.model_dump(),
            "updated_at": firestore.SERVER_TIMESTAMP
        })

        return validated_deck