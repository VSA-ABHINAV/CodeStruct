"""Advanced Architecture Module (Phase 19).

AST + LLM Component Clustering and Architecture Narrative Generation.
Implements:
- Prompt construction from graph summary, metrics, and detected patterns.
- LLM invocation via qwen_client.query_qwen.
- Strict non-negotiable validation layer:
  1. Every member_symbol_ids entry must be an actual node id in the current graph.
     Any invented id is dropped and logged, never shown to the user as real.
  2. Every real symbol must appear either in some component or in unclustered_symbol_ids.
     Nothing is silently lost.
  3. Malformed LLM output triggers one retry with a stricter prompt, then a clear UI error.
  4. Dropped invented symbols confirm the safety net works.
- Caching layer: key = SHA-256 hash of graph nodes, edges, patterns.
"""

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.patterns import detect_patterns
from backend.qwen_client import query_qwen

logger = logging.getLogger("codestruct.advanced_architecture")

# In-memory cache for advanced architecture responses: hash -> response dict
_ARCH_CACHE: Dict[str, Dict[str, Any]] = {}


class MalformedLLMOutputError(Exception):
    """Raised when LLM output cannot be parsed as JSON or violates the required schema."""
    pass


def clear_architecture_cache() -> None:
    """Clear the in-memory architecture cache."""
    global _ARCH_CACHE
    _ARCH_CACHE.clear()


def get_architecture_cache_size() -> int:
    """Return the number of cached architecture responses."""
    return len(_ARCH_CACHE)


