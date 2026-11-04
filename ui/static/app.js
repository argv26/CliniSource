// Client application logic for CliniSource Web Interface
// Adheres to SKILL-Ui (ui-ux-pro-max) Accessibility, Responsive Design, and SVG Icon Standards

const STARTER_PROMPTS = [
  {
    label: "Thyroid Hormone Synthesis",
    query: "How is thyroid hormone synthesized and regulated, and what are the main clinical signs of hypothyroidism?"
  },
  {
    label: "Femoral Triangle Anatomy",
    query: "What are the boundaries, contents, and clinical significance of the femoral triangle?"
  },
  {
    label: "Adrenal Cortex Steroidogenesis",
    query: "Explain the zones of the adrenal cortex and the specific hormones synthesized in each zone."
  },
  {
    label: "Brachial Plexus Organization",
    query: "Describe the roots, trunks, divisions, cords, and branches of the brachial plexus."
  }
];

// App State
let sessionId = "session_" + Math.random().toString(36).substring(2, 10);
let cachedBooks = [];
let activeBooksSet = new Set();
let scopeWarningTimer = null;
let citationsCache = new Map(); // citation_id -> citationRecord
let isAwaitingResponse = false;

// DOM Elements
const messagesContainer = document.getElementById("messages-container");
const heroWelcome = document.getElementById("hero-welcome");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");
const btnStop = document.getElementById("btn-stop");
const btnNewChat = document.getElementById("btn-new-chat");
const btnScrollBottom = document.getElementById("btn-scroll-bottom");
let currentAbortController = null;
let userHasScrolledUp = false;
const SCROLL_THRESHOLD = 80;
const libraryList = document.getElementById("library-list");
const btnSelectAllBooks = document.getElementById("btn-select-all-books");
const scopeWarningToast = document.getElementById("scope-warning-toast");
const scopeWarningText = document.getElementById("scope-warning-text");
const starterPromptList = document.getElementById("starter-prompt-list");
const heroCards = document.getElementById("hero-cards");
const activeBookIndicator = document.getElementById("active-book-indicator");
const evidenceDrawer = document.getElementById("evidence-drawer");
const drawerBackdrop = document.getElementById("drawer-backdrop");
const drawerContent = document.getElementById("drawer-content");
const btnCloseDrawer = document.getElementById("btn-close-drawer");
const btnToggleEvidence = document.getElementById("btn-toggle-evidence");
const evidenceCountBadge = document.getElementById("evidence-count-badge");
const quotaText = document.getElementById("quota-text");

// Session History Elements
const sessionsList = document.getElementById("sessions-list");
const sessionsLoading = document.getElementById("sessions-loading");
const sessionsEmpty = document.getElementById("sessions-empty");
const sessionsCountBadge = document.getElementById("sessions-count-badge");

// View Switcher & Dedicated Library Manager Elements
const tabViewConsultation = document.getElementById("tab-view-consultation");
const tabViewLibrary = document.getElementById("tab-view-library");
const viewConsultation = document.getElementById("view-consultation");
const viewLibrary = document.getElementById("view-library");
const btnOpenFullLibrary = document.getElementById("btn-open-full-library");
const btnReturnConsultation = document.getElementById("btn-return-consultation");
const sidebarBookCountBadge = document.getElementById("sidebar-book-count-badge");
const statUserBooks = document.getElementById("stat-user-books");
const statActiveBooks = document.getElementById("stat-active-books");
const statGlobalBooks = document.getElementById("stat-global-books");
const subtabMyLibrary = document.getElementById("subtab-my-library");
const subtabGlobalCatalog = document.getElementById("subtab-global-catalog");
const subpanelMyLibrary = document.getElementById("subpanel-my-library");
const subpanelGlobalCatalog = document.getElementById("subpanel-global-catalog");
const subtabMyLibraryCount = document.getElementById("subtab-my-library-count");
const subtabGlobalCatalogCount = document.getElementById("subtab-global-catalog-count");
const myLibraryGrid = document.getElementById("my-library-grid");
const myLibraryEmpty = document.getElementById("my-library-empty");
const globalCatalogSearch = document.getElementById("global-catalog-search");
const btnClearGlobalSearch = document.getElementById("btn-clear-global-search");
const globalCatalogList = document.getElementById("global-catalog-list");
const btnLibActivateAll = document.getElementById("btn-lib-activate-all");
const btnLibDeactivateAll = document.getElementById("btn-lib-deactivate-all");
const btnLibGotoGlobal = document.getElementById("btn-lib-goto-global");
const btnEmptyBrowseGlobal = document.getElementById("btn-empty-browse-global");

// Upload Textbook Modal Elements
const btnOpenUploadModal = document.getElementById("btn-open-upload-modal");
const modalUploadBook = document.getElementById("modal-upload-book");
const btnCloseUploadModal = document.getElementById("btn-close-upload-modal");
const btnCancelUpload = document.getElementById("btn-cancel-upload");
const formUploadBook = document.getElementById("form-upload-book");
const uploadDropzone = document.getElementById("upload-dropzone");
const inputUploadFile = document.getElementById("input-upload-file");
const dropzoneEmptyState = document.getElementById("dropzone-empty-state");
const dropzoneFileState = document.getElementById("dropzone-file-state");
const selectedFileName = document.getElementById("selected-file-name");
const selectedFileSize = document.getElementById("selected-file-size");
const btnRemoveSelectedFile = document.getElementById("btn-remove-selected-file");
const inputUploadTitle = document.getElementById("input-upload-title");
const inputUploadSpecialty = document.getElementById("input-upload-specialty");
const uploadTitleDuplicateWarning = document.getElementById("upload-title-duplicate-warning");
const uploadFormError = document.getElementById("upload-form-error");
const btnSubmitUpload = document.getElementById("btn-submit-upload");

// Upload Progress & Notification Elements
const uploadProgressView = document.getElementById("upload-progress-view");
const uploadProgressStageLabel = document.getElementById("upload-progress-stage-label");
const uploadProgressPercent = document.getElementById("upload-progress-percent");
const uploadProgressBar = document.getElementById("upload-progress-bar");
const uploadProgressMessage = document.getElementById("upload-progress-message");
const stepPillValidate = document.getElementById("step-pill-validate");
const stepPillToc = document.getElementById("step-pill-toc");
const stepPillExtract = document.getElementById("step-pill-extract");
const stepPillReady = document.getElementById("step-pill-ready");
const uploadFailureCard = document.getElementById("upload-failure-card");
const uploadFailureReason = document.getElementById("upload-failure-reason");
const btnTryAnotherUpload = document.getElementById("btn-try-another-upload");
const uploadSuccessCard = document.getElementById("upload-success-card");
const uploadSuccessDetail = document.getElementById("upload-success-detail");
const btnDoneUpload = document.getElementById("btn-done-upload");

let selectedUploadFile = null;
let currentIngestionJobId = null;
let ingestionPollInterval = null;

let globalCatalogData = [];
let currentView = "consultation"; // "consultation" | "library"
let currentLibrarySubtab = "my-library"; // "my-library" | "global-catalog"
let globalSearchQuery = "";

// Responsive Mobile Sidebar Elements
const appSidebar = document.getElementById("app-sidebar");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const btnMobileMenu = document.getElementById("btn-mobile-menu");
const btnCloseSidebar = document.getElementById("btn-close-sidebar");

// User Authentication State & Elements
let currentUser = null;
let authMode = "login"; // "login" | "signup"

const authDropdownWrapper = document.getElementById("auth-dropdown-wrapper");
const btnAuthTrigger = document.getElementById("btn-auth-trigger");
const authUserLabel = document.getElementById("auth-user-label");
const authUserMenu = document.getElementById("auth-user-menu");
const authMenuUsername = document.getElementById("auth-menu-username");
const authMenuStatus = document.getElementById("auth-menu-status");
const btnMenuOpenAuth = document.getElementById("btn-menu-open-auth");
const btnMenuOpenAuthLabel = document.getElementById("btn-menu-open-auth-label");
const btnMenuLogout = document.getElementById("btn-menu-logout");

const authModal = document.getElementById("auth-modal");
const btnCloseAuthModal = document.getElementById("btn-close-auth-modal");
const btnGuestLogin = document.getElementById("btn-guest-login");
const tabLogin = document.getElementById("tab-login");
const tabSignup = document.getElementById("tab-signup");
const authErrorBanner = document.getElementById("auth-error-banner");
const authErrorText = document.getElementById("auth-error-text");
const authForm = document.getElementById("auth-form");
const authUsernameInput = document.getElementById("auth-username");
const authPasswordInput = document.getElementById("auth-password");
const authUsernameHint = document.getElementById("auth-username-hint");
const btnAuthSubmit = document.getElementById("btn-auth-submit");
const authSubmitLabel = document.getElementById("auth-submit-label");
const authModalTitle = document.getElementById("auth-modal-title");

// Figure Lightbox Elements
const figureLightboxModal = document.getElementById("figure-lightbox-modal");
const btnCloseLightbox = document.getElementById("btn-close-lightbox");
const lightboxImg = document.getElementById("lightbox-img");
const lightboxTitle = document.getElementById("lightbox-title");
const lightboxPageBadge = document.getElementById("lightbox-page-badge");
const lightboxCaption = document.getElementById("lightbox-caption");

// Stethoscope Avatar SVG (Standardized Clean Icon)
const AVATAR_SVG = `
  <svg class="w-4 h-4 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3"/>
    <path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4"/>
    <circle cx="20" cy="10" r="2"/>
  </svg>
`;

// Initialize application
document.addEventListener("DOMContentLoaded", () => {
  setupMarkdown();
  fetchBooks();
  fetchQuota();
  checkAuthStatus();
  fetchSessions();
  renderStarterPrompts();
  bindEvents();
  updateSendButtonState();
});

function updateSendButtonState() {
  if (!btnSend || !chatInput) return;
  const hasText = chatInput.value.trim().length > 0;
  if (isAwaitingResponse) {
    btnSend.classList.add("hidden");
    if (btnStop) {
      btnStop.classList.remove("hidden");
      btnStop.classList.add("flex");
    }
  } else {
    if (btnStop) {
      btnStop.classList.add("hidden");
      btnStop.classList.remove("flex");
    }
    btnSend.classList.remove("hidden");
    btnSend.disabled = !hasText;
  }
}

async function fetchQuota() {
  try {
    const res = await fetch(`/api/quota?session_id=${sessionId}`);
    if (res.ok) {
      const data = await res.json();
      if (quotaText) {
        if (data.limit <= 0) {
          quotaText.textContent = "Unlimited";
        } else {
          quotaText.textContent = `${data.remaining}/${data.limit} left`;
          const container = quotaText.parentElement;
          if (container) {
            if (data.remaining === 0) {
              container.className = "px-2.5 py-1 rounded-lg bg-rose-50 border border-rose-200 text-xs font-medium text-rose-700 flex items-center gap-1.5 shadow-2xs";
            } else if (data.remaining <= 5) {
              container.className = "px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200 text-xs font-medium text-amber-700 flex items-center gap-1.5 shadow-2xs";
            } else {
              container.className = "px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-xs font-medium text-slate-600 flex items-center gap-1.5 shadow-2xs";
            }
          }
        }
      }
    }
  } catch (err) {
    console.error("Quota fetch failed:", err);
  }
}

function setupMarkdown() {
  if (window.marked) {
    const renderer = new marked.Renderer();
    const originalTable = renderer.table.bind(renderer);
    renderer.table = function (header, body) {
      const tableHtml = originalTable(header, body);
      return `<div class="table-responsive-wrapper">${tableHtml}</div>`;
    };
    marked.setOptions({
      renderer: renderer,
      breaks: true,
      gfm: true
    });
  }
}

// =============================================================================
// User Library, Global Catalog & Multi-View Navigation
// =============================================================================

// Fetch user library and global catalogue & initialize toggle state
async function fetchBooks() {
  try {
    const res = await fetch("/api/user/library");
    const data = await res.json();
    if (data.library) {
      cachedBooks = data.library;
      globalCatalogData = data.global_catalog || [];

      // Update activeBooksSet from server state
      activeBooksSet = new Set(cachedBooks.filter(b => b.is_active).map(b => b.slug));

      renderBookToggles();
      updateSidebarBadge();
      updateScopeIndicator();
      updateLibraryStats();
      renderMyLibraryGrid();
      renderGlobalCatalogList();
    }
  } catch (err) {
    console.error("Failed to load user library:", err);
    if (libraryList) {
      libraryList.innerHTML = '<div class="text-xs text-rose-500 font-medium py-2 text-center">Error loading library</div>';
    }
  }
}

