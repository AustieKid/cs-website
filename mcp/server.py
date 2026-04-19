#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from site_index import SiteIndex  # noqa: E402


SERVER_NAME = "cs-website-readonly"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"


class MCPError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class CSWebsiteMCPServer:
    def __init__(self):
        self.index = SiteIndex()
        self.tool_definitions = self._build_tool_definitions()
        self.resource_definitions = self._build_resource_definitions()

    def _build_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "search_site_entities",
                "description": "Search courses, people, programs, groups, and structured pages from the CS website repo.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 15},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_courses",
                "description": "Search courses by code, title, aliases, keywords, and description.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_people",
                "description": "Search people by slug, name, aliases, keywords, topics, and supplemental external profile data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_faculty_by_topic",
                "description": "Find faculty whose internal or supplemental external profile topics match a query.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                    },
                    "required": ["topic"],
                },
            },
            {
                "name": "search_groups_by_topic",
                "description": "Find research groups whose related topics match a query topic.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    },
                    "required": ["topic"],
                },
            },
            {
                "name": "get_course",
                "description": "Fetch a single course by canonical course code or known alias.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"course_code": {"type": "string"}},
                    "required": ["course_code"],
                },
            },
            {
                "name": "get_person",
                "description": "Fetch a single person by slug, canonical name, alias, or normalized Last/First form.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"person_slug_or_name": {"type": "string"}},
                    "required": ["person_slug_or_name"],
                },
            },
            {
                "name": "get_course_offerings",
                "description": "Fetch current and future offerings for a course from generated offerings data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"course_code": {"type": "string"}},
                    "required": ["course_code"],
                },
            },
            {
                "name": "get_person_related_courses",
                "description": "Fetch current and future related courses for a person using generated teaching relationships.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"person_slug_or_name": {"type": "string"}},
                    "required": ["person_slug_or_name"],
                },
            },
            {
                "name": "get_external_faculty_profile",
                "description": "Fetch supplemental external faculty-profile enrichment for a person, including provenance and confidence.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"person_slug_or_name": {"type": "string"}},
                    "required": ["person_slug_or_name"],
                },
            },
            {
                "name": "get_program",
                "description": "Fetch a program page by slug, title, or alias.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"program_slug_or_name": {"type": "string"}},
                    "required": ["program_slug_or_name"],
                },
            },
            {
                "name": "get_recent_updates",
                "description": "Fetch recent updates and posts from the repo.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}
                    },
                },
            },
            {
                "name": "get_person_teaching_context",
                "description": "Fetch a person’s current/future teaching context from generated offerings data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"person_slug_or_name": {"type": "string"}},
                    "required": ["person_slug_or_name"],
                },
            },
            {
                "name": "get_course_context",
                "description": "Fetch course metadata, offerings, and relationships in one response.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"course_code": {"type": "string"}},
                    "required": ["course_code"],
                },
            },
            {
                "name": "get_entity_relationships",
                "description": "Fetch relationship context for a person, course, program, or group.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"entity_id": {"type": "string"}},
                    "required": ["entity_id"],
                },
            },
        ]

    def _build_resource_definitions(self) -> list[dict[str, Any]]:
        return [
            {"uri": "cs-website://summary", "name": "Site Summary", "mimeType": "application/json", "description": "High-level counts and source datasets."},
            {"uri": "cs-website://courses", "name": "Courses", "mimeType": "application/json", "description": "Canonical internal course data."},
            {"uri": "cs-website://people", "name": "People", "mimeType": "application/json", "description": "Canonical internal people data with optional supplemental enrichment."},
            {"uri": "cs-website://programs", "name": "Programs", "mimeType": "application/json", "description": "Program pages and related metadata."},
            {"uri": "cs-website://groups", "name": "Groups", "mimeType": "application/json", "description": "Research groups and relationship data."},
            {"uri": "cs-website://course-offerings", "name": "Course Offerings", "mimeType": "application/json", "description": "Generated current/future offerings and teaching relationships."},
            {"uri": "cs-website://external-faculty-profiles", "name": "External Faculty Profiles", "mimeType": "application/json", "description": "Supplemental external faculty-profile enrichment with provenance."},
            {"uri": "cs-website://menu", "name": "Menu Data", "mimeType": "application/json", "description": "Top-level menu configuration."},
            {"uri": "cs-website://section-indexes", "name": "Section Indexes", "mimeType": "application/json", "description": "Structured section-index data used across the site."},
        ]

    def run(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                return
            if "id" in message:
                response = self._handle_request(message)
                self._write_message(response)
            else:
                self._handle_notification(message)

    def _handle_request(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("id")
        try:
            result = self._dispatch(message.get("method"), message.get("params") or {})
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except MCPError as exc:
            error = {"code": exc.code, "message": exc.message}
            if exc.data is not None:
                error["data"] = exc.data
            return {"jsonrpc": "2.0", "id": request_id, "error": error}
        except Exception as exc:  # pragma: no cover - defensive server path
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "Internal server error",
                    "data": {"exception": str(exc), "traceback": traceback.format_exc()},
                },
            }

    def _handle_notification(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method in {"notifications/initialized", "initialized"}:
            return

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            protocol_version = params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION
            return {
                "protocolVersion": protocol_version,
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {"tools": {}, "resources": {}},
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": self.tool_definitions}
        if method == "tools/call":
            return self._call_tool(params)
        if method == "resources/list":
            return {"resources": self.resource_definitions}
        if method == "resources/read":
            return self._read_resource(params)
        raise MCPError(-32601, f"Method not found: {method}")

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}

        def required(key: str) -> Any:
            value = arguments.get(key)
            if value in (None, ""):
                raise MCPError(-32602, f"Missing required argument: {key}")
            return value

        if name == "search_site_entities":
            result = self.index.search_site_entities(required("query"), int(arguments.get("limit", 15)))
        elif name == "search_courses":
            result = self.index.search_courses(required("query"), int(arguments.get("limit", 10)))
        elif name == "search_people":
            result = self.index.search_people(required("query"), int(arguments.get("limit", 10)))
        elif name == "search_faculty_by_topic":
            result = self.index.search_faculty_by_topic(required("topic"), int(arguments.get("limit", 10)))
        elif name == "search_groups_by_topic":
            result = self.index.search_groups_by_topic(required("topic"), int(arguments.get("limit", 5)))
        elif name == "get_course":
            result = self.index.get_course(required("course_code"))
        elif name == "get_person":
            result = self.index.get_person(required("person_slug_or_name"))
        elif name == "get_course_offerings":
            result = self.index.get_course_offerings(required("course_code"))
        elif name == "get_person_related_courses":
            result = self.index.get_person_related_courses(required("person_slug_or_name"))
        elif name == "get_external_faculty_profile":
            result = self.index.get_external_faculty_profile(required("person_slug_or_name"))
        elif name == "get_program":
            result = self.index.get_program(required("program_slug_or_name"))
        elif name == "get_recent_updates":
            result = self.index.get_recent_updates(int(arguments.get("limit", 5)))
        elif name == "get_person_teaching_context":
            result = self.index.get_person_teaching_context(required("person_slug_or_name"))
        elif name == "get_course_context":
            result = self.index.get_course_context(required("course_code"))
        elif name == "get_entity_relationships":
            result = self.index.get_entity_relationships(required("entity_id"))
        else:
            raise MCPError(-32602, f"Unknown tool: {name}")

        if result is None:
            raise MCPError(-32001, "No matching entity found")

        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}],
            "structuredContent": result,
        }

    def _read_resource(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = params.get("uri")
        if not uri:
            raise MCPError(-32602, "Missing required parameter: uri")
        payload = self.index.resource_payload(uri)
        if payload is None:
            raise MCPError(-32002, f"Unknown resource: {uri}")
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(payload, indent=2, ensure_ascii=False),
                }
            ]
        }

    def _read_message(self) -> dict[str, Any] | None:
        content_length = None
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            header = line.decode("utf-8").strip()
            if header.lower().startswith("content-length:"):
                content_length = int(header.split(":", 1)[1].strip())
        if content_length is None:
            raise MCPError(-32700, "Missing Content-Length header")
        body = sys.stdin.buffer.read(content_length)
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    def _write_message(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()


def main() -> int:
    CSWebsiteMCPServer().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
