const API_URL = "http://127.0.0.1:8000";

// Marker the backend places between story pages (see storybook_service.py).
// If it is missing, the story is split into pages by paragraph instead.
const PAGE_BREAK = "<<<PAGE_BREAK>>>";

// Must match the CSS page-turn duration (0.65s) plus a small buffer.
const TRANSITION_MS = 700;

// Form elements
const storyForm = document.getElementById("storyForm");
const topicInput = document.getElementById("topic");
const ageInput = document.getElementById("age");
const moralInput = document.getElementById("moral");
const pagesInput = document.getElementById("pages");
const imageCountInput = document.getElementById("imageCount");
const generateButton = document.getElementById("generateButton");
const ideaChips = document.querySelectorAll(".chip");

// Sections
const heroSection = document.getElementById("heroSection");
const loadingSection = document.getElementById("loadingSection");
const loadingMessage = document.getElementById("loadingMessage");
const loadingProgress = document.querySelector(".loading-progress");
const errorSection = document.getElementById("errorSection");
const errorMessage = document.getElementById("errorMessage");
const resultSection = document.getElementById("resultSection");

// Book elements
const bookPages = document.getElementById("bookPages");
const pageIndicator = document.getElementById("pageIndicator");
const pageDots = document.getElementById("pageDots");
const bookDetails = document.getElementById("bookDetails");

// Buttons
const prevPageButton = document.getElementById("prevPage");
const nextPageButton = document.getElementById("nextPage");
const downloadBookButton = document.getElementById("downloadBookButton");
const downloadStatus = document.getElementById("downloadStatus");
const createAnotherButton = document.getElementById("createAnother");
const retryButton = document.getElementById("retryButton");

// Application state
let currentStorybook = null;
let currentPage = 0;
let lastRequest = null;
let loadingInterval = null;
let progressInterval = null;
let transitionTimer = null;

const loadingMessages = [
    "Dreaming up your story characters...",
    "Writing your magical adventure...",
    "Creating beautiful story illustrations...",
    "Bringing your characters to life...",
    "Adding the final magical touches...",
    "Almost ready to open your book..."
];


// -----------------------------
// LOADING
// -----------------------------

function startLoading(imageCount = 5) {
    let index = 0;
    const startedAt = Date.now();

    // Rough estimate: story first, then each illustration in turn.
    const estimatedSeconds = 20 + imageCount * 14;

    loadingMessage.textContent = loadingMessages[index];
    loadingProgress.style.width = "4%";

    clearInterval(loadingInterval);
    clearInterval(progressInterval);

    loadingInterval = setInterval(() => {
        index = (index + 1) % loadingMessages.length;
        loadingMessage.textContent = loadingMessages[index];
    }, 4500);

    // Ease towards 92% so the bar keeps moving but never claims to be done early.
    progressInterval = setInterval(() => {
        const elapsed = (Date.now() - startedAt) / 1000;
        const progress = 92 * (1 - Math.exp(-elapsed / (estimatedSeconds * 0.6)));

        loadingProgress.style.width = `${Math.max(4, progress).toFixed(1)}%`;
    }, 500);
}

function stopLoading() {
    clearInterval(loadingInterval);
    clearInterval(progressInterval);
}


// -----------------------------
// GENERATE COMPLETE STORYBOOK
// -----------------------------

async function generateStorybook(requestData) {
    const response = await fetch(`${API_URL}/api/storybook`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(requestData)
    });

    if (!response.ok) {
        let message = "Could not generate your storybook.";

        try {
            const errorData = await response.json();
            message = errorData.detail || message;
        } catch (_) {}

        throw new Error(message);
    }

    return await response.json();
}


// -----------------------------
// TEXT HELPERS
// -----------------------------

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

function splitStory(story) {
    return String(story ?? "")
        .split(/\n\s*\n/)
        .map(paragraph => paragraph.trim())
        .filter(paragraph => paragraph.length > 0);
}

