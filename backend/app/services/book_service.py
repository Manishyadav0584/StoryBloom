import base64
import math
import re
from io import BytesIO

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    KeepInFrame,
    Flowable,
    Table,
    TableStyle,
)


# Marker the story service puts between interior pages.
PAGE_BREAK = "<<<PAGE_BREAK>>>"

# StoryBloom pastel palette
CREAM = colors.HexColor("#FFF6EA")
PAPER = colors.HexColor("#FFFBF4")
ROSE = colors.HexColor("#F6C3D3")
ROSE_SOFT = colors.HexColor("#FDE6ED")
ROSE_DEEP = colors.HexColor("#C4507A")
LAVENDER = colors.HexColor("#D9D0F5")
LAVENDER_SOFT = colors.HexColor("#EFEAFC")
PLUM = colors.HexColor("#6B4FA3")
MINT = colors.HexColor("#CDEEDF")
BUTTER = colors.HexColor("#FFEAB3")
INK = colors.HexColor("#3B2F4D")
TEXT = colors.HexColor("#4A3D5C")
MUTED = colors.HexColor("#7A6F88")


# -------------------------------------------------
# Image helpers
# -------------------------------------------------

def decode_image(image_data):
    """Decode a base64 image data URL into an image buffer."""

    if not image_data:
        return None

    if "," in image_data:
        header, encoded_data = image_data.split(",", 1)

        if not re.match(
            r"^data:image/(png|jpeg|jpg|webp);base64$",
            header,
            re.IGNORECASE
        ):
            raise ValueError("Unsupported image format.")

    else:
        encoded_data = image_data

    try:
        image_bytes = base64.b64decode(
            encoded_data,
            validate=True
        )

        return BytesIO(image_bytes)

    except Exception as error:
        raise ValueError("Invalid image data.") from error


def prepare_image(image_data):
    """Decode an illustration and normalise it to a compact RGB JPEG."""

    buffer = decode_image(image_data)

    if buffer is None:
        return None

    raw = buffer.getvalue()

    try:
        from PIL import Image as PILImage

        with PILImage.open(BytesIO(raw)) as source:
            if source.mode in ("RGBA", "LA", "P"):
                rgba = source.convert("RGBA")
                flat = PILImage.new("RGB", rgba.size, (255, 255, 255))
                flat.paste(rgba, mask=rgba.split()[-1])
            else:
                flat = source.convert("RGB")

            flat.thumbnail((1600, 1600))

            output = BytesIO()
            flat.save(output, "JPEG", quality=90, optimize=True)

            return output.getvalue()

    except Exception:
        # Fall back to the original bytes; ReportLab may still read them.
        return raw


class RoundedImage(Flowable):
    """An illustration with rounded (or arched) corners, a white mat and a soft shadow."""

    def __init__(
        self,
        image_bytes,
        max_width,
        max_height,
        shape="rounded",
        radius=14,
        border=4,
        fill_box=False
    ):
        super().__init__()

        self.reader = ImageReader(BytesIO(image_bytes))

        source_width, source_height = self.reader.getSize()

        self.shape = shape
        self.radius = radius
        self.border = border
        self.fill_box = fill_box

        if fill_box:
            # Fixed frame; the picture is cropped to fill it.
            self.image_width = max_width - 2 * border
            self.image_height = max_height - 2 * border
        else:
            scale = min(
                (max_width - 2 * border) / source_width,
                (max_height - 2 * border) / source_height
            )

            self.image_width = source_width * scale
            self.image_height = source_height * scale

        self.source_width = source_width
        self.source_height = source_height

        self.width = self.image_width + 2 * border
        self.height = self.image_height + 2 * border

        self.hAlign = "CENTER"

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def _arch(self, path, x, y, w, h, bottom_radius):
        top = w / 2
        k = 0.5523
        b = bottom_radius

        path.moveTo(x, y + b)
        path.lineTo(x, y + h - top)
        path.curveTo(x, y + h - top + k * top, x + top - k * top, y + h, x + top, y + h)
        path.curveTo(x + top + k * top, y + h, x + w, y + h - top + k * top, x + w, y + h - top)
        path.lineTo(x + w, y + b)
        path.curveTo(x + w, y + b - k * b, x + w - b + k * b, y, x + w - b, y)
        path.lineTo(x + b, y)
        path.curveTo(x + b - k * b, y, x, y + b - k * b, x, y + b)
        path.close()

    def _outline(self, path, x, y, w, h, inset):
        if self.shape == "arch":
            self._arch(path, x, y, w, h, max(4, self.radius - inset))
        else:
            path.roundRect(x, y, w, h, max(2, self.radius - inset))

    def draw(self):
        canvas = self.canv
        b = self.border

        # Soft shadow
        canvas.saveState()
        canvas.setFillColor(PLUM)
        canvas.setFillAlpha(0.14)
        shadow = canvas.beginPath()
        self._outline(shadow, 2, -3, self.width, self.height, 0)
        canvas.drawPath(shadow, stroke=0, fill=1)
        canvas.restoreState()

        # White mat
        canvas.saveState()
        canvas.setFillColor(colors.white)
        mat = canvas.beginPath()
        self._outline(mat, 0, 0, self.width, self.height, 0)
        canvas.drawPath(mat, stroke=0, fill=1)
        canvas.restoreState()

        # Picture, clipped to the rounded shape
        canvas.saveState()
        clip = canvas.beginPath()
        self._outline(clip, b, b, self.image_width, self.image_height, b)
        canvas.clipPath(clip, stroke=0, fill=0)

        if self.fill_box:
            scale = max(
                self.image_width / self.source_width,
                self.image_height / self.source_height
            )
            draw_width = self.source_width * scale
            draw_height = self.source_height * scale
            offset_x = b + (self.image_width - draw_width) / 2
            offset_y = b + (self.image_height - draw_height) / 2
        else:
            draw_width, draw_height = self.image_width, self.image_height
            offset_x, offset_y = b, b

        canvas.drawImage(
            self.reader,
            offset_x,
            offset_y,
            draw_width,
            draw_height,
            mask="auto"
        )

        canvas.restoreState()


