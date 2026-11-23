
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.schemas.book import BookRequest
from app.services.book_service import create_storybook_pdf


router = APIRouter(
    prefix="/api",
    tags=["Storybook PDF"]
)


@router.post("/book")
async def generate_book(request: BookRequest):

    try:
        pdf_bytes = create_storybook_pdf(
            title=request.title,
            story=request.story,
            image=request.image,
            images=request.images,
            moral=request.moral,
            age=request.age,
            pages=request.pages
        )

        safe_title = "".join(
            character
            for character in request.title
            if character.isalnum() or character in (" ", "-", "_")
        ).strip()

        filename = f"{safe_title or 'storybook'}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{filename}"'
                )
            }
        )

    except Exception as error:
        print(f"PDF generation failed: {error}")

        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(error)}"
        )
