import io
import base64
from urllib.request import urlopen
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.schemas.pitch_deck import PitchDeckResponse

def generate_pdf_from_deck(deck: PitchDeckResponse) -> bytes:
    buffer = io.BytesIO()
    page_width, page_height = 720, 405
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(page_width, page_height),
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'SlideTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1E1B4B'),
        spaceAfter=10
    )
    headline_style = ParagraphStyle(
        'SlideHeadline',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#4338CA'),
        spaceAfter=12
    )
    bullet_style = ParagraphStyle(
        'SlideBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=6,
        leftIndent=12
    )

    story = []

    for slide in deck.slides:
        story.append(Paragraph(f"Slide {slide.slide_number}: {slide.slide_title}", title_style))
        story.append(Paragraph(f"<b>Headline:</b> {slide.headline}", headline_style))
        story.append(Spacer(1, 8))

        for bp in slide.bullet_points:
            story.append(Paragraph(f"• {bp}", bullet_style))

        story.append(Spacer(1, 10))

        if slide.image_url:
            try:
                if slide.image_url.startswith("data:image/"):
                    image_bytes = io.BytesIO(base64.b64decode(slide.image_url.split(",", 1)[1]))
                else:
                    with urlopen(slide.image_url, timeout=10) as image_response:
                        image_bytes = io.BytesIO(image_response.read())
                slide_image = Image(ImageReader(image_bytes), width=300, height=150)
                story.append(slide_image)
                story.append(Spacer(1, 8))
            except Exception:
                pass

        info_data = [
            [
                Paragraph(f"<b>Image Brief:</b> {slide.image_prompt or 'No image generated'}", bullet_style),
                Paragraph(f"<b>Core Takeaway:</b> {slide.key_takeaway}", bullet_style)
            ]
        ]
        info_table = Table(info_data, colWidths=[310, 310])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ]))
        story.append(info_table)
        
        if slide.slide_number < len(deck.slides):
            story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()