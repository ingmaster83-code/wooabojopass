"""
generate_pages.py — JSON 데이터 → HTML 자동 생성
- docs/jiwon/[slug].html  : 지원금별 상세 페이지
- docs/대상/[name].html    : 대상자별 페이지
- docs/분야/[name].html    : 분야별 페이지
- docs/sitemap.xml         : 사이트맵
"""

import json
import re
import unicodedata
from pathlib import Path
from datetime import datetime, date

from jinja2 import Environment, FileSystemLoader

CUR_YEAR = datetime.now().year

# ── 경로 ──────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
DATA_DIR  = ROOT / "data"
DETAIL_DIR = DATA_DIR / "detail"
DOCS_DIR  = ROOT / "docs"
TMPL_DIR  = ROOT / "scripts" / "templates"

JIWON_DIR = DOCS_DIR / "jiwon"
TARGET_DIR = DOCS_DIR / "대상"
FIELD_DIR  = DOCS_DIR / "분야"

for d in [JIWON_DIR, TARGET_DIR, FIELD_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Jinja2 환경 ────────────────────────────────────────────
env = Environment(loader=FileSystemLoader(str(TMPL_DIR)), autoescape=False)

# ── 상수 ──────────────────────────────────────────────────
TODAY = date.today()

TARGETS = ["청년", "중장년", "노인", "장애인", "임산부", "다자녀", "한부모", "소상공인"]
FIELDS  = ["주거", "취업", "육아", "의료", "교육", "창업", "금융", "복지"]

TARGET_KEYWORDS = {
    "청년":    ["청년", "대학생", "청소년", "만 19", "만19"],
    "중장년":  ["중장년", "중년", "만 40", "만40", "4050"],
    "노인":    ["노인", "어르신", "고령", "만 65", "만65", "시니어"],
    "장애인":  ["장애인", "장애", "장애등급"],
    "임산부":  ["임산부", "임신", "출산", "산모", "영아", "신생아"],
    "다자녀":  ["다자녀", "다문화", "자녀", "육아", "아동", "보육"],
    "한부모":  ["한부모", "편부", "편모", "미혼모", "미혼부"],
    "소상공인": ["소상공인", "자영업", "중소기업", "소기업", "창업", "사업자"],
}

FIELD_KEYWORDS = {
    "주거": ["주거", "주택", "임대", "전세", "월세", "주거급여"],
    "취업": ["취업", "일자리", "고용", "구직", "취창업", "직업훈련"],
    "육아": ["육아", "보육", "아동", "어린이집", "양육", "돌봄"],
    "의료": ["의료", "건강", "치료", "병원", "의약", "재활", "의료비"],
    "교육": ["교육", "학습", "장학", "학비", "학원", "학교"],
    "창업": ["창업", "스타트업", "벤처", "창업자금"],
    "금융": ["금융", "대출", "이자", "융자", "저축", "적금", "보증"],
    "복지": ["복지", "생활", "생계", "기초", "차상위", "수급"],
}

APPLY_TYPE_MAP = {
    "온라인": "온라인",
    "방문": "방문",
    "우편": "우편",
    "온라인신청": "온라인",
    "인터넷": "온라인",
    "전화": "전화",
}

# 행정 용어 → 쉬운 말 변환 딕셔너리
TERM_MAP = {
    "기준 중위소득": "기준 중위소득(월 소득 기준)",
    "소득인정액": "소득인정액(근로소득+재산환산액)",
    "수급자": "기초생활수급자",
    "차상위계층": "차상위계층(소득 기준 중위소득 50% 이하)",
    "LH": "한국토지주택공사(LH)",
    "공단": "공단",
}

# ══════════════════════════════════════════════════════════
# 유틸 함수
# ══════════════════════════════════════════════════════════

def slugify(text):
    """한글 포함 URL-safe slug 생성"""
    text = str(text).strip()
    # 특수문자 → 하이픈
    text = re.sub(r'[^\w\s가-힣]', '-', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = text.strip('-')
    return text


def easy_term(text):
    """어려운 행정 용어를 쉬운 말로 치환"""
    if not text:
        return text
    for k, v in TERM_MAP.items():
        text = text.replace(k, v)
    return text


def calc_dday(apply_end):
    """신청 종료일 → D-Day 계산"""
    if not apply_end:
        return "연중 상시", "badge-dday-ongoing", "상시"
    try:
        # YYYYMMDD 또는 YYYY-MM-DD 형식
        end_str = str(apply_end).replace("-", "").replace(".", "")[:8]
        if len(end_str) < 8:
            return "기간 확인 필요", "badge-dday-safe", "확인 필요"
        end_date = date(int(end_str[:4]), int(end_str[4:6]), int(end_str[6:8]))
        diff = (end_date - TODAY).days
        if diff < 0:
            return f"{end_str[:4]}.{end_str[4:6]}.{end_str[6:8]} 마감", "badge-dday-closed", "마감"
        elif diff <= 3:
            return f"~{end_str[:4]}.{end_str[4:6]}.{end_str[6:8]}", "badge-dday-danger", f"D-{diff}"
        elif diff <= 7:
            return f"~{end_str[:4]}.{end_str[4:6]}.{end_str[6:8]}", "badge-dday-warn", f"D-{diff}"
        elif diff <= 30:
            return f"~{end_str[:4]}.{end_str[4:6]}.{end_str[6:8]}", "badge-dday-warn", f"D-{diff}"
        else:
            return f"~{end_str[:4]}.{end_str[4:6]}.{end_str[6:8]}", "badge-dday-safe", f"D-{diff}"
    except Exception:
        return str(apply_end), "badge-dday-safe", "확인"


def detect_targets(item):
    """지원금 텍스트에서 대상자 태그 추출"""
    text = " ".join([
        str(item.get("name", "")),
        str(item.get("target_summary", "")),
        str(item.get("categories", "")),
        str(item.get("life_cycle", "")),
        str(item.get("summary", "")),
    ]).lower()

    found = []
    for target, keywords in TARGET_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            found.append(target)
    return found if found else ["복지"]


def detect_fields(item):
    """지원금 텍스트에서 분야 태그 추출"""
    text = " ".join([
        str(item.get("name", "")),
        str(item.get("categories", "")),
        str(item.get("summary", "")),
        str(item.get("amount_summary", "")),
    ]).lower()

    found = []
    for field, keywords in FIELD_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            found.append(field)
    return found if found else ["복지"]


def parse_apply_type(raw):
    """신청방법 원문 → 레이블"""
    if not raw:
        return "온라인/방문"
    raw_lower = raw.lower()
    labels = []
    if any(k in raw_lower for k in ["온라인", "인터넷", "홈페이지"]):
        labels.append("온라인")
    if any(k in raw_lower for k in ["방문", "주민센터", "동사무소"]):
        labels.append("방문")
    if "우편" in raw_lower:
        labels.append("우편")
    if "전화" in raw_lower:
        labels.append("전화")
    return " / ".join(labels) if labels else "온라인/방문"


def parse_documents(raw):
    """구비서류 원문 → 리스트"""
    if not raw:
        return []
    # 줄바꿈, 번호 등으로 분리
    items = re.split(r'[\n,·•\-①②③④⑤⑥⑦⑧⑨⑩]|\d+\.|[0-9]+\)', raw)
    result = []
    for item in items:
        item = item.strip()
        if len(item) > 3:
            result.append(item)
    return result[:10]  # 최대 10개


def parse_conditions(conditions):
    """지원조건 → 쉬운 말 자격 리스트"""
    if not conditions:
        return [], []
    qual, exclude = [], []
    for c in conditions:
        age_min = c.get("age_min", "")
        age_max = c.get("age_max", "")
        income_pct = c.get("income_pct", "")
        target_detail = easy_term(c.get("target_detail", ""))
        exc = easy_term(c.get("exclude", ""))

        if age_min and age_max:
            qual.append(f"나이 — 만 {age_min}세 이상 {age_max}세 이하")
        elif age_min:
            qual.append(f"나이 — 만 {age_min}세 이상")
        elif age_max:
            qual.append(f"나이 — 만 {age_max}세 이하")

        if income_pct:
            qual.append(f"소득 — 기준 중위소득 {income_pct}% 이하인 가구")

        if target_detail and len(target_detail) > 5:
            sentences = re.split(r'[\r\n]+|(?<=[가-힣)%])\s*[○◎·•]\s*|[-–—]\s+(?=[가-힣])', target_detail)
            for s in sentences:
                s = re.sub(r'^[○◎·•\-\s]+', '', s).strip()
                if 5 < len(s) < 150:
                    qual.append(s)

        if exc and len(exc) > 5:
            sentences = re.split(r'[\r\n]+|(?<=[가-힣)%])\s*[○◎·•]\s*|[-–—]\s+(?=[가-힣])', exc)
            for s in sentences:
                s = re.sub(r'^[○◎·•\-\s]+', '', s).strip()
                if 5 < len(s) < 150:
                    exclude.append(s)

    return qual[:6], exclude[:4]


def build_apply_steps(apply_detail):
    """신청방법 원문 → STEP 리스트"""
    if not apply_detail:
        return []
    steps = []
    lines = re.split(r'[\n]|[①②③④⑤⑥]|\d+\.\s', apply_detail)
    for line in lines:
        line = line.strip()
        if len(line) > 10:
            steps.append({"title": line[:30], "desc": line})
    return steps[:5]


def make_apply_period(apply_start, apply_end):
    """신청 시작/종료일 → 표시 문자열"""
    def fmt(d):
        if not d:
            return ""
        d = str(d).replace("-", "").replace(".", "")[:8]
        if len(d) == 8:
            return f"{d[:4]}.{d[4:6]}.{d[6:8]}"
        return d

    s, e = fmt(apply_start), fmt(apply_end)
    if s and e:
        return f"{s} ~ {e}"
    elif e:
        return f"~ {e}"
    elif s:
        return f"{s} ~"
    return "연중 상시"


# ══════════════════════════════════════════════════════════
# 데이터 빌드
# ══════════════════════════════════════════════════════════

def build_item(raw, detail=None):
    """raw JSON + detail JSON → 템플릿용 item dict"""
    d = detail or {}
    item = {**raw, **d}

    slug = slugify(item.get("name", item.get("id", "unknown")))
    item["slug"] = slug

    # D-Day
    period, dday_class, dday_label = calc_dday(item.get("apply_end", ""))
    item["apply_period"] = make_apply_period(item.get("apply_start"), item.get("apply_end"))
    item["dday_class"]   = dday_class
    item["dday_label"]   = dday_label
    item["is_closed"]    = dday_class == "badge-dday-closed"

    # 태그
    item["targets"] = detect_targets(item)
    item["fields"]  = detect_fields(item)
    item["primary_target"] = item["targets"][0] if item["targets"] else None
    item["tag_list"] = item["targets"][:2] + item["fields"][:1]

    # 신청방법 레이블
    item["apply_type_label"] = parse_apply_type(
        item.get("apply_detail") or item.get("apply_type", "")
    )

    # 자격 조건
    conditions = item.get("conditions", [])
    item["qual_list"], item["exclude_list"] = parse_conditions(conditions)

    # qual_list 없으면 target_summary 분리해서 사용
    if not item["qual_list"]:
        raw_ts = item.get("target_summary", "")
        if raw_ts:
            parts = re.split(r'[\r\n]+|(?<=[가-힣)%])\s*[○◎·•]\s*|[-–—]\s+(?=[가-힣])', raw_ts)
            item["qual_list"] = [
                re.sub(r'^[○◎·•\-\s]+', '', p).strip()
                for p in parts
                if 5 < len(p.strip()) < 150
            ][:8]

    # 서류
    item["doc_list"] = parse_documents(item.get("documents", ""))

    # 신청 스텝 (상세가 있으면)
    item["apply_steps"] = build_apply_steps(item.get("apply_detail", ""))

    # 신청 URL
    item["apply_url"] = (
        item.get("online_apply_url") or
        item.get("url") or
        ""
    )

    # FAQ (기본 생성)
    item["faqs"] = build_faqs(item)

    # 문장 쉽게
    item["support_detail"] = easy_term(item.get("support_detail") or item.get("amount_summary") or "")

    # SEO: title suffix (금액 키워드 추출)
    item["title_suffix"] = build_title_suffix(item)

    # SEO: meta description
    item["meta_description"] = build_meta_description(item)

    return item


def build_title_suffix(item):
    """amount_summary에서 핵심 금액 키워드를 추출해 title suffix 생성"""
    amount = str(item.get("amount_summary") or item.get("support_detail") or "")
    # 숫자+단위 패턴 (예: 165만원, 최대 330만원, 50,000원)
    patterns = re.findall(r'(?:최대\s*)?[\d,]+\s*(?:만\s*원|원|만원)', amount)
    # 중복 제거, 최대 2개
    seen, unique = set(), []
    for p in patterns:
        p = re.sub(r'\s+', '', p)
        if p not in seen:
            seen.add(p)
            unique.append(p)
        if len(unique) == 2:
            break
    if unique:
        return f" — 최대 {unique[0]}" if '최대' not in unique[0] and len(unique) == 1 else f" — {', '.join(unique)}"
    return ""


def build_meta_description(item):
    """금액+대상+신청방법을 조합한 자연스러운 meta description 생성 (최대 155자)"""
    name    = item.get("name", "")
    dept    = item.get("dept", "")
    summary = str(item.get("summary") or "").strip()
    amount  = str(item.get("amount_summary") or item.get("support_detail") or "").strip()
    target  = str(item.get("target_summary") or "").strip()
    apply   = item.get("apply_type_label", "")
    period  = item.get("apply_period", "")

    parts = []

    # 1. summary가 있으면 첫 문장 사용
    if summary:
        first = re.split(r'[\r\n。]', summary)[0].strip()
        first = re.sub(r'^[○◎·•\-\s]+', '', first).strip()
        if first:
            parts.append(first)

    # 2. 금액 키워드: amount 첫 줄에서 숫자+단위 포함 문장 추출
    if amount:
        first_line = re.split(r'[\r\n]', amount)[0].strip()
        first_line = re.sub(r'^[○◎·•\-\s]+', '', first_line).strip()
        if first_line and first_line not in ' '.join(parts):
            parts.append(first_line)

    # 3. 신청방법 + 기간
    if apply and period:
        parts.append(f"{apply} 신청 가능 ({period})")
    elif apply:
        parts.append(f"{apply} 신청 가능")

    desc = ' '.join(parts)

    # 155자 초과 시 자르기
    if len(desc) > 155:
        desc = desc[:152] + '...'

    # 빈 경우 fallback
    if not desc:
        desc = f"{name} 신청자격, 지원금액, 신청방법을 쉽게 정리했습니다. {dept} 지원금 상세 안내."

    return desc


def build_faqs(item):
    """항목별 자동 FAQ 생성"""
    faqs = []
    name = item.get("name", "이 지원금")
    targets = item.get("targets", [])
    conditions = item.get("conditions", [])

    # 나이 FAQ
    age_q = None
    for c in conditions:
        if c.get("age_min") and c.get("age_max"):
            age_q = {"q": f"{name} 신청 나이 기준이 어떻게 되나요?",
                     "a": f"만 {c['age_min']}세 이상 만 {c['age_max']}세 이하인 분이 신청할 수 있어요."}
            break
    if age_q:
        faqs.append(age_q)

    # 소득 FAQ
    for c in conditions:
        if c.get("income_pct"):
            faqs.append({
                "q": f"{name} 소득 기준이 어떻게 되나요?",
                "a": f"가구 소득이 기준 중위소득 {c['income_pct']}% 이하인 분이 신청할 수 있어요. 정확한 소득인정액은 주민센터에서 확인하세요."
            })
            break

    # 신청방법 FAQ
    apply_type = item.get("apply_type_label", "")
    faqs.append({
        "q": f"{name}은 어디서 신청하나요?",
        "a": f"{apply_type} 방법으로 신청할 수 있어요. " +
             ("복지로(bokjiro.go.kr)에서 온라인 신청이 가능하고, " if "온라인" in apply_type else "") +
             ("가까운 읍·면·동 주민센터에 방문해서 신청할 수도 있어요." if "방문" in apply_type else "자세한 내용은 해당 기관에 문의하세요.")
    })

    # 중복 FAQ
    faqs.append({
        "q": f"다른 지원금을 받고 있어도 {name}을 신청할 수 있나요?",
        "a": "다른 지원금과 중복 수혜 가능 여부는 사업마다 달라요. 신청 전 담당 기관에 중복 수혜 가능 여부를 반드시 확인하세요."
    })

    return faqs[:4]


# ══════════════════════════════════════════════════════════
# 페이지 생성
# ══════════════════════════════════════════════════════════

def generate_detail_pages(all_items):
    """지원금별 상세 페이지 생성"""
    tmpl = env.get_template("detail.html")
    generated = 0

    # 관련 지원금 인덱스 (대상자 기준)
    target_index = {}
    for it in all_items:
        for t in it.get("targets", []):
            target_index.setdefault(t, []).append(it)

    for item in all_items:
        if item.get("is_closed"):
            continue  # 마감 항목은 생성 스킵 (선택적)

        # 관련 지원금 (같은 대상자 중 랜덤 3개)
        related = []
        for t in item.get("targets", []):
            candidates = [x for x in target_index.get(t, []) if x["slug"] != item["slug"]]
            related.extend(candidates[:2])
        # 중복 제거 후 3개
        seen = set()
        item["related"] = []
        for r in related:
            if r["slug"] not in seen and len(item["related"]) < 3:
                seen.add(r["slug"])
                item["related"].append(r)

        out_path = JIWON_DIR / f"{item['slug']}.html"
        try:
            html = tmpl.render(item=item, year=datetime.now().year)
            out_path.write_text(html, encoding="utf-8")
            generated += 1
        except Exception as e:
            print(f"  [오류] {item.get('name')}: {e}")

        if generated % 500 == 0:
            print(f"  상세 페이지 {generated}건 생성 중...")

    print(f"✓ 상세 페이지 총 {generated}건 생성")
    return generated


def generate_target_pages(all_items):
    """대상자별 페이지 생성"""
    for target in TARGETS:
        items = [x for x in all_items if target in x.get("targets", [])]
        if not items:
            continue

        html = build_category_page(
            title=f"{target} 지원금 {CUR_YEAR} 총정리",
            description=f"{CUR_YEAR}년 {target} 정부지원금 종류와 신청방법을 총정리했습니다.",
            items=items,
            category_type="target",
            category_name=target,
            filters=FIELDS,
            filter_type="field",
            base_path="../",
        )
        out = TARGET_DIR / f"{target}.html"
        out.write_text(html, encoding="utf-8")

    print(f"✓ 대상자별 페이지 {len(TARGETS)}건 생성")


def generate_field_pages(all_items):
    """분야별 페이지 생성"""
    for field in FIELDS:
        items = [x for x in all_items if field in x.get("fields", [])]
        if not items:
            continue

        html = build_category_page(
            title=f"{field} 지원금 {CUR_YEAR} 총정리",
            description=f"{CUR_YEAR}년 {field} 정부지원금 종류와 신청방법을 총정리했습니다.",
            items=items,
            category_type="field",
            category_name=field,
            filters=TARGETS,
            filter_type="target",
            base_path="../",
        )
        out = FIELD_DIR / f"{field}.html"
        out.write_text(html, encoding="utf-8")

    print(f"✓ 분야별 페이지 {len(FIELDS)}건 생성")


def build_category_page(title, description, items, category_type,
                         category_name, filters, filter_type, base_path):
    """대상자별/분야별 페이지 HTML 생성"""
    cards_html = ""
    for item in items[:60]:  # 페이지당 최대 60건
        cards_html += render_card(item, base_path)

    filter_btns = f'<button class="tab-btn active" data-filter="all">전체</button>\n'
    for f in filters:
        filter_btns += f'<button class="tab-btn" data-filter="{f}">{f}</button>\n'

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — 신청방법 &amp; 자격 | bojopass</title>
  <meta name="description" content="{description}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="bojopass">
  <meta property="og:locale" content="ko_KR">
  <meta property="og:image" content="https://wooabojopass.wooahouse.com/og.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="https://wooabojopass.wooahouse.com/og.png">
  <link rel="canonical" href="https://wooabojopass.wooahouse.com/{('대상' if category_type == 'target' else '분야')}/{category_name}.html">
  <link rel="stylesheet" href="{base_path}css/style.css">
</head>
<body>
<header class="header">
  <div class="header-inner">
    <a href="{base_path}index.html" class="logo">bojo<span>pass</span></a>
    <div class="header-search">
      <span class="search-icon">🔍</span>
      <input type="text" id="catSearch" placeholder="찾는 지원금을 검색하세요">
    </div>
    <nav class="header-nav">
      <a href="{base_path}list.html">전체 목록</a>
      <a href="{base_path}calendar.html">신청 캘린더</a>
    </nav>
  </div>
</header>

<script src="{base_path}js/wooa-sites-bar.js"></script>

<div class="ad-wrap">
  <div class="ad-slot ad-slot-top"><!-- 광고 --></div>
</div>

<div style="background:linear-gradient(135deg,#FFF7ED,#FFEDD5);padding:36px 20px;text-align:center;border-bottom:1px solid #FFE4C4;">
  <div style="font-size:13px;font-weight:600;color:var(--primary);margin-bottom:8px;">{CUR_YEAR} 최신 정보</div>
  <h1 style="font-size:clamp(22px,4vw,32px);font-weight:800;letter-spacing:-0.5px;">{title}</h1>
  <p style="color:var(--text-secondary);margin-top:8px;">총 {len(items)}개 지원금 · 매일 자동 업데이트</p>
</div>

<div class="section">
  <div class="tabs" id="filterTabs">
    {filter_btns}
  </div>
  <div class="card-grid" id="cardGrid">
    {cards_html}
  </div>
</div>

<div style="margin:0 20px 20px;display:flex;justify-content:center;">
  <div class="ad-slot ad-slot-mid"><!-- 광고 --></div>
</div>

<footer class="footer">
  <div class="footer-inner">
    <div class="footer-top">
      <div>
        <div class="footer-logo">bojo<span>pass</span></div>
        <p class="footer-desc">정부지원금 및 복지혜택 정보를 쉽고 빠르게.</p>
      </div>
      <div class="footer-links">
        <a href="{base_path}list.html">전체 목록</a>
        <a href="{base_path}privacy.html">개인정보처리방침</a>
      </div>
    </div>
    <div class="footer-bottom"><p>© {CUR_YEAR} bojopass</p></div>
  </div>
</footer>
<script>
document.querySelectorAll('#filterTabs .tab-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('#filterTabs .tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const f = btn.dataset.filter;
    document.querySelectorAll('#cardGrid .jiwon-card').forEach(card => {{
      card.style.display = (f === 'all' || card.dataset.tags?.includes(f)) ? '' : 'none';
    }});
  }});
}});
document.getElementById('catSearch').addEventListener('input', e => {{
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('#cardGrid .jiwon-card').forEach(card => {{
    const text = card.textContent.toLowerCase();
    card.style.display = (!q || text.includes(q)) ? '' : 'none';
  }});
}});
</script>
</body>
</html>"""


def render_card(item, base_path=""):
    """지원금 카드 HTML 조각"""
    source_badge = "중앙부처" if item.get("source") == "central" else "지자체"
    source_class = "badge-source-central" if item.get("source") == "central" else "badge-source-local"
    tags = " ".join(item.get("targets", []) + item.get("fields", []))
    name = item.get("name", "")
    dept = item.get("dept", "")
    slug = item.get("slug", "")
    amount = str(item.get("amount_summary", ""))[:30]
    period = item.get("apply_period", "")
    summary = str(item.get("summary", ""))[:80]
    dday_class = item.get("dday_class", "badge-dday-safe")
    dday_label = item.get("dday_label", "")

    is_closed = item.get("is_closed", False)
    if is_closed:
        return f"""<div class="jiwon-card jiwon-card--closed" data-tags="{tags}">
  <div class="card-top">
    <div class="card-badges">
      <span class="badge {source_class}">{source_badge}</span>
    </div>
    <span class="badge-dday {dday_class}">{dday_label}</span>
  </div>
  <div class="card-title">{name}</div>
  <div class="card-dept">{dept}</div>
  <div class="card-info">
    <div class="card-info-item">
      <span class="card-info-label">지원내용</span>
      <span class="card-info-value">{amount}</span>
    </div>
    <div class="card-info-item">
      <span class="card-info-label">신청기간</span>
      <span class="card-info-value">{period}</span>
    </div>
  </div>
  <div class="card-target">{summary}</div>
  <div class="card-btn card-btn--closed">마감된 지원금</div>
