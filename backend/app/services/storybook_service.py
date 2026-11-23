import asyncio
import re

from app.services.ai_gateway import generate_text
from app.services.image_service import generate_story_image


# Placed between interior pages inside the returned "story" string so the
# website and the PDF show exactly the page the author wrote. If a consumer
# does not know the marker it still sees normal blank-line-separated text.
PAGE_BREAK = "<<<PAGE_BREAK>>>"

PAGE_HEADING = re.compile(
    r"(?im)^[ \t]*(?:#+[ \t]*)?\**[ \t]*PAGE[ \t]+\d+[ \t]*\**[ \t]*[:.\-]?[ \t]*\**[ \t]*$"
)

MORAL_LINE = re.compile(
    r"(?im)^[ \t]*(?:#+[ \t]*)?\**[ \t]*(?:MORAL|LESSON)[ \t]*\**[ \t]*:[ \t]*\**[ \t]*(.+?)[ \t]*\**[ \t]*$"
)

VISUAL_GUIDE = re.compile(
    r"(?im)^[ \t]*(?:#+[ \t]*)?\**[ \t]*(?:VISUAL|CHARACTER)[ \t]+GUIDE[ \t]*\**[ \t]*:?[ \t]*\**[ \t]*"
)

# One art direction, repeated word for word in every illustration prompt,
# so the whole book looks like it was painted by the same hand.
ART_STYLE = (
    "Premium children's picture-book illustration, soft watercolor and gouache "
    "texture, pastel palette of blush pink, lavender, mint, butter yellow and sky blue, "
    "warm gentle light, rounded friendly shapes, expressive faces, whimsical "
    "storybook details, full scene composition. No text, letters, words, captions, "
    "speech bubbles, watermarks, logos or borders."
)


# -------------------------------------------------
# Small helpers
# -------------------------------------------------

def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("*", "")).strip()


def clip(text: str, limit: int) -> str:
    text = collapse(text)

    if len(text) <= limit:
        return text

    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "..."


def split_paragraphs(text: str):
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text or "")
        if paragraph.strip()
    ]


def words_per_page(age: int) -> str:
    if age <= 5:
        return "25 to 45 words"

    if age <= 8:
        return "50 to 85 words"

    if age <= 11:
        return "80 to 120 words"

    return "110 to 150 words"


