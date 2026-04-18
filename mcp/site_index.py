from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://www.cs.umb.edu"


def collapse_whitespace(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_text(value: str | None) -> str:
    value = collapse_whitespace(value).casefold()
    value = re.sub(r"[.,;:()/_-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_course_code(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "").upper())


def tokens_for_name(value: str | None) -> tuple[str, ...]:
    normalized = normalize_text(value)
    if not normalized:
        return ()
    parts = [part for part in normalized.replace(",", " ").split() if part]
    return tuple(sorted(parts))


def strip_markdown(text: str) -> str:
    text = re.sub(r"{%.*?%}", " ", text, flags=re.S)
    text = re.sub(r"{{.*?}}", " ", text, flags=re.S)
    text = re.sub(r"`{1,3}.*?`{1,3}", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^[#>*\-+]+\s*", "", text, flags=re.M)
    return collapse_whitespace(text)


def parse_front_matter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, text
    front_matter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    return (yaml.safe_load(front_matter) or {}), body


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def excerpt(text: str, length: int = 220) -> str:
    text = collapse_whitespace(text)
    if len(text) <= length:
        return text
    return text[: length - 1].rsplit(" ", 1)[0] + "…"


def entity_url(permalink: str | None) -> str | None:
    if not permalink:
        return None
    return permalink if permalink.startswith("/") else f"/{permalink}"


@dataclass
class EntityMatch:
    entity_type: str
    score: int
    data: dict[str, Any]


class SiteIndex:
    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or REPO_ROOT
        self.data_dir = self.repo_root / "_data"
        self.people_dir = self.repo_root / "_people"
        self.groups_dir = self.repo_root / "_groups"
        self.courses_dir = self.repo_root / "WEB" / "academics" / "courses"
        self.web_dir = self.repo_root / "WEB"

        self.menu = self._load_yaml("menu.yml")
        self.section_indexes = self._load_yaml("section_indexes.yml")
        self.course_offerings = self._load_yaml("course_offerings.yml")
        self.external_profiles = self._load_yaml("external_faculty_profiles.yml")

        self.people = self._load_people()
        self.groups = self._load_groups()
        self.courses = self._load_courses()
        self.pages = self._load_pages()
        self.posts = self._load_posts()

        self.people_by_slug = {item["slug"]: item for item in self.people}
        self.groups_by_slug = {item["slug"]: item for item in self.groups}
        self.courses_by_code = {item["course_code"]: item for item in self.courses}
        self.programs = [page for page in self.pages if page.get("entity_type") == "program"]
        self.programs_by_slug = {item["slug"]: item for item in self.programs}

        self._person_name_map = self._build_person_name_map()
        self._course_alias_map = self._build_course_alias_map()
        self._program_alias_map = self._build_program_alias_map()
        self._group_alias_map = self._build_group_alias_map()
        self._person_group_map = self._build_person_group_map()

    def _format_external_profiles(self, person: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        formatted_profiles = []
        for entry in profile.get("profiles", []):
            fields = entry.get("fields", {}) or {}
            formatted = dict(entry)
            formatted["supplemental"] = True
            formatted["authority"] = "supplemental_external_profile"
            formatted["extracted_field_names"] = list(fields.keys())
            formatted_profiles.append(formatted)
        return {
            "slug": person["slug"],
            "person_name": person["person_name"],
            "supplemental": True,
            "authority": "supplemental_external_profile",
            "profiles": formatted_profiles,
            "source_urls": profile.get("source_urls", []),
            "last_checked": self.external_profiles.get("last_checked"),
            "generated_at": self.external_profiles.get("generated_at"),
        }

    def _load_yaml(self, name: str) -> Any:
        path = self.data_dir / name
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _base_entity(self, path: Path, front_matter: dict[str, Any], body: str) -> dict[str, Any]:
        permalink = entity_url(front_matter.get("permalink"))
        aliases = [collapse_whitespace(alias) for alias in ensure_list(front_matter.get("aliases")) if collapse_whitespace(alias)]
        keywords = [collapse_whitespace(keyword) for keyword in ensure_list(front_matter.get("keywords")) if collapse_whitespace(keyword)]
        summary = collapse_whitespace(front_matter.get("summary"))
        description = collapse_whitespace(front_matter.get("description"))
        body_text = strip_markdown(body)
        return {
            "source_path": str(path.relative_to(self.repo_root)),
            "title": collapse_whitespace(front_matter.get("title")),
            "summary": summary or None,
            "description": description or None,
            "keywords": keywords,
            "aliases": aliases,
            "permalink": permalink,
            "canonical_url": f"{SITE_URL}{permalink}" if permalink else None,
            "content_excerpt": excerpt(body_text, 260) if body_text else None,
            "entity_type": front_matter.get("entity_type") or "page",
            "raw_front_matter": front_matter,
        }

    def _load_people(self) -> list[dict[str, Any]]:
        people = []
        for path in sorted(self.people_dir.glob("*.md")):
            front_matter, body = parse_front_matter(path)
            if not front_matter:
                continue
            entity = self._base_entity(path, front_matter, body)
            slug = path.stem
            entity.update(
                {
                    "slug": slug,
                    "person_name": collapse_whitespace(front_matter.get("person_name") or front_matter.get("title") or slug),
                    "job_title": collapse_whitespace(front_matter.get("job_title")) or None,
                    "email": collapse_whitespace(front_matter.get("email")) or None,
                    "office": collapse_whitespace(front_matter.get("office")) or None,
                    "telephone": collapse_whitespace(front_matter.get("telephone")) or None,
                    "same_as": [collapse_whitespace(url) for url in ensure_list(front_matter.get("same_as")) if collapse_whitespace(url)],
                    "research_areas": [collapse_whitespace(value) for value in ensure_list(front_matter.get("research_areas")) if collapse_whitespace(value)],
                    "related_topics": [collapse_whitespace(value) for value in ensure_list(front_matter.get("related_topics")) if collapse_whitespace(value)],
                    "related_groups": [collapse_whitespace(value) for value in ensure_list(front_matter.get("related_groups")) if collapse_whitespace(value)],
                    "related_courses": [normalize_course_code(value) for value in ensure_list(front_matter.get("related_courses")) if collapse_whitespace(value)],
                }
            )
            people.append(entity)
        return people

    def _load_groups(self) -> list[dict[str, Any]]:
        groups = []
        for path in sorted(self.groups_dir.glob("*.md")):
            front_matter, body = parse_front_matter(path)
            if not front_matter:
                continue
            entity = self._base_entity(path, front_matter, body)
            entity.update(
                {
                    "slug": path.stem,
                    "group_name": collapse_whitespace(front_matter.get("group_name") or front_matter.get("title") or path.stem),
                    "lead_people": [collapse_whitespace(value) for value in ensure_list(front_matter.get("lead_people")) if collapse_whitespace(value)],
                    "member_people": [collapse_whitespace(value) for value in ensure_list(front_matter.get("member_people")) if collapse_whitespace(value)],
                    "related_topics": [collapse_whitespace(value) for value in ensure_list(front_matter.get("related_topics")) if collapse_whitespace(value)],
                }
            )
            groups.append(entity)
        return groups

    def _load_courses(self) -> list[dict[str, Any]]:
        courses = []
        for path in sorted(self.courses_dir.glob("*.markdown")):
            front_matter, body = parse_front_matter(path)
            if not front_matter or not front_matter.get("course_code"):
                continue
            entity = self._base_entity(path, front_matter, body)
            entity.update(
                {
                    "slug": path.stem,
                    "course_code": normalize_course_code(front_matter.get("course_code")),
                    "course_name": collapse_whitespace(front_matter.get("course_name")) or None,
                    "credits": front_matter.get("credits"),
                    "prerequisites": [collapse_whitespace(value) for value in ensure_list(front_matter.get("prerequisites")) if collapse_whitespace(value)],
                    "co_requisites": [collapse_whitespace(value) for value in ensure_list(front_matter.get("co_requisites")) if collapse_whitespace(value)],
                    "related_programs": [collapse_whitespace(value) for value in ensure_list(front_matter.get("related_programs")) if collapse_whitespace(value)],
                    "related_topics": [collapse_whitespace(value) for value in ensure_list(front_matter.get("related_topics")) if collapse_whitespace(value)],
                }
            )
            courses.append(entity)
        return courses

    def _load_pages(self) -> list[dict[str, Any]]:
        pages = []
        for path in sorted(self.web_dir.rglob("*.markdown")):
            if "academics/courses" in path.as_posix() or "/POSTS/" in path.as_posix() or path.name == "course-catalog.markdown":
                continue
            front_matter, body = parse_front_matter(path)
            if not front_matter:
                continue
            entity = self._base_entity(path, front_matter, body)
            slug = collapse_whitespace(front_matter.get("permalink") or path.stem).strip("/") or path.stem
            entity.update(
                {
                    "slug": slug.split("/")[-1],
                    "program_name": collapse_whitespace(front_matter.get("program_name")) or None,
                    "related_people": [collapse_whitespace(value) for value in ensure_list(front_matter.get("related_people")) if collapse_whitespace(value)],
                    "related_courses": [normalize_course_code(value) for value in ensure_list(front_matter.get("related_courses")) if collapse_whitespace(value)],
                    "related_topics": [collapse_whitespace(value) for value in ensure_list(front_matter.get("related_topics")) if collapse_whitespace(value)],
                    "same_as": [collapse_whitespace(value) for value in ensure_list(front_matter.get("same_as")) if collapse_whitespace(value)],
                }
            )
            pages.append(entity)
        return pages

    def _load_posts(self) -> list[dict[str, Any]]:
        posts = []
        posts_root = self.web_dir / "POSTS"
        for path in sorted(posts_root.rglob("*.md")):
            front_matter, body = parse_front_matter(path)
            if not front_matter:
                continue
            entity = self._base_entity(path, front_matter, body)
            entity.update(
                {
                    "slug": path.stem,
                    "date": collapse_whitespace(str(front_matter.get("date") or "")) or self._date_from_filename(path.name),
                    "category": self._category_from_path(path),
                }
            )
            posts.append(entity)
        posts.sort(key=lambda item: item.get("date") or "", reverse=True)
        return posts

    def _date_from_filename(self, filename: str) -> str | None:
        match = re.match(r"(\d{4}-\d{2}-\d{2})-", filename)
        return match.group(1) if match else None

    def _category_from_path(self, path: Path) -> str | None:
        parts = path.parts
        if "_posts" in parts:
            idx = parts.index("_posts")
            if idx > 0:
                return parts[idx - 1].lower()
        return None

    def _build_person_name_map(self) -> dict[str, list[dict[str, Any]]]:
        mapping: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for person in self.people:
            seen_keys: set[str] = set()
            candidates = [person["slug"], person["person_name"], person["title"], *person["aliases"]]
            for candidate in candidates:
                normalized = normalize_text(candidate)
                if normalized and normalized not in seen_keys:
                    mapping[normalized].append(person)
                    seen_keys.add(normalized)
                name_tokens = tokens_for_name(candidate)
                token_key = "__TOKENS__:" + " ".join(name_tokens)
                if name_tokens and token_key not in seen_keys:
                    mapping[token_key].append(person)
                    seen_keys.add(token_key)
        return mapping

    def _build_course_alias_map(self) -> dict[str, dict[str, Any]]:
        mapping: dict[str, dict[str, Any]] = {}
        for course in self.courses:
            candidates = [course["course_code"], course["title"], course["course_name"], *course["aliases"]]
            for candidate in candidates:
                if not candidate:
                    continue
                mapping[normalize_text(candidate)] = course
                code = normalize_course_code(candidate)
                if code and re.match(r"^[A-Z]+[0-9]", code):
                    mapping[code] = course
        return mapping

    def _build_program_alias_map(self) -> dict[str, dict[str, Any]]:
        mapping: dict[str, dict[str, Any]] = {}
        for program in self.programs:
            candidates = [program["slug"], program["title"], program.get("program_name"), *program["aliases"]]
            for candidate in candidates:
                normalized = normalize_text(candidate)
                if normalized:
                    mapping[normalized] = program
        return mapping

    def _build_group_alias_map(self) -> dict[str, dict[str, Any]]:
        mapping: dict[str, dict[str, Any]] = {}
        for group in self.groups:
            candidates = [group["slug"], group["title"], group.get("group_name"), *group["aliases"]]
            for candidate in candidates:
                normalized = normalize_text(candidate)
                if normalized:
                    mapping[normalized] = group
        return mapping

    def _build_person_group_map(self) -> dict[str, list[dict[str, Any]]]:
        """Build reverse index: person slug → list of groups they lead or belong to."""
        mapping: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for group in self.groups:
            for slug in group.get("lead_people", []) + group.get("member_people", []):
                if slug:
                    mapping[slug].append(group)
        return dict(mapping)

    def _entity_brief(self, entity_type: str, entity: dict[str, Any]) -> dict[str, Any]:
        result = {
            "type": entity_type,
            "title": entity.get("title") or entity.get("person_name") or entity.get("group_name"),
            "url": entity.get("permalink"),
            "canonical_url": entity.get("canonical_url"),
            "summary": entity.get("summary") or entity.get("description") or entity.get("content_excerpt"),
        }
        if entity_type == "course":
            result["course_code"] = entity.get("course_code")
            result["course_name"] = entity.get("course_name")
        if entity_type == "person":
            result["slug"] = entity.get("slug")
            result["job_title"] = entity.get("job_title")
        if entity_type == "program":
            result["slug"] = entity.get("slug")
        if entity_type == "group":
            result["slug"] = entity.get("slug")
        return result

    def match_course(self, query: str) -> dict[str, Any] | None:
        normalized_code = normalize_course_code(query)
        if normalized_code in self._course_alias_map:
            return self._course_alias_map[normalized_code]
        return self._course_alias_map.get(normalize_text(query))

    def match_person(self, query: str) -> dict[str, Any] | None:
        normalized = normalize_text(query)
        if normalized in self._person_name_map:
            candidates = self._unique_people(self._person_name_map[normalized])
            return candidates[0] if len(candidates) == 1 else None
        token_key = "__TOKENS__:" + " ".join(tokens_for_name(query))
        candidates = self._unique_people(self._person_name_map.get(token_key, []))
        return candidates[0] if len(candidates) == 1 else None

    def _unique_people(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for person in candidates:
            slug = person["slug"]
            if slug in seen:
                continue
            seen.add(slug)
            unique.append(person)
        return unique

    def match_program(self, query: str) -> dict[str, Any] | None:
        return self._program_alias_map.get(normalize_text(query))

    def match_group(self, query: str) -> dict[str, Any] | None:
        return self._group_alias_map.get(normalize_text(query))

    def search_courses(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        normalized = normalize_text(query)
        normalized_code = normalize_course_code(query)
        results: list[EntityMatch] = []
        for course in self.courses:
            score = 0
            haystacks = [
                course["title"],
                course.get("course_name"),
                course.get("description"),
                course.get("summary"),
                course.get("content_excerpt"),
                " ".join(course.get("keywords", [])),
                " ".join(course.get("aliases", [])),
                " ".join(course.get("related_topics", [])),
            ]
            if course["course_code"] == normalized_code:
                score += 100
            elif normalized_code and normalized_code in course["course_code"]:
                score += 40
            for value in haystacks:
                hay = normalize_text(value)
                if not hay:
                    continue
                if hay == normalized:
                    score += 50
                elif normalized and normalized in hay:
                    score += 15
            if score > 0:
                results.append(EntityMatch("course", score, course))
        results.sort(key=lambda item: (-item.score, item.data["course_code"]))
        return [self._entity_brief("course", match.data) for match in results[:limit]]

    def search_people(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        normalized = normalize_text(query)
        token_key = tokens_for_name(query)
        results: list[EntityMatch] = []
        for person in self.people:
            score = 0
            candidates = [
                person["person_name"],
                person["title"],
                person.get("job_title"),
                person.get("summary"),
                person.get("content_excerpt"),
                " ".join(person.get("keywords", [])),
                " ".join(person.get("aliases", [])),
                " ".join(person.get("research_areas", [])),
                " ".join(person.get("related_topics", [])),
            ]
            if normalize_text(person["slug"]) == normalized:
                score += 80
            if tokens_for_name(person["person_name"]) == token_key and token_key:
                score += 70
            for value in candidates:
                hay = normalize_text(value)
                if not hay:
                    continue
                if hay == normalized:
                    score += 40
                elif normalized and normalized in hay:
                    score += 12
            ext = self.get_external_faculty_profile(person["slug"])
            if ext:
                profile_blob = normalize_text(json.dumps(ext, sort_keys=True))
                if normalized and normalized in profile_blob:
                    score += 8
            for group in self._person_group_map.get(person["slug"], []):
                group_haystacks = [
                    group.get("group_name"),
                    group.get("title"),
                    " ".join(group.get("aliases", [])),
                    " ".join(group.get("related_topics", [])),
                ]
                for value in group_haystacks:
                    hay = normalize_text(value)
                    if not hay:
                        continue
                    if hay == normalized:
                        score += 20
                    elif normalized and normalized in hay:
                        score += 8
            if score > 0:
                results.append(EntityMatch("person", score, person))
        results.sort(key=lambda item: (-item.score, item.data["person_name"]))
        return [self._entity_brief("person", match.data) for match in results[:limit]]

    def search_faculty_by_topic(self, topic: str, limit: int = 10) -> list[dict[str, Any]]:
        normalized = normalize_text(topic)
        results: list[EntityMatch] = []
        for person in self.people:
            score = 0
            evidence: list[str] = []
            topics = person.get("research_areas", []) + person.get("related_topics", [])
            # Note: keywords are intentionally excluded here. Keywords include person names,
            # job titles, and institution names which should not score as research-topic matches.
            for value in topics:
                hay = normalize_text(value)
                if not hay:
                    continue
                if hay == normalized:
                    score += 40
                    evidence.append(value)
                elif normalized and normalized in hay:
                    score += 15
                    evidence.append(value)
            for group in self._person_group_map.get(person["slug"], []):
                for value in group.get("related_topics", []):
                    hay = normalize_text(value)
                    if not hay:
                        continue
                    if hay == normalized:
                        score += 25
                        evidence.append(value)
                    elif normalized and normalized in hay:
                        score += 8
                        evidence.append(value)
            ext = self.get_external_faculty_profile(person["slug"])
            if ext:
                for profile in ext.get("profiles", []):
                    fields = profile.get("fields", {})
                    research = fields.get("research_topics", {}).get("value", [])
                    for value in research:
                        hay = normalize_text(value)
                        if hay == normalized:
                            score += 30
                            evidence.append(value)
                        elif normalized and normalized in hay:
                            score += 10
                            evidence.append(value)
            if score > 0:
                payload = self._entity_brief("person", person)
                payload["matching_topics"] = list(dict.fromkeys(evidence))[:8]
                results.append(EntityMatch("person", score, payload))
        results.sort(key=lambda item: (-item.score, item.data["title"]))
        return [match.data for match in results[:limit]]

    def search_site_entities(self, query: str, limit: int = 15) -> list[dict[str, Any]]:
        normalized = normalize_text(query)
        matches: list[EntityMatch] = []
        for entity_type, entities, identity_key in (
            ("course", self.courses, "course_code"),
            ("person", self.people, "person_name"),
            ("program", self.programs, "title"),
            ("group", self.groups, "group_name"),
            ("page", self.pages, "title"),
        ):
            for entity in entities:
                score = 0
                candidates = [
                    entity.get("title"),
                    entity.get("summary"),
                    entity.get("description"),
                    entity.get("content_excerpt"),
                    " ".join(entity.get("keywords", [])),
                    " ".join(entity.get("aliases", [])),
                    " ".join(entity.get("related_topics", [])),
                ]
                primary = normalize_text(entity.get(identity_key) or entity.get("slug"))
                if primary == normalized:
                    score += 50
                for value in candidates:
                    hay = normalize_text(value)
                    if not hay:
                        continue
                    if hay == normalized:
                        score += 30
                    elif normalized and normalized in hay:
                        score += 8
                if score > 0:
                    matches.append(EntityMatch(entity_type, score, entity))
        matches.sort(key=lambda item: (-item.score, item.entity_type, item.data.get("title") or ""))
        return [self._entity_brief(match.entity_type, match.data) for match in matches[:limit]]

    def get_course(self, course_code: str) -> dict[str, Any] | None:
        course = self.match_course(course_code)
        if not course:
            return None
        result = {
            "course_code": course["course_code"],
            "course_name": course.get("course_name"),
            "title": course["title"],
            "url": course.get("permalink"),
            "canonical_url": course.get("canonical_url"),
            "description": course.get("description"),
            "summary": course.get("summary"),
            "credits": course.get("credits"),
            "keywords": course.get("keywords", []),
            "aliases": course.get("aliases", []),
            "prerequisites": course.get("prerequisites", []),
            "co_requisites": course.get("co_requisites", []),
            "related_topics": course.get("related_topics", []),
            "related_programs": course.get("related_programs", []),
        }
        course_rel = self.course_offerings.get("relationships", {}).get("courses", {}).get(course["course_code"], {})
        if course_rel:
            result["related_people"] = course_rel.get("related_people_entries", [])
        return result

    def get_course_offerings(self, course_code: str) -> dict[str, Any] | None:
        course = self.match_course(course_code)
        if not course:
            return None
        offerings = self.course_offerings.get("course_index", {}).get(course["course_code"], [])
        terms: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for offering in offerings:
            terms[offering["term_label"]].append(offering)
        return {
            "course_code": course["course_code"],
            "course_name": course.get("course_name"),
            "url": course.get("permalink"),
            "current_academic_year": self.course_offerings.get("current_academic_year"),
            "offerings": offerings,
            "offerings_by_term": dict(terms),
        }

    def get_person(self, person_slug_or_name: str) -> dict[str, Any] | None:
        person = self.match_person(person_slug_or_name)
        if not person:
            return None
        result = {
            "slug": person["slug"],
            "person_name": person["person_name"],
            "title": person["title"],
            "job_title": person.get("job_title"),
            "url": person.get("permalink"),
            "canonical_url": person.get("canonical_url"),
            "summary": person.get("summary"),
            "email": person.get("email"),
            "office": person.get("office"),
            "telephone": person.get("telephone"),
            "keywords": person.get("keywords", []),
            "aliases": person.get("aliases", []),
            "research_areas": person.get("research_areas", []),
            "related_topics": person.get("related_topics", []),
            "same_as": person.get("same_as", []),
        }
        external = self.get_external_faculty_profile(person["slug"])
        if external:
            result["external_profiles"] = external
        return result

    def get_person_related_courses(self, person_slug_or_name: str) -> dict[str, Any] | None:
        person = self.match_person(person_slug_or_name)
        if not person:
            return None
        rel = self.course_offerings.get("relationships", {}).get("people", {}).get(person["slug"], {})
        return {
            "slug": person["slug"],
            "person_name": person["person_name"],
            "related_courses": rel.get("related_course_entries", []),
            "current_academic_year": self.course_offerings.get("current_academic_year"),
        }

    def get_external_faculty_profile(self, person_slug_or_name: str) -> dict[str, Any] | None:
        person = self.match_person(person_slug_or_name)
        if not person:
            return None
        external_people = self.external_profiles.get("people", {})
        profile = external_people.get(person["slug"])
        if not profile:
            return None
        return self._format_external_profiles(person, profile)

    def get_program(self, program_slug_or_name: str) -> dict[str, Any] | None:
        program = self.match_program(program_slug_or_name)
        if not program:
            return None
        return {
            "slug": program["slug"],
            "title": program["title"],
            "program_name": program.get("program_name"),
            "url": program.get("permalink"),
            "canonical_url": program.get("canonical_url"),
            "description": program.get("description"),
            "summary": program.get("summary"),
            "keywords": program.get("keywords", []),
            "aliases": program.get("aliases", []),
            "related_people": program.get("related_people", []),
            "related_courses": [self.get_course(code) or {"course_code": code} for code in program.get("related_courses", [])],
            "related_topics": program.get("related_topics", []),
        }

    def get_recent_updates(self, limit: int = 5) -> list[dict[str, Any]]:
        updates = []
        for page in self.pages:
            if "/updates/" in (page.get("permalink") or ""):
                updates.append(
                    {
                        "type": "page",
                        "title": page["title"],
                        "url": page.get("permalink"),
                        "canonical_url": page.get("canonical_url"),
                        "summary": page.get("summary") or page.get("content_excerpt"),
                    }
                )
        for post in self.posts:
            updates.append(
                {
                    "type": "post",
                    "title": post["title"],
                    "url": post.get("permalink"),
                    "canonical_url": post.get("canonical_url"),
                    "date": post.get("date"),
                    "category": post.get("category"),
                    "summary": post.get("summary") or post.get("description") or post.get("content_excerpt"),
                }
            )
        updates.sort(key=lambda item: item.get("date") or "", reverse=True)
        return updates[:limit]

    def get_person_teaching_context(self, person_slug_or_name: str) -> dict[str, Any] | None:
        person = self.match_person(person_slug_or_name)
        if not person:
            return None
        rel = self.course_offerings.get("relationships", {}).get("people", {}).get(person["slug"], {})
        offerings = []
        instructor_matches = self.course_offerings.get("relationships", {}).get("instructor_matches", {})
        for course_code, records in self.course_offerings.get("course_index", {}).items():
            for offering in records:
                instructor = offering.get("instructor")
                match = instructor_matches.get(instructor)
                if match and match.get("slug") == person["slug"]:
                    offerings.append(offering)
        offerings.sort(key=lambda item: (item.get("academic_year"), item.get("term_order", 99), item.get("course_code"), item.get("section")))
        return {
            "slug": person["slug"],
            "person_name": person["person_name"],
            "current_academic_year": self.course_offerings.get("current_academic_year"),
            "related_courses": rel.get("related_course_entries", []),
            "offerings": offerings,
        }

    def get_course_context(self, course_code: str) -> dict[str, Any] | None:
        course = self.get_course(course_code)
        if not course:
            return None
        offerings = self.get_course_offerings(course_code)
        relationships = self.get_entity_relationships(course_code)
        return {
            "course": course,
            "offerings": offerings,
            "relationships": relationships,
        }

    def get_entity_relationships(self, entity_id: str) -> dict[str, Any] | None:
        person = self.match_person(entity_id)
        if person:
            rel = self.course_offerings.get("relationships", {}).get("people", {}).get(person["slug"], {})
            return {
                "entity_type": "person",
                "slug": person["slug"],
                "person_name": person["person_name"],
                "related_courses": rel.get("related_course_entries", []),
                "related_groups": [
                    self._entity_brief("group", self.groups_by_slug[group_slug])
                    for group_slug in person.get("related_groups", [])
                    if group_slug in self.groups_by_slug
                ],
                "related_topics": list(dict.fromkeys(person.get("research_areas", []) + person.get("related_topics", []))),
            }
        course = self.match_course(entity_id)
        if course:
            rel = self.course_offerings.get("relationships", {}).get("courses", {}).get(course["course_code"], {})
            return {
                "entity_type": "course",
                "course_code": course["course_code"],
                "related_people": rel.get("related_people_entries", []),
                "related_topics": course.get("related_topics", []),
                "related_programs": course.get("related_programs", []),
                "prerequisites": course.get("prerequisites", []),
                "co_requisites": course.get("co_requisites", []),
            }
        program = self.match_program(entity_id)
        if program:
            return {
                "entity_type": "program",
                "slug": program["slug"],
                "title": program["title"],
                "related_people": [
                    self._entity_brief("person", self.people_by_slug[slug])
                    for slug in program.get("related_people", [])
                    if slug in self.people_by_slug
                ],
                "related_courses": [
                    self._entity_brief("course", self.courses_by_code[code])
                    for code in program.get("related_courses", [])
                    if code in self.courses_by_code
                ],
                "related_topics": program.get("related_topics", []),
            }
        group = self.match_group(entity_id)
        if group:
            return {
                "entity_type": "group",
                "slug": group["slug"],
                "group_name": group["group_name"],
                "lead_people": [
                    self._entity_brief("person", self.people_by_slug[slug])
                    for slug in group.get("lead_people", [])
                    if slug in self.people_by_slug
                ],
                "member_people": [
                    self._entity_brief("person", self.people_by_slug[slug])
                    for slug in group.get("member_people", [])
                    if slug in self.people_by_slug
                ],
                "related_topics": group.get("related_topics", []),
            }
        return None

    def resource_payload(self, uri: str) -> dict[str, Any] | list[Any] | None:
        if uri == "cs-website://summary":
            return {
                "site_url": SITE_URL,
                "counts": {
                    "courses": len(self.courses),
                    "people": len(self.people),
                    "programs": len(self.programs),
                    "groups": len(self.groups),
                    "pages": len(self.pages),
                    "posts": len(self.posts),
                },
                "current_academic_year": self.course_offerings.get("current_academic_year"),
                "data_sources": [
                    "_people/*.md",
                    "_groups/*.md",
                    "WEB/academics/courses/*.markdown",
                    "WEB/**/*.markdown",
                    "_data/course_offerings.yml",
                    "_data/external_faculty_profiles.yml",
                    "_data/menu.yml",
                    "_data/section_indexes.yml",
                ],
            }
        if uri == "cs-website://courses":
            return [self.get_course(course["course_code"]) for course in self.courses]
        if uri == "cs-website://people":
            return [self.get_person(person["slug"]) for person in self.people]
        if uri == "cs-website://programs":
            return [self.get_program(program["slug"]) for program in self.programs]
        if uri == "cs-website://groups":
            return [self.get_entity_relationships(group["slug"]) for group in self.groups]
        if uri == "cs-website://course-offerings":
            return self.course_offerings
        if uri == "cs-website://external-faculty-profiles":
            return self.external_profiles
        if uri == "cs-website://menu":
            return self.menu
        if uri == "cs-website://section-indexes":
            return self.section_indexes
        return None
