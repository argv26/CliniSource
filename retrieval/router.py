"""Semantic Book Router for multi-textbook classification and scope binding."""
from __future__ import annotations

import re
from typing import Any

from retrieval.tools import list_books

# Standard specialty profiles for indexed textbooks (extensible as new books are indexed)
BOOK_SPECIALTY_PROFILES: dict[str, dict[str, Any]] = {
    "Williams_Textbook_of_Endocrinology_15th_edition_2": {
        "title": "Williams Textbook of Endocrinology",
        "specialty": "Endocrinology & Metabolism",
        "keywords": {
            "hormone", "hormones", "endocrine", "endocrinology", "thyroid", "adrenal",
            "pituitary", "hypothalamus", "parathyroid", "pancreas", "islet", "insulin",
            "glucagon", "cortisol", "aldosterone", "catecholamine", "catecholamines",
            "epinephrine", "norepinephrine", "metanephrine", "pheochromocytoma", "cushing",
            "addison", "diabetes", "dka", "ketoacidosis", "calcium", "hypercalcemia",
            "hypocalcemia", "pth", "tsh", "trh", "acth", "gonadotropin", "growth hormone",
            "prolactin", "somatostatin", "testosterone", "estrogen", "progesterone",
            "steroid", "steroidogenesis", "graves", "hashimoto", "thyroiditis", "goiter",
            "hypothyroidism", "hyperthyroidism", "hyperaldosteronism", "conn", "paraganglioma",
            "hypoglycemia", "glycemia", "sglt", "hba1c", "zona glomerulosa", "zona fasciculata",
            "zona reticularis", "chromaffin", "paraventricular", "neuroendocrine", "metabolic"
        },
        "description": "Comprehensive authority on hormonal regulation, endocrine glands, biochemical steroidogenesis, and metabolic disorders."
    },
    "anatomy-and-physiology-2e_-_WEB": {
        "title": "Anatomy and Physiology 2e",
        "specialty": "Anatomy & Physiology",
        "keywords": {
            "anatomy", "physiology", "bone", "bones", "skeleton", "skeletal", "muscle",
            "muscles", "muscular", "joint", "joints", "tendon", "ligament", "nerve",
            "nerves", "brachial plexus", "lumbar plexus", "femoral", "femoral triangle",
            "triangle", "artery", "arteries", "vein", "veins", "vascular", "aorta",
            "heart", "cardiac", "ventricle", "atrium", "circulation", "brain", "cerebrum",
            "cerebellum", "spinal cord", "cranial", "meninges", "axon", "neuron",
            "tissue", "epithelial", "connective", "integumentary", "skin", "dermis",
            "epidermis", "respiratory", "lungs", "trachea", "bronchi", "digestive",
            "stomach", "intestine", "colon", "esophagus", "peritoneum", "urinary",
            "kidney", "nephron", "bladder", "ureter", "urethra", "lymphatic", "spleen",
            "reproductive", "testes", "ovaries", "uterus", "boundaries", "contents",
            "origins", "insertions", "innervation", "histology", "fascia", "inguinal"
        },
        "description": "Core textbook covering human macroscopic anatomy, regional relationships, organ systems, and physiological principles."
    },
    "Harrison_2025_22nd_Edition": {
        "title": "Harrison's Principles of Internal Medicine (22nd Edition)",
        "specialty": "Internal Medicine",
        "keywords": {
            "internal medicine", "medicine", "diagnosis", "differential", "differential diagnosis",
            "cardiology", "chest pain", "angina", "infarction", "myocardial", "troponin", "arrhythmia",
            "heart failure", "pulmonology", "dyspnea", "asthma", "copd", "pneumonia", "embolism",
            "nephrology", "renal", "kidney injury", "aki", "ckd", "glomerulonephritis", "acidosis",
            "gastroenterology", "cirrhosis", "hepatitis", "pancreatitis", "ulcer", "bleeding",
            "infectious", "infection", "sepsis", "bacteremia", "endocarditis", "meningitis", "fever",
            "hematology", "anemia", "thrombocytopenia", "leukemia", "lymphoma", "coagulation",
            "rheumatology", "lupus", "arthritis", "vasculitis", "autoimmune", "neurology", "stroke",
            "seizure", "delirium", "coma", "dka", "resuscitation", "shock", "intensive care", "oncology"
        },
        "description": "Gold-standard internal medicine masterwork covering clinical presentation, multi-system differential diagnosis, pathophysiology, and patient management."
    },
    "CORNEA_FundamentalsDiagnosis_and_Management_5th_Ed": {
        "title": "Cornea: Fundamentals, Diagnosis and Management (5th Edition)",
        "specialty": "Ophthalmology",
        "keywords": {
            "eye", "cornea", "corneal", "keratitis", "keratoplasty", "ulcer", "stroma", "epithelium",
            "endothelium", "conjunctiva", "vision", "refractive", "transplant", "ophthalmology"
        },
        "description": "Comprehensive reference work on corneal anatomy, diseases, keratoplasty, and ocular surface management."
    },
}