function updateSidebarBadge() {
  if (sidebarBookCountBadge) {
    sidebarBookCountBadge.textContent = `${activeBooksSet.size} Active`;
  }
}

function updateLibraryStats() {
  if (statUserBooks) statUserBooks.textContent = cachedBooks.length;
  if (statActiveBooks) statActiveBooks.textContent = activeBooksSet.size;
  if (statGlobalBooks) statGlobalBooks.textContent = globalCatalogData.length;
  if (subtabMyLibraryCount) subtabMyLibraryCount.textContent = cachedBooks.length;
  if (subtabGlobalCatalogCount) subtabGlobalCatalogCount.textContent = globalCatalogData.length;
}

function renderBookToggles() {
  if (!libraryList) return;
  libraryList.innerHTML = "";

  if (cachedBooks.length === 0) {
    libraryList.innerHTML = '<div class="text-xs text-slate-400 py-3 text-center">No textbooks in study library</div>';
    return;
  }

  cachedBooks.forEach(b => {
    const isActive = activeBooksSet.has(b.slug);
    const card = document.createElement("div");

    if (isActive) {
      card.className = "p-2.5 rounded-xl bg-white border border-slate-200 hover:border-slate-300 transition duration-150 shadow-2xs";
    } else {
      card.className = "p-2.5 rounded-xl bg-slate-50/80 border border-slate-200 opacity-60 transition duration-150";
    }

    card.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0 flex-1">
          <div class="font-semibold text-xs text-slate-800 leading-snug line-clamp-2" title="${escapeHtml(b.title)}">
            ${escapeHtml(b.title)}
          </div>
          <div class="flex items-center gap-2 mt-1.5 text-xs">
            <span class="text-slate-600 font-mono">${b.total_pages ? b.total_pages.toLocaleString() + ' pp' : ''}</span>
            ${isActive 
              ? '<span class="inline-flex items-center gap-1 font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200/70 px-2 py-0.5 rounded-full"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>Active</span>'
              : '<span class="inline-flex items-center gap-1 font-medium text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-full"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span>Excluded</span>'
            }
          </div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked="${isActive}"
          aria-label="Toggle ${escapeHtml(b.title)} in search scope"
          class="toggle-switch relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${isActive ? 'bg-emerald-500' : 'bg-slate-300'}"
          data-slug="${escapeHtml(b.slug)}"
        >
          <span class="sr-only">Toggle ${escapeHtml(b.title)}</span>
          <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isActive ? 'translate-x-4' : 'translate-x-0'}"></span>
        </button>
      </div>
    `;

    const toggleBtn = card.querySelector(".toggle-switch");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        handleToggleBook(b.slug);
      });
    }

    libraryList.appendChild(card);
  });
}

async function handleToggleBook(slug, targetState = null) {
  const isCurrentlyActive = activeBooksSet.has(slug);
  const nextState = targetState !== null ? targetState : !isCurrentlyActive;

  if (!nextState && activeBooksSet.size <= 1 && isCurrentlyActive) {
    showScopeWarning("At least 1 textbook must remain active for clinical search.");
    return;
  }

  if (nextState) {
    activeBooksSet.add(slug);
  } else {
    activeBooksSet.delete(slug);
  }

  const found = cachedBooks.find(b => b.slug === slug);
  if (found) found.is_active = nextState;

  saveActiveBooks();
  renderBookToggles();
  updateSidebarBadge();
  updateScopeIndicator();
  updateLibraryStats();
  renderMyLibraryGrid();

  try {
    await fetch("/api/user/library/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug, is_active: nextState })
    });
  } catch (e) {
    console.warn("Failed to persist book toggle to server:", e);
  }
}

async function handleAddBookToLibrary(slug) {
  try {
    const res = await fetch("/api/user/library/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug })
    });
    if (res.ok) {
      await fetchBooks();
    }
  } catch (e) {
    console.error("Failed to add book:", e);
  }
}

async function handleRemoveBookFromLibrary(slug) {
  if (cachedBooks.length <= 1) {
    showScopeWarning("Cannot remove the only textbook in your study library.");
    return;
  }
  try {
    const res = await fetch("/api/user/library/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug })
    });
    if (res.ok) {
      await fetchBooks();
    }
  } catch (e) {
    console.error("Failed to remove book:", e);
  }
}

async function handleToggleAllBooks(activeState) {
  if (!activeState && cachedBooks.length > 0) {
    showScopeWarning("At least 1 textbook must remain active for clinical search.");
    return;
  }
  try {
    const res = await fetch("/api/user/library/toggle-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: activeState })
    });
    if (res.ok) {
      await fetchBooks();
    }
  } catch (e) {
    console.error("Failed to toggle all books:", e);
  }
}

function showScopeWarning(msg) {
  if (!scopeWarningToast || !scopeWarningText) return;
  scopeWarningText.textContent = msg;
  scopeWarningToast.classList.remove("hidden");
  if (scopeWarningTimer) clearTimeout(scopeWarningTimer);
  scopeWarningTimer = setTimeout(() => {
    scopeWarningToast.classList.add("hidden");
  }, 3000);
}

function saveActiveBooks() {
  try {
    const serialized = JSON.stringify(Array.from(activeBooksSet));
    localStorage.setItem("clinisource_active_books", serialized);
    localStorage.setItem("textbook_rag_active_books", serialized);
  } catch (e) {
    console.error("Failed to save active books:", e);
  }
}

function updateScopeIndicator() {
  if (!activeBookIndicator || cachedBooks.length === 0) return;
  if (activeBooksSet.size === cachedBooks.length) {
    activeBookIndicator.textContent = `All Textbooks (${cachedBooks.length})`;
    activeBookIndicator.className = "font-semibold text-slate-800 bg-slate-100 border border-slate-200 px-2.5 py-0.5 rounded-full truncate max-w-[180px]";
    activeBookIndicator.title = "All textbooks active";
  } else if (activeBooksSet.size === 1) {
    const activeSlug = Array.from(activeBooksSet)[0];
    const found = cachedBooks.find(b => b.slug === activeSlug);
    activeBookIndicator.textContent = found ? found.title : "1 Textbook";
    activeBookIndicator.title = found ? found.title : "";
    activeBookIndicator.className = "font-semibold text-blue-800 bg-blue-50 border border-blue-200 px-2.5 py-0.5 rounded-full truncate max-w-[180px]";
  } else {
    activeBookIndicator.textContent = `${activeBooksSet.size} of ${cachedBooks.length} Active`;
    activeBookIndicator.title = `${activeBooksSet.size} books active`;
    activeBookIndicator.className = "font-semibold text-indigo-800 bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 rounded-full truncate max-w-[180px]";
  }
}

function switchView(targetView) {
  currentView = targetView;
  if (targetView === "library") {
    viewConsultation?.classList.add("hidden");
    viewLibrary?.classList.remove("hidden");

    tabViewConsultation?.classList.remove("bg-white", "text-blue-600", "shadow-2xs", "font-bold");
    tabViewConsultation?.classList.add("text-slate-600", "hover:text-slate-900");
    tabViewConsultation?.setAttribute("aria-selected", "false");

    tabViewLibrary?.classList.add("bg-white", "text-blue-600", "shadow-2xs", "font-bold");
    tabViewLibrary?.classList.remove("text-slate-600", "hover:text-slate-900");
    tabViewLibrary?.setAttribute("aria-selected", "true");

    fetchBooks();
  } else {
    viewLibrary?.classList.add("hidden");
    viewConsultation?.classList.remove("hidden");

    tabViewLibrary?.classList.remove("bg-white", "text-blue-600", "shadow-2xs", "font-bold");
    tabViewLibrary?.classList.add("text-slate-600", "hover:text-slate-900");
    tabViewLibrary?.setAttribute("aria-selected", "false");

    tabViewConsultation?.classList.add("bg-white", "text-blue-600", "shadow-2xs", "font-bold");
    tabViewConsultation?.classList.remove("text-slate-600", "hover:text-slate-900");
    tabViewConsultation?.setAttribute("aria-selected", "true");
  }
}

function switchLibrarySubtab(subtab) {
  currentLibrarySubtab = subtab;
  if (subtab === "global-catalog") {
    subpanelMyLibrary?.classList.add("hidden");
    subpanelGlobalCatalog?.classList.remove("hidden");

    subtabMyLibrary?.classList.remove("text-blue-600", "border-blue-600", "font-bold");
    subtabMyLibrary?.classList.add("text-slate-500", "font-semibold");
    subtabMyLibrary?.setAttribute("aria-selected", "false");

    subtabGlobalCatalog?.classList.add("text-blue-600", "border-blue-600", "font-bold");
    subtabGlobalCatalog?.classList.remove("text-slate-500", "font-semibold");
    subtabGlobalCatalog?.setAttribute("aria-selected", "true");
  } else {
    subpanelGlobalCatalog?.classList.add("hidden");
    subpanelMyLibrary?.classList.remove("hidden");

    subtabGlobalCatalog?.classList.remove("text-blue-600", "border-blue-600", "font-bold");
    subtabGlobalCatalog?.classList.add("text-slate-500", "font-semibold");
    subtabGlobalCatalog?.setAttribute("aria-selected", "false");

    subtabMyLibrary?.classList.add("text-blue-600", "border-blue-600", "font-bold");
    subtabMyLibrary?.classList.remove("text-slate-500", "font-semibold");
    subtabMyLibrary?.setAttribute("aria-selected", "true");
  }
}

function renderMyLibraryGrid() {
  if (!myLibraryGrid) return;
  if (!cachedBooks || cachedBooks.length === 0) {
    myLibraryGrid.innerHTML = "";
    myLibraryEmpty?.classList.remove("hidden");
    return;
  }
  myLibraryEmpty?.classList.add("hidden");
  myLibraryGrid.innerHTML = "";

  cachedBooks.forEach(b => {
    const isActive = activeBooksSet.has(b.slug);
    const card = document.createElement("div");
    card.className = `library-card p-5 rounded-2xl bg-white border ${isActive ? 'border-blue-200 shadow-sm' : 'border-slate-200 opacity-80'} flex flex-col justify-between gap-4 transition duration-150`;

    card.innerHTML = `
      <div class="space-y-2">
        <div class="flex items-start justify-between gap-2">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${isActive ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'bg-slate-100 text-slate-700 border border-slate-200'}">
            <span class="w-1.5 h-1.5 rounded-full ${isActive ? 'bg-blue-600' : 'bg-slate-400'}"></span>
            ${escapeHtml(b.specialty || 'General Medicine')}
          </span>
          <span class="text-xs font-mono text-slate-500">${b.total_pages ? b.total_pages.toLocaleString() + ' pp' : ''}</span>
        </div>
        <h3 class="font-bold text-sm sm:text-base text-slate-900 leading-snug">${escapeHtml(b.title)}</h3>
        <p class="text-xs text-slate-600 leading-relaxed line-clamp-3">${escapeHtml(b.description || '')}</p>
      </div>

      <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <button
            type="button"
            role="switch"
            aria-checked="${isActive}"
            class="toggle-switch relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${isActive ? 'bg-emerald-500' : 'bg-slate-300'}"
          >
            <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isActive ? 'translate-x-4' : 'translate-x-0'}"></span>
          </button>
          <span class="text-xs font-semibold ${isActive ? 'text-emerald-700' : 'text-slate-500'}">
            ${isActive ? 'Active in Scope' : 'Inactive'}
          </span>
        </div>

        <button
          type="button"
          class="btn-remove-book text-xs font-medium text-rose-600 hover:text-rose-700 hover:bg-rose-50 px-3 py-1.5 rounded-lg transition min-h-[36px]"
          title="Remove from My Study Library"
        >
          Remove
        </button>
      </div>
    `;

    card.querySelector(".toggle-switch")?.addEventListener("click", () => handleToggleBook(b.slug));
    card.querySelector(".btn-remove-book")?.addEventListener("click", () => handleRemoveBookFromLibrary(b.slug));
    myLibraryGrid.appendChild(card);
  });
}

function renderGlobalCatalogList() {
  if (!globalCatalogList) return;
  const query = (globalSearchQuery || "").trim().toLowerCase();

  let filtered = globalCatalogData;
  if (query) {
    filtered = globalCatalogData.filter(b =>
      b.title.toLowerCase().includes(query) ||
      (b.specialty && b.specialty.toLowerCase().includes(query)) ||
      (b.description && b.description.toLowerCase().includes(query))
    );
  }

  if (filtered.length === 0) {
    globalCatalogList.innerHTML = `
      <div class="p-8 text-center bg-white rounded-2xl border border-slate-200 text-slate-600 text-xs">
        No textbooks matched "<strong>${escapeHtml(query)}</strong>". Try searching for endocrine, anatomy, or hormone.
      </div>
    `;
    return;
  }

  // Group by specialty
  const grouped = {};
  filtered.forEach(b => {
    const spec = b.specialty || "General Medicine";
    if (!grouped[spec]) grouped[spec] = [];
    grouped[spec].push(b);
  });

  globalCatalogList.innerHTML = "";

  Object.entries(grouped).forEach(([specialty, books]) => {
    const section = document.createElement("div");
    section.className = "bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-2xs";

    const header = document.createElement("button");
    header.type = "button";
    header.className = "specialty-accordion-header w-full px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-left transition";
    header.setAttribute("aria-expanded", "true");
    header.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full bg-blue-600 flex-shrink-0"></span>
        <h3 class="font-bold text-xs sm:text-sm text-slate-800">${escapeHtml(specialty)}</h3>
        <span class="text-xs font-mono text-slate-600 bg-white border border-slate-200 px-2 py-0.5 rounded-full font-semibold">${books.length} volume${books.length > 1 ? 's' : ''}</span>
      </div>
      <svg class="specialty-chevron w-4 h-4 text-slate-500 transform transition-transform duration-200 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    `;

    const body = document.createElement("div");
    body.className = "specialty-body p-4 grid grid-cols-1 md:grid-cols-2 gap-4";

    header.addEventListener("click", () => {
      const isCollapsed = body.classList.toggle("collapsed");
      header.classList.toggle("collapsed", isCollapsed);
      header.setAttribute("aria-expanded", (!isCollapsed).toString());
    });

    books.forEach(b => {
      const inLib = cachedBooks.some(cb => cb.slug === b.slug);
      const card = document.createElement("div");
      card.className = "p-4 rounded-xl border border-slate-200 hover:border-slate-300 bg-slate-50/50 flex flex-col justify-between gap-3 transition";

      card.innerHTML = `
        <div class="space-y-1.5">
          <div class="flex items-start justify-between gap-2">
            <h4 class="font-bold text-xs sm:text-sm text-slate-900 leading-snug">${escapeHtml(b.title)}</h4>
            <span class="text-xs font-mono text-slate-500 flex-shrink-0">${b.total_pages ? b.total_pages.toLocaleString() + ' pp' : ''}</span>
          </div>
          <p class="text-xs text-slate-600 leading-relaxed line-clamp-2">${escapeHtml(b.description || '')}</p>
        </div>

        <div class="pt-2 flex items-center justify-end">
          ${inLib
            ? `<span class="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg min-h-[36px]">
                <svg class="w-3.5 h-3.5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                <span>In My Library</span>
              </span>`
            : `<button type="button" class="btn-add-catalog text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg shadow-2xs transition active:scale-95 flex items-center gap-1.5 min-h-[36px]">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                <span>Add to My Library</span>
              </button>`
          }
        </div>
      `;

      card.querySelector(".btn-add-catalog")?.addEventListener("click", () => handleAddBookToLibrary(b.slug));
      body.appendChild(card);
    });

    section.appendChild(header);
    section.appendChild(body);
    globalCatalogList.appendChild(section);
  });
}

