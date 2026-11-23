
from app.services.ai_gateway import generate_text


def generate_story(topic: str, age: int, moral: str = "") -> str:
    prompt = f"""
    You are StoryBloom, a creative children's story writer.

    Create an original, engaging children's story.

    Topic: {topic}
    Reader's age: {age}
    Moral or lesson: {moral if moral else "Choose a meaningful lesson."}

    Requirements:
    - Give the story a creative title.
    - Use simple language suitable for the child's age.
    - Include interesting characters and dialogue.
    - Make the story imaginative and enjoyable.
    - Include a satisfying and positive ending.
    - Keep the content child-friendly.
    - Return only the complete story.
    """

    result = generate_text(prompt)

    print(f"Story generated using: {result['provider']}")

    return result["text"]
