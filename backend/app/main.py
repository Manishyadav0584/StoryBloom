
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.story import router as story_router
from app.routes.images import router as image_router
from app.routes.books import router as book_router
from app.routes.storybooks import router as storybook_router


app = FastAPI(
    title="StoryBloom 2.0",
    description="An AI-powered illustrated children's storybook studio.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "Welcome to StoryBloom 2.0!",
        "status": "running"
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


app.include_router(story_router)
app.include_router(image_router)
app.include_router(book_router)
app.include_router(storybook_router)