// =============================================================================
// Upload Textbook Modal & Background Ingestion Controller
// =============================================================================

function openUploadModal() {
  if (!modalUploadBook) return;
  resetUploadModal();
  modalUploadBook.classList.remove("hidden");
  if (inputUploadTitle) inputUploadTitle.focus();
}

function closeUploadModal() {
  if (!modalUploadBook) return;
  if (ingestionPollInterval) {
    clearInterval(ingestionPollInterval);
    ingestionPollInterval = null;
  }
  modalUploadBook.classList.add("hidden");
}

function resetUploadModal() {
  selectedUploadFile = null;
  currentIngestionJobId = null;
  if (ingestionPollInterval) {
    clearInterval(ingestionPollInterval);
    ingestionPollInterval = null;
  }

  if (inputUploadFile) inputUploadFile.value = "";
  if (inputUploadTitle) inputUploadTitle.value = "";
  if (inputUploadSpecialty) inputUploadSpecialty.value = "";

  if (dropzoneEmptyState) dropzoneEmptyState.classList.remove("hidden");
  if (dropzoneFileState) dropzoneFileState.classList.add("hidden");
  if (uploadTitleDuplicateWarning) uploadTitleDuplicateWarning.classList.add("hidden");
  if (uploadFormError) {
    uploadFormError.textContent = "";
    uploadFormError.classList.add("hidden");
  }

  if (formUploadBook) formUploadBook.classList.remove("hidden");
  if (uploadProgressView) uploadProgressView.classList.add("hidden");
  if (uploadFailureCard) uploadFailureCard.classList.add("hidden");
  if (uploadSuccessCard) uploadSuccessCard.classList.add("hidden");

  if (uploadProgressBar) uploadProgressBar.style.width = "0%";
  if (uploadProgressPercent) uploadProgressPercent.textContent = "0%";
  if (uploadProgressStageLabel) uploadProgressStageLabel.textContent = "Validating PDF...";
  if (uploadProgressMessage) uploadProgressMessage.textContent = "Analyzing document structure and layout...";

  resetStepperPills();
  if (btnSubmitUpload) {
    btnSubmitUpload.disabled = false;
    btnSubmitUpload.classList.remove("opacity-50", "cursor-not-allowed");
  }
}

function resetStepperPills() {
  const pills = [
    { el: stepPillValidate, active: true },
    { el: stepPillToc, active: false },
    { el: stepPillExtract, active: false },
    { el: stepPillReady, active: false },
  ];
  pills.forEach(({ el, active }) => {
    if (!el) return;
    if (active) {
      el.className = "py-1 px-1 rounded-md bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200";
    } else {
      el.className = "py-1 px-1 rounded-md bg-slate-100 text-slate-500 font-medium";
    }
  });
}

function handleFileSelection(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showUploadError("Please select a valid PDF file (.pdf).");
    return;
  }

  selectedUploadFile = file;
  if (uploadFormError) uploadFormError.classList.add("hidden");

  if (selectedFileName) selectedFileName.textContent = file.name;
  if (selectedFileSize) {
    const mb = (file.size / (1024 * 1024)).toFixed(1);
    selectedFileSize.textContent = `(${mb} MB)`;
  }

  if (dropzoneEmptyState) dropzoneEmptyState.classList.add("hidden");
  if (dropzoneFileState) dropzoneFileState.classList.remove("hidden");

  // Derive title from filename if title is currently empty
  if (inputUploadTitle && !inputUploadTitle.value.trim()) {
    const rawName = file.name.replace(/\.pdf$/i, "").replace(/[_-]+/g, " ").trim();
    inputUploadTitle.value = rawName;
    checkDuplicateTitle(rawName);
  }
}

function checkDuplicateTitle(titleText) {
  if (!uploadTitleDuplicateWarning) return;
  const clean = titleText.trim().toLowerCase();
  if (!clean || clean.length < 3) {
    uploadTitleDuplicateWarning.classList.add("hidden");
    return;
  }

  const isDuplicate = globalCatalogData.some(b => {
    const bTitle = (b.title || "").toLowerCase();
    const bSlug = (b.slug || "").toLowerCase();
    return bTitle === clean || bSlug === clean || (clean.length > 12 && bTitle.includes(clean));
  });

  if (isDuplicate) {
    uploadTitleDuplicateWarning.classList.remove("hidden");
  } else {
    uploadTitleDuplicateWarning.classList.add("hidden");
  }
}

function showUploadError(msg) {
  if (!uploadFormError) return;
  uploadFormError.textContent = msg;
  uploadFormError.classList.remove("hidden");
}

async function handleUploadSubmit(e) {
  e.preventDefault();
  if (uploadFormError) uploadFormError.classList.add("hidden");

  if (!selectedUploadFile) {
    showUploadError("Please select a PDF textbook to upload.");
    return;
  }

  const title = inputUploadTitle ? inputUploadTitle.value.trim() : "";
  if (!title) {
    showUploadError("Textbook title is required.");
    inputUploadTitle?.focus();
    return;
  }

  const specialty = inputUploadSpecialty ? inputUploadSpecialty.value.trim() : "General Medicine";
  const inputUploadPrivate = document.getElementById("input-upload-private");
  const isPrivate = inputUploadPrivate ? inputUploadPrivate.checked : true;

  // Build FormData payload
  const formData = new FormData();
  formData.append("file", selectedUploadFile);
  formData.append("title", title);
  formData.append("specialty", specialty || "General Medicine");
  formData.append("is_private", isPrivate ? "true" : "false");

  if (btnSubmitUpload) {
    btnSubmitUpload.disabled = true;
    btnSubmitUpload.classList.add("opacity-50", "cursor-not-allowed");
  }

  try {
    const res = await fetch("/api/books/upload", {
      method: "POST",
      body: formData,
    });

    if (res.status === 409) {
      const err = await res.json();
      showUploadError(err.detail || "A textbook with this title or slug already exists in the Global Library.");
      if (btnSubmitUpload) {
        btnSubmitUpload.disabled = false;
        btnSubmitUpload.classList.remove("opacity-50", "cursor-not-allowed");
      }
      return;
    }

    if (!res.ok) {
      const err = await res.json();
      showUploadError(err.detail || "Upload failed. Please check the file format and try again.");
      if (btnSubmitUpload) {
        btnSubmitUpload.disabled = false;
        btnSubmitUpload.classList.remove("opacity-50", "cursor-not-allowed");
      }
      return;
    }

    const data = await res.json();
    currentIngestionJobId = data.job_id;

    // Transition form to progress stepper view
    if (formUploadBook) formUploadBook.classList.add("hidden");
    if (uploadProgressView) uploadProgressView.classList.remove("hidden");

    startIngestionPolling(data.job_id);

  } catch (err) {
    console.error("Upload network error:", err);
    showUploadError("Network error occurred during upload. Please try again.");
    if (btnSubmitUpload) {
      btnSubmitUpload.disabled = false;
      btnSubmitUpload.classList.remove("opacity-50", "cursor-not-allowed");
    }
  }
}

function startIngestionPolling(jobId) {
  if (ingestionPollInterval) {
    clearInterval(ingestionPollInterval);
  }

  const poll = async () => {
    try {
      const res = await fetch(`/api/books/ingestion/${encodeURIComponent(jobId)}`);
      if (!res.ok) return;
      const job = await res.json();

      updateProgressUI(job);

      if (job.status === "completed") {
        clearInterval(ingestionPollInterval);
        ingestionPollInterval = null;
        showUploadSuccess(job);
        // Refresh catalog and library immediately & auto-activate new book
        if (job.book_slug) {
          activeBooksSet.add(job.book_slug);
        }
        await fetchBooks();
        saveActiveBooks();
        renderBookToggles();
        updateSidebarBadge();
        updateScopeIndicator();
        updateLibraryStats();
      } else if (job.status === "failed") {
        clearInterval(ingestionPollInterval);
        ingestionPollInterval = null;
        showUploadFailure(job);
      }
    } catch (e) {
      console.warn("Polling error for ingestion job:", e);
    }
  };

  // Immediate poll, then every 1.5s
  poll();
  ingestionPollInterval = setInterval(poll, 1500);
}

function updateProgressUI(job) {
  const percent = job.progress_percent || 0;
  if (uploadProgressPercent) uploadProgressPercent.textContent = `${percent}%`;
  if (uploadProgressBar) uploadProgressBar.style.width = `${percent}%`;
  if (uploadProgressMessage) uploadProgressMessage.textContent = job.message || "Processing textbook...";
  if (uploadProgressStageLabel) uploadProgressStageLabel.textContent = formatStageLabel(job.stage, percent);

  // Update Stepper Pills
  updateStepperPills(percent);
}

function formatStageLabel(stage, percent) {
  switch (stage) {
    case "validating": return "1. Validating PDF & Text Layer...";
    case "toc": return "2. Extracting Table of Contents & Structure...";
    case "extraction": return "3. Extracting Reading-Order Text...";
    case "chunking": return "4. Generating Structured Chunks...";
    case "indexing": return "5. Indexing Database & Search...";
    case "completed": return "✓ Ingestion Complete!";
    case "failed": return "⚠️ Ingestion Halted";
    default: return `${percent}% Processing...`;
  }
}