// Light formatting: **bold** and *italic* from the model become real styling.
function formatInline(text) {
    return escapeHTML(text)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>");
}


// -----------------------------
// STORY PAGE GENERATION
// -----------------------------

// Returns one array of paragraphs for each interior page (pages 2 .. N-1).
function distributeStory(story, totalPages) {
    const interiorPageCount = Math.max(1, totalPages - 2);
    const text = String(story ?? "");

    // Preferred: the backend already split the story page by page.
    if (text.includes(PAGE_BREAK)) {
        const sections = text.split(PAGE_BREAK).map(section => section.trim());

        if (
            sections.length === interiorPageCount &&
            sections.every(section => section.length > 0)
        ) {
            return sections.map(splitStory);
        }
    }

    // Fallback: spread paragraphs evenly using integer maths.
    const paragraphs = splitStory(text.split(PAGE_BREAK).join("\n\n"));
    const pages = [];

    for (let index = 0; index < interiorPageCount; index++) {
        const start = Math.floor(index * paragraphs.length / interiorPageCount);
        const end = Math.floor((index + 1) * paragraphs.length / interiorPageCount);

        pages.push(paragraphs.slice(start, end));
    }

    return pages;
}


// -----------------------------
// IMAGE DISTRIBUTION
// -----------------------------

// Which interior page (0-based) each interior illustration belongs to.
// This must stay identical to image_page_indices() in the Python services,
// so every illustration sits beside the scene it was painted for.
function imagePageIndices(interiorPageCount, imageCount) {
    if (imageCount <= 0 || interiorPageCount <= 0) return [];

    if (imageCount === 1) {
        return [Math.floor(interiorPageCount / 2)];
    }

    const indices = [];

    for (let index = 0; index < imageCount; index++) {
        if (imageCount <= interiorPageCount) {
            // Evenly spaced, rounding half up with integer maths.
            indices.push(
                Math.floor(
                    (2 * index * (interiorPageCount - 1) + (imageCount - 1)) /
                    (2 * (imageCount - 1))
                )
            );
        } else {
            // More pictures than pages: share them out evenly.
            indices.push(
                Math.min(
                    interiorPageCount - 1,
                    Math.floor(index * interiorPageCount / imageCount)
                )
            );
        }
    }

    return indices;
}

// Returns { actualPageNumber: [image indexes] }. Image 0 is always the cover.
function getImageAssignments(totalPages, images) {
    const assignments = {};

    if (!images || images.length === 0) {
        return assignments;
    }

    assignments[0] = [0];

    const interiorPageCount = totalPages - 2;
    const pageIndexes = imagePageIndices(interiorPageCount, images.length - 1);

    pageIndexes.forEach((pageIndex, offset) => {
        const actualPageNumber = pageIndex + 2;

        if (!assignments[actualPageNumber]) {
            assignments[actualPageNumber] = [];
        }

        assignments[actualPageNumber].push(offset + 1);
    });

    return assignments;
}


// -----------------------------
// BOOK PAGE CREATION
// -----------------------------

function createPage(className, content) {
    const page = document.createElement("article");

    page.className = `book-page ${className}`;
    page.innerHTML = content;

    bookPages.appendChild(page);
}