class SemanticBookRouter:
    """Routes medical inquiries to the most relevant textbooks in the library."""

    def __init__(self, catalog: list[dict[str, Any]] | None = None):
        self._catalog = catalog

    @property
    def catalog(self) -> list[dict[str, Any]]:
        if self._catalog is None:
            self._catalog = list_books()
        return self._catalog

    def route(
        self,
        query: str,
        plan: Any | None = None,
        user_selected_books: list[str] | None = None,
    ) -> list[str]:
        """Selects the optimal textbook slugs to query.

        Rules:
        1. User Selection Sovereignty: If user explicitly selected a subset of books,
           strictly return that selection without modification.
        2. All Books Mode: If user_selected_books is None or equals all available books,
           evaluate the inquiry and plan against book domain profiles and return top 1-3.
        """
        all_slugs = [b["slug"] for b in self.catalog]
        if not all_slugs:
            return []

        # 1. User Selection Sovereignty
        if user_selected_books:
            valid_user_books = [b for b in user_selected_books if b in all_slugs]
            # If user explicitly filtered to a subset of books, honor it 100%
            if valid_user_books and len(valid_user_books) < len(all_slugs):
                return valid_user_books

        # 2. Extract search terms from query and clinical plan
        tokens: set[str] = set()
        clean_q = re.sub(r"[^\w\s-]", " ", query.lower())
        tokens.update(clean_q.split())

        if plan:
            # Add plan hypotheses, organ systems, and search queries
            hypotheses = getattr(plan, "diagnostic_hypotheses", []) or []
            organ_systems = getattr(plan, "organ_systems", []) or []
            search_queries = getattr(plan, "search_queries", []) or []

            combined_plan_text = " ".join(hypotheses + organ_systems + search_queries).lower()
            plan_tokens = re.sub(r"[^\w\s-]", " ", combined_plan_text).split()
            tokens.update(plan_tokens)

        # 3. Score each available textbook
        scores: dict[str, float] = {}
        for b in self.catalog:
            slug = b["slug"]
            profile = BOOK_SPECIALTY_PROFILES.get(slug, {})
            title = (profile.get("title") or b.get("title", "")).lower()
            specialty = (profile.get("specialty") or b.get("specialty") or "").lower()
            desc = profile.get("description", "").lower()
            keywords = profile.get("keywords", set())

            score = 0.0

            # Match tokens
            for t in tokens:
                if len(t) < 3:
                    continue
                if t in keywords:
                    score += 3.0
                if t in title:
                    score += 2.0
                if t in specialty:
                    score += 2.0
                if t in desc:
                    score += 1.0

            # Check for phrase matches (e.g. "femoral triangle", "adrenal cortex")
            full_text = f"{clean_q} {' '.join(tokens)}"
            for kw in keywords:
                if " " in kw and kw in full_text:
                    score += 5.0

            scores[slug] = score

        # 4. Rank and select top 1-3 books with score > 0
        ranked = sorted(all_slugs, key=lambda s: scores.get(s, 0.0), reverse=True)
        top_scores = [scores.get(s, 0.0) for s in ranked]

        if top_scores and top_scores[0] > 0:
            # If top book has strong score and second book is weak (< 20% of top), select top 1
            if len(ranked) > 1 and top_scores[1] > 0 and (top_scores[1] >= 0.2 * top_scores[0]):
                return ranked[:2]
            return [ranked[0]]

        # Default fallback: return all available textbooks
        return all_slugs


def extract_referenced_books(citations: list[Any]) -> list[dict[str, Any]]:
    """Extracts unique referenced textbooks with formatted page spans from citations list."""
    book_pages: dict[str, list[tuple[int, int]]] = {}
    book_meta: dict[str, dict[str, str]] = {}

    for cit in citations:
        slug = getattr(cit, "book_slug", None) or (cit.get("book_slug") if isinstance(cit, dict) else None)
        if not slug:
            continue
        p_start = getattr(cit, "page_start", 0) or (cit.get("page_start", 0) if isinstance(cit, dict) else 0)
        p_end = getattr(cit, "page_end", p_start) or (cit.get("page_end", p_start) if isinstance(cit, dict) else p_start)

        if slug not in book_pages:
            book_pages[slug] = []
            profile = BOOK_SPECIALTY_PROFILES.get(slug, {})
            title = profile.get("title") or (cit.get("book_title") if isinstance(cit, dict) else getattr(cit, "book_title", None)) or slug.replace("_", " ").title()
            specialty = profile.get("specialty") or (cit.get("specialty") if isinstance(cit, dict) else getattr(cit, "specialty", None)) or "Medical Reference"
            book_meta[slug] = {"title": title, "specialty": specialty}

        book_pages[slug].append((p_start, p_end))

    referenced: list[dict[str, Any]] = []
    for slug, spans in book_pages.items():
        # Deduplicate and sort spans
        unique_spans = sorted(set(spans))
        formatted_spans: list[str] = []
        for s, e in unique_spans:
            if s <= 0:
                continue
            if s == e or e <= 0:
                formatted_spans.append(str(s))
            else:
                formatted_spans.append(f"{s}\u2013{e}")

        if len(formatted_spans) == 1 and "\u2013" not in formatted_spans[0]:
            pages_str = f"p. {formatted_spans[0]}"
        elif formatted_spans:
            pages_str = f"pp. {', '.join(formatted_spans)}"
        else:
            pages_str = ""

        referenced.append({
            "slug": slug,
            "title": book_meta[slug]["title"],
            "specialty": book_meta[slug]["specialty"],
            "pages": pages_str,
        })

    return referenced