function updateStepperPills(percent) {
  const setPill = (el, state) => {
    if (!el) return;
    if (state === "done") {
      el.className = "py-1 px-1 rounded-md bg-emerald-100 text-emerald-800 font-bold border border-emerald-300";
    } else if (state === "active") {
      el.className = "py-1 px-1 rounded-md bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200 animate-pulse";
    } else {
      el.className = "py-1 px-1 rounded-md bg-slate-100 text-slate-500 font-medium";
    }
  };

  if (percent >= 100) {
    setPill(stepPillValidate, "done");
    setPill(stepPillToc, "done");
    setPill(stepPillExtract, "done");
    setPill(stepPillReady, "done");
  } else if (percent >= 75) {
    setPill(stepPillValidate, "done");
    setPill(stepPillToc, "done");
    setPill(stepPillExtract, "done");
    setPill(stepPillReady, "active");
  } else if (percent >= 35) {
    setPill(stepPillValidate, "done");
    setPill(stepPillToc, "done");
    setPill(stepPillExtract, "active");
    setPill(stepPillReady, "idle");
  } else if (percent >= 15) {
    setPill(stepPillValidate, "done");
    setPill(stepPillToc, "active");
    setPill(stepPillExtract, "idle");
    setPill(stepPillReady, "idle");
  } else {
    setPill(stepPillValidate, "active");
    setPill(stepPillToc, "idle");
    setPill(stepPillExtract, "idle");
    setPill(stepPillReady, "idle");
  }
}

function showUploadSuccess(job) {
  if (uploadSuccessCard) {
    uploadSuccessCard.classList.remove("hidden");
  }
  if (uploadSuccessDetail) {
    const pp = job.total_pages ? `${job.total_pages.toLocaleString()} pages` : "";
    const chk = job.chunks_count ? `${job.chunks_count.toLocaleString()} passages` : "";
    uploadSuccessDetail.textContent = `Successfully indexed "${job.title}" (${[pp, chk].filter(Boolean).join(", ")}) into your personal Study Library under ${job.specialty}. It is now active for clinical inquiries.`;
  }
}

function showUploadFailure(job) {
  if (uploadFailureCard) {
    uploadFailureCard.classList.remove("hidden");
  }
  if (uploadFailureReason) {
    uploadFailureReason.textContent = job.user_error_message || job.message || "An unexpected error occurred during textbook processing.";
  }
}

// Render starter prompts
function renderStarterPrompts() {
  if (starterPromptList) starterPromptList.innerHTML = "";
  if (heroCards) heroCards.innerHTML = "";

  STARTER_PROMPTS.forEach(p => {
    // Sidebar small prompt if element exists
    if (starterPromptList) {
      const btn = document.createElement("button");
      btn.className = "w-full text-left p-2 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-200 hover:border-blue-300 text-xs font-medium text-slate-700 transition truncate shadow-2xs active:scale-95";
      btn.textContent = p.label;
      btn.addEventListener("click", () => {
        closeSidebar();
        submitQuery(p.query);
      });
      starterPromptList.appendChild(btn);
    }

    // Hero card
    if (heroCards) {
      const card = document.createElement("button");
      card.className = "p-4 rounded-xl bg-white hover:bg-blue-50/40 border border-slate-200 hover:border-blue-300 text-left transition duration-200 group flex flex-col justify-between shadow-sm hover:shadow active:scale-95";
      card.innerHTML = `
        <div class="font-bold text-xs text-slate-800 group-hover:text-blue-600 transition">${escapeHtml(p.label)}</div>
        <div class="text-xs text-slate-600 line-clamp-2 mt-1.5 leading-relaxed">${escapeHtml(p.query)}</div>
        <div class="mt-3 text-xs text-blue-600 font-bold flex items-center gap-1.5">
          <span>Ask question</span>
          <svg class="w-3.5 h-3.5 transition group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </div>
      `;
      card.addEventListener("click", () => submitQuery(p.query));
      heroCards.appendChild(card);
    }
  });
}

// ---------------------------------------------------------------------------
// Consultation Sessions & History Management
// ---------------------------------------------------------------------------

async function fetchSessions() {
  if (!sessionsList) return;
  try {
    const res = await fetch("/api/sessions");
    if (!res.ok) return;
    const data = await res.json();
    renderSessionsList(data.sessions || []);
  } catch (err) {
    console.error("Failed to load sessions:", err);
    if (sessionsLoading) sessionsLoading.classList.add("hidden");
  }
}

function renderSessionsList(sessions) {
  if (!sessionsList) return;
  if (sessionsLoading) sessionsLoading.remove();
  sessionsList.innerHTML = "";

  if (sessionsCountBadge) {
    sessionsCountBadge.textContent = sessions.length;
  }

  if (sessions.length === 0) {
    if (sessionsEmpty) sessionsEmpty.classList.remove("hidden");
    return;
  }

  if (sessionsEmpty) sessionsEmpty.classList.add("hidden");

  sessions.forEach(s => {
    const isActive = s.id === sessionId;
    const item = document.createElement("div");
    item.className = `group relative flex items-center justify-between p-2 rounded-xl text-xs cursor-pointer transition border duration-150 ${
      isActive
        ? "bg-blue-50/90 border-blue-200 text-blue-900 font-semibold shadow-2xs"
        : "border-transparent text-slate-700 hover:bg-slate-100 hover:border-slate-200/60"
    }`;
    item.setAttribute("role", "button");
    item.setAttribute("tabindex", "0");
    item.setAttribute("aria-label", `Inquiry: ${s.title}`);
    item.setAttribute("data-session-id", s.id);

    const timeAgo = formatTimeAgo(s.updated_at);

    item.innerHTML = `
      <div class="flex items-center gap-2.5 min-w-0 flex-1 pr-1.5">
        <svg class="w-4 h-4 flex-shrink-0 ${isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-blue-500'} transition" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
        </svg>
        <div class="min-w-0 flex-1">
          <div class="truncate leading-snug">${escapeHtml(s.title)}</div>
          <div class="text-xs text-slate-500 font-normal mt-0.5 flex items-center gap-1.5">
            <span>${timeAgo}</span>
            ${s.message_count > 0 ? `<span>• ${s.message_count} turns</span>` : ''}
          </div>
        </div>
      </div>
      <button class="btn-delete-session p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 opacity-0 group-hover:opacity-100 focus:opacity-100 transition" aria-label="Delete inquiry: ${escapeHtml(s.title)}" title="Delete inquiry">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
        </svg>
      </button>
    `;

    // Click item to load session
    item.addEventListener("click", () => {
      loadSession(s.id);
    });

    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        loadSession(s.id);
      }
    });

    // Delete button click
    const btnDel = item.querySelector(".btn-delete-session");
    if (btnDel) {
      btnDel.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteConsultation(s.id, s.title);
      });
    }

    sessionsList.appendChild(item);
  });
}

function formatTimeAgo(isoString) {
  if (!isoString) return "Recently";
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);
    if (diffSec < 60) return "Just now";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch (e) {
    return "Recently";
  }
}

async function loadSession(id) {
  if (sessionId === id && heroWelcome && heroWelcome.classList.contains("hidden")) {
    closeSidebar();
    return;
  }

  try {
    const res = await fetch(`/api/sessions/${encodeURIComponent(id)}`);
    if (!res.ok) {
      throw new Error("Could not load inquiry");
    }
    const data = await res.json();
    sessionId = id;

    // Clear messages and hide hero
    messagesContainer.innerHTML = "";
    if (heroWelcome) heroWelcome.classList.add("hidden");
    citationsCache.clear();

    // Cache citations
    if (data.citations) {
      data.citations.forEach(c => citationsCache.set(String(c.citation_id), c));
    }
    updateEvidenceCount();

    // Render dialogue
    if (data.messages && data.messages.length > 0) {
      data.messages.forEach(m => {
        if (m.role === "user") {
          appendUserMessage(m.content);
        } else if (m.role === "assistant") {
          appendAssistantMessage({
            reply: m.content,
            citations: m.citations || [],
            tool_calls: m.tool_calls || [],
            follow_ups: m.follow_ups || [],
            figures: m.figures || [],
          });
        }
      });
      userHasScrolledUp = false;
      scrollToBottom(true);
      updateScrollButtonVisibility();
    } else {
      // Empty session
      if (heroWelcome) {
        messagesContainer.appendChild(heroWelcome);
        heroWelcome.classList.remove("hidden");
      }
    }

    // Update active highlight in sessions list
    fetchSessions();
    closeSidebar();
    chatInput.focus();

  } catch (err) {
    console.error("Failed to switch session:", err);
    appendErrorMessage("Failed to load inquiry session: " + err.message);
  }
}

async function deleteConsultation(id, title) {
  if (!confirm(`Delete inquiry "${title}"?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/sessions/${encodeURIComponent(id)}`, {
      method: "DELETE"
    });
    if (res.ok) {
      if (sessionId === id) {
        resetSession();
      } else {
        fetchSessions();
      }
    }
  } catch (err) {
    console.error("Failed to delete consultation:", err);
  }
}

