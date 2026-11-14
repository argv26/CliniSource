"""Agent Orchestrator connecting ContextManager, Retrieval Tools, and LLMs."""
from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any

from agent.offline import (
    build_offline_response_text,
    parse_follow_ups,
    run_offline_synthesizer_turn,
)
from agent.planner import AttendingPlanner, ClinicalPlan
from agent.prompts import INVARIANT_SYSTEM_PROMPT, SYSTEM_PROMPT
from agent.providers import resolve_gemini_candidate_models, run_gemini_turn, run_openai_turn
from agent.sanitizers import (
    _clean_chunk_prose,
    _extract_coherent_sentences,
    _sanitize_citations,
    _sanitize_medical_typography,
)
from agent.telemetry import TurnTelemetry, _safe_int, extract_gemini_usage
from agent.tools_spec import TOOL_DEFINITIONS, execute_tool
from context.manager import ContextManager
from context.models import CitationRecord
from retrieval.parallel import _execute_parallel_retrieval
from retrieval.router import SemanticBookRouter, extract_referenced_books
from retrieval.tools import search_figures

__all__ = [
    "AgentOrchestrator",
    "TOOL_DEFINITIONS",
    "execute_tool",
    "_clean_chunk_prose",
    "_execute_parallel_retrieval",
    "_extract_coherent_sentences",
    "_sanitize_medical_typography",
    "_sanitize_citations",
]