class Ornament(Flowable):
    """A small divider: two lines with a sparkle in the middle."""

    def __init__(self, width=1.6 * inch, color=ROSE_DEEP):
        super().__init__()
        self.width = width
        self.height = 14
        self.color = color
        self.hAlign = "CENTER"

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        middle = self.width / 2

        canvas.saveState()
        canvas.setStrokeColor(self.color)
        canvas.setLineWidth(0.9)
        canvas.line(0, 7, middle - 14, 7)
        canvas.line(middle + 14, 7, self.width, 7)
        draw_star(canvas, middle, 7, 6, self.color)
        canvas.restoreState()


def draw_star(canvas, cx, cy, radius, color, alpha=1.0):
    """A four-point sparkle."""

    canvas.saveState()
    canvas.setFillColor(color)
    canvas.setFillAlpha(alpha)

    path = canvas.beginPath()

    for step in range(8):
        angle = math.pi / 4 * step - math.pi / 2
        distance = radius if step % 2 == 0 else radius * 0.36
        x = cx + distance * math.cos(angle)
        y = cy + distance * math.sin(angle)

        if step == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)

    path.close()
    canvas.drawPath(path, stroke=0, fill=1)
    canvas.restoreState()


def make_image_flowable(
    image_data,
    width,
    height,
    shape="rounded",
    fill_box=False
):
    """Convert an image into a proportionally sized PDF illustration."""

    try:
        image_bytes = prepare_image(image_data)

        if image_bytes is None:
            return None

        return RoundedImage(
            image_bytes,
            width,
            height,
            shape=shape,
            radius=26 if shape == "arch" else 14,
            border=5 if shape == "arch" else 4,
            fill_box=fill_box
        )

    except Exception as error:
        print(f"Could not process illustration: {error}")
        return None


# -------------------------------------------------
# Story layout helpers
# -------------------------------------------------

def split_story_into_pages(story, page_count):
    """Distribute story text across the interior pages."""

    interior_count = max(1, page_count - 2)
    story = story or ""

    # Preferred: the story service already split it page by page.
    if PAGE_BREAK in story:
        sections = [section.strip() for section in story.split(PAGE_BREAK)]

        if len(sections) == interior_count and all(sections):
            return sections

        story = story.replace(PAGE_BREAK, "\n\n")

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", story)
        if paragraph.strip()
    ]

    if not paragraphs:
        return [""] * interior_count

    pages = []

    for index in range(interior_count):
        start = index * len(paragraphs) // interior_count
        end = (index + 1) * len(paragraphs) // interior_count

        pages.append(
            "\n\n".join(paragraphs[start:end])
        )

    return pages