// Event Bindings
function bindEvents() {
  if (btnStop) {
    btnStop.addEventListener("click", () => {
      stopCurrentGeneration();
    });
  }

  if (btnScrollBottom) {
    btnScrollBottom.addEventListener("click", () => {
      userHasScrolledUp = false;
      scrollToBottom(true);
      updateScrollButtonVisibility();
    });
  }

  if (messagesContainer) {
    messagesContainer.addEventListener("scroll", updateScrollButtonVisibility);
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (query) submitQuery(query);
  });

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const query = chatInput.value.trim();
      if (query) submitQuery(query);
    }
  });

  // Auto-resize input & toggle send button state
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
    updateSendButtonState();
  });

  // On mobile/virtual keyboard, scroll to bottom when focused so active content remains visible
  chatInput.addEventListener("focus", () => {
    if (window.innerWidth < 768) {
      setTimeout(() => {
        if (messagesContainer) {
          messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: "smooth" });
        }
      }, 250);
    }
  });

  // View Navigation & Library Manager listeners
  if (tabViewConsultation) {
    tabViewConsultation.addEventListener("click", () => switchView("consultation"));
  }
  if (tabViewLibrary) {
    tabViewLibrary.addEventListener("click", () => switchView("library"));
  }
  if (btnOpenFullLibrary) {
    btnOpenFullLibrary.addEventListener("click", () => {
      switchView("library");
      closeSidebar();
    });
  }
  if (btnReturnConsultation) {
    btnReturnConsultation.addEventListener("click", () => switchView("consultation"));
  }
  if (subtabMyLibrary) {
    subtabMyLibrary.addEventListener("click", () => switchLibrarySubtab("my-library"));
  }
  if (subtabGlobalCatalog) {
    subtabGlobalCatalog.addEventListener("click", () => switchLibrarySubtab("global-catalog"));
  }
  if (btnLibGotoGlobal) {
    btnLibGotoGlobal.addEventListener("click", () => switchLibrarySubtab("global-catalog"));
  }
  if (btnEmptyBrowseGlobal) {
    btnEmptyBrowseGlobal.addEventListener("click", () => switchLibrarySubtab("global-catalog"));
  }
  if (btnLibActivateAll) {
    btnLibActivateAll.addEventListener("click", () => handleToggleAllBooks(true));
  }
  if (btnLibDeactivateAll) {
    btnLibDeactivateAll.addEventListener("click", () => handleToggleAllBooks(false));
  }
  if (globalCatalogSearch) {
    globalCatalogSearch.addEventListener("input", (e) => {
      globalSearchQuery = e.target.value;
      if (btnClearGlobalSearch) {
        if (globalSearchQuery.trim()) {
          btnClearGlobalSearch.classList.remove("hidden");
        } else {
          btnClearGlobalSearch.classList.add("hidden");
        }
      }
      renderGlobalCatalogList();
    });
  }
  if (btnClearGlobalSearch) {
    btnClearGlobalSearch.addEventListener("click", () => {
      if (globalCatalogSearch) {
        globalCatalogSearch.value = "";
        globalSearchQuery = "";
        globalCatalogSearch.focus();
      }
      btnClearGlobalSearch.classList.add("hidden");
      renderGlobalCatalogList();
    });
  }

  // Upload Textbook Modal listeners
  if (btnOpenUploadModal) {
    btnOpenUploadModal.addEventListener("click", openUploadModal);
  }
  if (btnCloseUploadModal) {
    btnCloseUploadModal.addEventListener("click", closeUploadModal);
  }
  if (btnCancelUpload) {
    btnCancelUpload.addEventListener("click", closeUploadModal);
  }
  if (modalUploadBook) {
    modalUploadBook.addEventListener("click", (e) => {
      if (e.target === modalUploadBook) {
        closeUploadModal();
      }
    });
  }

  // Dropzone drag-and-drop & file picker
  if (uploadDropzone && inputUploadFile) {
    uploadDropzone.addEventListener("click", (e) => {
      if (e.target !== btnRemoveSelectedFile && !btnRemoveSelectedFile?.contains(e.target)) {
        inputUploadFile.click();
      }
    });

    inputUploadFile.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileSelection(e.target.files[0]);
      }
    });

    uploadDropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadDropzone.classList.add("border-emerald-500", "bg-emerald-50/30");
    });

    uploadDropzone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      uploadDropzone.classList.remove("border-emerald-500", "bg-emerald-50/30");
    });

    uploadDropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadDropzone.classList.remove("border-emerald-500", "bg-emerald-50/30");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFileSelection(e.dataTransfer.files[0]);
      }
    });
  }

  if (btnRemoveSelectedFile) {
    btnRemoveSelectedFile.addEventListener("click", (e) => {
      e.stopPropagation();
      selectedUploadFile = null;
      if (inputUploadFile) inputUploadFile.value = "";
      if (dropzoneEmptyState) dropzoneEmptyState.classList.remove("hidden");
      if (dropzoneFileState) dropzoneFileState.classList.add("hidden");
    });
  }

  if (inputUploadTitle) {
    inputUploadTitle.addEventListener("input", (e) => {
      checkDuplicateTitle(e.target.value);
    });
  }

  if (formUploadBook) {
    formUploadBook.addEventListener("submit", handleUploadSubmit);
  }

  if (btnTryAnotherUpload) {
    btnTryAnotherUpload.addEventListener("click", resetUploadModal);
  }

  if (btnDoneUpload) {
    btnDoneUpload.addEventListener("click", () => {
      closeUploadModal();
      switchView("library");
      switchLibrarySubtab("global-catalog");
    });
  }

  // Select All Books handler
  if (btnSelectAllBooks) {
    btnSelectAllBooks.addEventListener("click", () => {
      handleToggleAllBooks(true);
    });
  }

  // New Chat
  btnNewChat.addEventListener("click", () => {
    resetSession();
    closeSidebar();
  });
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      resetSession();
    } else if (e.key === "Escape") {
      if (figureLightboxModal && !figureLightboxModal.classList.contains("hidden")) {
        closeLightbox();
        return;
      }
      if (authModal && !authModal.classList.contains("hidden")) {
        closeAuthModal();
        return;
      }
      if (modalUploadBook && !modalUploadBook.classList.contains("hidden")) {
        closeUploadModal();
        return;
      }
      if (isAwaitingResponse) {
        stopCurrentGeneration();
      }
    } else if (e.key === "ArrowDown" && (document.activeElement !== chatInput || chatInput.value === "")) {
      if (messagesContainer && userHasScrolledUp) {
        messagesContainer.scrollBy({ top: 120, behavior: "smooth" });
      }
    }
  });

  if (btnCloseLightbox) {
    btnCloseLightbox.addEventListener("click", closeLightbox);
  }
  if (figureLightboxModal) {
    figureLightboxModal.addEventListener("click", (e) => {
      if (e.target === figureLightboxModal) {
        closeLightbox();
      }
    });
  }

  // Mobile sidebar handlers
  if (btnMobileMenu) {
    btnMobileMenu.addEventListener("click", openSidebar);
  }
  if (btnCloseSidebar) {
    btnCloseSidebar.addEventListener("click", closeSidebar);
  }
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener("click", closeSidebar);
  }

  // Drawer handlers
  btnCloseDrawer.addEventListener("click", closeDrawer);
  drawerBackdrop.addEventListener("click", closeDrawer);
  btnToggleEvidence.addEventListener("click", () => {
    if (evidenceDrawer.classList.contains("translate-x-full")) {
      openDrawer();
    } else {
      closeDrawer();
    }
  });

  // Authentication UI Handlers
  if (btnAuthTrigger) {
    btnAuthTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      if (!currentUser) {
        openAuthModal("login");
      } else if (authUserMenu) {
        const isHidden = authUserMenu.classList.contains("hidden");
        authUserMenu.classList.toggle("hidden");
        btnAuthTrigger.setAttribute("aria-expanded", String(isHidden));
      }
    });
  }

  // Click outside auth dropdown closes it
  document.addEventListener("click", (e) => {
    if (authUserMenu && !authUserMenu.classList.contains("hidden")) {
      if (authDropdownWrapper && !authDropdownWrapper.contains(e.target)) {
        authUserMenu.classList.add("hidden");
        if (btnAuthTrigger) btnAuthTrigger.setAttribute("aria-expanded", "false");
      }
    }
  });

  if (btnMenuOpenAuth) {
    btnMenuOpenAuth.addEventListener("click", () => {
      const targetMode = currentUser && currentUser.is_guest ? "signup" : "login";
      openAuthModal(targetMode);
    });
  }

  if (btnMenuLogout) {
    btnMenuLogout.addEventListener("click", handleLogout);
  }

  if (btnCloseAuthModal) {
    btnCloseAuthModal.addEventListener("click", closeAuthModal);
  }

  if (authModal) {
    authModal.addEventListener("click", (e) => {
      if (e.target === authModal) {
        closeAuthModal();
      }
    });
  }

  if (btnGuestLogin) {
    btnGuestLogin.addEventListener("click", handleGuestLogin);
  }

  if (tabLogin) {
    tabLogin.addEventListener("click", () => switchAuthTab("login"));
  }

  if (tabSignup) {
    tabSignup.addEventListener("click", () => switchAuthTab("signup"));
  }

  if (authForm) {
    authForm.addEventListener("submit", handleAuthSubmit);
  }

  // Global ESC key to close any active drawer/modal
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDrawer();
      closeSidebar();
      closeAuthModal();
      if (authUserMenu) authUserMenu.classList.add("hidden");
    }
  });
}

// ---------------------------------------------------------------------------
// Authentication UI Logic
// ---------------------------------------------------------------------------

async function checkAuthStatus() {
  try {
    const res = await fetch("/api/auth/me");
    if (res.ok) {
      const data = await res.json();
      currentUser = data.user;
      updateAuthUI();
      if (!currentUser) {
        // First visit prompt: show modal after short pause so evaluator can choose 1-click guest or login
        setTimeout(() => {
          if (!currentUser && authModal && authModal.classList.contains("hidden")) {
            openAuthModal("login");
          }
        }, 350);
      }
    }
  } catch (err) {
    console.error("Failed to check auth status:", err);
  }
}

function updateAuthUI() {
  if (!authUserLabel) return;

  if (currentUser) {
    if (currentUser.is_guest) {
      const shortGuest = currentUser.username.replace(/^Guest_/, "");
      authUserLabel.textContent = `Guest (${shortGuest})`;
      if (authMenuUsername) authMenuUsername.textContent = currentUser.username;
      if (authMenuStatus) authMenuStatus.textContent = "Ephemeral Session";
      if (btnMenuOpenAuthLabel) btnMenuOpenAuthLabel.textContent = "Create Permanent Account";
      if (btnMenuLogout) btnMenuLogout.classList.remove("hidden");
    } else {
      authUserLabel.textContent = `Dr. ${currentUser.username}`;
      if (authMenuUsername) authMenuUsername.textContent = `Dr. ${currentUser.username}`;
      if (authMenuStatus) authMenuStatus.textContent = "Registered Clinician";
      if (btnMenuOpenAuthLabel) btnMenuOpenAuthLabel.textContent = "Switch Account";
      if (btnMenuLogout) btnMenuLogout.classList.remove("hidden");
    }
  } else {
    authUserLabel.textContent = "Sign In / Guest";
    if (authMenuUsername) authMenuUsername.textContent = "Not Signed In";
    if (authMenuStatus) authMenuStatus.textContent = "Ephemeral Session";
    if (btnMenuOpenAuthLabel) btnMenuOpenAuthLabel.textContent = "Sign In or Register";
    if (btnMenuLogout) btnMenuLogout.classList.add("hidden");
  }
}

function openAuthModal(mode = "login") {
  if (!authModal) return;
  authModal.classList.remove("hidden");
  switchAuthTab(mode);
  clearAuthError();
  if (authUserMenu) authUserMenu.classList.add("hidden");
  setTimeout(() => {
    if (authUsernameInput) authUsernameInput.focus();
  }, 60);
}

function closeAuthModal() {
  if (!authModal) return;
  authModal.classList.add("hidden");
  clearAuthError();
}

function switchAuthTab(mode) {
  authMode = mode;
  clearAuthError();
  if (mode === "login") {
    tabLogin.className = "flex-1 pb-2.5 text-xs font-bold text-blue-600 border-b-2 border-blue-600 transition";
    tabLogin.setAttribute("aria-selected", "true");
    tabSignup.className = "flex-1 pb-2.5 text-xs font-medium text-slate-500 hover:text-slate-800 transition";
    tabSignup.setAttribute("aria-selected", "false");
    authModalTitle.textContent = "Sign In to CliniSource";
    authSubmitLabel.textContent = "Sign In";
    if (authUsernameHint) authUsernameHint.classList.add("hidden");
  } else {
    tabSignup.className = "flex-1 pb-2.5 text-xs font-bold text-blue-600 border-b-2 border-blue-600 transition";
    tabSignup.setAttribute("aria-selected", "true");
    tabLogin.className = "flex-1 pb-2.5 text-xs font-medium text-slate-500 hover:text-slate-800 transition";
    tabLogin.setAttribute("aria-selected", "false");
    authModalTitle.textContent = "Create Clinician Account";
    authSubmitLabel.textContent = "Create Account";
    if (authUsernameHint) authUsernameHint.classList.remove("hidden");
  }
}

function showAuthError(msg) {
  if (!authErrorBanner || !authErrorText) return;
  authErrorText.textContent = msg;
  authErrorBanner.classList.remove("hidden");
}

function clearAuthError() {
  if (!authErrorBanner || !authErrorText) return;
  authErrorBanner.classList.add("hidden");
  authErrorText.textContent = "";
}

async function handleGuestLogin() {
  try {
    const res = await fetch("/api/auth/guest", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      currentUser = data.user;
      updateAuthUI();
      closeAuthModal();
      fetchQuota();
      fetchSessions();
    } else {
      const err = await res.json();
      showAuthError(err.detail || "Failed to continue as guest.");
    }
  } catch (e) {
    showAuthError("Connection error. Please try again.");
  }
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  clearAuthError();
  const username = authUsernameInput.value.trim();
  const password = authPasswordInput.value;

  if (!username) {
    showAuthError("Please enter a username.");
    return;
  }
  if (!password) {
    showAuthError("Please enter a password.");
    return;
  }

  btnAuthSubmit.disabled = true;
  authSubmitLabel.textContent = authMode === "login" ? "Signing In..." : "Creating Account...";

  try {
    const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/signup";
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (res.ok) {
      currentUser = data.user;
      updateAuthUI();
      closeAuthModal();
      authUsernameInput.value = "";
      authPasswordInput.value = "";
      fetchQuota();
      fetchSessions();
    } else {
      showAuthError(data.detail || "Authentication failed.");
    }
  } catch (err) {
    showAuthError("Network connection error. Please try again.");
  } finally {
    btnAuthSubmit.disabled = false;
    authSubmitLabel.textContent = authMode === "login" ? "Sign In" : "Create Account";
  }
}

async function handleLogout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch (e) {
    console.error("Logout request error:", e);
  }
  currentUser = null;
  updateAuthUI();
  if (authUserMenu) authUserMenu.classList.add("hidden");
  fetchQuota();
  resetSession();
  fetchSessions();
}

// Mobile sidebar controls
function openSidebar() {
  if (appSidebar) {
    appSidebar.classList.remove("-translate-x-full");
  }
  if (sidebarBackdrop) {
    sidebarBackdrop.classList.remove("opacity-0", "pointer-events-none");
  }
}

function closeSidebar() {
  if (appSidebar) {
    appSidebar.classList.add("-translate-x-full");
  }
  if (sidebarBackdrop) {
    sidebarBackdrop.classList.add("opacity-0", "pointer-events-none");
  }
}

function resetSession() {
  sessionId = "session_" + Math.random().toString(36).substring(2, 10);
  citationsCache.clear();
  updateEvidenceCount();
  messagesContainer.innerHTML = "";
  messagesContainer.appendChild(heroWelcome);
  heroWelcome.classList.remove("hidden");
  chatInput.value = "";
  chatInput.style.height = "auto";
  updateSendButtonState();
  fetchSessions();
  chatInput.focus();
}