class AgentOrchestrator:
    """Orchestrates multi-turn conversation, structure-aware tool invocation, and LLM responses."""

    def __init__(
        self,
        context_manager: ContextManager | None = None,
        planner: AttendingPlanner | None = None,
        router: SemanticBookRouter | None = None,
    ):
        self.context_manager = context_manager or ContextManager()
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.planner = planner or AttendingPlanner(
            api_key=self.gemini_api_key,
            openai_api_key=self.openai_api_key,
        )
        self.router = router or SemanticBookRouter()

    def _parse_follow_ups(self, text: str) -> tuple[str, list[str]]:
        return parse_follow_ups(text)

    def _build_offline_response_text(self, user_message: str, chunks_result: list[dict[str, Any]]) -> str:
        return build_offline_response_text(user_message, chunks_result)

    def _run_offline_synthesizer_turn(
        self,
        session_id: str,
        user_message: str,
        book_slug: str | None = None,
        active_books: list[str] | None = None,
    ) -> dict[str, Any]:
        return run_offline_synthesizer_turn(
            context_manager=self.context_manager,
            session_id=session_id,
            user_message=user_message,
            book_slug=book_slug,
            active_books=active_books,
        )

    def _run_openai_turn(
        self,
        session_id: str,
        user_message: str,
        book_slug: str | None = None,
        active_books: list[str] | None = None,
    ) -> dict[str, Any]:
        return run_openai_turn(
            context_manager=self.context_manager,
            session_id=session_id,
            user_message=user_message,
            api_key=self.openai_api_key,
            book_slug=book_slug,
            active_books=active_books,
        )

    def _run_gemini_turn(
        self,
        session_id: str,
        user_message: str,
        book_slug: str | None = None,
        active_books: list[str] | None = None,
    ) -> dict[str, Any]:
        return run_gemini_turn(
            context_manager=self.context_manager,
            session_id=session_id,
            user_message=user_message,
            api_key=self.gemini_api_key,
            book_slug=book_slug,
            active_books=active_books,
        )

    def run_turn(
        self,
        session_id: str,
        user_message: str,
        book_slug: str | None = None,
        active_books: list[str] | None = None,
    ) -> dict[str, Any]:
        """Runs a complete conversation turn returning structured response."""
        t_turn = time.perf_counter()
        telemetry = TurnTelemetry()

        # 1. Add user message
        self.context_manager.add_user_message(session_id, user_message)

        # 2. Check for conversational greetings or pleasantries
        msg_clean = user_message.strip().lower()
        if re.match(r"^(?:hi|hello|hey|hola|greetings|howdy|good\s+(?:morning|afternoon|evening|day))[\s!.]*$", msg_clean):
            reply = (
                "Hello! I am your Clinical Tutor and Medical Study Companion.\n\n"
                "I am here to help you study, review clinical cases, and understand complex physiological and anatomical topics grounded directly in medical textbooks.\n\n"
                "You can ask me about:\n"
                "* **Anatomy & Structural Relationships** (e.g., *boundaries and contents of the femoral triangle*, *brachial plexus organization*)\n"
                "* **Endocrinology & Hormone Pathways** (e.g., *functional zonation of the adrenal cortex*, *thyroid hormone synthesis*)\n"
                "* **Physiology & Clinical Pathology** (e.g., *fluid balance in diabetes insipidus*, *mechanisms of hyperaldosteronism*)\n\n"
                "What medical topic would you like to explore today?"
            )
            follow_ups = [
                "Explain the zones of the adrenal cortex and the specific hormones synthesized in each zone.",
                "How is thyroid hormone synthesized and regulated, and what are the main clinical signs of hypothyroidism?",
                "What are the boundaries, contents, and clinical significance of the femoral triangle?"
            ]
            self.context_manager.add_assistant_message(session_id, reply)
            telemetry.provider = "fastpath"
            telemetry.model_used = "fastpath-greeting"
            telemetry.total_ms = round((time.perf_counter() - t_turn) * 1000, 2)
            return {
                "reply": reply,
                "citations": [],
                "tool_calls": [],
                "follow_ups": follow_ups,
                "routed_books": [],
                "telemetry": telemetry.to_dict(),
            }

        if re.match(r"^(?:thanks|thank\s+you|awesome|great|cool|ok|okay)[\s!.]*$", msg_clean):
            reply = (
                "You're very welcome! Feel free to ask whenever you want to explore more clinical mechanisms, review textbook passages, or work through a case study."
            )
            self.context_manager.add_assistant_message(session_id, reply)
            telemetry.provider = "fastpath"
            telemetry.model_used = "fastpath-gratitude"
            telemetry.total_ms = round((time.perf_counter() - t_turn) * 1000, 2)
            return {
                "reply": reply,
                "citations": [],
                "tool_calls": [],
                "follow_ups": [
                    "Explain the regulatory feedback of the hypothalamic-pituitary-adrenal axis",
                    "What are the clinical hallmarks of Addison's disease?",
                    "How does the renin-angiotensin-aldosterone system regulate arterial pressure?"
                ],
                "routed_books": [],
                "telemetry": telemetry.to_dict(),
            }

        # 3. Formulate Pre-Step Clinical Plan
        t_plan = time.perf_counter()
        plan = self.planner.plan(user_message=user_message, active_books=active_books)
        telemetry.planner_ms = round((time.perf_counter() - t_plan) * 1000, 2)
        planner_meta = getattr(self.planner, "last_telemetry", None)
        if isinstance(planner_meta, dict):
            telemetry.merge_usage(planner_meta)

        # 4. Route textbook scope (honoring explicit user selection if specified)
        t_route = time.perf_counter()
        routed_books = self.router.route(query=user_message, plan=plan, user_selected_books=active_books)
        telemetry.routing_ms = round((time.perf_counter() - t_route) * 1000, 2)

        # 5. Check for configured LLM or fallback to Smart Retrieval Synthesizer
        if self.gemini_api_key:
            try:
                turn_result = self._run_gemini_turn(session_id, user_message, book_slug=book_slug, active_books=routed_books)
            except Exception as e:
                print(f"[AgentOrchestrator] Gemini LLM unavailable ({e}). Falling back to local smart synthesizer.")
                telemetry.fallback_triggered = True
                telemetry.fallback_reason = str(e)
                turn_result = self._run_offline_synthesizer_turn(session_id, user_message, book_slug=book_slug, active_books=routed_books)
        elif self.openai_api_key:
            try:
                turn_result = self._run_openai_turn(session_id, user_message, book_slug=book_slug, active_books=routed_books)
            except Exception as e:
                print(f"[AgentOrchestrator] OpenAI LLM unavailable ({e}). Falling back to local smart synthesizer.")
                telemetry.fallback_triggered = True
                telemetry.fallback_reason = str(e)
                turn_result = self._run_offline_synthesizer_turn(session_id, user_message, book_slug=book_slug, active_books=routed_books)
        else:
            turn_result = self._run_offline_synthesizer_turn(session_id, user_message, book_slug=book_slug, active_books=routed_books)

        sub_tel = turn_result.get("telemetry")
        if isinstance(sub_tel, dict):
            telemetry.provider = str(sub_tel.get("provider", telemetry.provider))
            telemetry.model_used = str(sub_tel.get("model_used", telemetry.model_used))
            telemetry.llm_ms = float(sub_tel.get("llm_ms", 0.0) or 0.0)
            telemetry.retrieval_ms += float(sub_tel.get("retrieval_ms", 0.0) or 0.0)
            telemetry.react_iterations = _safe_int(sub_tel.get("react_iterations", 0))
            telemetry.merge_usage(sub_tel)

        turn_result["plan"] = plan.to_dict()
        turn_result["routed_books"] = routed_books
        session = self.context_manager.get_or_create_session(session_id)
        turn_result["referenced_books"] = extract_referenced_books(list(session.citations.values()))

        # 4. Secondary Figure Retrieval: Fetch 3-4 matching figure captions for visual evidence
        if "figures" not in turn_result or not turn_result["figures"]:
            clean_query = re.sub(r"[^\w\s-]", " ", user_message).strip()
            try:
                t_fig = time.perf_counter()
                figures = search_figures(
                    query=clean_query,
                    book_slug=book_slug,
                    allowed_books=routed_books or active_books,
                    limit=4,
                )
                telemetry.retrieval_ms = round(telemetry.retrieval_ms + (time.perf_counter() - t_fig) * 1000, 2)
                turn_result["figures"] = figures
            except Exception as e:
                print(f"[AgentOrchestrator] Figure search error: {e}")
                turn_result["figures"] = []

        telemetry.total_ms = round((time.perf_counter() - t_turn) * 1000, 2)
        turn_result["telemetry"] = telemetry.to_dict()
        return turn_result

    def stream_turn(
        self,
        session_id: str,
        user_message: str,
        book_slug: str | None = None,
        active_books: list[str] | None = None,
    ):
        """Streams a conversation turn yielding events: status, tools, token, citations, figures, follow_ups, done."""
        t_turn = time.perf_counter()
        telemetry = TurnTelemetry()
        ttft_recorded = False

        # 1. Add user message to session context
        self.context_manager.add_user_message(session_id, user_message)

        # 2. Conversational greetings & pleasantries
        msg_clean = user_message.strip().lower()
        if re.match(r"^(?:hi|hello|hey|hola|greetings|howdy|good\s+(?:morning|afternoon|evening|day))[\s!.]*$", msg_clean):
            yield {"event": "status", "data": {"text": "Preparing response..."}}
            reply = (
                "Hello! I am your Clinical Tutor and Medical Study Companion.\n\n"
                "I am here to help you study, review clinical cases, and understand complex physiological and anatomical topics grounded directly in medical textbooks.\n\n"
                "You can ask me about:\n"
                "* **Anatomy & Structural Relationships** (e.g., *boundaries and contents of the femoral triangle*, *brachial plexus organization*)\n"
                "* **Endocrinology & Hormone Pathways** (e.g., *functional zonation of the adrenal cortex*, *thyroid hormone synthesis*)\n"
                "* **Physiology & Clinical Pathology** (e.g., *fluid balance in diabetes insipidus*, *mechanisms of hyperaldosteronism*)\n\n"
                "What medical topic would you like to explore today?"
            )
            follow_ups = [
                "Explain the zones of the adrenal cortex and the specific hormones synthesized in each zone.",
                "How is thyroid hormone synthesized and regulated, and what are the main clinical signs of hypothyroidism?",
                "What are the boundaries, contents, and clinical significance of the femoral triangle?"
            ]
            words = reply.split(" ")
            for i, w in enumerate(words):
                if not ttft_recorded:
                    telemetry.ttft_ms = round((time.perf_counter() - t_turn) * 1000, 2)
                    ttft_recorded = True
                yield {"event": "token", "data": {"delta": (w + " ") if i < len(words) - 1 else w}}
                time.sleep(0.01)

            telemetry.provider = "fastpath"
            telemetry.model_used = "fastpath-greeting"
            telemetry.total_ms = round((time.perf_counter() - t_turn) * 1000, 2)
            yield {"event": "referenced_books", "data": []}
            yield {"event": "citations", "data": []}
            yield {"event": "figures", "data": []}
            yield {"event": "follow_ups", "data": follow_ups}
            yield {"event": "done", "data": {"reply": reply, "referenced_books": [], "routed_books": [], "telemetry": telemetry.to_dict()}}
            self.context_manager.add_assistant_message(session_id, reply)
            return

        if re.match(r"^(?:thanks|thank\s+you|awesome|great|cool|ok|okay)[\s!.]*$", msg_clean):
            yield {"event": "status", "data": {"text": "Preparing response..."}}
            reply = (
                "You're very welcome! Feel free to ask whenever you want to explore more clinical mechanisms, review textbook passages, or work through a case study."
            )
            follow_ups = [
                "Explain the regulatory feedback of the hypothalamic-pituitary-adrenal axis",
                "What are the clinical hallmarks of Addison's disease?",
                "How does the renin-angiotensin-aldosterone system regulate arterial pressure?"
            ]
            words = reply.split(" ")
            for i, w in enumerate(words):
                if not ttft_recorded:
                    telemetry.ttft_ms = round((time.perf_counter() - t_turn) * 1000, 2)
                    ttft_recorded = True
                yield {"event": "token", "data": {"delta": (w + " ") if i < len(words) - 1 else w}}
                time.sleep(0.01)

            telemetry.provider = "fastpath"
            telemetry.model_used = "fastpath-gratitude"
            telemetry.total_ms = round((time.perf_counter() - t_turn) * 1000, 2)
            yield {"event": "referenced_books", "data": []}
            yield {"event": "citations", "data": []}
            yield {"event": "figures", "data": []}
            yield {"event": "follow_ups", "data": follow_ups}
            yield {"event": "done", "data": {"reply": reply, "referenced_books": [], "routed_books": [], "telemetry": telemetry.to_dict()}}
            self.context_manager.add_assistant_message(session_id, reply)
            return

        meta_patterns = [
            r"are\s+you\s+(?:using\s+)?(?:a\s+)?(?:google\s+)?(?:llm|ai|gpt|gemini|model|claude|robot|bot)",
            r"who\s+(?:created|made|developed|built)\s+you",
            r"what\s+(?:model|llm|ai)\s+are\s+you",
            r"how\s+do\s+you\s+work",
        ]
        if any(re.search(p, msg_clean) for p in meta_patterns):
            yield {"event": "status", "data": {"text": "Preparing response..."}}
            reply = (
                "I am an AI Clinical Study Companion and Medical Tutor. "
                "I am powered by Google Gemini and equipped with structure-aware retrieval tools to search and cite verified medical textbooks.\n\n"
                "You can ask me questions about human anatomy, physiological mechanisms, endocrinology, and clinical diagnosis."
            )
            follow_ups = [
                "Explain the zones of the adrenal cortex and the specific hormones synthesized in each zone.",
                "How is thyroid hormone synthesized and regulated, and what are the main clinical signs of hypothyroidism?",
                "What are the boundaries, contents, and clinical significance of the femoral triangle?"
            ]
            words = reply.split(" ")
            for i, w in enumerate(words):
                if not ttft_recorded:
                    telemetry.ttft_ms = round((time.perf_counter() - t_turn) * 1000, 2)
                    ttft_recorded = True
                yield {"event": "token", "data": {"delta": (w + " ") if i < len(words) - 1 else w}}
                time.sleep(0.01)

            telemetry.provider = "fastpath"
            telemetry.model_used = "fastpath-meta"
            telemetry.total_ms = round((time.perf_counter() - t_turn) * 1000, 2)
            yield {"event": "referenced_books", "data": []}
            yield {"event": "citations", "data": []}
            yield {"event": "figures", "data": []}
            yield {"event": "follow_ups", "data": follow_ups}
            yield {"event": "done", "data": {"reply": reply, "referenced_books": [], "routed_books": [], "telemetry": telemetry.to_dict()}}
            self.context_manager.add_assistant_message(session_id, reply)
            return

        # 3. Clinical Query: Progressive breadcrumb status
        yield {"event": "status", "data": {"text": "Formulating clinical diagnosis plan..."}}

        t_plan = time.perf_counter()
        plan = self.planner.plan(
            user_message=user_message,
            active_books=active_books,
        )
        telemetry.planner_ms = round((time.perf_counter() - t_plan) * 1000, 2)
        planner_meta = getattr(self.planner, "last_telemetry", None)
        if isinstance(planner_meta, dict):
            telemetry.merge_usage(planner_meta)

        yield {"event": "plan", "data": plan.to_dict()}

        # 4. Semantic Book Routing (User sovereign selection preserved)
        t_route = time.perf_counter()
        routed_books = self.router.route(
            query=user_message,
            plan=plan,
            user_selected_books=active_books,
        )
        telemetry.routing_ms = round((time.perf_counter() - t_route) * 1000, 2)

        yield {"event": "status", "data": {"text": "Searching medical textbooks..."}}

        search_target_queries = plan.search_queries if plan.search_queries else [user_message]
        t_ret = time.perf_counter()
        retrieval = _execute_parallel_retrieval(
            query=search_target_queries,
            book_slug=book_slug,
            allowed_books=routed_books,
            chunk_limit=6,
            section_limit=2,
            figure_limit=4,
        )
        telemetry.retrieval_ms = round((time.perf_counter() - t_ret) * 1000, 2)
        clean_query = retrieval["clean_query"]
        chunks_result = retrieval["chunks"]
        sections_result = retrieval["sections"]
        figures_result = retrieval["figures"]

        tool_call_id_1 = f"call_{uuid.uuid4().hex[:8]}"
        self.context_manager.add_tool_result(
            session_id=session_id,
            tool_call_id=tool_call_id_1,
            name="search_chunks",
            result=chunks_result,
        )

        tool_call_id_2 = f"call_{uuid.uuid4().hex[:8]}"
        self.context_manager.add_tool_result(
            session_id=session_id,
            tool_call_id=tool_call_id_2,
            name="search_sections",
            result=sections_result,
        )

        tool_activity = [
            {
                "name": "search_chunks",
                "query": clean_query,
                "hits": len(chunks_result),
                "summary": f'Searched chunks for "{clean_query}" ({len(chunks_result)} hits)'
            },
            {
                "name": "search_sections",
                "query": clean_query,
                "hits": len(sections_result),
                "summary": f'Searched section outline for "{clean_query}" ({len(sections_result)} sections found)'
            }
        ]

        yield {"event": "tools", "data": tool_activity}
        
        # Parallel Figure Resolution: Emit figures early so UI thumbnail gallery renders while LLM text streams
        if figures_result:
            yield {"event": "figures", "data": figures_result}
            
        yield {"event": "status", "data": {"text": "Synthesizing clinical answer..."}}

        session = self.context_manager.get_or_create_session(session_id)
        current_citations = session.citations
        valid_ids = {c.citation_id for c in current_citations.values()}

        # 4. Stream tokens
        streamed_raw_text = ""
        used_llm_stream = False
        last_stream_error = ""

        if self.gemini_api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.gemini_api_key)
                models = resolve_gemini_candidate_models()

                messages = self.context_manager.assemble_prompt(
                    session_id=session_id,
                    system_prompt=INVARIANT_SYSTEM_PROMPT,
                )
                contents = []
                for m in messages:
                    if m["role"] == "system":
                        continue
                    role = "model" if m["role"] in ["assistant", "model"] else "user"
                    text_content = m["content"]
                    if m["role"] == "tool":
                        text_content = f"[Reference retrieved for {m.get('name', 'tool')}]:\n{text_content}"
                    if contents and contents[-1].role == role:
                        contents[-1].parts.append(types.Part.from_text(text=text_content))
                    else:
                        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text_content)]))

                for model in models:
                    try:
                        t_llm = time.perf_counter()
                        stream_usage: dict[str, int] = {}
                        stream_response = client.models.generate_content_stream(
                            model=model,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=INVARIANT_SYSTEM_PROMPT,
                            ),
                        )
                        for chunk in stream_response:
                            chunk_usage = extract_gemini_usage(chunk)
                            if chunk_usage.get("total_tokens", 0) > 0:
                                stream_usage = chunk_usage
                            if chunk.text:
                                if not ttft_recorded:
                                    telemetry.ttft_ms = round((time.perf_counter() - t_turn) * 1000, 2)
                                    ttft_recorded = True
                                streamed_raw_text += chunk.text
                                yield {"event": "token", "data": {"delta": chunk.text}}
                        if streamed_raw_text:
                            used_llm_stream = True
                            telemetry.provider = "gemini"
                            telemetry.model_used = model
                            telemetry.llm_ms = round((time.perf_counter() - t_llm) * 1000, 2)
                            telemetry.react_iterations = 1
                            telemetry.merge_usage(stream_usage)
                            break
                    except Exception as me:
                        last_stream_error = str(me)
                        print(f"[AgentOrchestrator] Gemini streaming model {model} failed: {me}")
                        continue
            except Exception as e:
                last_stream_error = str(e)
                print(f"[AgentOrchestrator] Gemini streaming setup error: {e}")

        if not used_llm_stream:
            if self.gemini_api_key:
                telemetry.fallback_triggered = True
                telemetry.fallback_reason = last_stream_error or "Gemini streaming returned empty response"
            telemetry.provider = "offline"
            telemetry.model_used = "offline-synthesizer"
            raw_synthesized = self._build_offline_response_text(user_message, chunks_result)
            streamed_raw_text = raw_synthesized
            words = raw_synthesized.split(" ")
            for i in range(0, len(words), 3):
                delta_group = " ".join(words[i:i+3])
                if i + 3 < len(words):
                    delta_group += " "
                if not ttft_recorded:
                    telemetry.ttft_ms = round((time.perf_counter() - t_turn) * 1000, 2)
                    ttft_recorded = True
                yield {"event": "token", "data": {"delta": delta_group}}
                time.sleep(0.015)

        # 5. Sanitize typography and citations, extract follow-ups
        clean_reply = _sanitize_medical_typography(streamed_raw_text)
        clean_reply = _sanitize_citations(clean_reply, valid_ids)
        clean_reply, follow_ups = self._parse_follow_ups(clean_reply)

        self.context_manager.add_assistant_message(session_id, clean_reply)

        referenced_books = extract_referenced_books(list(current_citations.values()))
        telemetry.total_ms = round((time.perf_counter() - t_turn) * 1000, 2)
        yield {"event": "referenced_books", "data": referenced_books}
        yield {"event": "citations", "data": [c.to_dict() for c in current_citations.values()]}
        yield {"event": "figures", "data": figures_result}
        yield {"event": "follow_ups", "data": follow_ups}
        yield {
            "event": "done",
            "data": {
                "reply": clean_reply,
                "referenced_books": referenced_books,
                "routed_books": routed_books,
                "telemetry": telemetry.to_dict(),
            },
        }
