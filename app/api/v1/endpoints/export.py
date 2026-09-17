from fastapi import APIRouter, HTTPException, Response

from app.schemas.pitch_deck import PitchDeckResponse
from app.services.pdf_generator import generate_pdf_from_deck
from app.services.pptx_generator import generate_pptx_from_deck

router = APIRouter()

@router.post("/export-pptx")
def export_deck_pptx(deck: PitchDeckResponse):
    try:
        pptx_bytes = generate_pptx_from_deck(deck)
        filename = f"{deck.project_title.replace(' ', '_')}_PitchDeck.pptx"
        return Response(
            content=pptx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PowerPoint export failed: {str(e)}")

@router.post("/export-pdf")
def export_deck_pdf(deck: PitchDeckResponse):
    try:
        pdf_bytes = generate_pdf_from_deck(deck)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={deck.project_title}_PitchDeck.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")