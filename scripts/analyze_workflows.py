"""
ComfyUI Workflow Analyzer
Parses all workflow JSON files (templates + blueprints) and extracts:
- Node types, counts, connections
- Data type flows (MODEL, CLIP, VAE, CONDITIONING, LATENT, IMAGE, MASK, VIDEO)
- Models referenced
- Entry/exit points (LoadImage/SaveImage etc.)
- Custom node detection
- Index.json metadata mapping (tags, category, models)
"""

import json
import os
import sys
from pathlib import Path
from collections import Counter, defaultdict


def load_index_metadata(templates_dir: Path) -> dict:
    """Load index.json to get metadata (tags, category, models) per template."""
    index_path = templates_dir / "index.json"
    metadata = {}
    if not index_path.exists():
        return metadata

    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    for module in index_data:
        module_name = module.get("moduleName", "")
        category = module.get("category", "")
        title = module.get("title", "")
        for tmpl in module.get("templates", []):
            name = tmpl.get("name", "")
            metadata[name] = {
                "module": module_name,
                "category": category,
                "module_title": title,
                "title": tmpl.get("title", ""),
                "description": tmpl.get("description", ""),
                "tags": tmpl.get("tags", []),
                "models": tmpl.get("models", []),
                "open_source": tmpl.get("openSource", None),
                "size": tmpl.get("size", 0),
                "vram": tmpl.get("vram", 0),
                "usage": tmpl.get("usage", 0),
                "requires_custom_nodes": tmpl.get("requiresCustomNodes", []),
                "io_inputs": [
                    inp.get("nodeType", "") for inp in tmpl.get("io", {}).get("inputs", [])
                ],
                "io_outputs": [
                    out.get("nodeType", "") for out in tmpl.get("io", {}).get("outputs", [])
                ],
            }
    return metadata


def analyze_workflow(filepath: Path) -> dict:
    """Analyze a single workflow JSON file."""
    result = {
        "file": filepath.name,
        "folder": filepath.parent.name,
        "parse_error": None,
        "node_count": 0,
        "link_count": 0,
        "node_types": [],
        "node_type_counts": {},
        "data_type_flows": [],
        "data_types_used": [],
        "models_referenced": [],
        "entry_nodes": [],
        "exit_nodes": [],
        "custom_nodes": [],
        "core_nodes": [],
        "has_subgraphs": False,
        "group_names": [],
    }

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        result["parse_error"] = str(e)
        return result

    if not isinstance(data, dict):
        result["parse_error"] = f"Root JSON is not a dictionary but {type(data).__name__}"
        return result

    nodes = data.get("nodes", [])
    links = data.get("links", [])
    groups = data.get("groups", [])
    definitions = data.get("definitions", {})

    result["node_count"] = len(nodes)
    result["link_count"] = len(links)
    result["has_subgraphs"] = bool(
        definitions.get("subgraphs", []) if isinstance(definitions, dict) else False
    )
    result["group_names"] = [g.get("title", "") for g in groups if g.get("title")]

    # Build node ID -> type map
    node_map = {}
    type_counter = Counter()
    entry_types = {
        "LoadImage", "LoadVideo", "LoadAudio",
        "VHS_LoadVideo", "VHS_LoadVideoPath",
    }
    exit_types = {
        "SaveImage", "PreviewImage", "SaveVideo", "VHS_VideoCombine",
        "SaveAnimatedWEBP", "SaveAnimatedPNG", "SaveAudio",
    }

    for node in nodes:
        nid = node.get("id")
        ntype = node.get("type", "unknown")

        # Some blueprints use UUID-style type IDs for subgraphs
        if len(ntype) > 30 and "-" in ntype:
            title = node.get("title", ntype)
            ntype = f"subgraph:{title}"

        node_map[nid] = {
            "type": ntype,
            "inputs": node.get("inputs", []),
            "outputs": node.get("outputs", []),
        }
        type_counter[ntype] += 1

        # Detect entry/exit
        base_type = ntype.split(":")[-1] if ":" in ntype else ntype
        if base_type in entry_types:
            result["entry_nodes"].append(ntype)
        if base_type in exit_types:
            result["exit_nodes"].append(ntype)

        # Extract referenced models
        props = node.get("properties", {})
        if isinstance(props, dict):
            for model_info in props.get("models", []):
                if isinstance(model_info, dict):
                    model_name = model_info.get("name", "")
                    if model_name:
                        result["models_referenced"].append(model_name)

            # Detect core vs custom
            cnr_id = props.get("cnr_id", "")
            if cnr_id and cnr_id != "comfy-core":
                result["custom_nodes"].append(
                    {"type": ntype, "cnr_id": cnr_id}
                )
            elif cnr_id == "comfy-core":
                result["core_nodes"].append(ntype)

    result["node_types"] = list(type_counter.keys())
    result["node_type_counts"] = dict(type_counter)

    # Analyze links for data type flows
    data_type_flows = []
    data_types_used = set()

    for link in links:
        if isinstance(link, list) and len(link) >= 6:
            # [linkId, fromNodeId, fromSlot, toNodeId, toSlot, dataType]
            _, from_id, from_slot, to_id, to_slot, dtype = link[:6]
            from_type = node_map.get(from_id, {}).get("type", f"node_{from_id}")
            to_type = node_map.get(to_id, {}).get("type", f"node_{to_id}")
            data_type_flows.append({
                "from": from_type,
                "to": to_type,
                "data_type": dtype,
            })
            if dtype:
                data_types_used.add(dtype)

    result["data_type_flows"] = data_type_flows
    result["data_types_used"] = sorted(list(data_types_used))

    # Deduplicate lists
    result["entry_nodes"] = list(set(result["entry_nodes"]))
    result["exit_nodes"] = list(set(result["exit_nodes"]))
    result["models_referenced"] = list(set(result["models_referenced"]))
    result["core_nodes"] = list(set(result["core_nodes"]))

    # Deduplicate custom nodes by type
    seen = set()
    unique_custom = []
    for cn in result["custom_nodes"]:
        key = cn["type"]
        if key not in seen:
            seen.add(key)
            unique_custom.append(cn)
    result["custom_nodes"] = unique_custom

    return result


