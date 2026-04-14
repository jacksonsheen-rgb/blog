// ---------------------------------------------------------------------------
// The Green Room — Client-side JS
// Handles: featured post injection, sorting
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  // Detect base URL from the script's own path
  const scriptSrc = document.querySelector('script[src*="main.js"]')?.src || "";
  const baseUrl = scriptSrc.replace(/\/static\/js\/main\.js.*$/, "");
  const basePath = new URL(baseUrl).pathname.replace(/\/$/, "");

  // Only run on homepage
  const latestSection = document.querySelector(".latest-post .section-inner");
  const grid = document.getElementById("posts-grid");
  if (!latestSection || !grid) return;

  // Load posts data for sorting
  let postsData = [];
  try {
    const res = await fetch(basePath + "/static/js/posts.json");
    postsData = await res.json();
  } catch (e) {
    console.warn("Could not load posts.json", e);
  }

  // Inject featured (latest) post card
  const cards = grid.querySelectorAll(".post-card");
  if (cards.length > 0) {
    const first = cards[0];
    const title = first.querySelector(".post-card-title")?.textContent || "";
    const desc = first.querySelector(".post-card-desc")?.textContent || "";
    const time = first.querySelector("time")?.textContent || "";
    const slug = first.dataset.slug || "";

    latestSection.innerHTML += `
      <a href="${basePath}/${slug}/" class="featured-card">
        <div class="featured-card-image"></div>
        <div class="featured-card-content">
          <div class="featured-card-meta">${time}</div>
          <h2 class="featured-card-title">${title}</h2>
          <p class="featured-card-desc">${desc}</p>
        </div>
      </a>
    `;
  }

  // Sorting
  const sortBtns = document.querySelectorAll(".sort-btn");
  sortBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      sortBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const mode = btn.dataset.sort;
      const cardsArray = Array.from(grid.querySelectorAll(".post-card"));

      if (mode === "recent") {
        // Sort by date descending (original order from build)
        const sorted = [...postsData].sort(
          (a, b) => new Date(b.date) - new Date(a.date)
        );
        reorderCards(sorted, cardsArray);
      } else if (mode === "popular") {
        // Placeholder: shuffle to simulate popularity until real metrics exist
        // When you add analytics, replace this with actual view/comment counts
        const shuffled = [...postsData].sort(() => Math.random() - 0.5);
        reorderCards(shuffled, cardsArray);
      }
    });
  });

  function reorderCards(orderedData, cardElements) {
    const cardMap = {};
    cardElements.forEach((card) => {
      cardMap[card.dataset.slug] = card;
    });
    orderedData.forEach((post) => {
      const card = cardMap[post.slug];
      if (card) grid.appendChild(card);
    });
  }
});
