"""
ComfyUI Workflow Generator & Customizer
Loads a template workflow JSON (from templates/ or blueprints/),
applies dynamic parameter updates, and saves as a customized output JSON (Editor Format).
Supports automatic helper flags for common updates (prompt, negative_prompt, model, seed).
"""

import argparse
import json
import os
import sys
from pathlib import Path


def find_template(name: str, search_dirs: list) -> Path:
    """Search for the template file in multiple directories."""
    for d in search_dirs:
        if d.exists():
            path = d / name
            if path.exists():
                return path
            # Try appending .json extension if not present
            if not name.endswith(".json"):
                path_json = d / f"{name}.json"
                if path_json.exists():
                    return path_json
    return None


def apply_smart_updates(data: dict, prompt: str, negative: str, checkpoint: str, seed: int) -> dict:
    """Helper to automatically find and update common nodes by type."""
    nodes = data.get("nodes", [])
    
    # 1. Update Checkpoint
    if checkpoint:
        checkpoint_updated = False
        for node in nodes:
            ntype = node.get("type", "")
            if ntype in ("CheckpointLoaderSimple", "UNETLoader", "CheckpointLoader"):
                node["widgets_values"] = node.get("widgets_values", [])
                if node["widgets_values"]:
                    node["widgets_values"][0] = checkpoint
                    checkpoint_updated = True
        if checkpoint_updated:
            print(f"  [Smart Update] Checkpoint set to: {checkpoint}")

    # 2. Update CLIPTextEncode (Positive / Negative prompts)
    if prompt or negative:
        clip_nodes = [n for n in nodes if n.get("type") == "CLIPTextEncode"]
        # If there are two CLIPTextEncode nodes, usually the first is Positive and the second is Negative.
        # Otherwise, check color/title if possible, or fallback to index.
        if len(clip_nodes) == 1 and prompt:
            clip_nodes[0]["widgets_values"] = [prompt]
            print("  [Smart Update] Single prompt node updated.")
        elif len(clip_nodes) >= 2:
            # Let's check titles or common negative keywords
            pos_node = None
            neg_node = None
            
            for node in clip_nodes:
                title = node.get("title", "").lower()
                widgets = node.get("widgets_values", [""])
                current_text = str(widgets[0]).lower() if widgets else ""
                
                if "negative" in title or "bad" in title or "watermark" in current_text or "text" in current_text:
                    neg_node = node
                else:
                    pos_node = node
            
            # Fallback if detection wasn't definitive
            if not pos_node and len(clip_nodes) > 0:
                pos_node = clip_nodes[0]
            if not neg_node and len(clip_nodes) > 1:
                # Ensure it's not the same node
                neg_node = clip_nodes[1] if clip_nodes[1] != pos_node else None

            if pos_node and prompt:
                pos_node["widgets_values"] = [prompt]
                print(f"  [Smart Update] Positive prompt updated: {prompt[:40]}...")
            if neg_node and negative:
                neg_node["widgets_values"] = [negative]
                print(f"  [Smart Update] Negative prompt updated: {negative[:40]}...")

    # 3. Update Seed in Samplers
    if seed is not None:
        seed_updated = False
        for node in nodes:
            ntype = node.get("type", "")
            if ntype in ("KSampler", "KSamplerAdvanced", "SamplerCustom", "KSamplerCustom"):
                widgets = node.get("widgets_values", [])
                if widgets:
                    # KSampler first widget value is typically the seed
                    widgets[0] = seed
                    seed_updated = True
        if seed_updated:
            print(f"  [Smart Update] Sampler seed updated to: {seed}")

    return data


def apply_manual_updates(data: dict, updates: dict) -> dict:
    """Manually apply updates map (node_id -> changes)."""
    nodes = data.get("nodes", [])
    node_map = {str(n.get("id")): n for n in nodes}

    for node_id, changes in updates.items():
        node_id_str = str(node_id)
        if node_id_str not in node_map:
            print(f"  [Warning] Node ID {node_id} not found in workflow template.")
            continue
            
        node = node_map[node_id_str]
        
        # Apply title update
        if "title" in changes:
            old_title = node.get("title", node.get("type"))
            node["title"] = changes["title"]
            print(f"  [Manual Update] Node {node_id} title changed from '{old_title}' to '{changes['title']}'")
            
        # Apply widget values
        if "widgets" in changes:
            new_widgets = changes["widgets"]
            if isinstance(new_widgets, list):
                node["widgets_values"] = new_widgets
                print(f"  [Manual Update] Node {node_id} widgets_values overridden with {new_widgets}")
            elif isinstance(new_widgets, dict):
                # Update specific indices within widgets_values
                current_widgets = node.get("widgets_values", [])
                for idx_str, val in new_widgets.items():
                    idx = int(idx_str)
                    # Extend list if index is out of bounds
                    while len(current_widgets) <= idx:
                        current_widgets.append(None)
                    current_widgets[idx] = val
                node["widgets_values"] = current_widgets
                print(f"  [Manual Update] Node {node_id} specific widgets updated: {new_widgets}")

    return data


def main():
    parser = argparse.ArgumentParser(description="Customize ComfyUI Workflow JSON templates.")
    parser.add_argument("--template", required=True, help="Filename of the base template (e.g. default.json)")
    parser.add_argument("--out", required=True, help="Output file path for the customized JSON")
    
    # Smart helper parameters
    parser.add_argument("--prompt", help="Positive prompt to insert into CLIPTextEncode")
    parser.add_argument("--negative", help="Negative prompt to insert into CLIPTextEncode")
    parser.add_argument("--checkpoint", help="Checkpoint model filename (e.g. v1-5-pruned-emaonly-fp16.safetensors)")
    parser.add_argument("--seed", type=int, help="Seed value for KSampler")
    
    # Advanced manual parameter mapping
    parser.add_argument("--updates", help="JSON string for manual node updates: '{\"node_id\": {\"widgets\": [...], \"title\": \"...\"}}'")

    args = parser.parse_args()

    # Search paths
    repo_root = Path(__file__).parent.parent
    search_dirs = [
        repo_root / "templates",
        repo_root / "blueprints",
        Path("e:/BRENXIA_AGENT_PROJECT/workflow_templates/templates"),
        Path("e:/BRENXIA_AGENT_PROJECT/workflow_templates/blueprints"),
    ]

    # Find template
    template_path = find_template(args.template, search_dirs)
    if not template_path:
        print(f"Error: Template '{args.template}' not found in search paths.")
        sys.exit(1)

    print(f"Loading template: {template_path}")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading template JSON: {e}")
        sys.exit(1)

    # 1. Apply Smart updates (prompt, negative, checkpoint, seed)
    data = apply_smart_updates(data, args.prompt, args.negative, args.checkpoint, args.seed)

    # 2. Apply manual updates if provided
    if args.updates:
        try:
            updates_dict = json.loads(args.updates)
            data = apply_manual_updates(data, updates_dict)
        except json.JSONDecodeError as e:
            print(f"Error parsing --updates JSON string: {e}")
            sys.exit(1)

    # Output path resolution
    out_path = Path(args.out)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Successfully generated custom workflow JSON: {out_path.resolve()}")
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