function buildBook(data) {
    currentStorybook = data;
    currentPage = 0;

    clearTimeout(transitionTimer);

    bookPages.innerHTML = "";
    pageDots.innerHTML = "";

    const totalPages = data.pages;
    const images = Array.isArray(data.images) ? data.images : [];

    const storyPages = distributeStory(data.story, totalPages);
    const imageAssignments = getImageAssignments(totalPages, images);

    // -----------------------------
    // COVER PAGE
    // -----------------------------

    createPage(
        "cover-page",
        `
        <span class="spark s1" aria-hidden="true">✦</span>
        <span class="spark s2" aria-hidden="true">✦</span>
        <span class="spark s3" aria-hidden="true">✦</span>
        <span class="spark s4" aria-hidden="true">✦</span>

        <div class="page-inner">

            <p class="cover-kicker">A StoryBloom original</p>

            <h2>${escapeHTML(data.title)}</h2>

            ${images[0] ? `
                <div class="cover-art">
                    <img
                        class="book-cover-image"
                        src="${escapeHTML(images[0])}"
                        alt="Cover illustration for ${escapeHTML(data.title)}"
                    >
                </div>
            ` : ""}

            <p class="cover-footer">
                A magical adventure for age ${escapeHTML(data.age)}
            </p>

        </div>
        `
    );


    // -----------------------------
    // INTERIOR STORY PAGES
    // -----------------------------

    for (let index = 0; index < storyPages.length; index++) {
        const actualPageNumber = index + 2;
        const paragraphs = storyPages[index];

        const assignedImageIndexes =
            imageAssignments[actualPageNumber] || [];

        const illustrations = assignedImageIndexes
            .map(imageIndex => images[imageIndex])
            .filter(Boolean);

        const hasArt = illustrations.length > 0;

        const storyText = paragraphs.length
            ? paragraphs.map(paragraph => `<p>${formatInline(paragraph)}</p>`).join("")
            : "<p>The adventure continues...</p>";

        const illustrationHTML = illustrations.map(
            (illustration, imageIndex) => `
                <img
                    class="story-scene-image"
                    src="${escapeHTML(illustration)}"
                    alt="Illustration ${imageIndex + 1} for chapter ${index + 1}"
                >
            `
        ).join("");

        // Alternate the picture side so the book has a natural rhythm.
        const classes = [
            "story-page",
            hasArt ? "has-art" : "text-only",
            index % 2 === 1 ? "flip" : ""
        ].join(" ").trim();

        createPage(
            classes,
            `
            <div class="page-inner">

                <p class="chapter-mark">Chapter ${index + 1}</p>

                <div class="story-spread">

                    ${hasArt ? `
                        <div class="story-art art-count-${Math.min(illustrations.length, 4)}">
                            ${illustrationHTML}
                        </div>
                    ` : ""}

                    <div class="story-text">
                        ${storyText}
                    </div>

                </div>

                <div class="story-page-number">
                    ${actualPageNumber}
                </div>

            </div>
            `
        );
    }


    // -----------------------------
    // ENDING PAGE
    // -----------------------------

    createPage(
        "moral-page",
        `
        <div class="page-inner">

            <div class="moral-icon" aria-hidden="true">🌟</div>

            <h2>The Little Lesson</h2>

            <p>
                ${escapeHTML(
                    data.moral ||
                    "Every adventure teaches us something beautiful."
                )}
            </p>

            <p class="cover-footer">
                The End. Keep dreaming!
            </p>

            <button type="button" class="reread" data-go="0">
                Read it again
            </button>

        </div>
        `
    );

    // Page dots are built once and updated on every page turn.
    const pageCount = bookPages.querySelectorAll(".book-page").length;

    for (let index = 0; index < pageCount; index++) {
        const dot = document.createElement("button");

        dot.type = "button";
        dot.className = "page-dot";
        dot.setAttribute("aria-label", `Go to page ${index + 1}`);
        dot.addEventListener("click", () => goToPage(index));

        pageDots.appendChild(dot);
    }

    bookDetails.textContent =
        `${totalPages} pages, ${images.length} illustrations`;

    renderPage();
}


// -----------------------------
// PAGE NAVIGATION
// -----------------------------

const TRANSITION_CLASSES = [
    "enter-next", "enter-prev", "leave-next", "leave-prev", "leaving"
];