</div>"""
    return f"""<a href="{base_path}jiwon/{slug}.html" class="jiwon-card" data-tags="{tags}">
  <div class="card-top">
    <div class="card-badges">
      <span class="badge {source_class}">{source_badge}</span>
    </div>
    <span class="badge-dday {dday_class}">{dday_label}</span>
  </div>
  <div class="card-title">{name}</div>
  <div class="card-dept">{dept}</div>
  <div class="card-info">
    <div class="card-info-item">
      <span class="card-info-label">지원내용</span>
      <span class="card-info-value">{amount}</span>
    </div>
    <div class="card-info-item">
      <span class="card-info-label">신청기간</span>
      <span class="card-info-value">{period}</span>
    </div>
  </div>
  <div class="card-target">{summary}</div>
  <div class="card-btn">자세히 보기 →</div>
</a>"""


def generate_sitemap(all_items):
    """sitemap.xml 자동 생성"""
    today = TODAY.strftime("%Y-%m-%d")
    urls = [
        '<url><loc>https://wooabojopass.wooahouse.com/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>',
        '<url><loc>https://wooabojopass.wooahouse.com/list.html</loc><changefreq>daily</changefreq><priority>0.9</priority></url>',
        '<url><loc>https://wooabojopass.wooahouse.com/calendar.html</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>',
    ]
    for t in TARGETS:
        urls.append(f'<url><loc>https://wooabojopass.wooahouse.com/대상/{t}.html</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for f in FIELDS:
        urls.append(f'<url><loc>https://wooabojopass.wooahouse.com/분야/{f}.html</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for item in all_items:
        if not item.get("is_closed"):
            urls.append(f'<url><loc>https://wooabojopass.wooahouse.com/jiwon/{item["slug"]}.html</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>')

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "\n".join(urls)
    xml += "\n</urlset>"

    (DOCS_DIR / "sitemap.xml").write_text(xml, encoding="utf-8")
    print(f"✓ sitemap.xml 생성 ({len(urls)}개 URL)")


# ══════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════

def main():
    start = datetime.now()
    print(f"=== 페이지 생성 시작: {start.strftime('%Y-%m-%d %H:%M:%S')} ===")

    # ── 데이터 로드
    central = json.loads((DATA_DIR / "central.json").read_text(encoding="utf-8")) if (DATA_DIR / "central.json").exists() else []
    local   = json.loads((DATA_DIR / "local.json").read_text(encoding="utf-8"))   if (DATA_DIR / "local.json").exists()   else []

    print(f"  중앙부처: {len(central)}건 / 지자체: {len(local)}건")

    # ── 상세 데이터 병합 + 아이템 빌드
    all_items = []
    for raw in central + local:
        item_id = str(raw.get("id", ""))
        detail_path = DETAIL_DIR / f"{item_id}.json"
        detail = {}
        if detail_path.exists():
            try:
                detail = json.loads(detail_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        built = build_item(raw, detail)
        all_items.append(built)

    print(f"  전체: {len(all_items)}건 빌드 완료")

    # ── 페이지 생성
    generate_detail_pages(all_items)
    generate_target_pages(all_items)
    generate_field_pages(all_items)
    generate_sitemap(all_items)

    # ── docs/data/ 에 JSON 복사 (클라이언트 사이드 로드용)
    docs_data_dir = DOCS_DIR / "data"
    docs_data_dir.mkdir(exist_ok=True)
    import shutil
    shutil.copy(DATA_DIR / "central.json", docs_data_dir / "central.json")
    shutil.copy(DATA_DIR / "local.json",   docs_data_dir / "local.json")
    print(f"✓ docs/data/ JSON 복사 완료")

    # ── 통계 JSON 생성 (이번달 마감 등 사전 계산)
    this_month_end = [
        x for x in all_items
        if x.get("dday_class") in ("badge-dday-danger", "badge-dday-warn")
    ]
    stats = {
        "total":      len(all_items),
        "central":    len([x for x in all_items if x.get("source") == "central"]),
        "local":      len([x for x in all_items if x.get("source") == "local"]),
        "deadline":   len(this_month_end),
        "active":     len([x for x in all_items if not x.get("is_closed")]),
    }
    (docs_data_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")
    print(f"✓ docs/data/stats.json 생성 (이번달 마감: {stats['deadline']}건)")

    elapsed = (datetime.now() - start).seconds
    print(f"\n=== 완료: {elapsed}초 소요 ===")


if __name__ == "__main__":
    main()
