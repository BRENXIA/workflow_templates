"""
Selected Workflows Deep Analyzer
Analyzes 6 specific key workflows and builds detailed Markdown files with:
- Summary & Use Case
- Mermaid Flow Diagrams (Auto-generated from links)
- Node Inputs/Outputs Detail
- Default Widget Settings (Parameters)
"""

import json
from pathlib import Path


def generate_mermaid_diagram(nodes: list, links: list) -> str:
    """Generate Mermaid graph code from ComfyUI nodes and links."""
    # Build node ID -> Title/Type mapping
    node_map = {}
    for node in nodes:
        nid = node.get("id")
        ntype = node.get("type", "Unknown")
        title = node.get("title", ntype)
        # Clean title for Mermaid syntax compatibility
        clean_title = title.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace('"', "")
        node_map[nid] = f"N_{nid}[\"{clean_title} ({ntype})\"]"

    lines = ["graph TD"]
    
    # Process links
    for link in links:
        if isinstance(link, list) and len(link) >= 6:
            # [linkId, fromNodeId, fromSlot, toNodeId, toSlot, dataType]
            _, from_id, from_slot, to_id, to_slot, dtype = link[:6]
            from_str = node_map.get(from_id, f"N_{from_id}[\"Node {from_id}\"]")
            to_str = node_map.get(to_id, f"N_{to_id}[\"Node {to_id}\"]")
            
            lines.append(f"    N_{from_id} -->|{dtype}| N_{to_id}")
            
    # Add nodes that might not have links
    for nid, node_str in node_map.items():
        # Only add to diagram explicitly if referenced or standalone
        lines.insert(1, f"    {node_str}")
        
    return "\n".join(lines)


def analyze_selected_file(filepath: Path, area_title: str) -> str:
    """Read a JSON workflow, parse its parameters and generate Markdown report."""
    if not filepath.exists():
        return f"# Error: File {filepath.name} not found\n"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return f"# Error Parsing {filepath.name}: {str(e)}\n"

    nodes = data.get("nodes", [])
    links = data.get("links", [])
    definitions = data.get("definitions", {})
    
    mermaid_code = generate_mermaid_diagram(nodes, links)

    markdown = f"""---
type: concept
date: 2026-07-01
status: active
client: BRENXIA (내부)
agent: Antigravity
---

# ComfyUI 워크플로우 심층 분석 — {area_title}

## Summary
*   **분석 대상 파일**: `{filepath.name}`
*   **분석 목적**: {area_title}에 대한 실질적인 모델 연결 관계 및 데이터 흐름 이해
*   **노드 수**: {len(nodes)}개
*   **연결(링크) 수**: {len(links)}개

---

## 🗺️ 데이터 흐름 다이어그램 (Mermaid)

```mermaid
{mermaid_code}
```

---

## ⚙️ 노드 구성 및 세부 파라미터 (Widgets)

본 워크플로우의 주요 노드들과 디폴트 위젯 파라미터 설정 정보입니다:

"""

    for node in nodes:
        nid = node.get("id")
        ntype = node.get("type", "Unknown")
        title = node.get("title", ntype)
        widgets = node.get("widgets_values", [])
        
        markdown += f"### 📦 Node {nid}: {title} (`{ntype}`)\n"
        if widgets:
            markdown += "*   **주요 기본 설정값 (Widgets)**:\n"
            for i, val in enumerate(widgets):
                # Format long strings or paths for better readability
                val_str = str(val)
                if len(val_str) > 80:
                    val_str = val_str[:80] + "..."
                markdown += f"    *   `Param {i}`: {val_str}\n"
        else:
            markdown += "*   *위젯 설정값 없음 (입력 핀 연결 방식)*\n"
        
        # Inputs/Outputs Pins information
        inputs = node.get("inputs", [])
        outputs = node.get("outputs", [])
        
        if inputs:
            inp_list = ", ".join([f"`{inp.get('name')}:{inp.get('type')}`" for inp in inputs if inp.get('name')])
            markdown += f"*   **입력 핀**: {inp_list}\n"
        if outputs:
            out_list = ", ".join([f"`{out.get('name')}:{out.get('type')}`" for out in outputs if out.get('name')])
            markdown += f"*   **출력 핀**: {out_list}\n"
            
        markdown += "\n"

    markdown += f"""---

## 🔍 학습 및 고도화 가이드

1.  **핵심 노드**: 이 워크플로우의 핵심은 {nodes[0].get('title') if nodes else 'N/A'} 노드입니다.
2.  **데이터 호환성**: 입출력 데이터 타입 흐름에서 명시된 데이터 유형에 맞춰 연결을 유지해야 오류가 발생하지 않습니다.
3.  **변경 제안**: 파라미터 설정 위젯값을 수정하여 해상도, 프레임 수, 또는 세부 품질 옵션을 제어할 수 있습니다.
"""
    return markdown


def main():
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    brain_wiki_dir = Path("e:/BRENXIA_AGENT_PROJECT/02.BRAIN_Obsidian/AI-Sessions/wiki/agents_ecosystem/concepts")

    target_files = [
        ("video_hunyuan_video_1.5_720p_t2v.json", "비디오 생성 (Hunyuan Video T2V)", "2026-07-01_concept_ComfyUI워크플로우분석_비디오생성.md"),
        ("video_wan21_scail2_character_replacement.json", "이미지 편집 및 제품합성 (Wan2.1 Character Swap)", "2026-07-01_concept_ComfyUI워크플로우분석_제품합성.md"),
        ("utility_birefnet_remove_background.json", "배경 제거 및 누끼 (BiRefNet RMBG)", "2026-07-01_concept_ComfyUI워크플로우분석_누끼마스킹.md"),
        ("utility_image_upscale_supir.json", "고급 업스케일 (SUPIR Image Upscale)", "2026-07-01_concept_ComfyUI워크플로우분석_고급업스케일.md"),
        ("3d_hunyuan3d_image_to_model.json", "3D 에셋 및 공간 생성 (Hunyuan3D Image to Model)", "2026-07-01_concept_ComfyUI워크플로우분석_3D에셋생성.md"),
        ("05_audio_ace_step_1_t2a_song_subgraphed.json", "오디오 및 음성 처리 (Ace T2A Song)", "2026-07-01_concept_ComfyUI워크플로우분석_오디오처리.md"),
    ]

    print("=== ComfyUI Selected Workflows Deep Analyzer ===")

    for json_name, area_title, output_md_name in target_files:
        # Search in templates and blueprints
        filepath = repo_root / "templates" / json_name
        if not filepath.exists():
            filepath = repo_root / "blueprints" / json_name
            
        print(f"Analyzing {json_name} ({area_title})...")
        md_content = analyze_selected_file(filepath, area_title)
        
        output_path = brain_wiki_dir / output_md_name
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"  Successfully wrote analysis to: {output_path}")
        except Exception as e:
            print(f"  Error writing {output_md_name}: {e}")


if __name__ == "__main__":
    main()