function renderPage(direction = null, previousPage = null) {
    const pages = Array.from(bookPages.querySelectorAll(".book-page"));

    // Reset every page, then mark the active one.
    pages.forEach((page, index) => {
        page.classList.remove(...TRANSITION_CLASSES);
        page.classList.toggle("active", index === currentPage);
        page.setAttribute("aria-hidden", index === currentPage ? "false" : "true");
    });

    // Play the page-turn between the previous and the new page.
    if (direction && previousPage !== null && pages[previousPage]) {
        const outgoing = pages[previousPage];
        const incoming = pages[currentPage];

        outgoing.classList.add("leaving", `leave-${direction}`);
        incoming.classList.add(`enter-${direction}`);

        clearTimeout(transitionTimer);

        transitionTimer = setTimeout(() => {
            outgoing.classList.remove(...TRANSITION_CLASSES);
            incoming.classList.remove(...TRANSITION_CLASSES);
        }, TRANSITION_MS);
    }

    // A fresh page always starts at the top.
    pages[currentPage].scrollTop = 0;

    pageIndicator.textContent =
        `Page ${currentPage + 1} of ${pages.length}`;

    prevPageButton.disabled = currentPage === 0;
    nextPageButton.disabled = currentPage === pages.length - 1;

    pageDots.querySelectorAll(".page-dot").forEach((dot, index) => {
        dot.classList.toggle("active", index === currentPage);

        if (index === currentPage) {
            dot.setAttribute("aria-current", "true");
        } else {
            dot.removeAttribute("aria-current");
        }
    });
}

function goToPage(target) {
    const totalPages = bookPages.querySelectorAll(".book-page").length;

    if (target < 0 || target >= totalPages || target === currentPage) return;

    const direction = target > currentPage ? "next" : "prev";
    const previousPage = currentPage;

    currentPage = target;
    renderPage(direction, previousPage);
}


prevPageButton.addEventListener("click", () => goToPage(currentPage - 1));
nextPageButton.addEventListener("click", () => goToPage(currentPage + 1));

// "Read it again" button on the ending page.
bookPages.addEventListener("click", event => {
    const target = event.target.closest("[data-go]");

    if (target) {
        goToPage(Number(target.dataset.go));
    }
});

// Keyboard: left and right arrows turn pages while the book is on screen.
document.addEventListener("keydown", event => {
    if (resultSection.classList.contains("hidden")) return;

    const tag = (event.target.tagName || "").toLowerCase();

    if (["input", "textarea", "select"].includes(tag)) return;

    if (event.key === "ArrowRight") {
        goToPage(currentPage + 1);
    } else if (event.key === "ArrowLeft") {
        goToPage(currentPage - 1);
    }
});

// Touch: swipe left for the next page, right for the previous one.
let touchStartX = 0;
let touchStartY = 0;

bookPages.addEventListener("touchstart", event => {
    touchStartX = event.changedTouches[0].clientX;
    touchStartY = event.changedTouches[0].clientY;
}, { passive: true });

bookPages.addEventListener("touchend", event => {
    const deltaX = event.changedTouches[0].clientX - touchStartX;
    const deltaY = event.changedTouches[0].clientY - touchStartY;

    if (Math.abs(deltaX) > 55 && Math.abs(deltaY) < 60) {
        goToPage(currentPage + (deltaX < 0 ? 1 : -1));
    }
}, { passive: true });


// -----------------------------
// STORY IDEA CHIPS
// -----------------------------

ideaChips.forEach(chip => {
    chip.addEventListener("click", () => {
        topicInput.value = chip.dataset.idea;
        topicInput.setCustomValidity("");
        topicInput.focus();
    });
});

topicInput.addEventListener("input", () => topicInput.setCustomValidity(""));


// -----------------------------
// FORM SUBMISSION
// -----------------------------