def image_page_indices(interior_count, image_count):
    """
    Which interior page (0-based) each interior illustration belongs to.
    Identical to imagePageIndices() in script.js and the story service.
    """

    if image_count <= 0 or interior_count <= 0:
        return []

    if image_count == 1:
        return [interior_count // 2]

    indices = []

    for index in range(image_count):
        if image_count <= interior_count:
            indices.append(
                (2 * index * (interior_count - 1) + (image_count - 1))
                // (2 * (image_count - 1))
            )
        else:
            indices.append(
                min(interior_count - 1, index * interior_count // image_count)
            )

    return indices


def distribute_images(images, page_count):
    """Assign all images to the cover (key 0) or interior pages (key = index + 1)."""

    assignments = {}

    if not images:
        return assignments

    assignments[0] = [images[0]]

    interior_count = max(1, page_count - 2)

    for page_index, image in zip(
        image_page_indices(interior_count, len(images) - 1),
        images[1:]
    ):
        assignments.setdefault(page_index + 1, []).append(image)

    return assignments


def safe_text(text):
    """Keep only characters the built-in PDF fonts can draw (no emoji boxes)."""

    text = (
        (text or "")
        .replace("\u2011", "-")
        .replace("\u2028", " ")
        .replace("\u00a0", " ")
    )

    return text.encode("cp1252", "ignore").decode("cp1252")


def rich_text(text):
    """Escape for ReportLab, then turn **bold** and *italic* into real styling."""

    escaped = escape(safe_text(text))

    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)

    return escaped.replace("*", "")


def measure(flowables, width):
    """Total height the flowables will use at this width."""

    total = 0

    for flowable in flowables:
        _, height = flowable.wrap(width, 10000)

        total += (
            height
            + flowable.getSpaceBefore()
            + flowable.getSpaceAfter()
        )

    return total


def centered(flowables, width, height, bias=0.5):
    """Pad the top so the content sits in the middle of the frame."""

    used = measure(flowables, width)

    if used >= height:
        return flowables

    return [Spacer(1, (height - used) * bias)] + flowables


def image_block(page_images, available_width):
    """Lay out one to four illustrations as a single flowable."""

    count = len(page_images)

    if count == 0:
        return None

    if count == 1:
        columns, cell_width, max_height = 1, available_width * 0.94, 4.3 * inch
    elif count == 2:
        columns, cell_width, max_height = 2, available_width / 2 - 8, 3.2 * inch
    elif count == 3:
        columns, cell_width, max_height = 3, available_width / 3 - 8, 2.5 * inch
    else:
        rows = math.ceil(count / 2)
        columns = 2
        cell_width = available_width / 2 - 8
        max_height = min(2.4 * inch, 4.4 * inch / rows - 10)

    flowables = [
        make_image_flowable(image, cell_width, max_height)
        for image in page_images
    ]

    flowables = [flowable for flowable in flowables if flowable is not None]

    if not flowables:
        return None

    if columns == 1:
        return flowables[0]

    rows_of_images = [
        flowables[start:start + columns]
        for start in range(0, len(flowables), columns)
    ]

    for row in rows_of_images:
        row.extend([""] * (columns - len(row)))

    table = Table(
        rows_of_images,
        colWidths=[available_width / columns] * columns
    )

    table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    return table


# -------------------------------------------------
# Page decoration (drawn behind the text)
# -------------------------------------------------

def draw_frame(canvas, inset, color, width, radius=24, alpha=1.0):
    page_width, page_height = A4

    canvas.saveState()
    canvas.setStrokeColor(color)
    canvas.setLineWidth(width)
    canvas.setStrokeAlpha(alpha)
    canvas.roundRect(
        inset,
        inset,
        page_width - 2 * inset,
        page_height - 2 * inset,
        radius,
        stroke=1,
        fill=0
    )
    canvas.restoreState()


def draw_blob(canvas, x, y, radius, color, alpha):
    canvas.saveState()
    canvas.setFillColor(color)
    canvas.setFillAlpha(alpha)
    canvas.circle(x, y, radius, stroke=0, fill=1)
    canvas.restoreState()


def paint_cover(canvas):
    width, height = A4

    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, width, height, stroke=0, fill=1)

    draw_blob(canvas, 40, height - 30, 210, ROSE, 0.55)
    draw_blob(canvas, width - 20, 60, 230, LAVENDER, 0.75)
    draw_blob(canvas, width - 60, height - 90, 90, BUTTER, 0.7)
    draw_blob(canvas, 70, 150, 70, MINT, 0.8)

    for x, y, size, color in (
        (90, height - 150, 11, ROSE_DEEP),
        (width - 100, height - 210, 9, PLUM),
        (66, 330, 8, ROSE_DEEP),
        (width - 76, 270, 12, PLUM),
        (width / 2 + 130, 90, 8, ROSE_DEEP),
    ):
        draw_star(canvas, x, y, size, color, alpha=0.55)

    draw_frame(canvas, 26, PLUM, 1.6, alpha=0.55)
    draw_frame(canvas, 34, ROSE_DEEP, 0.6, radius=19, alpha=0.5)