def compute_graph_hash(graph: Dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash representing the structural state of the graph."""
    nodes = [
        (n.get("id"), n.get("name"), n.get("kind"), n.get("module"), n.get("file_path"))
        for n in graph.get("nodes", [])
    ]
    nodes.sort(key=lambda x: str(x[0]))

    edges = [
        (e.get("source"), e.get("target"), e.get("type"))
        for e in graph.get("edges", [])
    ]
    edges.sort(key=lambda x: (str(x[0]), str(x[1]), str(x[2])))

    patterns = [
        (p.get("pattern"), p.get("symbol_id"), p.get("evidence"))
        for p in graph.get("patterns", [])
    ]
    patterns.sort(key=lambda x: (str(x[0]), str(x[1])))

    canonical_data = {
        "nodes": nodes,
        "edges": edges,
        "patterns": patterns,
        "project_root": str(graph.get("project_root", "")),
    }

    raw_bytes = json.dumps(canonical_data, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_symbol_metrics(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Compute fan-in, fan-out, and instability metrics for all nodes in the graph."""
    node_map = {n["id"]: n for n in graph.get("nodes", [])}
    fan_in: Dict[str, int] = {nid: 0 for nid in node_map}
    fan_out: Dict[str, int] = {nid: 0 for nid in node_map}

    for edge in graph.get("edges", []):
        src = edge.get("source")
        tgt = edge.get("target")
        if src in fan_out:
            fan_out[src] += 1
        if tgt in fan_in:
            fan_in[tgt] += 1

    metrics: Dict[str, Dict[str, Any]] = {}
    for nid in node_map:
        fi = fan_in[nid]
        fo = fan_out[nid]
        total = fi + fo
        instability = round(fo / total, 2) if total > 0 else 0.0
        metrics[nid] = {
            "fan_in": fi,
            "fan_out": fo,
            "instability": instability,
        }
    return metrics


def build_architecture_prompts(graph: Dict[str, Any]) -> Tuple[str, str]:
    """Construct (system_prompt, user_prompt) from the structural graph summary."""
    system_prompt = (
        "You are CodeStruct Architecture Analyst, a senior software architect specializing in "
        "structural code analysis, component clustering, and architectural narrative generation.\n"
        "Your task is to analyze the AST-derived symbols, relationships, metrics, and detected design patterns "
        "of a software project and cluster the symbols into meaningful high-level architectural components.\n"
        "You must output ONLY valid JSON adhering strictly to the requested schema, referencing ONLY real symbol IDs."
    )

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    summary = graph.get("summary", {})
    metrics = compute_symbol_metrics(graph)

    # Patterns
    patterns = graph.get("patterns")
    if patterns is None:
        patterns = detect_patterns(graph, graph.get("_ast_trees", {}))
        graph["patterns"] = patterns

    lines: List[str] = []
    lines.append("# CodeStruct Project Architectural Summary\n")
    lines.append(f"Node count: {summary.get('node_count', len(nodes))}")
    lines.append(f"Edge count: {summary.get('edge_count', len(edges))}")
    lines.append(f"Module count: {summary.get('module_count', 0)}")
    lines.append(f"Class count: {summary.get('class_count', 0)}")
    lines.append(f"Function count: {summary.get('function_count', 0)}")
    lines.append(f"Method count: {summary.get('method_count', 0)}\n")

    lines.append("## Symbols (Real Graph Nodes):")
    for n in nodes:
        nid = n.get("id")
        m = metrics.get(nid, {"fan_in": 0, "fan_out": 0, "instability": 0.0})
        lines.append(
            f"- ID: {nid} | Name: {n.get('name')} | Kind: {n.get('kind')} | "
            f"Module: {n.get('module')} | File: {n.get('file_path')} | "
            f"Fan-In: {m['fan_in']} | Fan-Out: {m['fan_out']} | Instability: {m['instability']}"
        )

    lines.append("\n## Relationships (Real Graph Edges):")
    for e in edges:
        lines.append(f"- {e.get('source')} --[{e.get('type')}]--> {e.get('target')}")

    if patterns:
        lines.append("\n## Detected Design Patterns:")
        for p in patterns:
            lines.append(f"- {p.get('pattern')} on symbol '{p.get('symbol_id')}': {p.get('evidence')}")

    lines.append("\n## Instructions:")
    lines.append(
        "Cluster the symbols into coherent architectural components (e.g. Domain Models, "
        "Services / Business Logic, Entrypoint / Orchestration, Utilities / Creation).\n"
        "CRITICAL RULES:\n"
        "1. Every ID listed in 'member_symbol_ids' MUST be an exact symbol ID from the Symbols list above. "
        "Do NOT invent, fabricate, or truncate any symbol IDs.\n"
        "2. Any symbol not grouped into a component should be listed in 'unclustered_symbol_ids'.\n"
        "3. Provide a high-level project narrative summarizing the system architecture.\n"
        "4. Output MUST be a single valid JSON object strictly matching this schema with no markdown or extra commentary:\n"
        "{\n"
        '  "components": [\n'
        "    {\n"
        '      "component_id": "comp_1",\n'
        '      "name": "Component Name",\n'
        '      "member_symbol_ids": ["symbol_id_1", "symbol_id_2"],\n'
        '      "role": "Architectural Role Label",\n'
        '      "rationale": "Natural language justification for grouping these symbols"\n'
        "    }\n"
        "  ],\n"
        '  "unclustered_symbol_ids": ["symbol_id_3"],\n'
        '  "narrative": "A concise architectural narrative explaining how the components interact."\n'
        "}"
    )

    user_prompt = "\n".join(lines)
    return system_prompt, user_prompt


def build_stricter_retry_prompt(initial_prompt: str, previous_output: str, error_msg: str) -> str:
    """Build a stricter prompt when the initial LLM output fails schema validation."""
    snippet = previous_output.strip()
    if len(snippet) > 400:
        snippet = snippet[:400] + "... [truncated]"

    return (
        "CRITICAL ERROR: Your previous response was rejected by the schema validator.\n"
        f"Validation Error: {error_msg}\n"
        f"Rejected snippet:\n{snippet}\n\n"
        "You MUST return ONLY a single strictly valid JSON object. Do NOT include markdown code blocks "
        "(do NOT use ```json), do NOT include introductory or concluding text.\n"
        "The root must be a JSON object with EXACT keys: 'components', 'unclustered_symbol_ids', 'narrative'.\n"
        "All IDs in 'member_symbol_ids' must strictly come from the provided symbol IDs list.\n\n"
        f"{initial_prompt}"
    )


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Parse JSON from raw LLM output, stripping markdown codeblocks if necessary."""
    raw = text.strip()

    # 1. Direct parse attempt
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2. Strip ```json ... ``` or ``` ... ```
    fence_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
    match = fence_pattern.search(raw)
    if match:
        content = match.group(1).strip()
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 3. Search for outermost matching { ... }
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = raw[first_brace : last_brace + 1].strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise MalformedLLMOutputError(
        f"LLM output could not be parsed as a valid JSON object. Raw output starts with: {raw[:150]}"
    )


def validate_clustering(
    raw_output: Union[str, Dict[str, Any]],
    real_node_ids: Set[str],
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate clustering output according to Phase 19 non-negotiable rules.
    
    Returns:
        Tuple of (validated_data_dict, dropped_invented_ids_list)
        
    Raises:
        MalformedLLMOutputError: If output cannot be parsed or lacks required fields.
    """
    if isinstance(raw_output, str):
        data = extract_json_from_text(raw_output)
    elif isinstance(raw_output, dict):
        data = raw_output
    else:
        raise MalformedLLMOutputError(f"Expected str or dict, got {type(raw_output).__name__}")

    # Check top-level required fields
    if "components" not in data or not isinstance(data["components"], list):
        raise MalformedLLMOutputError("Output missing required 'components' list.")

    if "narrative" not in data or not isinstance(data["narrative"], str):
        raise MalformedLLMOutputError("Output missing required 'narrative' string.")

    components_raw = data["components"]
    dropped_invented_ids: List[str] = []
    valid_components: List[Dict[str, Any]] = []
    clustered_symbol_ids: Set[str] = set()

    for idx, comp in enumerate(components_raw):
        if not isinstance(comp, dict):
            raise MalformedLLMOutputError(f"Component at index {idx} is not an object: {comp}")

        # Required fields in each component
        for req_field in ("component_id", "name", "member_symbol_ids", "role", "rationale"):
            if req_field not in comp:
                raise MalformedLLMOutputError(
                    f"Component at index {idx} missing required field '{req_field}': {comp}"
                )

        if not isinstance(comp["member_symbol_ids"], list):
            raise MalformedLLMOutputError(
                f"Component at index {idx} 'member_symbol_ids' must be a list."
            )

        valid_members: List[str] = []
        for mem in comp["member_symbol_ids"]:
            mem_id = str(mem).strip()
            if mem_id in real_node_ids:
                valid_members.append(mem_id)
                clustered_symbol_ids.add(mem_id)
            else:
                dropped_invented_ids.append(mem_id)
                logger.warning(
                    f"[Validation Layer] Dropping invented symbol ID: '{mem_id}' "
                    f"from component '{comp.get('name', idx)}'"
                )

        comp_copy = {
            "component_id": str(comp["component_id"]).strip() or f"comp_{idx + 1}",
            "name": str(comp["name"]).strip(),
            "member_symbol_ids": valid_members,
            "role": str(comp["role"]).strip(),
            "rationale": str(comp["rationale"]).strip(),
        }
        valid_components.append(comp_copy)

    # Validate unclustered_symbol_ids
    raw_unclustered = data.get("unclustered_symbol_ids", [])
    if isinstance(raw_unclustered, list):
        for unclustered_id in raw_unclustered:
            u_str = str(unclustered_id).strip()
            if u_str not in real_node_ids:
                dropped_invented_ids.append(u_str)
                logger.warning(
                    f"[Validation Layer] Dropping invented symbol ID from unclustered list: '{u_str}'"
                )

    # Requirement 2: Every real symbol must appear either in some component or in unclustered_symbol_ids
    # Nothing is silently lost!
    all_unclustered_set: Set[str] = set()
    if isinstance(raw_unclustered, list):
        for u in raw_unclustered:
            u_str = str(u).strip()
            if u_str in real_node_ids and u_str not in clustered_symbol_ids:
                all_unclustered_set.add(u_str)

    # Any real node not clustered is added to unclustered
    for node_id in real_node_ids:
        if node_id not in clustered_symbol_ids:
            all_unclustered_set.add(node_id)

    unclustered_symbol_ids = sorted(list(all_unclustered_set))

    validated_result = {
        "components": valid_components,
        "unclustered_symbol_ids": unclustered_symbol_ids,
        "narrative": str(data["narrative"]).strip(),
    }
    return validated_result, dropped_invented_ids


def cluster_architecture(
    graph: Dict[str, Any],
    force_refresh: bool = False,
    ollama_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Execute LLM component clustering with strict validation, retry, and caching.
    
    Args:
        graph: Analyzed project graph dictionary.
        force_refresh: If True, bypass in-memory cache and re-query LLM.
        ollama_url: Optional Ollama URL.
        model: Optional model name.
        timeout: Timeout in seconds for LLM call (default 30.0s).
        
    Returns:
        Validated dictionary conforming to AdvancedArchitectureResponse schema.
    """
    cache_key = compute_graph_hash(graph)
    if not force_refresh and cache_key in _ARCH_CACHE:
        logger.info(f"[Advanced Architecture] Cache hit for hash {cache_key[:8]}")
        return _ARCH_CACHE[cache_key]

    real_node_ids: Set[str] = {n["id"] for n in graph.get("nodes", [])}
    if not real_node_ids:
        empty_response = {
            "components": [],
            "unclustered_symbol_ids": [],
            "narrative": "No symbols available in the project graph to cluster.",
        }
        _ARCH_CACHE[cache_key] = empty_response
        return empty_response

    system_prompt, user_prompt = build_architecture_prompts(graph)

    # Initial LLM call
    logger.info("[Advanced Architecture] Querying LLM for component clustering...")
    reply = query_qwen(
        message=user_prompt,
        system_prompt=system_prompt,
        timeout=timeout,
        ollama_url=ollama_url,
        model=model,
    )

    if reply.startswith("[Error]"):
        raise RuntimeError(f"Ollama clustering request failed: {reply}")

    try:
        validated_data, dropped = validate_clustering(reply, real_node_ids)
        if dropped:
            logger.info(
                f"[Advanced Architecture] Safety net confirmed: dropped {len(dropped)} invented IDs on initial call: {dropped}"
            )
    except MalformedLLMOutputError as initial_err:
        logger.warning(
            f"[Advanced Architecture] Initial LLM output malformed ({initial_err}). Retrying once with stricter prompt..."
        )
        stricter_user_prompt = build_stricter_retry_prompt(user_prompt, reply, str(initial_err))
        stricter_system_prompt = (
            "You are CodeStruct Architecture Analyst. Your output was malformed. "
            "You MUST output ONLY a valid JSON object matching the schema with no extra text or fences."
        )

        retry_reply = query_qwen(
            message=stricter_user_prompt,
            system_prompt=stricter_system_prompt,
            timeout=timeout,
            ollama_url=ollama_url,
            model=model,
        )

        if retry_reply.startswith("[Error]"):
            raise RuntimeError(f"Ollama clustering retry failed: {retry_reply}")

        validated_data, dropped = validate_clustering(retry_reply, real_node_ids)
        if dropped:
            logger.info(
                f"[Advanced Architecture] Safety net confirmed: dropped {len(dropped)} invented IDs on retry: {dropped}"
            )

    # Cache and return
    _ARCH_CACHE[cache_key] = validated_data
    return validated_data

