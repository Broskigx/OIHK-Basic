"""Auditable application tools available to the local OIHK Agent.

The model never talks to the database or the network directly.  It selects a
named tool, this module validates the request against the current user and
investigation, and the existing application route/service performs the work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.routers import cases, custody, evidence, graph, operations, osint, reports, sources, transforms
from app.schemas import (
    CaseCreate,
    CaseUpdate,
    GraphEntityCreate,
    GraphRelationshipCreate,
    OsintLookupRequest,
    ReportGenerateRequest,
    TransformRunRequest,
)


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict[str, str]
    mutating: bool = False

    def prompt_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "changes_data": self.mutating,
        }


@dataclass(frozen=True)
class AgentToolResult:
    tool: str
    arguments: dict[str, Any]
    ok: bool
    result_summary: str
    result: Any = None

    def message_record(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "result_summary": self.result_summary,
            "ok": self.ok,
        }

    def model_record(self) -> dict[str, Any]:
        return {**self.message_record(), "result": self.result}


AGENT_TOOLS: tuple[AgentTool, ...] = (
    AgentTool("list_investigations", "List the investigations the current user can access.", {}),
    AgentTool(
        "get_investigation",
        "Read one investigation and its counters.",
        {"case_id": "optional investigation id; omit to use the active investigation"},
    ),
    AgentTool(
        "create_investigation",
        "Create a new authorized investigation and return its id.",
        {
            "title": "required title",
            "summary": "useful description",
            "legal_basis": "authorization basis; default Authorized research",
            "scope_statement": "bounded authorized scope",
            "priority": "low, normal, high, or critical",
            "tags": "array of short tags",
            "notes": "optional notes",
        },
        True,
    ),
    AgentTool(
        "update_investigation",
        "Update metadata or status on an existing investigation.",
        {
            "case_id": "optional id; omit to use the active investigation",
            "title": "optional",
            "summary": "optional",
            "legal_basis": "optional",
            "scope_statement": "optional",
            "status": "active, paused, closed, or archived",
            "priority": "low, normal, high, or critical",
            "tags": "optional array",
            "notes": "optional",
        },
        True,
    ),
    AgentTool(
        "get_investigation_overview",
        "Read status plus entity, relationship, and source totals.",
        {"case_id": "optional id; omit to use the active investigation"},
    ),
    AgentTool(
        "list_graph",
        "List graph entities and relationships for an investigation.",
        {"case_id": "optional id; omit to use the active investigation"},
    ),
    AgentTool(
        "add_entity",
        "Add a manual entity to the investigation graph.",
        {
            "case_id": "optional id; omit to use the active investigation",
            "label": "required display value",
            "type": "entity type such as person, domain, ip, email, organization, or note",
            "confidence": "0 to 1",
            "connect_to_id": "optional existing entity id",
            "relation_label": "relationship label when connecting",
        },
        True,
    ),
    AgentTool(
        "add_relationship",
        "Connect two existing graph entities.",
        {
            "case_id": "optional id; omit to use the active investigation",
            "source_id": "required source entity id",
            "target_id": "required target entity id",
            "label": "required relationship label",
            "confidence": "0 to 1",
        },
        True,
    ),
    AgentTool(
        "list_sources",
        "List collected sources and citations.",
        {"case_id": "optional id; omit to use the active investigation"},
    ),
    AgentTool(
        "list_evidence",
        "List managed evidence files and hashes.",
        {"case_id": "optional id; omit to use the active investigation"},
    ),
    AgentTool(
        "get_custody",
        "Read chain-of-custody and integrity status.",
        {"case_id": "optional id; omit to use the active investigation"},
    ),
    AgentTool(
        "list_osint_history",
        "List prior DNS, RDAP, certificate, IP, or email OSINT queries.",
        {"case_id": "optional id; omit to use the active investigation"},
    ),
    AgentTool(
        "run_osint_lookup",
        "Run the app's safe OSINT enrichment for a domain, IP address, or email and save it to history.",
        {
            "case_id": "optional id; omit to use the active investigation",
            "value": "required domain, IPv4/IPv6 address, or email",
        },
        True,
    ),
    AgentTool(
        "promote_osint_result",
        "Promote a saved OSINT query into sourced graph entities and relationships.",
        {"query_id": "required OSINT query id"},
        True,
    ),
    AgentTool(
        "list_reports",
        "List reports saved for an investigation.",
        {"case_id": "optional id; omit to use the active investigation"},
    ),
    AgentTool(
        "generate_report",
        "Generate and save a deterministic investigation report.",
        {
            "case_id": "optional id; omit to use the active investigation",
            "title": "required report title",
            "format": "markdown, html, or json",
            "sections": "array chosen from overview, entities, relationships, sources, evidence, notes, timeline, methodology, limitations",
            "methodology": "optional",
            "limitations": "optional",
        },
        True,
    ),
    AgentTool("list_transforms", "List every installed graph transform and its accepted entity types.", {}),
    AgentTool(
        "run_transform",
        "Run one installed DNS, RDAP, certificate, IP, or email transform on an existing entity.",
        {"transform_id": "required transform id", "entity_id": "required entity id"},
        True,
    ),
    AgentTool(
        "list_audit_events",
        "Read recent auditable investigation activity.",
        {"case_id": "optional id; omit to use active investigation", "limit": "1 to 100"},
    ),
)

_TOOL_BY_NAME = {tool.name: tool for tool in AGENT_TOOLS}

_WRITE_INTENT = {
    "create_investigation": r"\b(crea(?:r|me)?|create|new|nueva?|inicia|start)\b",
    "update_investigation": r"\b(actualiza|actualizar|cambia|cambiar|marca|editar?|update|change|set|archive|pausa|cierra)\b",
    "add_entity": r"\b(añade|añadir|agrega|agregar|crea|create|add|incorpora)\b",
    "add_relationship": r"\b(conecta|conectar|relaciona|relacionar|vincula|link|connect|add)\b",
    "run_osint_lookup": r"\b(busca|buscar|consulta|consultar|investiga|investigar|lookup|search|run|ejecuta)\b",
    "promote_osint_result": r"\b(promueve|promover|añade|agrega|sube|promote|add)\b",
    "generate_report": r"\b(genera|generar|crea|crear|generate|create|haz)\b",
    "run_transform": r"\b(ejecuta|ejecutar|corre|run|aplica|aplicar)\b",
}


def prefers_spanish(text: str) -> bool:
    normalized = f" {text.casefold()} "
    return bool(
        re.search(r"[áéíóúñ¿¡]", normalized)
        or re.search(
            r"\b(hola|buenas|gracias|por favor|crea|crear|investigaci[oó]n|investigaciones|caso|casos|lista|mis|"
            r"busca|investiga|agrega|añade|dime|quiero|necesito|sobre|herramientas|fuentes|evidencia)\b",
            normalized,
        )
    )


def enabled_agent_tools(configured: list[str] | None) -> list[AgentTool]:
    """An empty preference means all built-in tools, while a non-empty list is an allowlist."""
    if not configured:
        return list(AGENT_TOOLS)
    allowed = set(configured)
    return [tool for tool in AGENT_TOOLS if tool.name in allowed]


def agent_tool_catalog(configured: list[str] | None = None) -> list[dict[str, Any]]:
    return [tool.prompt_dict() for tool in enabled_agent_tools(configured)]


def _explicit_write_requested(tool_name: str, user_text: str) -> bool:
    """Best-effort check that the user's own words asked for a change.

    This bounds an over-eager model, and it is deliberately not a security
    boundary — say so plainly rather than let a reader infer more from it than
    it delivers. It is keyword matching over natural language: it does not
    understand negation, so "no agregues nada al grafo" contains "agrega" and
    passes, and several patterns share ordinary verbs, so one message can
    satisfy more than one write. What actually contains a wrong call is the
    layer underneath — the tool allowlist excludes evidence mutation, deletion
    and report approval, every call runs as the real authenticated user through
    the normal route, and each write lands in the audit trail.

    A mutating tool with no pattern registered is refused rather than allowed.
    The rest of this codebase fails closed, and the alternative here is that
    adding a tool to AGENT_TOOLS while forgetting _WRITE_INTENT silently grants
    it unconditional write access.
    """
    if not (pattern := _WRITE_INTENT.get(tool_name)):
        return False
    return re.search(pattern, user_text, flags=re.IGNORECASE) is not None


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _summary(tool: str, result: Any, *, spanish: bool) -> str:
    if spanish:
        if tool == "list_investigations":
            return f"Encontré {len(result)} investigación(es) accesible(s)."
        if tool == "create_investigation":
            return f"Creé la investigación '{result.title}' ({result.id})."
        if tool == "update_investigation":
            return f"Actualicé la investigación '{result.title}' ({result.id})."
        if tool == "get_investigation":
            return f"Abrí la investigación '{result.title}'."
        if tool == "get_investigation_overview":
            return f"Cargué el resumen de '{result.get('title', 'la investigación')}'."
        if tool == "list_graph":
            return f"Cargué {len(result.nodes)} entidades y {len(result.edges)} relaciones."
        if tool == "add_entity":
            return f"Añadí la entidad '{result.label}' al grafo ({result.id})."
        if tool == "add_relationship":
            return f"Añadí la relación '{result.label}' ({result.id})."
        if tool == "list_sources":
            return f"Encontré {len(result)} fuente(s)."
        if tool == "list_evidence":
            return f"Encontré {len(result)} elemento(s) de evidencia."
        if tool == "get_custody":
            return "Cargué el estado de cadena de custodia."
        if tool == "list_osint_history":
            return f"Encontré {len(result)} consulta(s) OSINT guardada(s)."
        if tool == "run_osint_lookup":
            return f"Guardé la consulta OSINT {result.query_id} con {len(result.findings)} hallazgo(s)."
        if tool == "promote_osint_result":
            return f"Promoví {len(result.entities)} entidades y {len(result.relationships)} relaciones al grafo."
        if tool == "list_reports":
            return f"Encontré {len(result)} reporte(s)."
        if tool == "generate_report":
            return f"Generé el reporte '{result.title}' ({result.id})."
        if tool == "list_transforms":
            return f"Encontré {result.get('count', 0)} transformaciones instaladas."
        if tool == "run_transform":
            return result.summary
        if tool == "list_audit_events":
            return f"Cargué {len(result)} evento(s) de auditoría."
        return f"{tool} terminó correctamente."
    if tool == "list_investigations":
        return f"Found {len(result)} accessible investigation(s)."
    if tool == "create_investigation":
        return f"Created investigation '{result.title}' ({result.id})."
    if tool == "update_investigation":
        return f"Updated investigation '{result.title}' ({result.id})."
    if tool == "get_investigation":
        return f"Opened investigation '{result.title}'."
    if tool == "get_investigation_overview":
        return f"Loaded overview for '{result.get('title', 'investigation')}'."
    if tool == "list_graph":
        return f"Loaded {len(result.nodes)} entities and {len(result.edges)} relationships."
    if tool == "add_entity":
        return f"Added graph entity '{result.label}' ({result.id})."
    if tool == "add_relationship":
        return f"Added relationship '{result.label}' ({result.id})."
    if tool == "list_sources":
        return f"Found {len(result)} source(s)."
    if tool == "list_evidence":
        return f"Found {len(result)} evidence item(s)."
    if tool == "get_custody":
        return "Loaded chain-of-custody status."
    if tool == "list_osint_history":
        return f"Found {len(result)} OSINT query record(s)."
    if tool == "run_osint_lookup":
        return f"Saved OSINT lookup {result.query_id} with {len(result.findings)} finding(s)."
    if tool == "promote_osint_result":
        return f"Promoted {len(result.entities)} entities and {len(result.relationships)} relationships."
    if tool == "list_reports":
        return f"Found {len(result)} report(s)."
    if tool == "generate_report":
        return f"Generated report '{result.title}' ({result.id})."
    if tool == "list_transforms":
        return f"Found {result.get('count', 0)} installed transform(s)."
    if tool == "run_transform":
        return result.summary
    if tool == "list_audit_events":
        return f"Loaded {len(result)} audit event(s)."
    return f"{tool} completed."


def _case_id(arguments: dict[str, Any], active_case_id: str | None) -> str:
    value = str(arguments.get("case_id") or active_case_id or "").strip()
    if not value:
        raise ValueError("This tool needs an investigation. Open one or provide case_id.")
    return value


async def execute_agent_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    user_text: str,
    active_case_id: str | None,
    enabled: list[str] | None,
    current: CurrentUser,
    session: AsyncSession,
) -> AgentToolResult:
    tool = _TOOL_BY_NAME.get(tool_name)
    allowed = {item.name for item in enabled_agent_tools(enabled)}
    if tool is None:
        return AgentToolResult(tool_name, arguments, False, f"Unknown tool: {tool_name}")
    if tool_name not in allowed:
        return AgentToolResult(tool_name, arguments, False, f"Tool '{tool_name}' is disabled in Local Models.")
    if tool.mutating and not _explicit_write_requested(tool_name, user_text):
        return AgentToolResult(
            tool_name,
            arguments,
            False,
            "The action was not executed because the user's latest message did not explicitly request this write.",
        )

    try:
        if tool_name == "list_investigations":
            value = await cases.list_cases(current, session)
        elif tool_name == "get_investigation":
            value = await cases.get_case(_case_id(arguments, active_case_id), current, session)
        elif tool_name == "create_investigation":
            title = str(arguments.get("title") or "").strip()
            default_summary = (
                f"Investigación autorizada sobre {title}."
                if prefers_spanish(user_text)
                else f"Authorized investigation focused on {title}."
            )
            payload = CaseCreate(
                title=title,
                summary=str(arguments.get("summary") or default_summary).strip(),
                legal_basis=str(arguments.get("legal_basis") or "Authorized research").strip(),
                scope_statement=str(
                    arguments.get("scope_statement")
                    or "Bounded authorized investigation using user-provided and public-source information."
                ).strip(),
                priority=str(arguments.get("priority") or "normal").lower(),
                tags=arguments.get("tags") if isinstance(arguments.get("tags"), list) else [],
                notes=str(arguments.get("notes") or "").strip(),
            )
            value = await cases.create_case_endpoint(payload, current, session)
        elif tool_name == "update_investigation":
            case_id = _case_id(arguments, active_case_id)
            changes = {
                key: arguments[key]
                for key in ("title", "summary", "legal_basis", "scope_statement", "status", "priority", "tags", "notes")
                if key in arguments and arguments[key] is not None
            }
            value = await cases.update_case(case_id, CaseUpdate.model_validate(changes), current, session)
        elif tool_name == "get_investigation_overview":
            value = await operations.get_case_monitor(_case_id(arguments, active_case_id), current, session)
        elif tool_name == "list_graph":
            value = await graph.get_graph(_case_id(arguments, active_case_id), current, session)
        elif tool_name == "add_entity":
            value = await graph.create_graph_entity(
                GraphEntityCreate(
                    case_id=_case_id(arguments, active_case_id),
                    label=str(arguments.get("label") or ""),
                    type=str(arguments.get("type") or "note"),
                    confidence=float(arguments.get("confidence", 0.68)),
                    connect_to_id=arguments.get("connect_to_id") or None,
                    relation_label=str(arguments.get("relation_label") or "analyst_linked"),
                ),
                current,
                session,
            )
        elif tool_name == "add_relationship":
            value = await graph.create_graph_relationship(
                GraphRelationshipCreate(
                    case_id=_case_id(arguments, active_case_id),
                    source_id=str(arguments.get("source_id") or ""),
                    target_id=str(arguments.get("target_id") or ""),
                    label=str(arguments.get("label") or ""),
                    confidence=float(arguments.get("confidence", 0.68)),
                ),
                current,
                session,
            )
        elif tool_name == "list_sources":
            value = await sources.list_sources(_case_id(arguments, active_case_id), current, session)
        elif tool_name == "list_evidence":
            value = await evidence.list_evidence(_case_id(arguments, active_case_id), current, session)
        elif tool_name == "get_custody":
            value = await custody.get_custody_report(_case_id(arguments, active_case_id), current, session)
        elif tool_name == "list_osint_history":
            value = await osint.osint_history(_case_id(arguments, active_case_id), current, session)
        elif tool_name == "run_osint_lookup":
            value = await osint.osint_lookup(
                OsintLookupRequest(
                    case_id=_case_id(arguments, active_case_id),
                    value=str(arguments.get("value") or ""),
                ),
                current,
                session,
            )
        elif tool_name == "promote_osint_result":
            value = await osint.promote_osint_query(str(arguments.get("query_id") or ""), current, session)
        elif tool_name == "list_reports":
            value = await reports.list_reports(_case_id(arguments, active_case_id), current, session)
        elif tool_name == "generate_report":
            value = await reports.generate_report(
                _case_id(arguments, active_case_id),
                ReportGenerateRequest(
                    title=str(arguments.get("title") or "Investigation report"),
                    format=str(arguments.get("format") or "markdown").lower(),
                    sections=arguments.get("sections")
                    or ["overview", "entities", "relationships", "sources", "evidence"],
                    methodology=str(arguments.get("methodology") or ""),
                    limitations=str(arguments.get("limitations") or ""),
                ),
                current,
                session,
            )
        elif tool_name == "list_transforms":
            value = await transforms.list_transforms(input=None, enabled_only=False)
        elif tool_name == "run_transform":
            value = await transforms.run_transform(
                str(arguments.get("transform_id") or ""),
                TransformRunRequest(entity_id=str(arguments.get("entity_id") or "")),
                current,
                session,
            )
        elif tool_name == "list_audit_events":
            value = await operations.list_audit_events(
                _case_id(arguments, active_case_id) if (arguments.get("case_id") or active_case_id) else None,
                max(1, min(int(arguments.get("limit", 30)), 100)),
                current,
                session,
            )
        else:  # pragma: no cover - registry and dispatcher are deliberately exhaustive
            raise ValueError(f"Tool '{tool_name}' has no executor")
        return AgentToolResult(
            tool_name,
            arguments,
            True,
            _summary(tool_name, value, spanish=prefers_spanish(user_text)),
            _jsonable(value),
        )
    except HTTPException as exc:
        await session.rollback()
        detail = exc.detail if isinstance(exc.detail, str) else "The application rejected the tool request."
        return AgentToolResult(tool_name, arguments, False, detail)
    except (TypeError, ValueError) as exc:
        await session.rollback()
        return AgentToolResult(tool_name, arguments, False, str(exc)[:500])