function openDrawer() {
  evidenceDrawer.classList.remove("translate-x-full");
  drawerBackdrop.classList.remove("opacity-0", "pointer-events-none");
}

function closeDrawer() {
  evidenceDrawer.classList.add("translate-x-full");
  drawerBackdrop.classList.add("opacity-0", "pointer-events-none");
}

function updateEvidenceCount() {
  evidenceCountBadge.textContent = citationsCache.size;
}

function stopCurrentGeneration() {
  if (currentAbortController) {
    currentAbortController.abort();
  }
}

// Send Query via Server-Sent Events (SSE) Streaming
async function submitQuery(queryText) {
  if (isAwaitingResponse) return;
  isAwaitingResponse = true;
  currentAbortController = new AbortController();
  updateSendButtonState();

  // Close mobile sidebar if open
  closeSidebar();

  // Hide hero if visible
  if (!heroWelcome.classList.contains("hidden")) {
    heroWelcome.classList.add("hidden");
  }

  // Append user bubble
  appendUserMessage(queryText);
  chatInput.value = "";
  chatInput.style.height = "auto";
  updateSendButtonState();

  // Reset scroll lock for new query turn
  userHasScrolledUp = false;
  updateScrollButtonVisibility();

  // Append typing indicator with dynamic status text
  const typingIndicator = appendTypingIndicator();
  const typingLabel = typingIndicator.querySelector(".typing-status-text");
  scrollToBottom(true);

  let assistantWrapper = null;
  let proseContainer = null;
  let toolsContainer = null;
  let referencedBooksContainer = null;
  let rawTextBuffer = "";
  let toolsData = [];
  let citationsData = [];
  let figuresData = [];
  let followUpsData = [];
  let referencedBooksData = [];

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: currentAbortController.signal,
      body: JSON.stringify({
        session_id: sessionId,
        message: queryText,
        active_books: Array.from(activeBooksSet)
      })
    });

    if (!res.ok) {
      if (res.status === 429) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Daily request limit reached. Quota resets at 00:00 UTC.");
      }
      throw new Error(`Server returned ${res.status}: ${res.statusText}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let streamBuffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      streamBuffer += decoder.decode(value, { stream: true });
      const blocks = streamBuffer.split("\n\n");
      streamBuffer = blocks.pop();

      for (const block of blocks) {
        if (!block.trim()) continue;
        const lines = block.split("\n");
        let eventName = "message";
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventName = line.substring(6).trim();
          } else if (line.startsWith("data:")) {
            dataStr = line.substring(5).trim();
          }
        }

        let payload = {};
        try {
          payload = JSON.parse(dataStr);
        } catch (e) {
          payload = dataStr;
        }

        if (eventName === "status") {
          if (typingLabel && payload.text) {
            typingLabel.textContent = payload.text;
          }
        } else if (eventName === "referenced_books") {
          referencedBooksData = Array.isArray(payload) ? payload : [];
          if (referencedBooksContainer) {
            renderReferencedBooksHtml(referencedBooksContainer, referencedBooksData);
          }
        } else if (eventName === "tools") {
          toolsData = Array.isArray(payload) ? payload : [];
          if (toolsContainer) {
            renderToolsHtml(toolsContainer, toolsData);
          }
        } else if (eventName === "token") {
          const delta = payload.delta || "";
          rawTextBuffer += delta;

          // Mount message bubble on first token
          if (!assistantWrapper) {
            typingIndicator.remove();
            const mounted = createStreamingAssistantBubble();
            assistantWrapper = mounted.wrapper;
            proseContainer = mounted.proseContainer;
            toolsContainer = mounted.toolsContainer;
            referencedBooksContainer = mounted.referencedBooksContainer;
            messagesContainer.appendChild(assistantWrapper);
            if (referencedBooksData.length > 0) {
              renderReferencedBooksHtml(referencedBooksContainer, referencedBooksData);
            }
            if (toolsData.length > 0) {
              renderToolsHtml(toolsContainer, toolsData);
            }
          }

          // Progressive Live Markdown Rendering
          const sanitized = sanitizeMedicalText(rawTextBuffer);
          let formattedHtml = window.marked ? marked.parse(sanitized) : sanitized;
          formattedHtml = formatCitationBadges(formattedHtml);
          proseContainer.innerHTML = formattedHtml;
          attachCitationBadgeListeners(assistantWrapper);
          scrollToBottom();

        } else if (eventName === "citations") {
          citationsData = Array.isArray(payload) ? payload : [];
          citationsData.forEach(c => {
            citationsCache.set(String(c.citation_id), c);
          });
          updateEvidenceCount();
          if (assistantWrapper) {
            attachCitationBadgeListeners(assistantWrapper);
          }
        } else if (eventName === "figures") {
          figuresData = Array.isArray(payload) ? payload : [];
          if (assistantWrapper && figuresData.length > 0) {
            appendFiguresToWrapper(assistantWrapper, figuresData);
          }
        } else if (eventName === "follow_ups") {
          followUpsData = Array.isArray(payload) ? payload : [];
          if (assistantWrapper && followUpsData.length > 0) {
            appendFollowUpsToWrapper(assistantWrapper, followUpsData);
          }
        } else if (eventName === "done") {
          if (payload.referenced_books && referencedBooksContainer) {
            renderReferencedBooksHtml(referencedBooksContainer, payload.referenced_books);
          }
          if (payload.reply && proseContainer) {
            const finalSanitized = sanitizeMedicalText(payload.reply);
            let finalHtml = window.marked ? marked.parse(finalSanitized) : finalSanitized;
            finalHtml = formatCitationBadges(finalHtml);
            proseContainer.innerHTML = finalHtml;
            attachCitationBadgeListeners(assistantWrapper);
          }
          fetchQuota();
          fetchSessions();
        } else if (eventName === "error") {
          throw new Error(payload.error || "Streaming error occurred");
        }
      }
    }

  } catch (err) {
    if (err.name === "AbortError") {
      console.log("Generation halted by user.");
      if (typingIndicator && typingIndicator.parentElement) {
        typingIndicator.remove();
      }
      if (assistantWrapper) {
        const stoppedBadge = document.createElement("div");
        stoppedBadge.className = "text-xs text-slate-400 italic mt-2 border-t border-slate-100 pt-2 flex items-center gap-1.5";
        stoppedBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span><span>Generation stopped by user.</span>`;
        assistantWrapper.querySelector(".space-y-2")?.appendChild(stoppedBadge);
      }
    } else {
      if (typingIndicator && typingIndicator.parentElement) {
        typingIndicator.remove();
      }
      appendErrorMessage(err.message);
    }
  } finally {
    isAwaitingResponse = false;
    currentAbortController = null;
    updateSendButtonState();
    chatInput.focus();
    fetchQuota();
    fetchSessions();
  }
}

// Append User Message Bubble
function appendUserMessage(text) {
  const wrapper = document.createElement("div");
  wrapper.className = "flex justify-end my-1.5";
  wrapper.innerHTML = `
    <div class="user-bubble">
      ${escapeHtml(text)}
    </div>
  `;
  messagesContainer.appendChild(wrapper);
}

// Append Typing Indicator
function appendTypingIndicator() {
  const wrapper = document.createElement("div");
  wrapper.className = "flex items-start gap-3";
  wrapper.innerHTML = `
    <div class="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center flex-shrink-0 text-sm shadow-xs" aria-hidden="true">
      ${AVATAR_SVG}
    </div>
    <div class="bg-white border border-slate-200 rounded-2xl rounded-tl-none sm:rounded-tl-sm px-4 py-3 shadow-sm flex items-center gap-2">
      <div class="w-2 h-2 rounded-full bg-blue-500 animate-bounce"></div>
      <div class="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0.2s]"></div>
      <div class="w-2 h-2 rounded-full bg-blue-300 animate-bounce [animation-delay:0.4s]"></div>
      <span class="typing-status-text text-xs text-slate-500 ml-2 font-medium">Searching textbook structure & chunks...</span>
    </div>
  `;
  messagesContainer.appendChild(wrapper);
  return wrapper;
}

function createStreamingAssistantBubble() {
  const wrapper = document.createElement("div");
  wrapper.className = "flex items-start gap-3";
  wrapper.innerHTML = `
    <div class="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center flex-shrink-0 text-sm shadow-xs" aria-hidden="true">
      ${AVATAR_SVG}
    </div>
    <div class="flex-1 max-w-3xl bg-white border border-slate-200 rounded-2xl rounded-tl-none sm:rounded-tl-sm px-5 py-4 shadow-sm space-y-2">
      <div class="referenced-books-container"></div>
      <div class="tools-container"></div>
      <div class="prose-custom"></div>
      <div class="figures-container"></div>
      <div class="follow-ups-container"></div>
    </div>
  `;
  return {
    wrapper,
    proseContainer: wrapper.querySelector(".prose-custom"),
    toolsContainer: wrapper.querySelector(".tools-container"),
    referencedBooksContainer: wrapper.querySelector(".referenced-books-container"),
    figuresContainer: wrapper.querySelector(".figures-container"),
    followUpsContainer: wrapper.querySelector(".follow-ups-container"),
  };
}

function renderReferencedBooksHtml(container, books) {
  if (!container || !books || books.length === 0) {
    if (container) container.innerHTML = "";
    return;
  }
  const badges = books.map(b => {
    const pageInfo = b.pages ? ` <span class="text-indigo-600 font-medium">(${escapeHtml(b.pages)})</span>` : '';
    return `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-2xs">
      <svg class="w-3.5 h-3.5 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
      <span>${escapeHtml(b.title)}</span>${pageInfo}
    </span>`;
  }).join("");

  container.innerHTML = `
    <div class="flex flex-wrap items-center gap-2 pb-2 mb-2 border-b border-slate-100">
      <span class="text-xs font-bold uppercase tracking-wider text-slate-500 mr-0.5">Referenced Textbooks:</span>
      ${badges}
    </div>
  `;
}

function renderToolsHtml(container, tools) {
  if (!container || !tools || tools.length === 0) return;
  const pills = tools.map(tc => {
    return `
      <div class="tool-pill">
        <svg class="w-3 h-3 text-amber-500" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
        </svg>
        <span>${escapeHtml(tc.summary || tc.name)}</span>
      </div>
    `;
  }).join("");
  container.innerHTML = `<div class="flex flex-wrap gap-1.5 mb-3">${pills}</div>`;
}