def generate_summary(results: list) -> dict:
    """Generate aggregate summary statistics."""
    total = len(results)
    errors = [r for r in results if r["parse_error"]]
    templates = [r for r in results if r["folder"] == "templates"]
    blueprints = [r for r in results if r["folder"] == "blueprints"]

    all_node_types = Counter()
    all_data_types = Counter()
    all_models = Counter()
    all_custom_cnr = Counter()
    category_counter = Counter()

    for r in results:
        for ntype, cnt in r.get("node_type_counts", {}).items():
            all_node_types[ntype] += cnt
        for dtype in r.get("data_types_used", []):
            all_data_types[dtype] += 1
        for model in r.get("models_referenced", []):
            all_models[model] += 1
        for cn in r.get("custom_nodes", []):
            all_custom_cnr[cn["cnr_id"]] += 1

    return {
        "total_workflows": total,
        "templates_count": len(templates),
        "blueprints_count": len(blueprints),
        "parse_errors": len(errors),
        "error_files": [e["file"] for e in errors],
        "top_30_node_types": dict(all_node_types.most_common(30)),
        "data_types_frequency": dict(all_data_types.most_common()),
        "top_20_models": dict(all_models.most_common(20)),
        "top_20_custom_node_packages": dict(all_custom_cnr.most_common(20)),
        "avg_nodes_per_workflow": round(
            sum(r["node_count"] for r in results) / max(total, 1), 1
        ),
        "avg_links_per_workflow": round(
            sum(r["link_count"] for r in results) / max(total, 1), 1
        ),
        "workflows_with_subgraphs": sum(
            1 for r in results if r.get("has_subgraphs")
        ),
    }


def main():
    repo_root = Path(__file__).parent.parent
    templates_dir = repo_root / "templates"
    blueprints_dir = repo_root / "blueprints"
    output_dir = Path(__file__).parent

    print("=== ComfyUI Workflow Analyzer ===")

    # Load index metadata
    print("Loading index.json metadata...")
    index_meta = load_index_metadata(templates_dir)
    print(f"  Found metadata for {len(index_meta)} templates in index.json")

    # Collect all JSON files
    json_files = []
    for d in [templates_dir, blueprints_dir]:
        if d.exists():
            for f in sorted(d.glob("*.json")):
                if f.name not in ("index.json", "index.schema.json"):
                    json_files.append(f)

    print(f"Found {len(json_files)} workflow JSON files to analyze")

    # Analyze each file
    results = []
    for i, filepath in enumerate(json_files):
        if (i + 1) % 100 == 0:
            print(f"  Analyzing... {i + 1}/{len(json_files)}")
        r = analyze_workflow(filepath)

        # Merge index metadata if available
        stem = filepath.stem
        meta = index_meta.get(stem, {})
        r["index_meta"] = meta if meta else None

        results.append(r)

    print(f"Analysis complete: {len(results)} files processed")

    # Generate summary
    summary = generate_summary(results)

    # Write output
    output = {
        "summary": summary,
        "workflows": results,
    }

    output_path = output_dir / "analysis_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_path}")
    print(f"\n--- Summary ---")
    print(f"Total workflows: {summary['total_workflows']}")
    print(f"  Templates: {summary['templates_count']}")
    print(f"  Blueprints: {summary['blueprints_count']}")
    print(f"  Parse errors: {summary['parse_errors']}")
    if summary['error_files']:
        print(f"  Error files: {summary['error_files'][:5]}...")
    print(f"Avg nodes/workflow: {summary['avg_nodes_per_workflow']}")
    print(f"Avg links/workflow: {summary['avg_links_per_workflow']}")
    print(f"Workflows with subgraphs: {summary['workflows_with_subgraphs']}")
    print(f"\nTop 10 node types:")
    for ntype, cnt in list(summary['top_30_node_types'].items())[:10]:
        print(f"  {ntype}: {cnt}")
    print(f"\nData types used (frequency):")
    for dtype, cnt in summary['data_types_frequency'].items():
        print(f"  {dtype}: {cnt} workflows")
    print(f"\nTop 10 models referenced:")
    for model, cnt in list(summary['top_20_models'].items())[:10]:
        print(f"  {model}: {cnt}")
    print(f"\nTop 10 custom node packages:")
    for pkg, cnt in list(summary['top_20_custom_node_packages'].items())[:10]:
        print(f"  {pkg}: {cnt}")


if __name__ == "__main__":
    main()
