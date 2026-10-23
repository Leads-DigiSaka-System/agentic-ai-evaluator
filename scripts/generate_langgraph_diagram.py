"""Generate agentic-ai-evaluator.png — LangGraph flow from actual project source."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "agentic-ai-evaluator.png"

W, H = 2600, 1680
BG = (241, 245, 249)
PANEL = (255, 255, 255)
BORDER = (226, 232, 240)
TEXT = (15, 23, 42)
MUTED = (71, 85, 105)
SOFT = (148, 163, 184)
ACCENT = (21, 128, 61)
ACCENT_LIGHT = (220, 252, 231)
BLUE = (29, 78, 216)
BLUE_LIGHT = (219, 234, 254)
ORANGE = (194, 65, 12)
ORANGE_LIGHT = (255, 237, 213)
RED = (185, 28, 28)
RED_LIGHT = (254, 226, 226)
PURPLE = (109, 40, 217)
PURPLE_LIGHT = (237, 233, 254)
SLATE = (51, 65, 85)
ARROW = (100, 116, 139)
RETRY = (217, 119, 6)
CODE_BG = (15, 23, 42)
CODE_FG = (226, 232, 240)
CODE_KEY = (125, 211, 252)
CODE_STR = (134, 239, 172)
CODE_NUM = (253, 224, 71)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None = None,
    radius: int = 16,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def shadow_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    radius: int = 16,
) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle((x1 + 3, y1 + 4, x2 + 3, y2 + 4), radius=radius, fill=(226, 232, 240))
    rounded_rect(draw, xy, fill, outline, radius=radius)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    fill: tuple[int, int, int],
    text_color: tuple[int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    tw, th = text_size(draw, text, font)
    pad_x, pad_y = 10, 5
    rounded_rect(draw, (x, y, x + tw + pad_x * 2, y + th + pad_y * 2), fill, fill, radius=12)
    draw.text((x + pad_x, y + pad_y - 1), text, fill=text_color, font=font)


def elbow(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    color: tuple[int, int, int] = ARROW,
    width: int = 3,
) -> None:
    draw.line(points, fill=color, width=width)
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    size = 9
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 > x1 else -1
        draw.polygon(
            [
                (x2, y2),
                (x2 - direction * size, y2 - size // 2),
                (x2 - direction * size, y2 + size // 2),
            ],
            fill=color,
        )
    else:
        direction = 1 if y2 > y1 else -1
        draw.polygon(
            [
                (x2, y2),
                (x2 - size // 2, y2 - direction * size),
                (x2 + size // 2, y2 - direction * size),
            ],
            fill=color,
        )


def v_arrow(draw: ImageDraw.ImageDraw, x: int, y1: int, y2: int, color: tuple[int, int, int] = ARROW) -> None:
    elbow(draw, [(x, y1), (x, y2)], color=color)


def node_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    step: str | None,
    title: str,
    subtitle: str,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    title_font: ImageFont.ImageFont,
    sub_font: ImageFont.ImageFont,
    step_font: ImageFont.ImageFont,
) -> None:
    shadow_rect(draw, box, fill, outline)
    x1, y1, x2, y2 = box
    tx = x1 + 18
    if step:
        badge = (x1 + 14, y1 + 14, x1 + 48, y1 + 42)
        rounded_rect(draw, badge, outline, outline, radius=10)
        bw, bh = text_size(draw, step, step_font)
        draw.text(
            (x1 + 14 + (34 - bw) // 2, y1 + 14 + (28 - bh) // 2 - 1),
            step,
            fill=(255, 255, 255),
            font=step_font,
        )
        tx = x1 + 58
    draw.text((tx, y1 + 14), title, fill=TEXT, font=title_font)
    draw.text((tx, y1 + 42), subtitle, fill=MUTED, font=sub_font)


def panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    title_font: ImageFont.ImageFont,
    accent: tuple[int, int, int] | None = None,
) -> None:
    shadow_rect(draw, box, PANEL, BORDER, radius=22)
    x1, y1, x2, _ = box
    if accent:
        draw.rounded_rectangle((x1, y1, x1 + 8, y1 + 52), radius=4, fill=accent)
    draw.text((x1 + 28, y1 + 18), title, fill=TEXT, font=title_font)
    draw.line((x1 + 24, y1 + 58, x2 - 24, y1 + 58), fill=BORDER, width=2)


def legend_item(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    color: tuple[int, int, int],
    label: str,
    font: ImageFont.ImageFont,
) -> None:
    rounded_rect(draw, (x, y, x + 18, y + 18), color, color, radius=5)
    draw.text((x + 26, y - 1), label, fill=MUTED, font=font)


def draw_code_line(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    parts: list[tuple[str, tuple[int, int, int]]],
    font: ImageFont.ImageFont,
) -> None:
    cx = x
    for text, color in parts:
        draw.text((cx, y), text, fill=color, font=font)
        tw, _ = text_size(draw, text, font)
        cx += tw


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    title_font = load_font(38, bold=True)
    h2_font = load_font(22, bold=True)
    node_font = load_font(18, bold=True)
    sub_font = load_font(14)
    small_font = load_font(14)
    tiny_font = load_font(13)
    step_font = load_font(13, bold=True)
    code_font = load_font(15)
    legend_font = load_font(13)

    # Header
    draw.text((48, 28), "Agentic AI Evaluator", fill=TEXT, font=title_font)
    draw.text(
        (48, 76),
        "LangGraph flow  ·  CrewAI evaluation  ·  sample structured output",
        fill=MUTED,
        font=small_font,
    )
    draw.text((48, 98), "Source of truth: src/workflow/graph.py + routers.py", fill=SOFT, font=tiny_font)

    # Legend
    lx = 1480
    legend_item(draw, lx, 40, BLUE_LIGHT, "Extract / validate", legend_font)
    legend_item(draw, lx + 190, 40, ACCENT_LIGHT, "Analyze / chunk", legend_font)
    legend_item(draw, lx + 380, 40, PURPLE_LIGHT, "CrewAI eval", legend_font)
    legend_item(draw, lx + 540, 40, ORANGE_LIGHT, "Graphs / cache", legend_font)
    legend_item(draw, lx + 740, 40, RED_LIGHT, "Errors", legend_font)
    legend_item(draw, lx, 72, (255, 247, 237), "Retry loop", legend_font)
    draw.line((lx + 160, 80, lx + 190, 80), fill=RETRY, width=3)

    # ===================== LEFT: FLOW =====================
    flow_box = (36, 130, 1520, 1640)
    panel(draw, flow_box, "LangGraph Processing Workflow  (ProcessingState)", h2_font, BLUE)

    draw.text(
        (64, 205),
        "Entry: POST /api/agent   ·   sync in-process or ARQ background   ·   storage is outside the graph",
        fill=MUTED,
        font=small_font,
    )

    # Layout constants
    left = 280
    right = 720
    cx = (left + right) // 2
    rail_x = 1180
    node_h = 68
    gap = 28

    y = 250
    start_box = (cx - 90, y, cx + 90, y + 48)
    shadow_rect(draw, start_box, ACCENT_LIGHT, ACCENT, radius=24)
    draw.text((cx - 34, y + 12), "START", fill=TEXT, font=node_font)
    draw.text((cx - 62, y + 52), "PDF / PNG / JPG", fill=MUTED, font=tiny_font)

    y = 320
    boxes: dict[str, tuple[int, int, int, int]] = {}

    def place(key: str, step: str | None, title: str, subtitle: str, fill, outline, y0: int) -> int:
        box = (left, y0, right, y0 + node_h)
        boxes[key] = box
        node_box(draw, box, step, title, subtitle, fill, outline, node_font, sub_font, step_font)
        return y0 + node_h

    y = place("extract", "1", "extract", "Gemini extraction + file format validation", BLUE_LIGHT, BLUE, y)
    v_arrow(draw, cx, start_box[3], boxes["extract"][1])

    y += gap
    y = place("validate", "2", "validate_content", "LLM checks if content is a product demo / trial", BLUE_LIGHT, BLUE, y)
    v_arrow(draw, cx, boxes["extract"][3], boxes["validate"][1])

    y += gap
    y = place("analyze", "3", "analyze", "Structured agricultural analysis (Gemini large)", ACCENT_LIGHT, ACCENT, y)
    v_arrow(draw, cx, boxes["validate"][3], boxes["analyze"][1])

    y += gap
    y = place("eval_a", "4", "evaluate_analysis", "CrewAI 4-agent quality evaluation", PURPLE_LIGHT, PURPLE, y)
    v_arrow(draw, cx, boxes["analyze"][3], boxes["eval_a"][1])

    y += gap
    y = place("graphs", "5", "suggest_graphs", "JSON chart specifications (not rendered images)", ORANGE_LIGHT, ORANGE, y)
    v_arrow(draw, cx, boxes["eval_a"][3], boxes["graphs"][1])

    y += gap
    y = place("eval_g", "6", "evaluate_graphs", "Same evaluation_node — graph context", PURPLE_LIGHT, PURPLE, y)
    v_arrow(draw, cx, boxes["graphs"][3], boxes["eval_g"][1])

    y += gap
    y = place("chunk", "7", "chunk", "Markdown table flatten + token chunking for RAG", ACCENT_LIGHT, ACCENT, y)
    v_arrow(draw, cx, boxes["eval_g"][3], boxes["chunk"][1])

    # END
    end_y = y + gap + 8
    end_box = (cx - 110, end_y, cx + 110, end_y + 52)
    shadow_rect(draw, end_box, ACCENT_LIGHT, ACCENT, radius=24)
    draw.text((cx - 28, end_y + 8), "END", fill=TEXT, font=node_font)
    draw.text((cx - 78, end_y + 30), "ready_for_approval", fill=MUTED, font=tiny_font)
    v_arrow(draw, cx, boxes["chunk"][3], end_box[1])

    # Error rail — vertical bus + short stubs (no spaghetti diagonals)
    error_box = (rail_x - 100, 540, rail_x + 160, 540 + node_h)
    node_box(
        draw,
        error_box,
        None,
        "handle_errors",
        "Collect errors → END",
        RED_LIGHT,
        RED,
        node_font,
        sub_font,
        step_font,
    )
    pill(draw, rail_x - 55, 508, "fail / invalid", RED_LIGHT, RED, tiny_font)

    bus_x = rail_x - 130
    draw.line((bus_x, boxes["extract"][1] + 10, bus_x, end_box[1] + 26), fill=RED, width=3)

    for key in ("extract", "validate", "analyze", "eval_a", "graphs", "eval_g", "chunk"):
        by = (boxes[key][1] + boxes[key][3]) // 2
        draw.line((right, by, bus_x, by), fill=(252, 165, 165), width=2)
        draw.ellipse((bus_x - 5, by - 5, bus_x + 5, by + 5), fill=RED)

    # Bus enters handle_errors, then continues to END
    ey_mid = (error_box[1] + error_box[3]) // 2
    draw.line((bus_x, ey_mid, error_box[0], ey_mid), fill=RED, width=3)
    elbow(draw, [(bus_x, end_box[1] + 26), (end_box[2], end_box[1] + 26)], color=RED, width=3)

    # Retry loops — left side, clean elbows
    retry_x1 = left - 70
    retry_x2 = left - 100

    # evaluate_analysis → analyze
    ay = (boxes["analyze"][1] + boxes["analyze"][3]) // 2
    ey = (boxes["eval_a"][1] + boxes["eval_a"][3]) // 2
    elbow(draw, [(left, ey), (retry_x1, ey), (retry_x1, ay), (left, ay)], color=RETRY, width=3)
    pill(draw, retry_x1 - 78, (ay + ey) // 2 - 12, "retry < 2", (255, 247, 237), RETRY, tiny_font)

    # evaluate_graphs → suggest_graphs
    gy = (boxes["graphs"][1] + boxes["graphs"][3]) // 2
    egy = (boxes["eval_g"][1] + boxes["eval_g"][3]) // 2
    elbow(draw, [(left, egy), (retry_x2, egy), (retry_x2, gy), (left, gy)], color=RETRY, width=3)
    pill(draw, retry_x2 - 78, (gy + egy) // 2 - 12, "retry < 2", (255, 247, 237), RETRY, tiny_font)

    # Outside-graph divider
    outside_y = end_box[3] + 36
    draw.line((64, outside_y, 1490, outside_y), fill=BORDER, width=2)
    for dash_x in range(64, 1490, 18):
        draw.line((dash_x, outside_y, min(dash_x + 10, 1490), outside_y), fill=SOFT, width=2)
    pill(draw, 64, outside_y - 14, "Outside LangGraph", (241, 245, 249), MUTED, tiny_font)

    # Redis + approve
    cache_y = outside_y + 36
    cache_box = (left, cache_y, right, cache_y + node_h)
    node_box(
        draw,
        cache_box,
        None,
        "Redis cache",
        "agent:cache:{user_id}:{cache_id}   TTL ~10 min",
        ORANGE_LIGHT,
        ORANGE,
        node_font,
        sub_font,
        step_font,
    )
    v_arrow(draw, cx, end_box[3], cache_box[1])

    approve_y = cache_y + node_h + gap
    approve_box = (left, approve_y, right, approve_y + node_h)
    node_box(
        draw,
        approve_box,
        None,
        "POST /api/storage/approve-simple",
        "Human approval → Qdrant form chunks + analysis",
        BLUE_LIGHT,
        BLUE,
        node_font,
        sub_font,
        step_font,
    )
    v_arrow(draw, cx, cache_box[3], approve_box[1])

    # Routing notes card (right of Redis/approve, under error rail)
    notes_box = (right + 40, cache_y, 1490, approve_y + node_h)
    shadow_rect(draw, notes_box, (248, 250, 252), BORDER, radius=14)
    draw.text((right + 58, cache_y + 14), "Routing notes", fill=TEXT, font=small_font)
    for i, note in enumerate(
        [
            "• shared evaluation_attempts for analysis + graphs",
            "• source_limitation → proceed to suggest_graphs",
            "• fixable_analysis + low confidence → retry analyze",
            "• graph_issue + low confidence → retry suggest_graphs",
            "• legacy /upload-file-product-demo bypasses approval",
        ]
    ):
        draw.text((right + 58, cache_y + 44 + i * 22), note, fill=MUTED, font=tiny_font)

    # ===================== RIGHT TOP: CREWAI =====================
    eval_box = (1560, 130, 2560, 700)
    panel(draw, eval_box, "CrewAI Evaluation  (steps 4 & 6)", h2_font, PURPLE)

    agents = [
        ("1", "Document Context Analyst", "Source limits vs extraction / OCR issues"),
        ("2", "Output Quality Evaluator", "Confidence, completeness, accuracy"),
        ("3", "Processing Strategy Advisor", "Recommend retry vs proceed"),
        ("4", "Evaluation Decision Coordinator", "Final decision + issue_type"),
    ]
    ay = 210
    for num, title, desc in agents:
        box = (1590, ay, 2530, ay + 78)
        shadow_rect(draw, box, PURPLE_LIGHT, PURPLE, radius=14)
        badge = (1610, ay + 22, 1644, ay + 56)
        rounded_rect(draw, badge, PURPLE, PURPLE, radius=10)
        bw, bh = text_size(draw, num, step_font)
        draw.text((1610 + (34 - bw) // 2, ay + 22 + (34 - bh) // 2 - 1), num, fill=(255, 255, 255), font=step_font)
        draw.text((1660, ay + 16), title, fill=TEXT, font=node_font)
        draw.text((1660, ay + 44), desc, fill=MUTED, font=sub_font)
        ay += 92

    decision = (1590, 590, 2530, 670)
    shadow_rect(draw, decision, ACCENT_LIGHT, ACCENT, radius=14)
    draw.text((1615, 604), "Router outputs → next node", fill=TEXT, font=node_font)
    draw.text(
        (1615, 634),
        "decision · confidence · feedback · issue_type   →   analyze | suggest_graphs | chunk | handle_errors",
        fill=MUTED,
        font=tiny_font,
    )

    # ===================== RIGHT BOTTOM: SAMPLE OUTPUT =====================
    out_box = (1560, 730, 2560, 1640)
    panel(draw, out_box, "Sample Structured Output  (per report)", h2_font, ACCENT)

    code_area = (1590, 810, 2530, 1520)
    rounded_rect(draw, code_area, CODE_BG, CODE_BG, radius=16)

    lines: list[list[tuple[str, tuple[int, int, int]]]] = [
        [("{", CODE_FG)],
        [('  "status"', CODE_KEY), (": ", CODE_FG), ('"success"', CODE_STR), (",", CODE_FG)],
        [('  "total_reports"', CODE_KEY), (": ", CODE_FG), ("1", CODE_NUM), (",", CODE_FG)],
        [('  "cache_id"', CODE_KEY), (": ", CODE_FG), ('"uuid"', CODE_STR), (",", CODE_FG)],
        [('  "reports"', CODE_KEY), (": [{", CODE_FG)],
        [('    "form_type"', CODE_KEY), (": ", CODE_FG), ('"agricultural demo form"', CODE_STR), (",", CODE_FG)],
        [('    "storage_status"', CODE_KEY), (": ", CODE_FG), ('"ready_for_approval"', CODE_STR), (",", CODE_FG)],
        [('    "analysis"', CODE_KEY), (": {", CODE_FG)],
        [('      "basic_info"', CODE_KEY), (": { product, location, crop }", CODE_FG)],
        [('      "performance_analysis"', CODE_KEY), (": { improvement_percent }", CODE_FG)],
        [('      "yield_analysis"', CODE_KEY), (": { ... },", CODE_FG)],
        [('      "cooperator_feedback"', CODE_KEY), (": { sentiment },", CODE_FG)],
        [('      "recommendations"', CODE_KEY), (": [...],", CODE_FG)],
        [('      "executive_summary"', CODE_KEY), (": ", CODE_FG), ('"..."', CODE_STR)],
        [("    },", CODE_FG)],
        [('    "graph_suggestions"', CODE_KEY), (": {", CODE_FG)],
        [('      "suggested_charts"', CODE_KEY), (": [{ chart_type, title, labels, datasets }]", CODE_FG)],
        [("    },", CODE_FG)],
        [('    "chunks"', CODE_KEY), (": [{ content, metadata }],", CODE_FG)],
        [('    "validation"', CODE_KEY), (": { is_valid_demo: true }", CODE_FG)],
        [("  }]", CODE_FG)],
        [("}", CODE_FG)],
    ]

    cy = 830
    for parts in lines:
        draw_code_line(draw, 1620, cy, parts, code_font)
        cy += 28

    draw.text(
        (1590, 1550),
        "Files:  evaluation_node.py  ·  evaluation_crew.py  ·  routers.py",
        fill=MUTED,
        font=tiny_font,
    )
    draw.text(
        (1590, 1575),
        "Note: graph_suggestions are JSON specs only — no PNG/SVG renderer yet",
        fill=SOFT,
        font=tiny_font,
    )

    img.save(OUTPUT, format="PNG", optimize=True)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
