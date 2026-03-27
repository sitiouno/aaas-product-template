"""Shared execution service for CLI and full-report experiences."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from .config import load_settings, validate_google_credentials
from .models import LanguageCode
from .research.registry import StyleRegistry
from .tools import render_markdown_like_html

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]

_registry: StyleRegistry | None = None


def get_registry() -> StyleRegistry:
    global _registry
    if _registry is None:
        _registry = StyleRegistry()
        _registry.auto_discover()
    return _registry


@dataclass
class StageStatus:
    id: str
    title: str
    description: str
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class ArtifactInfo:
    name: str
    path: str
    url: str
    kind: str
    is_public: bool = False
    requires_payment: bool = True
    mime_type: str | None = None


@dataclass
class ResultSection:
    id: str
    title: str
    text: str
    html: str


@dataclass
class PipelineRunResult:
    status: str
    prompt: str
    session_id: str
    final_text: str
    stages: list[dict[str, Any]]
    sections: list[dict[str, str]]
    artifacts: list[dict[str, str | bool | None]]
    logs: list[dict[str, str]]
    research_style: str
    workflow_version: str
    language: str
    error: str | None = None


def _language_from_value(value: str | LanguageCode | None) -> LanguageCode:
    if isinstance(value, LanguageCode):
        return value
    normalized = (value or "en").strip().lower()
    return LanguageCode.ES if normalized == "es" else LanguageCode.EN


def _language_instruction(language: LanguageCode) -> str:
    return (
        "Respond entirely in Spanish. Keep labels and report sections in Spanish."
        if language == LanguageCode.ES
        else "Respond entirely in English. Keep labels and report sections in English."
    )


def _initial_snapshot(
    job_id: str,
    prompt: str,
    research_style: str,
    language: LanguageCode,
    workflow_version: str = "v1",
) -> dict[str, Any]:
    registry = get_registry()
    try:
        style = registry.get(research_style)
        stages = style.get_stages()
    except KeyError:
        stages = []
    return {
        "job_id": job_id,
        "status": "idle",
        "prompt": prompt,
        "research_style": research_style,
        "workflow_version": workflow_version,
        "language": language.value,
        "session_id": None,
        "progress_percent": 0,
        "current_stage_id": None,
        "stages": [
            {
                "id": stage.id,
                "title": stage.title,
                "description": stage.description,
                "status": "pending",
                "started_at": None,
                "completed_at": None,
            }
            for stage in stages
        ],
        "logs": [],
        "sections": [],
        "artifacts": [],
        "final_text": "",
        "error": None,
    }


def _serialize_stage_statuses(stage_statuses: dict[str, StageStatus]) -> list[dict[str, Any]]:
    return [
        {
            "id": stage.id,
            "title": stage.title,
            "description": stage.description,
            "status": stage.status,
            "started_at": stage.started_at,
            "completed_at": stage.completed_at,
        }
        for stage in stage_statuses.values()
    ]


def _build_sections(
    session_state: dict[str, Any],
    research_style: str = "deploy_product",
) -> list[ResultSection]:
    registry = get_registry()
    try:
        style = registry.get(research_style)
        titles = style.get_section_titles()
    except KeyError:
        titles = {}
    sections = []
    for key, title in titles.items():
        value = session_state.get(key)
        if not value:
            continue
        text = str(value)
        sections.append(
            ResultSection(
                id=key,
                title=title,
                text=text,
                html=render_markdown_like_html(text),
            )
        )
    return sections


def _extract_text_parts(event: Any) -> list[str]:
    parts = []
    if not getattr(event, "content", None) or not getattr(event.content, "parts", None):
        return parts
    for part in event.content.parts:
        text = getattr(part, "text", None)
        if text:
            parts.append(text.strip())
    return [part for part in parts if part]


def _collect_recent_outputs(output_dir: Path, started_at: datetime) -> list[Path]:
    results = []
    for path in sorted(output_dir.glob("*")):
        if not path.is_file():
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        if modified_at >= started_at:
            results.append(path)
    return results


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".webp"}:
        return "image"
    if suffix == ".html":
        return "report_html"
    if suffix == ".pdf":
        return "report_pdf"
    return "file"


async def _emit(
    callback: ProgressCallback | None,
    *,
    event_type: str,
    prompt: str,
    session_id: str,
    status: str,
    research_style: str,
    workflow_version: str,
    language: LanguageCode,
    stage_statuses: dict[str, StageStatus],
    logs: list[dict[str, str]],
    current_stage_id: str | None,
    sections: list[ResultSection] | None = None,
    artifacts: list[ArtifactInfo] | None = None,
    final_text: str = "",
    error: str | None = None,
    message: str | None = None,
) -> None:
    if callback is None:
        return

    completed_count = sum(
        1 for stage in stage_statuses.values() if stage.status == "completed"
    )
    snapshot = {
        "status": status,
        "prompt": prompt,
        "research_style": research_style,
        "workflow_version": workflow_version,
        "language": language.value,
        "session_id": session_id,
        "progress_percent": int((completed_count / max(len(stage_statuses), 1)) * 100),
        "current_stage_id": current_stage_id,
        "stages": _serialize_stage_statuses(stage_statuses),
        "logs": logs,
        "sections": [
            {
                "id": section.id,
                "title": section.title,
                "text": section.text,
                "html": section.html,
            }
            for section in (sections or [])
        ],
        "artifacts": [
            {
                "name": artifact.name,
                "path": artifact.path,
                "url": artifact.url,
                "kind": artifact.kind,
                "is_public": artifact.is_public,
                "requires_payment": artifact.requires_payment,
                "mime_type": artifact.mime_type,
            }
            for artifact in (artifacts or [])
        ],
        "final_text": final_text,
        "error": error,
    }
    await callback({"type": event_type, "message": message, "snapshot": snapshot})


async def run_product_app(
    prompt: str,
    *,
    research_style: str = "deploy_product",
    workflow_version: str = "v1",
    language: str | LanguageCode = LanguageCode.EN,
    user_id: str | None = None,
    session_id: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PipelineRunResult:
    from google.adk.artifacts import InMemoryArtifactService
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    validate_google_credentials()
    settings = load_settings()
    started_at = datetime.now()
    resolved_workflow_version = (workflow_version or "v1").strip() or "v1"
    resolved_language = _language_from_value(language)
    resolved_user_id = user_id or settings.user_id
    resolved_session_id = session_id or (
        f"{settings.session_id}_{started_at.strftime('%Y%m%d_%H%M%S')}"
    )

    registry = get_registry()
    style = registry.get(research_style)
    selected_agent = style.build_pipeline(settings)
    stages = style.get_stages()
    stage_by_agent = {stage.agent_name: stage for stage in stages}
    stage_statuses = {
        stage.id: StageStatus(id=stage.id, title=stage.title, description=stage.description)
        for stage in stages
    }
    logs: list[dict[str, str]] = []
    final_response_parts: list[str] = []
    current_stage_id: str | None = None

    await _emit(
        progress_callback,
        event_type="job_started",
        prompt=prompt,
        session_id=resolved_session_id,
        status="running",
        research_style=research_style,
        workflow_version=resolved_workflow_version,
        language=resolved_language,
        stage_statuses=stage_statuses,
        logs=logs,
        current_stage_id=current_stage_id,
        message="Analysis started.",
    )

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    runner = Runner(
        agent=selected_agent,
        app_name=settings.app_name,
        session_service=session_service,
        artifact_service=artifact_service,
    )

    await session_service.create_session(
        app_name=settings.app_name,
        user_id=resolved_user_id,
        session_id=resolved_session_id,
    )

    try:
        effective_prompt = (
            f"{_language_instruction(resolved_language)}\n"
            f"Research style: {research_style}\n"
            f"Workflow version: {resolved_workflow_version}\n\n"
            f"{prompt}"
        )
        user_message = types.Content(role="user", parts=[types.Part(text=effective_prompt)])

        async for event in runner.run_async(
            user_id=resolved_user_id,
            session_id=resolved_session_id,
            new_message=user_message,
        ):
            stage = stage_by_agent.get(getattr(event, "author", None))
            if stage and current_stage_id != stage.id:
                if current_stage_id and stage_statuses[current_stage_id].status == "running":
                    stage_statuses[current_stage_id].status = "completed"
                    stage_statuses[current_stage_id].completed_at = datetime.now().isoformat()
                    await _emit(
                        progress_callback,
                        event_type="stage_completed",
                        prompt=prompt,
                        session_id=resolved_session_id,
                        status="running",
                        research_style=research_style,
                        workflow_version=resolved_workflow_version,
                        language=resolved_language,
                        stage_statuses=stage_statuses,
                        logs=logs,
                        current_stage_id=current_stage_id,
                        message=f"{stage_statuses[current_stage_id].title} completed.",
                    )

                current_stage_id = stage.id
                if stage_statuses[stage.id].status == "pending":
                    stage_statuses[stage.id].status = "running"
                    stage_statuses[stage.id].started_at = datetime.now().isoformat()
                    await _emit(
                        progress_callback,
                        event_type="stage_started",
                        prompt=prompt,
                        session_id=resolved_session_id,
                        status="running",
                        research_style=research_style,
                        workflow_version=resolved_workflow_version,
                        language=resolved_language,
                        stage_statuses=stage_statuses,
                        logs=logs,
                        current_stage_id=current_stage_id,
                        message=stage.description,
                    )

            text_parts = _extract_text_parts(event)
            if text_parts:
                message = text_parts[-1][:260]
                logs.append(
                    {
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "stage_id": current_stage_id or "system",
                        "author": getattr(event, "author", "system"),
                        "message": message,
                    }
                )
                logs = logs[-18:]
                await _emit(
                    progress_callback,
                    event_type="log",
                    prompt=prompt,
                    session_id=resolved_session_id,
                    status="running",
                    research_style=research_style,
                    workflow_version=resolved_workflow_version,
                    language=resolved_language,
                    stage_statuses=stage_statuses,
                    logs=logs,
                    current_stage_id=current_stage_id,
                    message=message,
                )

            if event.is_final_response() and getattr(event, "content", None):
                final_response_parts = _extract_text_parts(event)

        if current_stage_id and stage_statuses[current_stage_id].status == "running":
            stage_statuses[current_stage_id].status = "completed"
            stage_statuses[current_stage_id].completed_at = datetime.now().isoformat()

        session = await session_service.get_session(
            app_name=settings.app_name,
            user_id=resolved_user_id,
            session_id=resolved_session_id,
        )
        session_state = dict(getattr(session, "state", {}) or {})
        sections = _build_sections(session_state, research_style)

        artifacts = [
            ArtifactInfo(
                name=path.name,
                path=path.name,
                url=f"/artifacts/{path.name}",
                kind=_artifact_kind(path),
                is_public=False,
                requires_payment=False,
            )
            for path in _collect_recent_outputs(settings.output_dir, started_at)
        ]
        final_text = "\n".join(final_response_parts).strip()
        if not final_text:
            style_obj = registry.get(research_style)
            section_keys = list(style_obj.get_section_titles().keys())
            fallback_key = section_keys[-1] if section_keys else "investor_memo"
            final_text = str(session_state.get(fallback_key) or "")

        await _emit(
            progress_callback,
            event_type="finished",
            prompt=prompt,
            session_id=resolved_session_id,
            status="completed",
            research_style=research_style,
            workflow_version=resolved_workflow_version,
            language=resolved_language,
            stage_statuses=stage_statuses,
            logs=logs,
            current_stage_id=None,
            sections=sections,
            artifacts=artifacts,
            final_text=final_text,
            message="Analysis completed.",
        )

        return PipelineRunResult(
            status="completed",
            prompt=prompt,
            session_id=resolved_session_id,
            final_text=final_text,
            stages=_serialize_stage_statuses(stage_statuses),
            sections=[
                {
                    "id": section.id,
                    "title": section.title,
                    "text": section.text,
                    "html": section.html,
                }
                for section in sections
            ],
            artifacts=[
                {
                    "name": artifact.name,
                    "path": artifact.path,
                    "url": artifact.url,
                    "kind": artifact.kind,
                    "is_public": artifact.is_public,
                    "requires_payment": artifact.requires_payment,
                    "mime_type": artifact.mime_type,
                }
                for artifact in artifacts
            ],
            logs=logs,
            research_style=research_style,
            workflow_version=resolved_workflow_version,
            language=resolved_language.value,
            error=None,
        )
    except Exception as exc:
        _svc_log = logging.getLogger(__name__)
        _svc_log.exception(
            "run_product_app failed at stage=%s style=%s",
            current_stage_id, research_style,
        )
        print(f"[CRITICAL] run_product_app failed: {exc!r}",
              file=sys.stderr, flush=True)

        if current_stage_id and stage_statuses[current_stage_id].status == "running":
            stage_statuses[current_stage_id].status = "failed"
            stage_statuses[current_stage_id].completed_at = datetime.now().isoformat()

        error_message = str(exc)
        logs.append(
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "stage_id": current_stage_id or "system",
                "author": "system",
                "message": error_message[:260],
            }
        )
        logs = logs[-18:]

        await _emit(
            progress_callback,
            event_type="error",
            prompt=prompt,
            session_id=resolved_session_id,
            status="failed",
            research_style=research_style,
            workflow_version=resolved_workflow_version,
            language=resolved_language,
            stage_statuses=stage_statuses,
            logs=logs,
            current_stage_id=current_stage_id,
            final_text="\n".join(final_response_parts),
            error=error_message,
            message=error_message,
        )

        return PipelineRunResult(
            status="failed",
            prompt=prompt,
            session_id=resolved_session_id,
            final_text="\n".join(final_response_parts),
            stages=_serialize_stage_statuses(stage_statuses),
            sections=[],
            artifacts=[],
            logs=logs,
            research_style=research_style,
            workflow_version=resolved_workflow_version,
            language=resolved_language.value,
            error=error_message,
        )