def paint_story_page(canvas, page_number):
    width, height = A4

    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, width, height, stroke=0, fill=1)

    draw_blob(canvas, width - 10, height - 10, 120, ROSE_SOFT, 0.9)
    draw_blob(canvas, 10, 10, 110, LAVENDER_SOFT, 0.95)
    draw_blob(canvas, 14, height - 40, 40, MINT, 0.5)

    draw_star(canvas, width - 64, height - 62, 9, ROSE_DEEP, alpha=0.5)
    draw_star(canvas, 62, 72, 8, PLUM, alpha=0.45)

    draw_frame(canvas, 28, LAVENDER, 1.4)

    # Page number in a small pastel badge
    canvas.saveState()
    canvas.setFillColor(LAVENDER_SOFT)
    canvas.circle(width / 2, 46, 13, stroke=0, fill=1)
    canvas.setFillColor(PLUM)
    canvas.setFont("Times-Bold", 11)
    canvas.drawCentredString(width / 2, 42, str(page_number))
    canvas.restoreState()


def paint_ending(canvas):
    width, height = A4

    canvas.setFillColor(colors.HexColor("#F6EFFB"))
    canvas.rect(0, 0, width, height, stroke=0, fill=1)

    draw_blob(canvas, 30, height - 20, 200, BUTTER, 0.6)
    draw_blob(canvas, width - 30, 40, 220, ROSE, 0.55)
    draw_blob(canvas, width - 40, height - 120, 70, MINT, 0.8)

    for x, y, size, color in (
        (110, height - 190, 10, ROSE_DEEP),
        (width - 110, height - 300, 9, PLUM),
        (80, 260, 11, PLUM),
        (width - 90, 190, 8, ROSE_DEEP),
    ):
        draw_star(canvas, x, y, size, color, alpha=0.5)

    draw_frame(canvas, 26, PLUM, 1.6, alpha=0.5)
    draw_frame(canvas, 34, ROSE_DEEP, 0.6, radius=19, alpha=0.45)


# -------------------------------------------------
# PDF builder
# -------------------------------------------------

