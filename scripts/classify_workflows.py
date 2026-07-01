"""
ComfyUI Workflow Classifier & Document Generator
Reads analysis_results.json, classifies all 658 workflows under advanced categories
(Video, Audio, 3D, Background Removal, Upscale, Editing/Product Swap, Base Gen),
and generates a structured Obsidian Concept document.
"""

import json
from pathlib import Path
from collections import defaultdict


def classify_workflow(w: dict) -> str:
    filename = w["file"].lower()
    folder = w["folder"]
    entry_nodes = [e.lower() for e in w["entry_nodes"]]
    exit_nodes = [e.lower() for e in w["exit_nodes"]]
    node_types = [n.lower() for n in w["node_types"]]
    data_types = [d.upper() for d in w["data_types_used"]]

    # 1. Audio & Voice
    if "audio" in filename or "voice" in filename or "separation" in filename or "AUDIO" in data_types:
        return "Audio & Voice Processing"

    # 2. 3D Asset & Gaussian Splat
    if "3d" in filename or "triposplat" in filename or "splat" in filename or "moge" in filename or "mesh" in filename or "FILE_3D_GLB" in data_types or "FILE_3D_OBJ" in data_types or "FILE_3D_FBX" in data_types:
        return "3D Asset & Spatial Gen"

    # 3. Video Generation & Editing
    if "video" in filename or "wan" in filename or "ltx" in filename or "mochi" in filename or "h2v" in filename or "i2v" in filename or "t2v" in filename or "v2v" in filename or "interpolation" in filename or "VIDEO" in data_types:
        # Check if it's upscale or background removal utility for video
        if "upscale" in filename or "enhance" in filename:
            return "Advanced Upscaling & Enhance (Video)"
        if "remove_background" in filename or "bria_remove_video" in filename or "segment" in filename:
            return "Background Removal & Segmentation (Video)"
        return "Video Generation & Editing"

    # 4. Background Removal & Segmentation (Image)
    if "remove_background" in filename or "birefnet" in filename or "bria" in filename or "sam3" in filename or "segment" in filename or "face_detection" in filename or "pose" in filename or "MASK" in data_types:
        return "Background Removal, Segmentation & Masking"

    # 5. Advanced Upscaling & Enhance (Image)
    if "upscale" in filename or "enhance" in filename or "supir" in filename or "seedvr" in filename or "topaz" in filename or "hitpaw" in filename or "gan_upscaler" in filename or "sharpen" in filename or "detail" in filename:
        return "Advanced Upscaling & Enhance"

    # 6. Image Edit & Product Integration (Inpaint, Outpaint, Product Swap, Multi-angle)
    if "inpaint" in filename or "outpaint" in filename or "edit" in filename or "swap" in filename or "replacement" in filename or "multiangle" in filename or "crop" in filename or "grid" in filename or "stitch" in filename:
        return "Image Editing & Product Integration"

    # 7. Base Image Generation
    if "text_to_image" in filename or "txt_to_image" in filename or "flux" in filename or "sdxl" in filename or "sd1" in filename or "anima" in filename or "default.json" in filename:
        return "Base Image Generation"

    # Fallback based on data types
    if "IMAGE" in data_types:
        return "Base Image Generation"

    return "Utility & Other Workflows"


