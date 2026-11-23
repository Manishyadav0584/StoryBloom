
from fastapi import APIRouter, HTTPException
from app.schemas.story import StoryRequest, StoryResponse
from app.services.story_service import generate_story

router = APIRouter(prefix="/api", tags=["Stories"])


@router.post("/story", response_model=StoryResponse)
def create_story(request: StoryRequest):
    try:
        generated_story = generate_story(
            topic=request.topic,
            age=request.age,
            moral=request.moral
        )

        lines = generated_story.splitlines()
        title = "A Magical Story"

        for line in lines:
            cleaned = line.strip().lstrip("#").strip().strip("*")
            if cleaned:
                title = cleaned[:100]
                break

        return StoryResponse(
            title=title,
            story=generated_story
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Story generation failed: {str(error)}"
        )
