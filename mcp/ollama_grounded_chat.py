#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "llama3.2:1b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_LIMITS = {
    "search_hits": 3,
    "offerings": 5,
    "related_courses": 8,
    "recent_news": 3,
    "links": 5,
}
FULL_LIMITS = {
    "search_hits": 5,
    "offerings": 8,
    "related_courses": 12,
    "recent_news": 5,
    "links": 8,
}
QUESTION_STOPWORDS = {
    "what", "which", "who", "does", "do", "is", "are", "the", "a", "an", "for", "of",
    "current", "upcoming", "associated", "with", "work", "works", "teach", "teaches",
    "faculty", "course", "courses", "related", "on", "in", "or", "and", "to",
}

INTENT_PERSON_RESEARCH = "person_research"
INTENT_PERSON_TEACHING = "person_teaching"
INTENT_TEACHING = "teaching"
INTENT_COURSE_LOOKUP = "course_lookup"
INTENT_PERSON_LOOKUP = "person_lookup"
INTENT_RESEARCH = "research"
INTENT_GENERAL = "general"


class MCPClient:
    def __init__(self, repo_root: Path):
        self.proc = subprocess.Popen(
            [sys.executable, "mcp/server.py"],
            cwd=repo_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._request_id = 0
        self._initialize()

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8") + body)
        self.proc.stdin.flush()

    def _recv(self) -> dict:
        headers = {}
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server exited unexpectedly")
            if line in (b"\r\n", b"\n"):
                break
            key, value = line.decode("utf-8").split(":", 1)
            headers[key.lower()] = value.strip()
        content_length = int(headers["content-length"])
        body = self.proc.stdout.read(content_length)
        return json.loads(body.decode("utf-8"))

    def _request(self, method: str, params: dict | None = None) -> dict:
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": method, "params": params or {}}
        self._send(payload)
        response = self._recv()
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        return response["result"]

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ollama-grounded-chat", "version": "0.1.0"},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call_tool(self, name: str, arguments: dict) -> dict:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        return result.get("structuredContent")


def ollama_generate(model: str, prompt: str, ollama_url: str) -> str:
    request_body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        ollama_url,
        data=request_body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("response", "").strip()
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {ollama_url}. Start it with `ollama serve`."
        ) from exc


def detect_course_code(query: str) -> str | None:
    match = re.search(r"\b([A-Za-z]{2,4})\s?(\d{3}[A-Za-z]?)\b", query)
    if not match:
        return None
    return f"{match.group(1).upper()}{match.group(2).upper()}"


def extract_person_phrase(query: str) -> str | None:
    candidates = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z.\-]+)+)\b", query)
    ignored = {"What", "Which", "Who", "Computer Science", "UMass Boston"}
    filtered = [candidate for candidate in candidates if candidate not in ignored]
    return filtered[0] if filtered else None


def extract_search_terms(query: str) -> list[str]:
    terms: list[str] = []
    if query.strip():
        terms.append(query.strip())

    person_phrase = extract_person_phrase(query)
    if person_phrase:
        terms.append(person_phrase)

    course_code = detect_course_code(query)
    if course_code:
        terms.append(course_code)

    simplified_tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", query)
        if token.lower() not in QUESTION_STOPWORDS
    ]
    if simplified_tokens:
        terms.append(" ".join(simplified_tokens))
        if len(simplified_tokens) > 1:
            terms.extend(simplified_tokens)

    deduped: list[str] = []
    seen = set()
    for term in terms:
        key = term.casefold().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(term)
    return deduped[:6]


