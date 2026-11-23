
from fastapi import APIRouter, HTTPException

from app.schemas.storybook import (
    StorybookRequest,
    StorybookResponse
)

from app.services.storybook_service import (
    generate_complete_storybook
)

router = APIRouter(
    prefix="/api",
    tags=["Complete Storybooks"]
)


@router.post(
    "/storybook",
    response_model=StorybookResponse
)
async def create_complete_storybook(request: StorybookRequest):
    try:
        print(
            f"Creating {request.pages}-page storybook "
            f"with {request.image_count} illustrations..."
        )

        result = await generate_complete_storybook(
            topic=request.topic,
            age=request.age,
            moral=request.moral,
            pages=request.pages,
            image_count=request.image_count
        )

        print("Complete storybook generated successfully!")

        return StorybookResponse(**result)

    except Exception as error:
        print(f"Storybook generation failed: {error}")

        raise HTTPException(
            status_code=500,
            detail=f"Storybook generation failed: {str(error)}"
        )