function appendFiguresToWrapper(wrapper, figures) {
  const container = wrapper.querySelector(".figures-container");
  if (!container || !figures || figures.length === 0) return;

  const cards = figures.map((fig, idx) => {
    const bookTitle = fig.book_slug ? fig.book_slug.replace(/_/g, " ").replace(/-/g, " ").toUpperCase() : "Textbook Volume";
    const rawText = fig.text || "";
    const cleanCaption = rawText
      .replace(/(\w+)-\s*\n\s*(\w+)/g, "$1$2")
      .replace(/\s+/g, " ")
      .trim();

    const match = cleanCaption.match(/^(FIGURE\s+[\d\.]+[\w\s–—\-:]*?)(?:\.|\n|$)/i);
    const figTitle = match && match[1].length < 60 ? match[1].trim() : `Figure ${idx + 1}`;

    return `
      <div class="figure-card bg-white hover:bg-blue-50/40 border border-slate-200 hover:border-blue-300 rounded-xl p-3 cursor-pointer transition shadow-2xs group flex flex-col justify-between" data-fig-chunk="${escapeHtml(fig.chunk_id)}">
        <div>
          <!-- Thumbnail Container -->
          <div class="relative w-full h-36 bg-slate-50 border border-slate-100 rounded-lg overflow-hidden mb-2.5 flex items-center justify-center group-hover:border-blue-200 transition">
            <img 
              src="/api/figure/${encodeURIComponent(fig.chunk_id)}/image" 
              alt="${escapeHtml(figTitle)}" 
              class="w-full h-full object-contain p-1 transition-transform duration-200 group-hover:scale-105" 
              loading="lazy" 
              onerror="const card = this.closest('.figure-card'); if (card) { const cont = card.closest('.figures-container'); card.remove(); if (cont && cont.querySelectorAll('.figure-card').length === 0) cont.remove(); }" 
            />
            <span class="absolute bottom-1.5 right-1.5 bg-slate-900/70 text-white text-xs px-1.5 py-0.5 rounded backdrop-blur-xs font-mono">p. ${fig.page_start}</span>
          </div>

          <div class="flex items-center justify-between gap-1 mb-1">
            <span class="font-bold text-xs text-slate-800 group-hover:text-blue-700 truncate">${escapeHtml(figTitle)}</span>
          </div>
          <p class="text-xs text-slate-600 line-clamp-2 leading-relaxed font-sans mb-1">${escapeHtml(cleanCaption)}</p>
        </div>
        <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <span class="truncate max-w-[150px]">${escapeHtml(bookTitle)}</span>
          <span class="text-blue-600 font-semibold group-hover:underline flex items-center gap-0.5">Enlarge 🔍</span>
        </div>
      </div>
    `;
  }).join("");

  const isSlider = figures.length > 2;

  if (isSlider) {
    container.innerHTML = `
      <div class="mt-4 pt-3 border-t border-slate-100">
        <div class="flex items-center justify-between mb-2">
          <div class="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            <span>Related Textbook Figures & Diagrams (${figures.length})</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="text-xs text-slate-500 font-mono hidden sm:inline">Scroll &rarr;</span>
            <button type="button" class="btn-slider-chevron btn-slide-figures-left" aria-label="Slide figures left" title="Previous figure">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
            </button>
            <button type="button" class="btn-slider-chevron btn-slide-figures-right" aria-label="Slide figures right" title="Next figure">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
            </button>
          </div>
        </div>
        <div class="figures-slider">${cards}</div>
      </div>
    `;

    const slider = container.querySelector(".figures-slider");
    if (slider) {
      const leftBtn = container.querySelector(".btn-slide-figures-left");
      const rightBtn = container.querySelector(".btn-slide-figures-right");
      if (leftBtn) {
        leftBtn.addEventListener("click", () => {
          slider.scrollBy({ left: -260, behavior: "smooth" });
        });
      }
      if (rightBtn) {
        rightBtn.addEventListener("click", () => {
          slider.scrollBy({ left: 260, behavior: "smooth" });
        });
      }
    }
  } else {
    container.innerHTML = `
      <div class="mt-4 pt-3 border-t border-slate-100">
        <div class="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2 flex items-center gap-1.5">
          <svg class="w-3.5 h-3.5 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          <span>Related Textbook Figures & Diagrams (${figures.length})</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">${cards}</div>
      </div>
    `;
  }

  container.querySelectorAll(".figure-card").forEach(card => {
    card.addEventListener("click", () => {
      const chunkId = card.getAttribute("data-fig-chunk");
      if (chunkId) openLightboxForChunk(chunkId);
    });
  });
}

function appendFollowUpsToWrapper(wrapper, followUps) {
  const container = wrapper.querySelector(".follow-ups-container");
  if (!container || !followUps || followUps.length === 0) return;

  const chips = followUps.map(q => {
    return `
      <button class="follow-up-chip" data-question="${escapeHtml(q)}" aria-label="Explore follow-up: ${escapeHtml(q)}">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"></circle>
          <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon>
        </svg>
        <span>${escapeHtml(q)}</span>
      </button>
    `;
  }).join("");

  container.innerHTML = `
    <div class="mt-4 pt-3 border-t border-slate-100">
      <div class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Explore Related Clinical Questions</div>
      <div class="flex flex-col sm:flex-row flex-wrap gap-2">${chips}</div>
    </div>
  `;

  container.querySelectorAll(".follow-up-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-question");
      if (q) submitQuery(q);
    });
  });
}

function attachCitationBadgeListeners(container) {
  if (!container) return;
  container.querySelectorAll(".citation-badge").forEach(btn => {
    if (!btn.hasAttribute("data-bound")) {
      btn.setAttribute("data-bound", "true");
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const citId = btn.getAttribute("data-cit");
        if (citId) showCitationInDrawer(citId);
      });
    }
  });
}

// Sanitize clinical typography, raw LaTeX tags, and hormone notation
function sanitizeMedicalText(text) {
  if (!text) return "";
  return text
    // 1. Strip raw LaTeX \text{} tags: e.g. \text{pH} -> pH
    .replace(/\\text\{([^}]+)\}/g, "$1")
    // 2. Thyroid and clinical hormone notations: $T_4$ -> T4, $T_3$ -> T3, $fT_4$ -> fT4
    .replace(/\$?([fF]?[tT])_([34])\$?/g, "$1$2")
    .replace(/\$([tT][34])\$/g, "$1")
    // 3. LaTeX symbols to clean Unicode
    .replace(/\\(?:ge|geq)\b/g, "≥")
    .replace(/\\(?:le|leq)\b/g, "≤")
    .replace(/\\sim\b/g, "~")
    .replace(/\\pm\b/g, "±")
    .replace(/\\times\b/g, "×")
    .replace(/\\(?:mu|micro)\b/g, "μ")
    .replace(/\\alpha\b/g, "α")
    .replace(/\\beta\b/g, "β")
    .replace(/\\(?:Delta|delta)\b/g, "Δ")
    .replace(/\\(?:degree|circ)\b/g, "°")
    // 4. Unwrap single dollar math delimiters around clinical lab values/units
    .replace(/\$([A-Za-z0-9\s\.\<\>\=\-\+~±×μμβ°%/–—]+)\$/g, "$1")
    // 5. Strip stray trailing dollar signs from numbers (e.g. 15$, 35$)
    .replace(/(\d+)\$/g, "$1")
    // 6. Standardize ion and enzyme typography
    .replace(/Na\^?\+\/K\^?\+\-?ATPase/gi, "Na⁺/K⁺-ATPase")
    .replace(/\bMg\^?2\+\b/g, "Mg²⁺")
    .replace(/\bCa\^?2\+\b/g, "Ca²⁺")
    // 7. Auto-balance unclosed bold markers at line endings
    .replace(/^(\s*[\*•\-\d\.]+\s*)\*\*([^\*\n]+)$/gm, "$1**$2**");
}

// Append Assistant Message with Tool Pills, Clickable Citations, and Follow-ups
function appendAssistantMessage(data) {
  const wrapper = document.createElement("div");
  wrapper.className = "flex items-start gap-3";

  // Sanitize medical typography then format markdown
  const sanitizedReply = sanitizeMedicalText(data.reply || "");
  let formattedHtml = window.marked ? marked.parse(sanitizedReply) : sanitizedReply;
  formattedHtml = formatCitationBadges(formattedHtml);

  // Referenced Books Header
  let refBooksHtml = "";
  const refBooks = data.referenced_books || [];
  if (refBooks && refBooks.length > 0) {
    const badges = refBooks.map(b => {
      const pageInfo = b.pages ? ` <span class="text-indigo-600 font-medium">(${escapeHtml(b.pages)})</span>` : '';
      return `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-2xs">
        <svg class="w-3.5 h-3.5 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
        <span>${escapeHtml(b.title)}</span>${pageInfo}
      </span>`;
    }).join("");
    refBooksHtml = `
      <div class="flex flex-wrap items-center gap-2 pb-2 mb-2 border-b border-slate-100">
        <span class="text-xs font-bold uppercase tracking-wider text-slate-400 mr-0.5">Referenced Textbooks:</span>
        ${badges}
      </div>
    `;
  }

  // Tool pills HTML with bolt SVG
  let toolsHtml = "";
  if (data.tool_calls && data.tool_calls.length > 0) {
    const pills = data.tool_calls.map(tc => {
      return `
        <div class="tool-pill">
          <svg class="w-3 h-3 text-amber-500" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
          </svg>
          <span>${escapeHtml(tc.summary || tc.name)}</span>
        </div>
      `;
    }).join("");
    toolsHtml = `<div class="flex flex-wrap gap-1.5 mb-3">${pills}</div>`;
  }

  // Follow-up questions HTML with compass SVG
  let followUpsHtml = "";
  if (data.follow_ups && data.follow_ups.length > 0) {
    const chips = data.follow_ups.map(q => {
      return `
        <button class="follow-up-chip" data-question="${escapeHtml(q)}" aria-label="Explore follow-up: ${escapeHtml(q)}">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"></circle>
            <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon>
          </svg>
          <span>${escapeHtml(q)}</span>
        </button>
      `;
    }).join("");
    followUpsHtml = `
      <div class="mt-4 pt-3 border-t border-slate-100">
        <div class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Explore Related Clinical Questions</div>
        <div class="flex flex-col sm:flex-row flex-wrap gap-2">${chips}</div>
      </div>
    `;
  }

  // Related Figures Tray HTML
  let figuresHtml = "";
  if (data.figures && data.figures.length > 0) {
    const cards = data.figures.map((fig, idx) => {
      const bookTitle = fig.book_slug ? fig.book_slug.replace(/_/g, " ").replace(/-/g, " ").toUpperCase() : "Textbook Volume";
      const rawText = fig.text || "";
      const cleanCaption = rawText
        .replace(/(\w+)-\s*\n\s*(\w+)/g, "$1$2")
        .replace(/\s+/g, " ")
        .trim();

      const match = cleanCaption.match(/^(FIGURE\s+[\d\.]+[\w\s–—\-:]*?)(?:\.|\n|$)/i);
      const figTitle = match && match[1].length < 60 ? match[1].trim() : `Figure ${idx + 1}`;

      return `
        <div class="figure-card bg-white hover:bg-blue-50/40 border border-slate-200 hover:border-blue-300 rounded-xl p-3 cursor-pointer transition shadow-2xs group flex flex-col justify-between" data-fig-chunk="${escapeHtml(fig.chunk_id)}">
          <div>
            <!-- Thumbnail Container -->
            <div class="relative w-full h-36 bg-slate-50 border border-slate-100 rounded-lg overflow-hidden mb-2.5 flex items-center justify-center group-hover:border-blue-200 transition">
              <img 
                src="/api/figure/${encodeURIComponent(fig.chunk_id)}/image" 
                alt="${escapeHtml(figTitle)}" 
                class="w-full h-full object-contain p-1 transition-transform duration-200 group-hover:scale-105" 
                loading="lazy" 
                onerror="const card = this.closest('.figure-card'); if (card) { const cont = card.closest('.figures-container'); card.remove(); if (cont && cont.querySelectorAll('.figure-card').length === 0) cont.remove(); }" 
              />
              <span class="absolute bottom-1.5 right-1.5 bg-slate-900/70 text-white text-xs px-1.5 py-0.5 rounded backdrop-blur-xs font-mono">p. ${fig.page_start}</span>
            </div>

            <div class="flex items-center justify-between gap-1 mb-1">
              <span class="font-bold text-xs text-slate-800 group-hover:text-blue-700 truncate">${escapeHtml(figTitle)}</span>
            </div>
            <p class="text-xs text-slate-500 line-clamp-2 leading-relaxed font-sans mb-1">${escapeHtml(cleanCaption)}</p>
          </div>
          <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
            <span class="truncate max-w-[150px]">${escapeHtml(bookTitle)}</span>
            <span class="text-blue-600 font-semibold group-hover:underline flex items-center gap-0.5">Enlarge 🔍</span>
          </div>
        </div>
      `;
    }).join("");

    figuresHtml = `
      <div class="figures-container mt-4 pt-3 border-t border-slate-100">
        <div class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
          <svg class="w-3.5 h-3.5 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          <span>Related Textbook Figures & Diagrams (${data.figures.length})</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">${cards}</div>
      </div>
    `;
  }

  wrapper.innerHTML = `
    <div class="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center flex-shrink-0 text-sm shadow-xs" aria-hidden="true">
      ${AVATAR_SVG}
    </div>
    <div class="flex-1 max-w-3xl bg-white border border-slate-200 rounded-2xl rounded-tl-none sm:rounded-tl-sm px-5 py-4 shadow-sm space-y-2">
      ${refBooksHtml}
      ${toolsHtml}
      <div class="prose-custom">
        ${formattedHtml}
      </div>
      ${figuresHtml}
      ${followUpsHtml}
    </div>
  `;

  // Attach citation click events
  wrapper.querySelectorAll(".citation-badge").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const citId = btn.getAttribute("data-cit");
      showCitationInDrawer(citId);
    });
  });

  // Attach figure card click events
  wrapper.querySelectorAll(".figure-card").forEach(card => {
    card.addEventListener("click", () => {
      const chunkId = card.getAttribute("data-fig-chunk");
      if (chunkId) openLightboxForChunk(chunkId);
    });
  });

  // Attach follow-up question click events
  wrapper.querySelectorAll(".follow-up-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-question");
      if (q) submitQuery(q);
    });
  });

  messagesContainer.appendChild(wrapper);
}