storyForm.addEventListener("submit", async event => {
    event.preventDefault();

    const requestData = {
        topic: topicInput.value.trim(),
        age: Number(ageInput.value),
        moral: moralInput.value.trim(),
        pages: Number(pagesInput.value),
        image_count: Number(imageCountInput.value)
    };

    if (requestData.topic.length < 3) {
        topicInput.setCustomValidity(
            "Please enter a story topic with at least 3 characters."
        );
        topicInput.reportValidity();
        return;
    }

    lastRequest = requestData;

    heroSection.classList.add("hidden");
    resultSection.classList.add("hidden");
    errorSection.classList.add("hidden");
    loadingSection.classList.remove("hidden");

    window.scrollTo({ top: 0, behavior: "smooth" });

    generateButton.disabled = true;

    startLoading(requestData.image_count);

    try {
        const data = await generateStorybook(requestData);

        if (
            !data.title ||
            !data.story ||
            !Array.isArray(data.images)
        ) {
            throw new Error(
                "The server returned an incomplete storybook."
            );
        }

        if (data.images.length !== requestData.image_count) {
            throw new Error(
                `Expected ${requestData.image_count} illustrations, but received ${data.images.length}.`
            );
        }

        if (data.pages !== requestData.pages) {
            throw new Error(
                "The server returned an unexpected page count."
            );
        }

        buildBook(data);

        loadingProgress.style.width = "100%";

        loadingSection.classList.add("hidden");
        resultSection.classList.remove("hidden");

        resultSection.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    } catch (error) {
        console.error("Storybook generation error:", error);

        loadingSection.classList.add("hidden");
        errorSection.classList.remove("hidden");

        errorMessage.textContent =
            error instanceof TypeError
                ? `Can't reach the StoryBloom server at ${API_URL}. Check that the backend is running, then try again.`
                : error.message;

    } finally {
        stopLoading();
        generateButton.disabled = false;
    }
});


// -----------------------------
// PDF DOWNLOAD
// -----------------------------

downloadBookButton.addEventListener("click", async () => {
    if (!currentStorybook) return;

    downloadBookButton.disabled = true;

    downloadStatus.textContent =
        "Preparing your illustrated storybook...";

    try {
        const response = await fetch(`${API_URL}/api/book`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                title: currentStorybook.title,
                story: currentStorybook.story,

                // Send every generated illustration.
                images: currentStorybook.images || [],

                // Keep backward compatibility.
                image: currentStorybook.images?.[0] || null,

                moral: currentStorybook.moral,
                age: currentStorybook.age,

                // Preserve the selected total page count.
                pages: currentStorybook.pages
            })
        });

        if (!response.ok) {
            let message = "PDF generation failed.";

            try {
                const errorData = await response.json();
                message = errorData.detail || message;
            } catch (_) {}

            throw new Error(message);
        }

        const blob = await response.blob();

        const url = URL.createObjectURL(blob);

        const link = document.createElement("a");

        link.href = url;
        link.download = "StoryBloom-Storybook.pdf";

        document.body.appendChild(link);

        link.click();
        link.remove();

        setTimeout(() => URL.revokeObjectURL(url), 1000);

        downloadStatus.textContent =
            "Your illustrated storybook is ready! 🌷";

    } catch (error) {
        console.error("PDF download error:", error);

        downloadStatus.textContent = error.message;

    } finally {
        downloadBookButton.disabled = false;
    }
});


// -----------------------------
// CREATE ANOTHER STORY
// -----------------------------

createAnotherButton.addEventListener("click", () => {
    currentStorybook = null;
    currentPage = 0;

    storyForm.reset();

    resultSection.classList.add("hidden");
    errorSection.classList.add("hidden");

    heroSection.classList.remove("hidden");

    downloadStatus.textContent = "";

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
});


// -----------------------------
// RETRY GENERATION
// -----------------------------

retryButton.addEventListener("click", () => {
    if (!lastRequest) return;

    topicInput.value = lastRequest.topic;
    ageInput.value = String(lastRequest.age);
    moralInput.value = lastRequest.moral;
    pagesInput.value = String(lastRequest.pages);
    imageCountInput.value = String(lastRequest.image_count);

    storyForm.requestSubmit();
});