def create_storybook_pdf(
    title,
    story,
    image=None,
    moral="",
    age=6,
    images=None,
    pages=10
):
    """Create a multi-page illustrated children's storybook."""

    if pages not in (6, 10, 15):
        raise ValueError("Supported page counts are 6, 10 and 15.")

    if images is None:
        images = []

    # Support older requests that send only one cover image.
    if not images and image:
        images = [image]

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.85 * inch,
        leftMargin=0.85 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.85 * inch,
        title=safe_text(title),
        author="StoryBloom 2.0"
    )

    frame_width = document.width - 12
    frame_height = document.height - 12

    # Younger readers get larger type.
    try:
        reader_age = int(age)
    except (TypeError, ValueError):
        reader_age = 7

    if reader_age <= 6:
        body_size, body_leading = 16, 26
    elif reader_age <= 9:
        body_size, body_leading = 14.5, 23.5
    else:
        body_size, body_leading = 13, 21

    styles = getSampleStyleSheet()

    cover_brand = ParagraphStyle(
        "CoverBrand",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=15,
        leading=20,
        alignment=TA_CENTER,
        textColor=ROSE_DEEP,
        spaceAfter=8
    )

    cover_heading = ParagraphStyle(
        "CoverHeading",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=34,
        leading=40,
        alignment=TA_CENTER,
        textColor=INK,
        spaceAfter=10
    )

    cover_subtitle = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=13,
        leading=18,
        alignment=TA_CENTER,
        textColor=MUTED,
        spaceAfter=6
    )

    chapter_heading = ParagraphStyle(
        "ChapterHeading",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        textColor=ROSE_DEEP,
        spaceAfter=4
    )

    story_style = ParagraphStyle(
        "StoryText",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=body_size,
        leading=body_leading,
        alignment=TA_LEFT,
        textColor=TEXT,
        spaceAfter=body_leading * 0.45
    )

    end_heading = ParagraphStyle(
        "EndHeading",
        parent=styles["Title"],
        fontName="Times-BoldItalic",
        fontSize=40,
        leading=46,
        alignment=TA_CENTER,
        textColor=PLUM,
        spaceAfter=8
    )

    moral_label = ParagraphStyle(
        "MoralLabel",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=17,
        leading=22,
        alignment=TA_CENTER,
        textColor=ROSE_DEEP,
        spaceAfter=6
    )

    moral_style = ParagraphStyle(
        "MoralText",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=19,
        leading=29,
        alignment=TA_CENTER,
        textColor=TEXT,
        leftIndent=24,
        rightIndent=24
    )

    story_pages = split_story_into_pages(story, pages)
    image_assignments = distribute_images(images, pages)

    story_content = []

    # -------------------------------------------------
    # PAGE 1: COVER
    # -------------------------------------------------

    cover_content = [
        Spacer(1, 0.3 * inch),
        Paragraph("A StoryBloom original", cover_brand),
        Spacer(1, 0.08 * inch),
        Paragraph(rich_text(title), cover_heading),
        Ornament(),
        Spacer(1, 0.22 * inch)
    ]

    for cover_image in image_assignments.get(0, []):
        picture = make_image_flowable(
            cover_image,
            4.3 * inch,
            5.1 * inch,
            shape="arch",
            fill_box=True
        )

        if picture:
            cover_content.append(picture)
            cover_content.append(Spacer(1, 0.2 * inch))

    cover_content.append(
        Paragraph(
            f"A magical adventure for readers aged {escape(str(age))}",
            cover_subtitle
        )
    )

    story_content.append(
        KeepInFrame(
            frame_width,
            frame_height,
            centered(cover_content, frame_width, frame_height, bias=0.4),
            mode="shrink"
        )
    )

    story_content.append(PageBreak())

    # -------------------------------------------------
    # INTERIOR STORY PAGES
    # -------------------------------------------------

    for index, page_text in enumerate(story_pages):

        page_content = [
            Paragraph(f"Chapter {index + 1}", chapter_heading),
            Ornament(width=1.1 * inch),
            Spacer(1, 0.18 * inch)
        ]

        block = image_block(
            image_assignments.get(index + 1, []),
            frame_width
        )

        if block is not None:
            page_content.append(block)
            page_content.append(Spacer(1, 0.22 * inch))

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n|\n", page_text)
            if paragraph.strip()
        ]

        for paragraph in paragraphs:
            page_content.append(
                Paragraph(
                    rich_text(paragraph),
                    story_style
                )
            )

        if not paragraphs:
            page_content.append(
                Paragraph(
                    "The adventure continues...",
                    story_style
                )
            )

        story_content.append(
            KeepInFrame(
                frame_width,
                frame_height,
                centered(page_content, frame_width, frame_height),
                mode="shrink"
            )
        )

        story_content.append(PageBreak())

    # -------------------------------------------------
    # FINAL PAGE: ENDING AND MORAL
    # -------------------------------------------------

    moral_text = (moral or "").strip() or (
        "Every adventure teaches us something beautiful."
    )

    final_content = [
        Paragraph("The End", end_heading),
        Ornament(width=2.0 * inch),
        Spacer(1, 0.45 * inch),
        Paragraph("The Little Lesson", moral_label),
        Spacer(1, 0.1 * inch),
        Paragraph(rich_text(moral_text), moral_style),
        Spacer(1, 0.7 * inch),
        Paragraph("Thank you for reading!", cover_subtitle),
        Paragraph("Made with StoryBloom 2.0", cover_subtitle)
    ]

    story_content.append(
        KeepInFrame(
            frame_width,
            frame_height,
            centered(final_content, frame_width, frame_height, bias=0.45),
            mode="shrink"
        )
    )

    # -------------------------------------------------
    # PAGE BACKGROUNDS AND NUMBERS
    # -------------------------------------------------

    total_pages = pages

    def decorate_page(canvas, doc):
        canvas.saveState()

        if doc.page == 1:
            paint_cover(canvas)
        elif doc.page >= total_pages:
            paint_ending(canvas)
        else:
            paint_story_page(canvas, doc.page)

        canvas.restoreState()

    document.build(
        story_content,
        onFirstPage=decorate_page,
        onLaterPages=decorate_page
    )

    pdf_bytes = buffer.getvalue()

    buffer.close()

    return pdf_bytes