def main():
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    analysis_results_path = script_dir / "analysis_results.json"
    brain_wiki_dir = Path("e:/BRENXIA_AGENT_PROJECT/02.BRAIN_Obsidian/AI-Sessions/wiki/agents_ecosystem/concepts")

    if not analysis_results_path.exists():
        print(f"Error: {analysis_results_path} does not exist.")
        return

    with open(analysis_results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    workflows = data.get("workflows", [])
    summary = data.get("summary", {})

    print(f"Classifying {len(workflows)} workflows...")

    # Group workflows by category
    categories = defaultdict(list)
    for w in workflows:
        if w.get("parse_error"):
            continue
        category = classify_workflow(w)
        categories[category].append(w)

    print(f"Classification complete. Found {len(categories)} categories.")
    for cat, items in categories.items():
        print(f"  {cat}: {len(items)} files")

    # Generate Obsidian markdown document
    doc_path = brain_wiki_dir / "2026-07-01_concept_ComfyUI워크플로우_분류체계.md"
    
    markdown_content = f"""---
type: concept
date: 2026-07-01
status: active
client: BRENXIA (내부)
agent: Antigravity
---

# ComfyUI 워크플로우 분류체계 및 노드 분석 (고도화)

## Summary
BRENXIA/workflow_templates에 포함된 총 {summary.get('total_workflows', 0)}개의 ComfyUI 공식 워크플로우 및 블루프린트 JSON을 분석하여 다각도(이미지, 비디오, 오디오, 3D, 제품 합성 등)로 고도화한 분류체계 문서입니다. 에이전트가 특정 목적의 워크플로우를 구성할 때 필요한 최적의 노드 패턴과 참조 모델을 학습하기 위한 지식 베이스로 활용됩니다.

## 카테고리별 워크플로우 현황

| 카테고리 | 워크플로우 개수 | 핵심 타겟 데이터 및 모델 범위 |
|---|---|---|
| **비디오 생성 및 편집** | {len(categories['Video Generation & Editing'])} | VIDEO (Wan2.2, LTX-2.3, Hunyuan Video, Mochi) |
| **이미지 편집 및 제품 합성** | {len(categories['Image Editing & Product Integration'])} | IMAGE, MASK (Flux Fill, Scail, Qwen Multiangle, Product Swap) |
| **누끼, 세그멘테이션 및 마스킹** | {len(categories['Background Removal, Segmentation & Masking'])} | IMAGE, MASK (BiRefNet, Bria, SAM3, OpenPose) |
| **고급 이미지 업스케일 및 복원** | {len(categories['Advanced Upscaling & Enhance'])} | IMAGE (SUPIR, SeedVR, Topaz, HitPaw, GAN, Recraft) |
| **3D 에셋 및 공간 생성** | {len(categories['3D Asset & Spatial Gen'])} | FILE_3D_GLB/OBJ/FBX (Hunyuan3D 2.0, TripoSplat, MoGe) |
| **오디오 및 음성 처리** | {len(categories['Audio & Voice Processing'])} | AUDIO (Stable Audio 3, Audio Separation, ElevenLabs) |
| **기본 이미지 생성** | {len(categories['Base Image Generation'])} | IMAGE, LATENT (Flux.1 Dev/Schnell, SDXL, SD 1.5) |
| **비디오 업스케일 및 보정** | {len(categories['Advanced Upscaling & Enhance (Video)'])} | VIDEO (HitPaw Video, SeedVR Video, Topaz Video) |
| **비디오 누끼 및 세그멘테이션** | {len(categories['Background Removal & Segmentation (Video)'])} | VIDEO, MASK (Bria Video RMBG, SAM3 Video) |
| **기타 유틸리티** | {len(categories['Utility & Other Workflows'])} | JSON/TXT (Data conversion, switch, text select) |

---

"""

    # Add details for each category
    for category in sorted(categories.keys()):
        items = categories[category]
        markdown_content += f"## 📂 {category} ({len(items)}개)\n\n"
        
        # Sort items by file name
        items_sorted = sorted(items, key=lambda x: x["file"])
        
        markdown_content += "| 파일명 | 노드 수 | 핵심 노드 구성 (주요 연결 패턴) | 사용 모델 / 커스텀 노드 |\n"
        markdown_content += "|---|---|---|---|\n"
        
        for w in items_sorted[:15]: # Show top 15 for readability in each category
            nodes_summary = ", ".join(w["node_types"][:5])
            if len(w["node_types"]) > 5:
                nodes_summary += "..."
                
            models = ", ".join(w["models_referenced"]) if w["models_referenced"] else "N/A"
            custom = ", ".join([c["type"] for c in w["custom_nodes"][:3]])
            if len(w["custom_nodes"]) > 3:
                custom += "..."
            cust_str = f"Custom: {custom}" if custom else "Core Only"
            
            # Form clean link back to the file inside the repo
            file_link = f"[{w['file']}](file:///e:/BRENXIA_AGENT_PROJECT/workflow_templates/{w['folder']}/{w['file']})"
            
            markdown_content += f"| {file_link} | {w['node_count']} | `{nodes_summary}` | {models} <br> *({cust_str})* |\n"
            
        if len(items_sorted) > 15:
            markdown_content += f"| ...외 {len(items_sorted)-15}개 파일 생략 | | | |\n"
            
        markdown_content += "\n---\n\n"

    # Save to Obsidian wiki
    try:
        brain_wiki_dir.mkdir(parents=True, exist_ok=True)
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"Concept document successfully written to: {doc_path}")
    except Exception as e:
        print(f"Error writing concept document: {e}")


if __name__ == "__main__":
    main()
