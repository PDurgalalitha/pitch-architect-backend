from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field

class SlideType(str, Enum):
    PROBLEM = "Problem"
    SOLUTION = "Solution"
    MARKET_SIZE = "Market Size (TAM/SAM/SOM)"
    BUSINESS_MODEL = "Business Model"
    COMPETITIVE_LANDSCAPE = "Competitive Landscape"
    GO_TO_MARKET = "Go-To-Market Strategy"
    TEAM = "Team Composition"
    FINANCIALS = "Financial Projections"
    TRACTION = "Traction Metrics"
    FUNDING_ASK = "Funding Ask"

class BusinessConceptInput(BaseModel):
    title: str = Field(..., description="Project or startup name")
    business_idea: str = Field(..., description="Core business concept and value proposition")
    target_audience: str = Field(..., description="Primary user personas and target customers")
    industry_vertical: str = Field(..., description="Industry sector (e.g., FinTech, B2B SaaS)")
    reference_deck_ids: Optional[List[str]] = Field(default_factory=list, description="User-selected reference deck IDs for retrieval grounding")

class SlideContentGen(BaseModel):
    slide_number: int = Field(..., ge=1)
    slide_title: str
    headline: str
    bullet_points: List[str] = Field(..., min_length=1, max_length=5)
    image_prompt: str = Field(..., description="A visual asset prompt, or an explanation of the chart/diagram to use")
    key_takeaway: str

class PitchDeckGenerationSchema(BaseModel):
    project_title: str
    industry: str
    slides: List[SlideContentGen] = Field(..., min_length=1)

class SlideContent(BaseModel):
    slide_number: int = Field(..., ge=1)
    slide_title: str
    headline: str
    bullet_points: List[str] = Field(..., min_items=1, max_items=5)
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None
    key_takeaway: str
    font_family: str = Field(default="Arial")
    text_color: str = Field(default="#0F172A")
    bg_color: str = Field(default="#F8FAFC")
    accent_color: str = Field(default="#4F46E5")
    headline_size: int = Field(default=24)
    body_size: int = Field(default=14)

class PitchDeckResponse(BaseModel):
    deck_id: Optional[str] = None
    project_title: str
    industry: str
    slides: List[SlideContent] = Field(..., min_length=1)
    pptx_url: Optional[str] = Field(default=None, description="Signed GCS URL to downloadable editable PPTX")

class IngestionRequest(BaseModel):
    gcs_bucket: str
    gcs_prefix: Optional[str] = ""

class IngestionJobStatus(BaseModel):
    job_id: str
    processed_files: int
    indexed_chunks: int
    status: str

class ReferenceDeckMetadata(BaseModel):
    doc_id: str
    filename: str
    gcs_path: str
    uploaded_at: str
    chunk_count: int