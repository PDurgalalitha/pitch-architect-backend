import pymupdf
import uuid
from typing import List, Dict, Any
from datetime import datetime
from google.cloud import storage, firestore
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

class PitchDeckIngestionPipeline:
    def __init__(self, project_id: str, location: str, gcs_bucket_name: str, index_endpoint_id: str, deployed_index_id: str):
        self.project_id = project_id
        self.location = location
        self.gcs_bucket_name = gcs_bucket_name
        self.index_endpoint_id = index_endpoint_id
        self.deployed_index_id = deployed_index_id
        
        aiplatform.init(project=project_id, location=location)
        self.storage_client = storage.Client(project=project_id)
        self.db = firestore.Client(project=project_id)
        self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")

    def download_and_extract_pdf_file(self, file_bytes: bytes, filename: str, user_id: str) -> List[Dict[str, Any]]:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        chunks = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            
            if len(text) < 30:
                continue

            chunk_id = f"usr_{user_id}_{filename}_slide_{page_num + 1}"
            chunks.append({
                "chunk_id": chunk_id,
                "user_id": user_id,
                "document_id": filename,
                "slide_number": page_num + 1,
                "content": text,
                "metadata": {
                    "source": filename,
                    "slide_num": page_num + 1,
                    "user_id": user_id
                }
            })
            
        doc.close()
        return chunks

    def generate_embeddings(self, text_list: List[str]) -> List[List[float]]:
        inputs = [TextEmbeddingInput(text, "RETRIEVAL_DOCUMENT") for text in text_list]
        embeddings = self.embedding_model.get_embeddings(inputs)
        return [embedding.values for embedding in embeddings]

    def ingest_user_reference_deck(self, user_id: str, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        bucket = self.storage_client.bucket(self.gcs_bucket_name)
        doc_id = str(uuid.uuid4())
        gcs_path = f"users/{user_id}/references/{doc_id}_{filename}"
        
        blob = bucket.blob(gcs_path)
        blob.upload_from_string(file_bytes, content_type="application/pdf")

        chunks = self.download_and_extract_pdf_file(file_bytes, filename, user_id)
        if chunks:
            texts = [c["content"] for c in chunks]
            vectors = self.generate_embeddings(texts)

            batch = self.db.batch()
            for idx, chunk in enumerate(chunks):
                doc_ref = self.db.collection("reference_pitch_chunks").document(chunk["chunk_id"])
                batch.set(doc_ref, {
                    "chunk_id": chunk["chunk_id"],
                    "user_id": user_id,
                    "document_id": doc_id,
                    "filename": filename,
                    "slide_number": chunk["slide_number"],
                    "content": chunk["content"],
                    "embedding_vector": vectors[idx],
                    "metadata": chunk["metadata"]
                })
            batch.commit()

        metadata = {
            "doc_id": doc_id,
            "filename": filename,
            "gcs_path": gcs_path,
            "user_id": user_id,
            "uploaded_at": datetime.utcnow().isoformat(),
            "chunk_count": len(chunks)
        }
        self.db.collection("users").document(user_id).collection("reference_decks").document(doc_id).set(metadata)

        return metadata