def image_page_indices(interior_count: int, image_count: int):
    """
    Which interior page (0-based) each interior illustration belongs to.
    Must stay identical to imagePageIndices() in script.js and
    image_page_indices() in book_service.py.
    """

    if image_count <= 0 or interior_count <= 0:
        return []

    if image_count == 1:
        return [interior_count // 2]

    indices = []

    for index in range(image_count):
        if image_count <= interior_count:
            # Evenly spaced, rounding half up with integer maths.
            indices.append(
                (2 * index * (interior_count - 1) + (image_count - 1))
                // (2 * (image_count - 1))
            )
        else:
            # More pictures than pages: share them out evenly.
            indices.append(
                min(interior_count - 1, index * interior_count // image_count)
            )

    return indices


# -------------------------------------------------
# Parsing the model's answer
# -------------------------------------------------

def clean_title(story: str) -> str:
    for line in story.splitlines():
        cleaned = line.strip().lstrip("#").strip().strip("*").strip()

        if cleaned:
            cleaned = re.sub(r"^title:\s*", "", cleaned, flags=re.I)
            cleaned = cleaned.strip("*").strip().strip('"\u201c\u201d').strip()
            return cleaned[:100] or "A Magical Story"

    return "A Magical Story"


def extract_pages(story: str, page_count: int):
    """Split the story body into one text block for every interior page."""

    interior_pages = max(1, page_count - 2)
    story = story or ""

    # 1) Pages already joined with the page-break marker.
    if PAGE_BREAK in story:
        sections = [section.strip() for section in story.split(PAGE_BREAK)]

        if len(sections) == interior_pages and all(sections):
            return sections

        story = story.replace(PAGE_BREAK, "\n\n")

    # 2) "PAGE 2", "PAGE 3" ... headings written by the model.
    if PAGE_HEADING.search(story):
        sections = [section.strip() for section in PAGE_HEADING.split(story)]

        # Anything before the first heading is not part of a page.
        sections = [section for section in sections[1:] if section]

        if len(sections) == interior_pages:
            return sections

        story = "\n\n".join(sections)
    else:
        story = PAGE_HEADING.sub("", story)

    # 3) Fallback: spread paragraphs evenly using integer maths.
    paragraphs = split_paragraphs(story)

    if not paragraphs:
        return [""] * interior_pages

    pages = []

    for index in range(interior_pages):
        start = index * len(paragraphs) // interior_pages
        end = (index + 1) * len(paragraphs) // interior_pages

        pages.append("\n\n".join(paragraphs[start:end]))

    return pages


def join_pages(pages):
    return f"\n\n{PAGE_BREAK}\n\n".join(page.strip() for page in pages)


def parse_story_response(raw: str):
    """Split the raw model answer into title, story body, moral and visual guide."""

    text = (raw or "").replace("\r\n", "\n").strip()

    # Moral line (can appear anywhere after the pages).
    lesson = ""
    moral_match = MORAL_LINE.search(text)

    if moral_match:
        lesson = collapse(moral_match.group(1)).strip("*").strip()
        text = (text[:moral_match.start()] + text[moral_match.end():]).strip()

    # Visual guide block (everything after its heading).
    guide = ""
    guide_match = VISUAL_GUIDE.search(text)

    if guide_match:
        guide = text[guide_match.end():].strip()
        text = text[:guide_match.start()].strip()

    guide = re.sub(r"(?m)^[ \t]*[-*\u2022][ \t]*", "", guide)
    guide = collapse(guide.replace("**", ""))

    # Title: first meaningful line, skipping chatty openers.
    lines = text.split("\n")
    first = 0

    while first < len(lines):
        candidate = lines[first].strip()

        if not candidate:
            first += 1
            continue

        chatty = re.match(
            r"(?i)^(here('s| is)|sure|certainly|of course|okay)\b", candidate
        )

        if chatty and candidate.endswith((":", "!", ".")):
            first += 1
            continue

        break

    title = "A Magical Story"
    body = text

    if first < len(lines):
        if PAGE_HEADING.match(lines[first]):
            # The model skipped the title; keep every line as story.
            body = "\n".join(lines[first:]).strip()
        else:
            title = clean_title(lines[first])
            body = "\n".join(lines[first + 1:]).strip()

    return title, body, lesson, guide


# -------------------------------------------------
# Illustration prompts
# -------------------------------------------------

def chunk_for_image(page_text: str, share_count: int, share_index: int) -> str:
    """When several pictures share a page, give each a different part of it."""

    if share_count <= 1:
        return page_text

    sentences = [
        sentence for sentence in re.split(r"(?<=[.!?])\s+", collapse(page_text))
        if sentence
    ]

    start = share_index * len(sentences) // share_count
    end = (share_index + 1) * len(sentences) // share_count

    return " ".join(sentences[start:end]) or page_text


def create_image_prompts(
    title,
    topic,
    story_pages,
    image_count,
    character_guide=""
):
    guide = clip(character_guide, 650) or (
        f"The main characters of a story about: {clip(topic, 120)}. "
        "Give each a clear, simple design with fixed colors and clothing."
    )

    consistency = (
        "Recurring characters, identical in every illustration of this book "
        f"(same faces, proportions, colors and clothing): {guide}"
    )

    prompts = [
        " ".join([
            ART_STYLE,
            consistency,
            "Book COVER illustration: the main character or characters in a "
            "wonderful magical setting that captures the whole story, "
            "centered composition with open space around the subject. "
            f"Story idea: {clip(topic, 160)}. Do not draw the title."
        ])
    ]

    interior_count = image_count - 1

    if interior_count <= 0 or not story_pages:
        return prompts

    page_indices = image_page_indices(len(story_pages), interior_count)

    for image_number, page_index in enumerate(page_indices, start=2):
        # Pictures that share a page each illustrate a different moment of it.
        sharing = [i for i, value in enumerate(page_indices) if value == page_index]
        position = sharing.index(image_number - 2)

        scene = clip(
            chunk_for_image(story_pages[page_index], len(sharing), position),
            420
        )

        prompts.append(
            " ".join([
                ART_STYLE,
                consistency,
                f"Interior illustration {image_number} of {image_count}. "
                f"Illustrate exactly this moment: {scene}"
            ])
        )

    return prompts


async def generate_image_with_retry(prompt: str, attempts: int = 2):
    """Free image services are flaky; try once more before giving up."""

    last_error = None

    for attempt in range(attempts):
        try:
            return await generate_story_image(prompt)

        except Exception as error:
            last_error = error
            print(f"Illustration attempt {attempt + 1} failed: {error}")

            if attempt < attempts - 1:
                await asyncio.sleep(2)

    raise last_error


# -------------------------------------------------
# Main entry point
# -------------------------------------------------

async def generate_complete_storybook(
    topic: str,
    age: int,
    moral: str = "",
    pages: int = 10,
    image_count: int = 5
) -> dict:

    interior = pages - 2

    prompt = f"""
    You are StoryBloom, an award-winning children's picture-book author.

    Write an original, warm and logically consistent story.

    Topic: {topic}
    Reader age: {age}
    Lesson to weave in: {moral if moral else "Choose a meaningful, positive lesson."}

    BOOK STRUCTURE:
    - The book has exactly {pages} pages in total.
    - Page 1 is the cover and page {pages} is the ending page. You write neither.
    - Write exactly {interior} story pages, labelled PAGE 2, PAGE 3 and so on,
      up to PAGE {pages - 1}. Each label sits alone on its own line.
    - Each story page holds about {words_per_page(age)}, in one to three short
      paragraphs, and shows one clear moment that can be painted as a picture.

    STORY ARC:
    - Early pages: meet the main character, their home and what they long for.
    - Middle pages: a problem, a try-and-fail or two, a helpful friend or discovery.
    - Late pages: a brave or kind turning point, then a satisfying, gentle ending.
    - Keep names, personalities and settings consistent on every page.
    - Use natural dialogue, sensory details and a read-aloud rhythm.
    - Use vocabulary suited to age {age}. Avoid repetition and keep it child-friendly.

    OUTPUT FORMAT (follow exactly, with no extra commentary):
    Line 1: the story title only, with no label and no markdown.
    Then the labelled story pages.
    Then one line starting with "MORAL:" that states the lesson in one warm sentence.
    Then a line "VISUAL GUIDE:" followed by one line per recurring character
    (at most 3) in the form "Name: species or age, fur/skin/hair color, eye color,
    outfit and one distinctive feature", and finally one line "Setting: ..."
    describing the main place and colors.
    """

    result = generate_text(prompt)
    raw_story = result["text"]

    print(f"Story generated using: {result['provider']}")

    title, story_body, generated_moral, character_guide = parse_story_response(
        raw_story
    )

    story_pages = extract_pages(story_body, pages)

    # Without a visual guide, ask once for a short character description.
    if not character_guide:
        try:
            guide_result = generate_text(
                "Describe the recurring main characters of this children's story "
                "for an illustrator in at most 80 words. Give each one species or "
                "age, fur/skin/hair color, eye color, outfit and one distinctive "
                "feature. Reply with the description only.\n\n"
                f"Title: {title}\n\n" + "\n\n".join(story_pages)[:2500]
            )
            character_guide = collapse(guide_result["text"])

        except Exception as error:
            print(f"Character guide fallback failed: {error}")

    prompts = create_image_prompts(
        title,
        topic,
        story_pages,
        image_count,
        character_guide
    )

    images = []

    # Generate images sequentially to respect free-service limits.
    for index, image_prompt in enumerate(prompts, start=1):
        print(f"Generating illustration {index}/{image_count}...")

        image = await generate_image_with_retry(
            image_prompt.strip()[:1900]
        )

        images.append(image)

    return {
        "title": title,
        "story": join_pages(story_pages),
        "images": images,
        "moral": moral.strip() or generated_moral,
        "age": age,
        "pages": pages,
        "image_count": image_count
    }