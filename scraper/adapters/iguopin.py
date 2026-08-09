# -*- coding: utf-8 -*-
"""国聘网适配器。

API: POST https://gp-api.iguopin.com/api/jobs/v1/recom-job
无签名即可用,page_size 上限 20;需客户端过滤"校园招聘"。
"""
import time

import requests

API = "https://gp-api.iguopin.com/api/jobs/v1/recom-job"
DETAIL_PREFIX = "https://www.iguopin.com/job/detail?id="

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.iguopin.com/job",
    "Content-Type": "application/json",
}

CAMPUS_KEYWORDS = ("校园招聘", "校招", "应届")


def _fetch_page(page, page_size=20, session=None):
    s = session or requests.Session()
    resp = s.post(
        API,
        headers=HEADERS,
        json={
            "search": {"page": page, "page_size": page_size},
            "recom": {"update_time": True, "company_nature": True, "hot_job": True},
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200 and data.get("code") != 0:
        raise RuntimeError("iguopin API error: %s" % data)
    return data


def _is_campus(job):
    rtype = job.get("recruitment_type_cn") or ""
    return any(k in rtype for k in CAMPUS_KEYWORDS)


def _norm_type(job, company):
    """企业类型:优先 company_info.nature_cn,关键词兜底。"""
    info = job.get("company_info") or {}
    nature = info.get("nature_cn") or job.get("company_nature_cn") or ""
    name = company or ""
    if any(k in name for k in ("银行", "农信社", "信用社")):
        return "银行"
    if any(k in nature for k in ("央企", "国企")):
        return "国企/央企"
    if any(k in nature for k in ("外资", "外企", "合资")):
        return "外企"
    if any(k in nature for k in ("事业单位", "机关", "其他")):
        return "事业单位"
    return "民企"


def _nature_of(job):
    """返回规范化后的企业性质(用于词典)。"""
    info = job.get("company_info") or {}
    nature = info.get("nature_cn") or job.get("company_nature_cn") or ""
    if any(k in nature for k in ("央企", "国企")):
        return "国企/央企"
    if any(k in nature for k in ("外资", "外企", "合资")):
        return "外企"
    if any(k in nature for k in ("事业单位", "机关")):
        return "事业单位"
    if any(k in nature for k in ("民企", "民营")):
        return "民企"
    return None


def _extract_job(job):
    company = job.get("company_name") or ""
    district = job.get("district_list") or []
    area = district[0].get("area_cn") if district else ""
    info = job.get("company_info") or {}
    industry = info.get("industry_cn") or ""
    return {
        "company": company,
        "type": _norm_type(job, company),
        "location": area,
        "positions": [job.get("job_name") or ""],
        "publish_date": (job.get("start_time") or "")[:10] or None,
        "deadline": (job.get("end_time") or "")[:10] or None,
        "link": DETAIL_PREFIX + str(job.get("job_id")),
        "source": "iguopin",
        "batch": "国聘",
        "deadline_note": "",
        "extra": {
            "education": job.get("education_cn") or "",
            "major": "、".join(job.get("major_cn") or []) or "",
            "industry": industry,
            "nature": _nature_of(job),
        },
    }


def fetch(max_pages=30):
    """抓国聘校园招聘岗位(推荐流,按更新时间排序)。返回 (items, total)。"""
    items = []
    seen = set()
    session = requests.Session()
    total = None
    page = 1
    while page <= max_pages:
        try:
            data = _fetch_page(page, session=session)
        except requests.RequestException:
            break
        payload = data.get("data") or {}
        total = payload.get("total", total)
        jobs = payload.get("list") or []
        if not jobs:
            break
        for job in jobs:
            if not _is_campus(job):
                continue
            item = _extract_job(job)
            key = (item["company"], item["positions"][0], item["deadline"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
        if len(jobs) < 20:
            break
        page += 1
        time.sleep(0.2)
    return items, total


def collect_natures(items, out_path=None):
    """从抓取结果收集 公司名 -> 性质 词典,与旧词典合并后落盘。

    返回合并后的词典 dict。
    """
    import json
    import os

    old = {}
    if out_path and os.path.isfile(out_path):
        try:
            with open(out_path, encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            old = {}
    merged = dict(old)
    for it in items:
        nature = (it.get("extra") or {}).get("nature")
        company = it.get("company")
        if nature and company:
            merged[company] = nature
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=0)
    return merged
