"""
create_og_image.py — OG 이미지 생성 (1200x630)
링크 공유 시 카카오톡·디스코드·슬랙 등에서 보이는 미리보기 이미지
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sys

DOCS_DIR = Path(__file__).parent.parent / "docs"

# 색상
BG        = (255, 247, 237)   # #FFF7ED
ACCENT    = (234, 88,  12)    # #EA580C  orange-600
ACCENT2   = (251, 146, 60)    # #FB923C  orange-400
DARK      = (28,  25,  23)    # #1C1917
GRAY      = (120, 113, 108)   # #78716C
WHITE     = (255, 255, 255)

W, H = 1200, 630


def load_font(size, bold=False):
    """시스템에서 한글 지원 폰트 탐색, 없으면 기본 폰트 반환"""
    candidates = [
        # Linux (GitHub Actions)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        # Windows
        "C:/Windows/Fonts/malgunbd.ttf",  # 맑은고딕 Bold
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/NanumGothicBold.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # 기본 폰트 (한글 깨질 수 있음)
    return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + radius * 2, y0 + radius * 2], fill=fill)
    draw.ellipse([x1 - radius * 2, y0, x1, y0 + radius * 2], fill=fill)
    draw.ellipse([x0, y1 - radius * 2, x0 + radius * 2, y1], fill=fill)
    draw.ellipse([x1 - radius * 2, y1 - radius * 2, x1, y1], fill=fill)


def create_og_image():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── 배경 장식: 우측 큰 원 ──
    draw.ellipse([820, -120, 1380, 440], fill=(254, 215, 170))   # orange-200
    draw.ellipse([900, 340, 1300, 740], fill=(253, 186, 116))    # orange-300, 투명도 효과

    # ── 좌측 세로 악센트 바 ──
    draw_rounded_rect(draw, (60, 60, 72, 570), 6, ACCENT)

    # ── 상단 작은 배지 "2026 최신 정보" ──
    badge_font = load_font(22, bold=True)
    badge_text = "2026 최신 정보"
    bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    bw = bbox[2] - bbox[0] + 32
    bh = bbox[3] - bbox[1] + 14
    draw_rounded_rect(draw, (100, 120, 100 + bw, 120 + bh), 8, ACCENT)
    draw.text((116, 127), badge_text, fill=WHITE, font=badge_font)

    # ── 메인 타이틀 ──
    title_font = load_font(80, bold=True)
    title1 = "정부지원금"
    title2 = "한눈에 총정리"
    draw.text((100, 185), title1, fill=DARK, font=title_font)
    draw.text((100, 285), title2, fill=ACCENT, font=title_font)

    # ── 서브 텍스트 ──
    sub_font = load_font(34)
    draw.text((100, 410), "청년·노인·장애인·소상공인 대상별 맞춤 지원금", fill=GRAY, font=sub_font)

    # ── 아이콘 박스 3개 ──
    icon_font = load_font(28, bold=True)
    boxes = [
        ("매일 자동 갱신", ACCENT),
        ("전국 지원금 통합", (16, 185, 129)),
        ("신청 방법 안내", (59, 130, 246)),
    ]
    cx, y = 100, 478
    for label, color in boxes:
        lbbox = draw.textbbox((0, 0), label, font=icon_font)
        lw = lbbox[2] - lbbox[0]
        bw = lw + 36
        draw_rounded_rect(draw, (cx, y, cx + bw, y + 52), 10, color)
        draw.text((cx + 18, y + 12), label, fill=WHITE, font=icon_font)
        cx += bw + 14

    # ── 도메인 ──
    domain_font = load_font(30, bold=True)
    draw.text((100, 575), "wooabojopass.wooahouse.com", fill=ACCENT, font=domain_font)

    # 저장
    DOCS_DIR.mkdir(exist_ok=True)
    out = DOCS_DIR / "og.png"
    img.save(str(out), "PNG", optimize=True)
    print(f"OG image created: {out} ({W}x{H})")


if __name__ == "__main__":
    create_og_image()