def merge_unique_items(items: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen = set()
    for item in items:
        if not item:
            continue
        key = item.get("id") or item.get("slug") or item.get("course_code") or item.get("title")
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def query_mentions_teaching(query: str) -> bool:
    lowered = query.casefold()
    return any(
        token in lowered
        for token in [
            "teach",
            "teaches",
            "teaching",
            "course",
            "courses",
            "offering",
            "offerings",
            "current",
            "upcoming",
            "associated with",
        ]
    )


def query_mentions_research(query: str) -> bool:
    lowered = query.casefold()
    return any(
        token in lowered
        for token in [
            "research",
            "topic",
            "topics",
            "lab",
            "group",
            "publication",
            "publications",
            "profile",
            "work on",
        ]
    )


def detect_query_intent(query: str) -> dict:
    explicit_person = extract_person_phrase(query)
    explicit_course = detect_course_code(query)
    teaching = query_mentions_teaching(query)
    research = query_mentions_research(query)

    if research and explicit_person:
        intent = INTENT_PERSON_RESEARCH
    elif teaching and explicit_person:
        intent = INTENT_PERSON_TEACHING
    elif teaching:
        intent = INTENT_TEACHING
    elif explicit_course:
        intent = INTENT_COURSE_LOOKUP
    elif explicit_person:
        intent = INTENT_PERSON_LOOKUP
    elif research:
        intent = INTENT_RESEARCH
    else:
        intent = INTENT_GENERAL

    return {
        "type": intent,
        "explicit_person": explicit_person,
        "explicit_course": explicit_course,
        "teaching": teaching,
        "research": research,
    }


def fetch_person(mcp: MCPClient, person_key: str | None) -> dict | None:
    if not person_key:
        return None
    result = mcp.call_tool("get_person", {"person_slug_or_name": person_key})
    return result if result else None


def fetch_course_context(mcp: MCPClient, course_code: str | None) -> dict | None:
    if not course_code:
        return None
    result = mcp.call_tool("get_course_context", {"course_code": course_code})
    return result if result else None


def select_teaching_course_codes(raw_context: dict, limit: int) -> list[str]:
    course_codes: list[str] = []
    seen = set()
    for item in (raw_context.get("search_courses") or []) + (raw_context.get("search_site_entities") or []):
        course_code = item.get("course_code")
        if not course_code and item.get("type") == "course":
            title = item.get("title") or ""
            match = re.match(r"([A-Za-z]{2,4}\d{3}[A-Za-z]?)", title.replace(" ", ""))
            if match:
                course_code = match.group(1).upper()
        if not course_code:
            continue
        normalized = course_code.replace(" ", "").upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        course_codes.append(normalized)
        if len(course_codes) >= limit:
            break
    return course_codes


def build_context(mcp: MCPClient, query: str) -> dict:
    intent = detect_query_intent(query)
    search_terms = extract_search_terms(query)
    site_hits = []
    course_hits = []
    people_hits = []
    topic_hits = []

    for term in search_terms:
        site_hits.extend(mcp.call_tool("search_site_entities", {"query": term, "limit": 6}) or [])
        course_hits.extend(mcp.call_tool("search_courses", {"query": term, "limit": 4}) or [])
        people_hits.extend(mcp.call_tool("search_people", {"query": term, "limit": 4}) or [])
        topic_hits.extend(mcp.call_tool("search_faculty_by_topic", {"topic": term, "limit": 4}) or [])

    context = {
        "query": query,
        "intent": intent,
        "search_terms": search_terms,
        "search_site_entities": merge_unique_items(site_hits)[:6],
        "search_courses": merge_unique_items(course_hits)[:4],
        "search_people": merge_unique_items(people_hits)[:4],
        "search_faculty_by_topic": merge_unique_items(topic_hits)[:4],
    }

    course_code = intent["explicit_course"]
    # For TEACHING intent the course is already covered by course_contexts; fetching
    # course_context separately would duplicate the same data in the raw context and
    # the compact/grounded output.  COURSE_LOOKUP (non-teaching) still needs it.
    if course_code and not intent["teaching"]:
        course_context = fetch_course_context(mcp, course_code)
        if course_context:
            context["course_context"] = course_context

    selected_person = fetch_person(mcp, intent["explicit_person"])
    if not selected_person and intent["type"] in {INTENT_PERSON_RESEARCH, INTENT_PERSON_LOOKUP}:
        top_people = context.get("search_people") or []
        if top_people:
            selected_person = fetch_person(mcp, top_people[0].get("slug") or top_people[0].get("title"))

    if selected_person:
        context["person"] = selected_person
        person_key = selected_person.get("slug") or selected_person.get("person_name") or selected_person.get("title")
        if intent["type"] == INTENT_PERSON_TEACHING:
            context["person_teaching_context"] = mcp.call_tool(
                "get_person_teaching_context",
                {"person_slug_or_name": person_key},
            )
        if intent["research"] or intent["type"] == INTENT_PERSON_LOOKUP:
            context["external_profile"] = mcp.call_tool(
                "get_external_faculty_profile",
                {"person_slug_or_name": person_key},
            )

    if intent["teaching"]:
        course_contexts = []
        course_codes = [course_code] if course_code else select_teaching_course_codes(context, 3)
        for code in course_codes:
            fetched = fetch_course_context(mcp, code)
            if fetched:
                course_contexts.append(fetched)
        if course_contexts:
            context["course_contexts"] = course_contexts

    return context


def normalize_items(values) -> list:
    if values is None:
        return []
    if isinstance(values, list):
        return values
    if isinstance(values, tuple):
        return list(values)
    if isinstance(values, dict):
        normalized: list = []
        for value in values.values():
            if isinstance(value, list):
                normalized.extend(value)
            elif isinstance(value, dict):
                normalized.append(value)
            elif value is not None:
                normalized.append(value)
        return normalized
    return [values]


def limit_list(values, limit: int) -> list:
    return normalize_items(values)[:limit]


def compact_offerings(offerings: list[dict] | None, limit: int) -> list[dict]:
    compact: list[dict] = []
    for offering in normalize_items(offerings):
        if not isinstance(offering, dict):
            continue
        if not any(
            offering.get(key)
            for key in ("course_code", "title", "term_label", "instructor", "schedule_summary", "location")
        ):
            continue
        compact.append(
            {
                "course_code": offering.get("course_code"),
                "title": offering.get("title"),
                "term": offering.get("term_label"),
                "section": offering.get("section"),
                "instructor": offering.get("instructor"),
                "schedule": offering.get("schedule_summary"),
                "location": offering.get("location"),
                "url": offering.get("course_url") or offering.get("canonical_url") or offering.get("url"),
            }
        )
        if len(compact) >= limit:
            break
    return compact


def compact_related_courses(courses: list[dict] | None, limit: int) -> list[dict]:
    compact: list[dict] = []
    for course in normalize_items(courses):
        if not isinstance(course, dict):
            continue
        compact.append(
            {
                "course_code": course.get("course_code"),
                "course_name": course.get("course_name"),
                "url": course.get("canonical_url") or course.get("url"),
            }
        )
        if len(compact) >= limit:
            break
    return compact


def compact_search_hits(items: list[dict] | None, limit: int) -> list[dict]:
    compact: list[dict] = []
    for item in limit_list(items, limit):
        compact.append(
            {
                "type": item.get("type"),
                "title": item.get("title"),
                "course_code": item.get("course_code"),
                "slug": item.get("slug"),
                "summary": item.get("summary"),
                "url": item.get("canonical_url") or item.get("url"),
            }
        )
    return compact


def compact_external_profile(profile: dict | None, limits: dict[str, int]) -> dict | None:
    if not profile:
        return None
    first_profile = (profile.get("profiles") or [None])[0]
    if not first_profile:
        return None
    fields = first_profile.get("fields") or {}
    compact: dict = {
        "source_url": first_profile.get("resolved_url") or first_profile.get("url"),
        "last_checked": profile.get("last_checked") or first_profile.get("last_checked"),
        "research_topics": limit_list((fields.get("research_topics") or {}).get("value"), limits["related_courses"]),
        "lab_or_group": (fields.get("lab_or_group") or {}).get("value"),
        "recent_news_titles": limit_list((fields.get("recent_news_titles") or {}).get("value"), limits["recent_news"]),
        "profile_links": limit_list((fields.get("profile_links") or {}).get("value"), limits["links"]),
        "teaching_links": limit_list((fields.get("teaching_links") or {}).get("value"), limits["links"]),
        "external_summary": (fields.get("external_summary") or {}).get("value"),
    }
    return {key: value for key, value in compact.items() if value}


def compact_course_contexts(course_contexts: list[dict] | None, limits: dict[str, int]) -> list[dict]:
    compact: list[dict] = []
    for course_context in normalize_items(course_contexts):
        if not isinstance(course_context, dict):
            continue
        course_record = course_context.get("course") if isinstance(course_context.get("course"), dict) else course_context
        offerings_record = course_context.get("offerings")
        if isinstance(offerings_record, dict) and "offerings" in offerings_record:
            offerings_source = offerings_record.get("offerings")
        else:
            offerings_source = course_context.get("offerings")
        compact.append(
            {
                "course_code": course_record.get("course_code"),
                "title": course_record.get("title") or course_record.get("course_name"),
                "description": course_record.get("description"),
                "instructors": limit_list(course_record.get("instructors"), limits["links"]),
                "offerings": compact_offerings(offerings_source, limits["offerings"]),
                "url": course_record.get("canonical_url") or course_record.get("url"),
            }
        )
        if len(compact) >= limits["search_hits"]:
            break
    return compact


def dedupe_instructors(course_contexts: list[dict] | None, limit: int) -> list[str]:
    instructors: list[str] = []
    seen = set()
    for course_context in course_contexts or []:
        for name in (course_context.get("instructors") or []):
            if not name or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            instructors.append(name)
        for offering in (course_context.get("offerings") or []):
            name = offering.get("instructor")
            if not name or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            instructors.append(name)
        if len(instructors) >= limit:
            break
    return instructors[:limit]


def build_compact_context(raw_context: dict, limits: dict[str, int]) -> dict:
    intent = (raw_context.get("intent") or {}).get("type", INTENT_GENERAL)
    compact = {
        "query": raw_context.get("query"),
        "intent": intent,
    }

    if intent in {INTENT_TEACHING, INTENT_COURSE_LOOKUP}:
        compact["matched_people"] = []
    elif intent in {INTENT_PERSON_RESEARCH, INTENT_PERSON_LOOKUP, INTENT_PERSON_TEACHING}:
        compact["matched_people"] = compact_search_hits(raw_context.get("search_people"), 1)
    else:
        compact["matched_people"] = compact_search_hits(raw_context.get("search_people"), limits["search_hits"])

    if intent in {INTENT_TEACHING, INTENT_COURSE_LOOKUP}:
        compact["matched_courses"] = compact_search_hits(raw_context.get("search_courses"), min(3, limits["search_hits"]))
    else:
        compact["matched_courses"] = []

    person = raw_context.get("person")
    if person:
        # Merge research_areas and related_topics so that faculty who populate only
        # related_topics (not research_areas) still have their topics surfaced in the
        # compact context under a single unified key.  research_areas takes priority.
        # Order-preserving dedup (dict.fromkeys) is used to maintain priority ordering.
        research_areas = list(dict.fromkeys(
            person.get("research_areas", []) + person.get("related_topics", [])
        ))
        compact["person"] = {
            "name": person.get("person_name") or person.get("title"),
            "job_title": person.get("job_title"),
            "summary": person.get("summary"),
            "research_areas": limit_list(research_areas, limits["related_courses"]),
            "url": person.get("canonical_url") or person.get("url"),
        }

    teaching = raw_context.get("person_teaching_context")
    if teaching:
        compact["person_teaching_context"] = {
            "person_name": teaching.get("person_name"),
            "related_courses": compact_related_courses(teaching.get("related_courses"), limits["related_courses"]),
            "offerings": compact_offerings(teaching.get("offerings"), limits["offerings"]),
        }

    course_context = raw_context.get("course_context")
    if course_context:
        # get_course_context() returns {"course": {...}, "offerings": {...}, "relationships": {...}}.
        # Flat dicts (legacy callers or direct dict construction) are also accepted as a fallback.
        # The "offerings" value is itself a dict with an inner "offerings" list, so unwrap it.
        course_inner = course_context.get("course")
        course_record = course_inner if isinstance(course_inner, dict) else course_context
        offerings_record = course_context.get("offerings")
        if isinstance(offerings_record, dict) and "offerings" in offerings_record:
            offerings_source = offerings_record.get("offerings")
        else:
            offerings_source = offerings_record
        compact["course_context"] = {
            "course_code": course_record.get("course_code"),
            "title": course_record.get("title") or course_record.get("course_name"),
            "description": course_record.get("description"),
            "instructors": limit_list(course_record.get("instructors"), limits["links"]),
            "offerings": compact_offerings(offerings_source, limits["offerings"]),
            "url": course_record.get("canonical_url") or course_record.get("url"),
        }

    course_contexts = compact_course_contexts(raw_context.get("course_contexts"), limits)
    if course_contexts:
        compact["course_contexts"] = course_contexts
        compact["teaching_instructors"] = dedupe_instructors(course_contexts, limits["links"])

    external_profile = compact_external_profile(raw_context.get("external_profile"), limits)
    if external_profile:
        compact["external_profile"] = external_profile

    faculty_topics = []
    faculty_topic_limit = 1 if intent == INTENT_PERSON_RESEARCH else limits["search_hits"]
    for person_hit in limit_list(raw_context.get("search_faculty_by_topic"), faculty_topic_limit):
        faculty_topics.append(
            {
                "name": person_hit.get("title"),
                "matching_topics": limit_list(person_hit.get("matching_topics"), 5),
                "url": person_hit.get("canonical_url") or person_hit.get("url"),
            }
        )
    if faculty_topics and intent not in {INTENT_TEACHING, INTENT_PERSON_TEACHING, INTENT_PERSON_RESEARCH, INTENT_COURSE_LOOKUP}:
        compact["faculty_topic_matches"] = faculty_topics

    if intent == INTENT_RESEARCH:
        group_hits = [
            h for h in (raw_context.get("search_site_entities") or [])
            if h.get("type") == "group"
        ]
        if group_hits:
            compact["matched_groups"] = [
                {
                    "name": h.get("title"),
                    "lead_people": h.get("lead_people") or [],
                    "member_people": h.get("member_people") or [],
                    "related_topics": h.get("related_topics") or [],
                    "url": h.get("canonical_url") or h.get("url"),
                }
                for h in group_hits[:limits["search_hits"]]
            ]

    return compact


def build_grounding_block(compact_context: dict) -> str:
    intent = compact_context.get("intent", INTENT_GENERAL)
    lines = ["Grounded facts:"]
    has_explicit_research_signal = False

    person = compact_context.get("person")
    if person:
        lines.append(
            f"- Matched person: {person.get('name')}"
            + (f" ({person.get('job_title')})" if person.get("job_title") else "")
            + (f" - {person.get('summary')}" if person.get("summary") else "")
        )
        if person.get("research_areas"):
            lines.append(f"- Internal research areas: {', '.join(person['research_areas'])}")
            has_explicit_research_signal = True
        if person.get("url"):
            lines.append(f"- Internal page: {person['url']}")

    teaching = compact_context.get("person_teaching_context")
    if teaching:
        if teaching.get("related_courses"):
            course_labels = []
            for course in teaching["related_courses"]:
                label = course.get("course_code") or ""
                if course.get("course_name"):
                    label = f"{label}: {course['course_name']}" if label else course["course_name"]
                if course.get("url"):
                    label += f" [{course['url']}]"
                course_labels.append(label)
            lines.append("- Related internal courses: " + "; ".join(course_labels))
        if teaching.get("offerings"):
            lines.append("- Current/upcoming offerings:")
            for offering in teaching["offerings"]:
                offering_line = f"  - {offering.get('course_code')}: {offering.get('title')}"
                details = [
                    offering.get("term"),
                    f"section {offering.get('section')}" if offering.get("section") else None,
                    offering.get("schedule"),
                    offering.get("location"),
                ]
                details = [detail for detail in details if detail]
                if details:
                    offering_line += f" ({'; '.join(details)})"
                if offering.get("url"):
                    offering_line += f" [{offering['url']}]"
                lines.append(offering_line)

    course_context = compact_context.get("course_context")
    if course_context:
        lines.append(f"- Matched course: {course_context.get('title')}")
        if course_context.get("description"):
            lines.append(f"- Course description: {course_context['description']}")
        if course_context.get("instructors"):
            lines.append(f"- Instructors: {', '.join(course_context['instructors'])}")

    course_contexts = compact_context.get("course_contexts")
    if course_contexts and intent in {INTENT_TEACHING, INTENT_COURSE_LOOKUP}:
        lines.append("- Matched course offerings:")
        for course in course_contexts:
            line = f"  - {course.get('title')}"
            if course.get("instructors"):
                line += f" | instructors: {', '.join(course['instructors'])}"
            if course.get("url"):
                line += f" [{course['url']}]"
            lines.append(line)
            if course.get("description"):
                lines.append(f"    Description: {course['description']}")
            for offering in course.get("offerings") or []:
                offering_line = f"    - {offering.get('term')}: {offering.get('instructor')}"
                details = [
                    f"section {offering.get('section')}" if offering.get("section") else None,
                    offering.get("schedule"),
                    offering.get("location"),
                ]
                details = [detail for detail in details if detail]
                if details:
                    offering_line += f" ({'; '.join(details)})"
                lines.append(offering_line)

    teaching_instructors = compact_context.get("teaching_instructors")
    if teaching_instructors and intent in {INTENT_TEACHING, INTENT_COURSE_LOOKUP}:
        lines.append(f"- Instructors found in current/upcoming offerings: {', '.join(teaching_instructors)}")

    matched_groups = compact_context.get("matched_groups")
    if matched_groups:
        for group in matched_groups:
            group_line = f"- Research group: {group.get('name')}"
            if group.get("lead_people"):
                group_line += f" | director(s): {', '.join(group['lead_people'])}"
            if group.get("member_people"):
                group_line += f" | members: {', '.join(group['member_people'])}"
            if group.get("url"):
                group_line += f" [{group['url']}]"
            lines.append(group_line)
            if group.get("related_topics"):
                lines.append(f"  - Group research topics: {', '.join(group['related_topics'])}")

    faculty_topic_matches = compact_context.get("faculty_topic_matches")
    if faculty_topic_matches:
        lines.append("- Faculty topic matches:")
        for match in faculty_topic_matches:
            topics = ", ".join(match.get("matching_topics") or [])
            lines.append(f"  - {match.get('name')}: {topics}")

    external = compact_context.get("external_profile")
    if external:
        if external.get("external_summary"):
            lines.append(f"- External summary: {external['external_summary']}")
        if external.get("research_topics"):
            lines.append(f"- External research topics: {', '.join(external['research_topics'])}")
            has_explicit_research_signal = True
        if external.get("lab_or_group"):
            lines.append(f"- External lab/group: {external['lab_or_group']}")
            has_explicit_research_signal = True
        if external.get("recent_news_titles"):
            lines.append(f"- External recent news: {', '.join(external['recent_news_titles'])}")
        if external.get("source_url"):
            lines.append(f"- External source: {external['source_url']}")
        if intent == INTENT_PERSON_RESEARCH and not (
            external.get("external_summary")
            or external.get("research_topics")
            or external.get("lab_or_group")
            or external.get("recent_news_titles")
        ):
            lines.append("- External profile found, but no explicit research-topic fields were extracted.")

    matched_courses = compact_context.get("matched_courses")
    if matched_courses and intent not in {INTENT_PERSON_RESEARCH, INTENT_PERSON_LOOKUP, INTENT_PERSON_TEACHING}:
        lines.append("- Relevant course matches:")
        for course in matched_courses:
            course_line = f"  - {course.get('title')}"
            if course.get("url"):
                course_line += f" [{course['url']}]"
            lines.append(course_line)

    matched_people = compact_context.get("matched_people")
    if matched_people and not person and intent not in {INTENT_TEACHING, INTENT_COURSE_LOOKUP}:
        lines.append("- Relevant people matches:")
        for person_hit in matched_people:
            person_line = f"  - {person_hit.get('title')}"
            if person_hit.get("summary"):
                person_line += f": {person_hit['summary']}"
            if person_hit.get("url"):
                person_line += f" [{person_hit['url']}]"
            lines.append(person_line)

    if intent == INTENT_PERSON_RESEARCH and not has_explicit_research_signal:
        lines.append("- Grounded research topics: not specified in the available internal or supplemental profile data.")

    return "\n".join(lines)


def build_prompt(query: str, compact_context: dict) -> str:
    instructions = (
        "You are answering questions about the UMass Boston Computer Science website. "
        "Use only the grounded facts below. "
        "Treat internal repo data as authoritative. "
        "Treat external profile data as supplemental only. "
        "If the answer is uncertain, say so briefly. "
        "When possible, mention relevant internal page URLs. "
        "Answer concisely and prioritize directly relevant facts over completeness. "
        "For teaching questions, answer from current/upcoming offering and instructor evidence first. "
        "For person research questions, answer from the matched person and supplemental external profile data first. "
        "Do not use outside knowledge. If the grounded facts include a line saying research topics are not specified, say exactly that in substance and do not infer topics."
    )
    grounding_block = build_grounding_block(compact_context)
    return (
        f"{instructions}\n\n"
        f"Question:\n{query}\n\n"
        f"{grounding_block}\n\n"
        "Answer:"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ground a local Ollama model with the CS website MCP.")
    parser.add_argument("query", help="Natural-language question to ask.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama generate endpoint URL.")
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Print both raw MCP context and the compact prompt context before the model answer.",
    )
    parser.add_argument(
        "--context-only",
        action="store_true",
        help="Print retrieved MCP context and exit without calling Ollama.",
    )
    parser.add_argument(
        "--small-model",
        dest="small_model",
        action="store_true",
        default=True,
        help="Use aggressively trimmed grounding context for small local models (default).",
    )
    parser.add_argument(
        "--no-small-model",
        dest="small_model",
        action="store_false",
        help="Use slightly larger grounding limits.",
    )
    args = parser.parse_args()

    mcp = MCPClient(REPO_ROOT)
    try:
        raw_context = build_context(mcp, args.query)
        limits = DEFAULT_LIMITS if args.small_model else FULL_LIMITS
        compact_context = build_compact_context(raw_context, limits)
        if args.show_context:
            print(f"Selected query intent: {compact_context.get('intent')}\n")
            print("---\n")
            print("Raw MCP context:\n")
            print(json.dumps(raw_context, indent=2, ensure_ascii=False))
            print("\n---\n")
            print("Compact prompt context:\n")
            print(json.dumps(compact_context, indent=2, ensure_ascii=False))
            print("\n---\n")
        if args.context_only:
            if not args.show_context:
                print(json.dumps(raw_context, indent=2, ensure_ascii=False))
                print("\n---\n")
                print(json.dumps(compact_context, indent=2, ensure_ascii=False))
            return 0
        prompt = build_prompt(args.query, compact_context)
        answer = ollama_generate(args.model, prompt, args.ollama_url)
        print(answer)
        return 0
    finally:
        mcp.close()


if __name__ == "__main__":
    raise SystemExit(main())