// Figure Lightbox Functions
function openLightbox({ chunkId, title, page, caption }) {
  if (!figureLightboxModal || !lightboxImg) return;
  lightboxImg.src = `/api/figure/${encodeURIComponent(chunkId)}/image`;
  if (lightboxTitle) lightboxTitle.textContent = title || "Textbook Diagram";
  if (lightboxPageBadge) lightboxPageBadge.textContent = page ? `p. ${page}` : "";
  if (lightboxCaption) lightboxCaption.textContent = caption || "";
  figureLightboxModal.classList.remove("hidden");
  document.body.classList.add("overflow-hidden");
}

function closeLightbox() {
  if (!figureLightboxModal) return;
  figureLightboxModal.classList.add("hidden");
  if (lightboxImg) lightboxImg.src = "";
  document.body.classList.remove("overflow-hidden");
}

async function openLightboxForChunk(chunkId) {
  try {
    const res = await fetch(`/api/chunk/${encodeURIComponent(chunkId)}`);
    if (res.ok) {
      const data = await res.json();
      const rawText = data.text || "";
      const match = rawText.match(/^(FIGURE\s+[\d\.]+[\w\s–—\-:]*?)(?:\.|\n|$)/i);
      const figTitle = match && match[1].length < 60 ? match[1].trim() : "Textbook Figure";
      openLightbox({
        chunkId,
        title: figTitle,
        page: data.page_start,
        caption: rawText
      });
      return;
    }
  } catch (err) {
    console.warn("Failed to fetch chunk details for lightbox:", err);
  }
  openLightbox({ chunkId, title: "Textbook Figure", page: "", caption: "" });
}

// Show textbook figure in Evidence Drawer
async function showFigureInDrawer(chunkId) {
  drawerContent.innerHTML = `
    <div class="p-4 bg-white rounded-xl border border-slate-200 text-xs text-slate-500 flex items-center gap-2">
      <div class="w-2 h-2 rounded-full bg-blue-500 animate-bounce"></div>
      <span>Loading textbook figure from database...</span>
    </div>
  `;
  openDrawer();

  try {
    const res = await fetch(`/api/chunk/${encodeURIComponent(chunkId)}`);
    if (!res.ok) throw new Error("Could not retrieve figure details");
    const figData = await res.json();

    const bookName = (figData.book_slug || "").replace(/_/g, " ").replace(/-/g, " ").toUpperCase();
    const cleanText = (figData.text || "").replace(/(\w+)-\s*\n\s*(\w+)/g, "$1$2");

    drawerContent.innerHTML = `
      <div class="space-y-4 text-xs">
        <!-- Header Badge -->
        <div class="flex items-center justify-between">
          <span class="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-bold font-mono flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            Textbook Figure
          </span>
          <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-xs font-semibold">
            Visual Illustration
          </span>
        </div>

        <!-- Textbook Figure Image Preview -->
        <div class="bg-white p-2.5 rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div class="flex items-center justify-between text-xs font-bold text-slate-700 px-1 mb-1.5">
            <span class="flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              <span>Textbook Diagram</span>
            </span>
            <button type="button" class="text-blue-600 hover:text-blue-800 text-xs font-semibold cursor-pointer flex items-center gap-0.5" onclick="openLightboxForChunk('${escapeHtml(chunkId)}')">
              <span>Enlarge</span> &nearr;
            </button>
          </div>
          <div class="relative bg-slate-950/5 rounded-lg overflow-hidden flex items-center justify-center p-1 min-h-[140px] cursor-zoom-in" onclick="openLightboxForChunk('${escapeHtml(chunkId)}')">
            <img src="/api/figure/${encodeURIComponent(chunkId)}/image" alt="Textbook Figure Visual" class="w-full max-h-60 object-contain rounded transition hover:scale-102" loading="lazy" onerror="this.parentElement.parentElement.remove();" />
          </div>
        </div>

        <!-- Source Book -->
        <div class="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
          <div class="flex items-center gap-1.5 text-xs uppercase font-bold text-slate-400 mb-1">
            <svg class="w-3.5 h-3.5 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            <span>Textbook Volume</span>
          </div>
          <div class="font-semibold text-slate-800">${escapeHtml(bookName)}</div>
        </div>

        <!-- Hierarchy / Heading Path -->
        <div class="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
          <div class="text-xs uppercase font-bold text-slate-400 mb-1">Section Location</div>
          <div class="text-blue-700 font-semibold leading-relaxed">${escapeHtml(figData.heading_path || "Textbook Section")}</div>
        </div>

        <!-- Page info -->
        <div class="grid grid-cols-2 gap-2">
          <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
            <div class="text-xs uppercase font-bold text-slate-400">Printed Page</div>
            <div class="text-sm font-bold text-slate-900 mt-0.5">p. ${figData.page_start}</div>
          </div>
          <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
            <div class="text-xs uppercase font-bold text-slate-400">Content Type</div>
            <div class="text-xs font-semibold text-slate-800 mt-1 flex items-center gap-1">
              <span class="inline-block w-2 h-2 rounded-full bg-blue-500"></span>
              <span>FIGURE CAPTION</span>
            </div>
          </div>
        </div>

        <!-- Passage Text -->
        <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-2">
          <div class="flex items-center justify-between text-xs uppercase font-bold text-slate-400">
            <span>Verified Figure Caption</span>
            <span class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold text-xs">VERIFIED FIGURE</span>
          </div>
          <div class="text-slate-700 leading-relaxed font-sans text-xs max-h-80 overflow-y-auto whitespace-pre-wrap bg-slate-50 p-3 rounded-lg border border-slate-200">
            ${escapeHtml(cleanText)}
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    drawerContent.innerHTML = `
      <div class="p-4 bg-rose-50 rounded-xl border border-rose-200 text-xs text-rose-700">
        Failed to load figure details: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

// Replace [1], [2] in HTML with clickable badge buttons ONLY if registered in cache
function formatCitationBadges(html) {
  return html.replace(/\[(\d+)\]/g, (match, p1) => {
    if (citationsCache && citationsCache.has(String(p1))) {
      return `<button type="button" class="citation-badge" data-cit="${p1}" aria-label="View citation source ${p1}" title="Click to view citing evidence">[${p1}]</button>`;
    }
    // Return original bracket text (e.g. literature reference or non-cached citation)
    return match;
  });
}

// Inspect citation in Right Evidence Drawer
async function showCitationInDrawer(citId) {
  const cit = citationsCache.get(String(citId));
  if (!cit) {
    drawerContent.innerHTML = `
      <div class="p-4 bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
        Citation [${citId}] details not found in cache.
      </div>
    `;
    openDrawer();
    return;
  }

  // Display initial cached metadata
  const bookName = cit.book_slug.replace(/_/g, " ").replace(/-/g, " ").toUpperCase();
  drawerContent.innerHTML = `
    <div class="space-y-4 text-xs">
      <!-- Header Badge -->
      <div class="flex items-center justify-between">
        <span class="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-bold font-mono">
          Citation [${cit.citation_id}]
        </span>
        <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-medium">
          <svg class="w-3 h-3 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          Authoritative Evidence
        </span>
      </div>

      <!-- Source Book -->
      <div class="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
        <div class="flex items-center gap-1.5 text-xs uppercase font-bold text-slate-400 mb-1">
          <svg class="w-3.5 h-3.5 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
          <span>Textbook Volume</span>
        </div>
        <div class="font-semibold text-slate-800">${escapeHtml(bookName)}</div>
      </div>

      <!-- Hierarchy / Heading Path -->
      <div class="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
        <div class="text-xs uppercase font-bold text-slate-400 mb-1">Chapter & Topic Breadcrumb</div>
        <div class="text-blue-700 font-semibold leading-relaxed">${escapeHtml(cit.heading_path || "Chapter Subsection")}</div>
      </div>

      <!-- Clean Clinical Reference Info (Developer Section ID replaced with Clinical Focus) -->
      <div class="grid grid-cols-2 gap-2">
        <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
          <div class="text-xs uppercase font-bold text-slate-400">Printed Page</div>
          <div class="text-sm font-bold text-slate-900 mt-0.5">p. ${cit.page_start}${cit.page_start !== cit.page_end ? `–${cit.page_end}` : ''}</div>
        </div>
        <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
          <div class="text-xs uppercase font-bold text-slate-400">Source Type</div>
          <div class="text-xs font-semibold text-slate-800 mt-1 flex items-center gap-1 text-slate-700">
            <span class="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>Core Textbook</span>
          </div>
        </div>
      </div>

      <!-- Passage Text -->
      <div id="drawer-passage-box" class="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-2">
        <div class="flex items-center justify-between text-xs uppercase font-bold text-slate-400">
          <span>Verified Passage Excerpt</span>
          <span id="drawer-chunk-type" class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold text-xs">VERIFIED EXCERPT</span>
        </div>
        <div id="drawer-chunk-text" class="text-slate-700 leading-relaxed font-sans text-xs max-h-80 overflow-y-auto whitespace-pre-wrap bg-slate-50 p-3 rounded-lg border border-slate-200">
          Fetching chunk details from database...
        </div>
      </div>
    </div>
  `;

  openDrawer();

  // Fetch full chunk details from /api/chunk/{chunk_id}
  try {
    const res = await fetch(`/api/chunk/${encodeURIComponent(cit.chunk_id)}`);
    if (res.ok) {
      const chunkData = await res.json();
      const textEl = document.getElementById("drawer-chunk-text");
      const typeEl = document.getElementById("drawer-chunk-type");
      if (textEl && chunkData.text) {
        // De-hyphenate column-split line wraps
        textEl.textContent = chunkData.text.replace(/(\w+)-\s*\n\s*(\w+)/g, "$1$2");
      }
      if (typeEl && chunkData.content_type) {
        typeEl.textContent = chunkData.content_type.toUpperCase();
      }

      // If chunk is a figure or diagram caption, inject visual image preview
      const isFigure = chunkData.content_type === "figure_caption" || chunkData.sub_type === "figure" || /^\s*FIGURE\s+[\d\.]+/i.test(chunkData.text || "");
      if (isFigure) {
        const passageBox = document.getElementById("drawer-passage-box");
        if (passageBox && passageBox.parentElement) {
          const figPreview = document.createElement("div");
          figPreview.className = "bg-white p-2.5 rounded-xl border border-slate-200 shadow-2xs overflow-hidden mb-3";
          figPreview.innerHTML = `
            <div class="flex items-center justify-between text-xs font-bold text-slate-700 px-1 mb-1.5">
              <span class="flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                <span>Textbook Figure Visual</span>
              </span>
              <button type="button" class="text-blue-600 hover:text-blue-800 text-xs font-semibold cursor-pointer flex items-center gap-0.5" onclick="openLightboxForChunk('${escapeHtml(cit.chunk_id)}')">
                <span>Enlarge</span> &nearr;
              </button>
            </div>
            <div class="relative bg-slate-950/5 rounded-lg overflow-hidden flex items-center justify-center p-1 min-h-[140px] cursor-zoom-in" onclick="openLightboxForChunk('${escapeHtml(cit.chunk_id)}')">
              <img src="/api/figure/${encodeURIComponent(cit.chunk_id)}/image" alt="Citation Figure Preview" class="w-full max-h-60 object-contain rounded transition hover:scale-102" loading="lazy" onerror="this.parentElement.parentElement.remove();" />
            </div>
          `;
          passageBox.parentElement.insertBefore(figPreview, passageBox);
        }
      }
    }
  } catch (err) {
    console.error("Failed to load chunk text:", err);
  }
}

// Append Error Bubble
function appendErrorMessage(msg) {
  const wrapper = document.createElement("div");
  wrapper.className = "flex justify-center";
  wrapper.innerHTML = `
    <div class="max-w-md bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl px-4 py-2.5 text-center font-medium shadow-xs flex items-center gap-2">
      <svg class="w-4 h-4 text-rose-600 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <span>${escapeHtml(msg)}</span>
    </div>
  `;
  messagesContainer.appendChild(wrapper);
}

function isNearBottom() {
  if (!messagesContainer) return true;
  const fromBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop - messagesContainer.clientHeight;
  return fromBottom <= SCROLL_THRESHOLD;
}

function updateScrollButtonVisibility() {
  if (!btnScrollBottom || !messagesContainer) return;
  if (isNearBottom()) {
    userHasScrolledUp = false;
    btnScrollBottom.classList.add("hidden");
    btnScrollBottom.classList.remove("flex");
  } else {
    userHasScrolledUp = true;
    btnScrollBottom.classList.remove("hidden");
    btnScrollBottom.classList.add("flex");
  }
}

function scrollToBottom(force = false) {
  if (!messagesContainer) return;
  if (force || !userHasScrolledUp) {
    if (force) {
      messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: "smooth"
      });
    } else {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
