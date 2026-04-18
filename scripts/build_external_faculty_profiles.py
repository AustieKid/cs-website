#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from collections import OrderedDict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import yaml
from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[1]
PEOPLE_DIR = REPO_ROOT / "_people"
OUTPUT_PATH = REPO_ROOT / "_data" / "external_faculty_profiles.yml"
USER_AGENT = "Mozilla/5.0 (compatible; CSWebsiteBot/1.0; +https://www.cs.umb.edu/)"
TIMEOUT_SECONDS = 20
FIELD_ORDER = [
    "external_summary",
    "research_topics",
    "lab_or_group",
    "recent_news_titles",
    "publication_links",
    "profile_links",
    "teaching_links",
    "teaching_terms",
]
PROFILE_LINK_PATTERNS = (
    "google scholar",
    "scholar.google",
    "dblp",
    "cv",
    "curriculum vitae",
    "orcid",
    "github",
    "linkedin",
)
TEACHING_LINK_PATTERNS = (
    "teach",
    "course",
    "class",
    "syllabus",
)
NEWS_HEADING_PATTERNS = (
    "news",
    "recent news",
    "updates",
    "announcements",
)
PUBLICATION_HEADING_PATTERNS = (
    "publications",
    "publication",
    "papers",
    "selected publications",
)
RESEARCH_HEADING_PATTERNS = (
    "research interests",
    "research areas",
    "research topics",
    "areas of interest",
    "research",
    "interests",
)
LAB_HEADING_PATTERNS = (
    "lab",
    "group",
    "research group",
    "laboratory",
)
ABOUT_HEADING_PATTERNS = (
    "about",
    "about me",
    "bio",
    "biography",
)
TERM_PATTERN = re.compile(
    r"\b(Fall|Spring|Summer(?:\s+Session\s+[123])?)\s+(20\d{2})\b",
    re.IGNORECASE,
)
# Sentence-starter words whose presence at the beginning of a research-topic item
# indicates it is prose/navigational text, not a topic name.
SENTENCE_STARTER_PATTERN = re.compile(
    r"^(i |you |we |they |it |this |the |these |those |a |an |my |our |your )",
    re.IGNORECASE,
)
SUMMARY_CANDIDATE_MIN_LENGTH = 80
SUMMARY_CANDIDATE_MAX_LENGTH = 400


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_list(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        clean = collapse_whitespace(value)
        key = clean.casefold()
        if not clean or key in seen:
            continue
        seen.add(key)
        normalized.append(clean)
    return normalized


def is_url_like(value: str) -> bool:
    return value.casefold().startswith(("http://", "https://", "www."))


def is_bio_summary_candidate(text: str) -> bool:
    text_key = text.casefold()
    if any(
        marker in text_key
        for marker in (
            "paper entitled",
            "special issue",
            "call for papers",
            "cfp",
            "presented at",
            "news",
            "announcement",
        )
    ):
        return False
    return any(
        marker in text_key
        for marker in (
            "i am",
            "i was",
            "i obtained",
            "received my",
            "associate professor",
            "assistant professor",
            "senior lecturer",
            "lecturer",
            "professor",
            "research focuses",
            "research interests",
            "department of computer science",
        )
    )


def is_topic_item(text: str) -> bool:
    """Return True when text looks like a research topic name (not a sentence)."""
    text_key = text.casefold().strip()
    if not text_key:
        return False
    # Prose sentences typically start with a pronoun, article, or possessive.
    if SENTENCE_STARTER_PATTERN.match(text_key):
        return False
    # "period space" in the middle of an item means it contains multiple sentences.
    if ". " in text_key:
        return False
    return True


def is_generic_group_label(value: str) -> bool:
    key = value.casefold()
    return key in {"group", "lab", "laboratory", "center", "research group", "home", "service", "publications"}


def has_group_keyword(value: str) -> bool:
    return bool(re.search(r"\b(lab|group|laboratory|center)\b", value.casefold()))


def looks_like_profile_link(link: dict) -> bool:
    haystack = f"{link['text']} {link['url']}".casefold()
    text_key = link["text"].casefold()
    if any(ext in link["url"].casefold() for ext in (".gif", ".jpg", ".jpeg", ".png", ".svg", ".webp")):
        return False
    if "@" in urlparse(link["url"]).path:
        return False
    if any(token in text_key for token in ("room ", "office ", "m-", "science center")):
        return False
    if text_key in {"home", "publications", "service", "group"}:
        return False
    if any(pattern in haystack for pattern in PROFILE_LINK_PATTERNS):
        return True
    if has_group_keyword(text_key) and not is_generic_group_label(link["text"]):
        return True
    return False


def looks_like_teaching_link(link: dict) -> bool:
    haystack = f"{link['text']} {link['url']}".casefold()
    return any(pattern in haystack for pattern in TEACHING_LINK_PATTERNS)


def to_ordered_mapping(value):
    if isinstance(value, OrderedDict):
        return value
    return OrderedDict(value)


def to_plain_data(value):
    if isinstance(value, OrderedDict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    return value


def parse_front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    _, _, remainder = text.partition("\n")
    front_matter, _, _ = remainder.partition("\n---")
    return yaml.safe_load(front_matter) or {}


def load_people_seed_data() -> list[dict]:
    people: list[dict] = []
    for path in sorted(PEOPLE_DIR.glob("*.md")):
        data = parse_front_matter(path)
        same_as = data.get("same_as") or []
        if isinstance(same_as, str):
            same_as = [same_as]
        same_as = [url for url in same_as if collapse_whitespace(url)]
        if not same_as:
            continue
        people.append(
            {
                "slug": path.stem,
                "title": data.get("title"),
                "person_name": data.get("person_name"),
                "same_as": same_as,
            }
        )
    return people


def fetch_url(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        status = getattr(response, "status", None) or response.getcode()
        content_type = response.headers.get_content_type()
        body = response.read()
        final_url = response.geturl()
    if content_type != "text/html":
        raise ValueError(f"Unsupported content type: {content_type}")
    html = body.decode("utf-8", "ignore")
    return {
        "status": status,
        "html": html,
        "final_url": final_url,
    }


def maybe_follow_meta_refresh(url: str, html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
    if not meta:
        return None
    content = meta.get("content", "")
    match = re.search(r"url\s*=\s*(.+)$", content, re.I)
    if not match:
        return None
    return urljoin(url, match.group(1).strip(" '\""))


def parse_html(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = collapse_whitespace(soup.title.get_text(" ", strip=True) if soup.title else "")
    meta_description = ""
    for selector in (
        {"attrs": {"name": re.compile(r"description", re.I)}},
        {"attrs": {"property": re.compile(r"og:description", re.I)}},
        {"attrs": {"name": re.compile(r"twitter:description", re.I)}},
    ):
        node = soup.find("meta", **selector)
        if node and node.get("content"):
            meta_description = collapse_whitespace(node["content"])
            if meta_description:
                break

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    body_root = soup.find(["main", "article"]) or soup.body or soup
    sections = extract_sections(body_root, url)
    links = extract_links(body_root, url)

    fields: OrderedDict[str, OrderedDict] = OrderedDict()

    if meta_description:
        fields["external_summary"] = OrderedDict(
            [
                ("value", meta_description),
                ("confidence", "high"),
                ("source_section", "meta description"),
            ]
        )
    else:
        summary, summary_source = extract_summary(body_root, sections)
        if summary:
            fields["external_summary"] = OrderedDict(
                [
                    ("value", summary),
                    ("confidence", "medium"),
                    ("source_section", summary_source),
                ]
            )

    research_topics, research_source = extract_research_topics(sections)
    if research_topics:
        fields["research_topics"] = OrderedDict(
            [
                ("value", research_topics),
                ("confidence", "medium"),
                ("source_section", research_source),
            ]
        )

    lab_or_group, lab_source = extract_lab_or_group(sections, links)
    if lab_or_group:
        fields["lab_or_group"] = OrderedDict(
            [
                ("value", lab_or_group),
                ("confidence", "medium"),
                ("source_section", lab_source),
            ]
        )

    recent_news_titles, news_source = extract_news_titles(sections)
    if recent_news_titles:
        fields["recent_news_titles"] = OrderedDict(
            [
                ("value", recent_news_titles),
                ("confidence", "medium"),
                ("source_section", news_source),
            ]
        )

    publication_links, publication_source = extract_publication_links(sections, links)
    if publication_links:
        fields["publication_links"] = OrderedDict(
            [
                ("value", publication_links),
                ("confidence", "medium"),
                ("source_section", publication_source),
            ]
        )

    profile_links = extract_profile_links(links)
    if profile_links:
        fields["profile_links"] = OrderedDict(
            [
                ("value", profile_links),
                ("confidence", "high"),
                ("source_section", "page links"),
            ]
        )

    teaching_links, teaching_source = extract_teaching_links(sections, links)
    if teaching_links:
        fields["teaching_links"] = OrderedDict(
            [
                ("value", teaching_links),
                ("confidence", "medium"),
                ("source_section", teaching_source),
            ]
        )

    teaching_terms, teaching_terms_source = extract_teaching_terms(sections)
    if teaching_terms:
        fields["teaching_terms"] = OrderedDict(
            [
                ("value", teaching_terms),
                ("confidence", "low"),
                ("source_section", teaching_terms_source),
            ]
        )

    ordered_fields = OrderedDict()
    for field_name in FIELD_ORDER:
        if field_name in fields:
            ordered_fields[field_name] = fields[field_name]

    return {
        "title": title,
        "fields": ordered_fields,
    }


def extract_sections(root, base_url: str) -> list[dict]:
    sections: list[dict] = []
    current = {"heading": "page", "texts": [], "links": []}

    # Pre-identify <p> / <dt> elements whose sole non-whitespace content is a
    # <b> or <strong> tag – treat these as implicit section headings.  Old-style
    # faculty homepages often use <p><b>Research Interests</b></p> rather than
    # a proper <h*> tag for section headers.
    bold_heading_ids: set[int] = set()
    for node in root.find_all(["p", "dt"]):
        content_nodes = [
            c
            for c in node.children
            if getattr(c, "name", None) is not None
            or (isinstance(c, str) and c.strip())
        ]
        if len(content_nodes) == 1:
            child = content_nodes[0]
            if getattr(child, "name", None) in {"b", "strong"}:
                heading_text = collapse_whitespace(child.get_text(" ", strip=True))
                if heading_text:
                    bold_heading_ids.add(id(node))

    def start_section(heading: str):
        nonlocal current
        if current["texts"] or current["links"]:
            sections.append(current)
        current = {"heading": collapse_whitespace(heading), "texts": [], "links": []}

    for node in root.descendants:
        if getattr(node, "name", None) and re.fullmatch(r"h[1-4]", node.name):
            heading = node.get_text(" ", strip=True)
            if heading:
                start_section(heading)
            continue
        if id(node) in bold_heading_ids:
            heading = collapse_whitespace(node.find(["b", "strong"]).get_text(" ", strip=True))
            if heading:
                start_section(heading)
            continue
        if getattr(node, "name", None) == "a":
            href = node.get("href")
            text = collapse_whitespace(node.get_text(" ", strip=True))
            if href and text:
                current["links"].append({"text": text, "url": urljoin(base_url, href)})
        if getattr(node, "name", None) in {"p", "li"}:
            if id(node) not in bold_heading_ids:
                text = collapse_whitespace(node.get_text(" ", strip=True))
                if text:
                    current["texts"].append(text)

    if current["texts"] or current["links"]:
        sections.append(current)
    return sections


def extract_links(root, base_url: str) -> list[dict]:
    links: list[dict] = []
    for node in root.find_all("a", href=True):
        href = urljoin(base_url, node["href"])
        text = collapse_whitespace(node.get_text(" ", strip=True))
        if not href:
            continue
        links.append({"text": text, "url": href})
    deduped = []
    seen = set()
    for link in links:
        key = (link["text"], link["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(link)
    return deduped


def extract_summary(root, sections: list[dict]) -> tuple[str | None, str | None]:
    for section in sections:
        if section_matches(section["heading"], ABOUT_HEADING_PATTERNS):
            for text in section["texts"]:
                if SUMMARY_CANDIDATE_MIN_LENGTH <= len(text) <= SUMMARY_CANDIDATE_MAX_LENGTH:
                    return text, section["heading"]
    for node in root.find_all("p"):
        text = collapse_whitespace(node.get_text(" ", strip=True))
        if SUMMARY_CANDIDATE_MIN_LENGTH <= len(text) <= SUMMARY_CANDIDATE_MAX_LENGTH:
            if "cookie" in text.casefold() or "copyright" in text.casefold():
                continue
            if is_bio_summary_candidate(text):
                return text, "intro paragraph"
    return None, None


def section_matches(heading: str, patterns: Iterable[str]) -> bool:
    heading_key = collapse_whitespace(heading).casefold()
    return any(pattern in heading_key for pattern in patterns)


def extract_research_topics(sections: list[dict]) -> tuple[list[str], str] | tuple[None, None]:
    for section in sections:
        if section_matches(section["heading"], RESEARCH_HEADING_PATTERNS):
            topics: list[str] = []
            for text in section["texts"]:
                if "," in text and len(text) < 160:
                    topics.extend(
                        part.strip()
                        for part in text.split(",")
                        if part.strip() and is_topic_item(part.strip())
                    )
                elif len(text) <= 80 and is_topic_item(text):
                    topics.append(text)
            topics = normalize_list(topics)
            if topics:
                return topics[:10], section["heading"]
    return None, None


def extract_lab_or_group(sections: list[dict], links: list[dict]) -> tuple[str, str] | tuple[None, None]:
    for section in sections:
        if section_matches(section["heading"], LAB_HEADING_PATTERNS):
            for link in section["links"]:
                text_key = link["text"].casefold()
                if has_group_keyword(text_key):
                    if not is_generic_group_label(link["text"]):
                        return collapse_whitespace(link["text"].rstrip(" ,;.:")), section["heading"]
            for text in section["texts"]:
                text_key = text.casefold()
                if has_group_keyword(text_key):
                    if not is_generic_group_label(text):
                        return collapse_whitespace(text.rstrip(" ,;.:")), section["heading"]
    for link in links:
        link_text = f"{link['text']} {link['url']}".casefold()
        if has_group_keyword(link_text):
            label = link["text"] or link["url"]
            if not is_generic_group_label(label):
                return collapse_whitespace(label.rstrip(" ,;.:")), "page links"
    return None, None


def extract_news_titles(sections: list[dict]) -> tuple[list[str], str] | tuple[None, None]:
    for section in sections:
        if section_matches(section["heading"], NEWS_HEADING_PATTERNS):
            titles = normalize_list(
                [link["text"] for link in section["links"] if len(link["text"]) > 8 and not is_url_like(link["text"])]
                + [text for text in section["texts"] if len(text) > 8 and not is_url_like(text)]
            )
            if titles:
                return titles[:5], section["heading"]
    return None, None


def extract_publication_links(sections: list[dict], links: list[dict]) -> tuple[list[dict], str] | tuple[None, None]:
    for section in sections:
        if section_matches(section["heading"], PUBLICATION_HEADING_PATTERNS):
            publication_links = [
                link for link in section["links"]
                if "bibtexkey" not in link["url"].casefold()
                and "+bibtexkey+" not in link["url"].casefold()
                and not any(pattern in f"{link['text']} {link['url']}".casefold() for pattern in TEACHING_LINK_PATTERNS)
            ]
            values = normalize_link_entries(publication_links)
            if values:
                return values[:8], section["heading"]
    filtered = [
        link
        for link in links
        if any(pattern in f"{link['text']} {link['url']}".casefold() for pattern in ("publication", "paper", "arxiv"))
        and "bibtexkey" not in link["url"].casefold()
    ]
    values = normalize_link_entries(filtered)
    if values:
        return values[:8], "page links"
    return None, None


def extract_profile_links(links: list[dict]) -> list[dict] | None:
    filtered = [link for link in links if looks_like_profile_link(link)]
    values = normalize_link_entries(filtered)
    return values[:8] if values else None


def extract_teaching_links(sections: list[dict], links: list[dict]) -> tuple[list[dict], str] | tuple[None, None]:
    for section in sections:
        if section_matches(section["heading"], TEACHING_LINK_PATTERNS):
            values = normalize_link_entries([link for link in section["links"] if looks_like_teaching_link(link)])
            if values:
                return values[:8], section["heading"]
    filtered = [link for link in links if looks_like_teaching_link(link)]
    values = normalize_link_entries(filtered)
    if values:
        return values[:8], "page links"
    return None, None


def extract_teaching_terms(sections: list[dict]) -> tuple[list[str], str] | tuple[None, None]:
    candidates: list[str] = []
    source = None
    for section in sections:
        if section_matches(section["heading"], TEACHING_LINK_PATTERNS):
            source = section["heading"]
            text_blob = " ".join(section["texts"])
            for match in TERM_PATTERN.finditer(text_blob):
                candidates.append(f"{match.group(1).title()} {match.group(2)}")
    candidates = normalize_list(candidates)
    if candidates:
        return candidates, source or "teaching section"
    return None, None


def normalize_link_entries(links: Iterable[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        text = collapse_whitespace(link.get("text", "")) or None
        url = collapse_whitespace(link.get("url", ""))
        if not url:
            continue
        if any(pattern in url.casefold() for pattern in ("javascript:", "mailto:", "tel:")):
            continue
        if text and is_url_like(text) and text == url:
            text = None
        key = ((text or "").casefold(), url)
        if key in seen:
            continue
        seen.add(key)
        entry = OrderedDict([("url", url)])
        if text:
            entry["label"] = text
        deduped.append(entry)
    return deduped


def enrich_profile(url: str, today: date) -> OrderedDict:
    profile = OrderedDict()
    profile["url"] = url
    profile["last_checked"] = today.isoformat()
    try:
        fetch_result = fetch_url(url)
        html = fetch_result["html"]
        final_url = fetch_result["final_url"]
        refresh_target = maybe_follow_meta_refresh(final_url, html)
        if refresh_target and refresh_target != final_url:
            redirected = fetch_url(refresh_target)
            html = redirected["html"]
            final_url = redirected["final_url"]
            profile["redirected_to"] = final_url
            profile["http_status"] = redirected["status"]
        else:
            profile["http_status"] = fetch_result["status"]
        parsed = parse_html(final_url, html)
        profile["source_title"] = parsed["title"] or None
        if final_url != url and "redirected_to" not in profile:
            profile["resolved_url"] = final_url
        elif final_url != url:
            profile["resolved_url"] = final_url
        if parsed["fields"]:
            profile["fields"] = parsed["fields"]
    except Exception as exc:
        profile["fetch_error"] = collapse_whitespace(str(exc))
    return profile


def build_payload(today: date | None = None) -> OrderedDict:
    today = today or date.today()
    payload = OrderedDict()
    payload["generated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload["last_checked"] = today.isoformat()
    payload["people"] = OrderedDict()

    for person in load_people_seed_data():
        person_entry = OrderedDict()
        person_entry["person_name"] = person["person_name"] or person["title"] or person["slug"]
        person_entry["source_urls"] = person["same_as"]
        person_entry["profiles"] = [enrich_profile(url, today) for url in person["same_as"]]
        payload["people"][person["slug"]] = person_entry

    return payload


def main() -> None:
    override_today = os.environ.get("EXTERNAL_PROFILES_TODAY")
    today = date.fromisoformat(override_today) if override_today else date.today()
    payload = build_payload(today=today)
    OUTPUT_PATH.write_text(
        yaml.safe_dump(to_plain_data(payload), sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )
    people_count = len(payload["people"])
    profile_count = sum(len(person["profiles"]) for person in payload["people"].values())
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} for {people_count} people across {profile_count} profiles.")


if __name__ == "__main__":
    main()
