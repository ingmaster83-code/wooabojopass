"""
fetch_data.py — 공공데이터 API 수집 스크립트
- 행정안전부 혜택알리미 (중앙부처 지원금)
- 한국사회보장정보원 지자체복지서비스
"""

import os
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

import sys
import requests
from dotenv import load_dotenv

# ── 환경변수 로드 ──────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env")
API_KEY = os.environ.get("API_KEY", "")
if not API_KEY:
    raise SystemExit("API_KEY 환경변수가 설정되지 않았습니다.")

# ── 경로 설정 ──────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DETAIL_DIR = DATA_DIR / "detail"
DATA_DIR.mkdir(exist_ok=True)
DETAIL_DIR.mkdir(exist_ok=True)

# ── 기존 데이터 로드 (증분 업데이트용) ───────────────────
def load_existing(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def existing_ids(items):
    return {str(item.get("id", "")) for item in items}

# ── 공통 유틸 ──────────────────────────────────────────────
def get_json(url, params, retry=3):
    for attempt in range(retry):
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  [재시도 {attempt+1}/{retry}] {e}")
            time.sleep(1)
    return None

def get_xml(url, params, retry=3):
    for attempt in range(retry):
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            return ET.fromstring(r.content)
        except Exception as e:
            print(f"  [재시도 {attempt+1}/{retry}] {e}")
            time.sleep(1)
    return None

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ══════════════════════════════════════════════════════════
# 1. 행정안전부 혜택알리미 (중앙부처)
# ══════════════════════════════════════════════════════════

CENTRAL_LIST_URL   = "https://api.odcloud.kr/api/gov24/v3/serviceList"
CENTRAL_DETAIL_URL = "https://api.odcloud.kr/api/gov24/v3/serviceDetail"
CENTRAL_COND_URL   = "https://api.odcloud.kr/api/gov24/v3/supportConditions"

def fetch_central_list():
    """전체 중앙부처 지원금 목록 수집 (페이지 순회)"""
    print("\n[중앙부처] 목록 수집 시작...")
    all_items = []
    page = 1
    per_page = 100

    while True:
        params = {
            "page": page,
            "perPage": per_page,
            "serviceKey": API_KEY,
        }
        data = get_json(CENTRAL_LIST_URL, params)
        if not data:
            print(f"  페이지 {page} 호출 실패, 중단")
            break

        items = data.get("data", [])
        total = data.get("totalCount", 0)
        print(f"  페이지 {page} — {len(items)}건 (전체 {total}건)")

        for item in items:
            all_items.append({
                "source": "central",
                "id": str(item.get("서비스ID", "")),
                "name": item.get("서비스명", ""),
                "summary": item.get("서비스목적요약", ""),
                "dept": item.get("소관기관명", ""),
                "ministry": item.get("소관부처명", ""),
                "apply_start": item.get("신청기한시작일", ""),
                "apply_end": item.get("신청기한종료일", ""),
                "apply_type": item.get("신청방법", ""),
                "support_type": item.get("지원유형", ""),
                "target_summary": item.get("지원대상", ""),
                "amount_summary": item.get("지원내용", ""),
                "categories": item.get("서비스분야", ""),
                "life_cycle": item.get("생애주기", ""),
                "url": item.get("신청사이트URL", ""),
            })

        if page * per_page >= total:
            break
        page += 1
        time.sleep(0.5)

    print(f"  ✓ 중앙부처 목록 총 {len(all_items)}건")
    return all_items


def fetch_central_detail(service_id):
    """단일 서비스 상세 + 지원조건 수집"""
    detail = {}
    cond = {}

    # 상세 (cond 필터로 서비스ID 정확히 매칭)
    data = get_json(CENTRAL_DETAIL_URL, {
        "page": 1, "perPage": 1,
        "serviceKey": API_KEY,
        "cond[서비스ID::EQ]": service_id,
    })
    if data and data.get("data"):
        items = data["data"] if isinstance(data["data"], list) else [data["data"]]
        d = next((x for x in items if str(x.get("서비스ID", "")) == str(service_id)), items[0] if items else None)
        if d:
            detail = {
                "apply_detail": d.get("신청방법", ""),
                "support_detail": d.get("지원내용", ""),
                "documents": d.get("구비서류", ""),
                "contact": d.get("문의처", ""),
                "contact_tel": d.get("대표전화번호", ""),
                "online_apply_url": d.get("온라인신청사이트URL", ""),
            }
    time.sleep(0.5)

    # 지원조건 (cond 필터로 서비스ID 정확히 매칭)
    data2 = get_json(CENTRAL_COND_URL, {
        "page": 1, "perPage": 10,
        "serviceKey": API_KEY,
        "cond[서비스ID::EQ]": service_id,
    })
    if data2 and data2.get("data"):
        items = data2["data"] if isinstance(data2["data"], list) else [data2["data"]]
        cond = {
            "conditions": [
                {
                    "age_min": c.get("연령최솟값", ""),
                    "age_max": c.get("연령최댓값", ""),
                    "income_criteria": c.get("소득기준", ""),
                    "income_pct": c.get("기준중위소득퍼센트", ""),
                    "property_criteria": c.get("재산기준", ""),
                    "target_detail": c.get("지원대상상세", ""),
                    "exclude": c.get("제외대상", ""),
                }
                for c in items
            ]
        }
    time.sleep(0.5)

    return {**detail, **cond}


# ══════════════════════════════════════════════════════════
# 2. 한국사회보장정보원 지자체복지서비스
# ══════════════════════════════════════════════════════════

LOCAL_LIST_URL   = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfarelist"
LOCAL_DETAIL_URL = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfaredetailed"

def xml_text(root, tag, default=""):
    el = root.find(f".//{tag}")
    return el.text.strip() if el is not None and el.text else default

def fetch_local_list():
    """전체 지자체 지원금 목록 수집"""
    print("\n[지자체] 목록 수집 시작...")
    all_items = []
    page = 1
    per_page = 100

    while True:
        params = {
            "serviceKey": API_KEY,
            "pageNo": page,
            "numOfRows": per_page,
        }
        root = get_xml(LOCAL_LIST_URL, params)
        if root is None:
            print(f"  페이지 {page} 호출 실패, 중단")
            break

        items = root.findall(".//servList")
        total_el = root.find(".//totalCount")
        total = int(total_el.text) if total_el is not None and total_el.text else 0
        print(f"  페이지 {page} — {len(items)}건 (전체 {total}건)")

        for item in items:
            t = lambda tag: xml_text(item, tag)
            all_items.append({
                "source": "local",
                "id": t("servId"),
                "name": t("servNm"),
                "summary": t("servDgst"),
                "dept": t("intrsAgId"),        # 관심기관ID
                "ministry": t("jurMnofNm"),    # 소관부처명
                "region": t("sigunguNm"),       # 시군구명
                "apply_start": t("aplyBgngDt"),
                "apply_end": t("aplyEndDt"),
                "apply_type": t("aplyMthdCd"),
                "support_type": t("sprtCyclCd"),
                "target_summary": t("trgterIndvdlNm"),
                "amount_summary": t("servDgst"),
                "categories": t("lifeNmArray"),
                "life_cycle": t("lifeNmArray"),
                "url": t("siteAddr"),
            })

        if page * per_page >= total:
            break
        page += 1
        time.sleep(0.5)

    print(f"  ✓ 지자체 목록 총 {len(all_items)}건")
    return all_items


def fetch_local_detail(serv_id):
    """단일 지자체 서비스 상세 수집"""
    params = {"serviceKey": API_KEY, "servId": serv_id}
    root = get_xml(LOCAL_DETAIL_URL, params)
    if root is None:
        return {}
    t = lambda tag: xml_text(root, tag)
    return {
        "support_detail": t("servDgst"),
        "apply_detail": t("aplyMthdCd"),
        "documents": t("rfrnCn"),
        "contact": t("rprsCtadr"),
        "contact_tel": t("rprsCtadr"),
        "online_apply_url": t("siteAddr"),
        "conditions": [{
            "age_min": t("minAge"),
            "age_max": t("maxAge"),
            "income_criteria": t("incmCritCn"),
            "target_detail": t("trgterIndvdlNm"),
            "exclude": "",
        }],
    }


# ══════════════════════════════════════════════════════════
# 메인 실행
# ══════════════════════════════════════════════════════════

def main():
    start = datetime.now()
    print(f"=== 데이터 수집 시작: {start.strftime('%Y-%m-%d %H:%M:%S')} ===")

    # ── 기존 데이터 로드
    existing_central = load_existing(DATA_DIR / "central.json")
    existing_local   = load_existing(DATA_DIR / "local.json")
    old_central_ids  = existing_ids(existing_central)
    old_local_ids    = existing_ids(existing_local)

    # ── 1. 중앙부처 목록
    central_list = fetch_central_list()

    # 신규/변경 감지
    new_central = [x for x in central_list if x["id"] not in old_central_ids]
    print(f"\n[중앙부처] 신규: {len(new_central)}건 / 기존: {len(old_central_ids)}건")

    # 상세 수집 (신규 우선, detail 파일 없는 것 순서로 최대 200건/회)
    new_central_ids = {x["id"] for x in new_central}
    detail_queue = (
        [x for x in central_list if x["id"] in new_central_ids] +
        [x for x in central_list if x["id"] not in new_central_ids
         and not (DETAIL_DIR / f"{x['id']}.json").exists()]
    )
    for i, item in enumerate(detail_queue[:200]):
        print(f"  [중앙부처 상세 {i+1}/{len(detail_queue)}] {item['name'][:30]}")
        detail = fetch_central_detail(item["id"])
        save_json(DETAIL_DIR / f"{item['id']}.json", {**item, **detail})

    save_json(DATA_DIR / "central.json", central_list)
    print(f"\n✓ central.json 저장 완료 ({len(central_list)}건)")

    # ── 2. 지자체 목록
    local_list = fetch_local_list()

    new_local = [x for x in local_list if x["id"] not in old_local_ids]
    print(f"\n[지자체] 신규: {len(new_local)}건 / 기존: {len(old_local_ids)}건")

    new_local_ids = {x["id"] for x in new_local}
    local_queue = (
        [x for x in local_list if x["id"] in new_local_ids] +
        [x for x in local_list if x["id"] not in new_local_ids
         and not (DETAIL_DIR / f"{x['id']}.json").exists()]
    )
    for i, item in enumerate(local_queue[:200]):
        print(f"  [지자체 상세 {i+1}/{len(local_queue)}] {item['name'][:30]}")
        detail = fetch_local_detail(item["id"])
        save_json(DETAIL_DIR / f"{item['id']}.json", {**item, **detail})

    save_json(DATA_DIR / "local.json", local_list)
    print(f"\n✓ local.json 저장 완료 ({len(local_list)}건)")

    elapsed = (datetime.now() - start).seconds // 60
    print(f"\n=== 완료: 총 {elapsed}분 소요 ===")
    print(f"  중앙부처: {len(central_list)}건")
    print(f"  지자체:   {len(local_list)}건")
    print(f"  상세파일: {len(list(DETAIL_DIR.glob('*.json')))}건")


if __name__ == "__main__":
    main()
