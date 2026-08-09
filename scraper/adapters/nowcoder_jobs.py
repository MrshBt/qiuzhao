# -*- coding: utf-8 -*-
"""牛客网校招职位(岗位级)适配器。

API: POST https://www.nowcoder.com/np-api/u/job/search
无登录、无 cookie 即可用。
"""
import datetime
import re
import time

import requests

API = "https://www.nowcoder.com/np-api/u/job/search"
JOB_DETAIL = "https://www.nowcoder.com/jobs/detail/%s"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nowcoder.com/jobs/school/jobs",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _fetch_page(page, page_size=50, session=None):
    s = session or requests.Session()
    resp = s.post(
        API,
        headers=HEADERS,
        data={"page": page, "pageSize": page_size, "recruitType": 1},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError("nowcoder jobs API error: %s" % data)
    return data["data"]


def _parse_time(ms):
    if not ms:
        return None
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def _norm_type(company_name, industry_tags, guoqi_dict):
    """岗位级数据没有企业性质字段,用国聘词典 + 关键词兜底。"""
    name = company_name or ""
    if name in guoqi_dict:
        return guoqi_dict[name]
    if any(k in name for k in ("银行", "农信社", "信用社", "农商行")):
        return "银行"
    text = " ".join(industry_tags or [])
    if any(k in text for k in ("银行", "证券", "保险")):
        return "银行/金融"
    if any(k in text for k in ("游戏", "互联网", "软件", "电商")):
        return "互联网"
    return "民企"


def _build_item(d, guoqi_dict):
    company = (d.get("recommendInternCompany") or {}).get("companyName") or ""
    if not company:
        identity = d.get("user", {}).get("identity") or []
        company = identity[0].get("companyName") if identity else ""
    industry = (d.get("recommendInternCompany") or {}).get("industryTagNameList") or []
    grad = d.get("graduationYear") or ""
    job_name = d.get("jobName") or ""
    positions = [job_name]
    if grad and grad not in ("毕业不限",):
        positions.append(grad)
    # 批次判定:优先看岗位名/毕业届次中的届数
    text = job_name + " " + grad
    if re.search(r"2027|27届", text):
        batch = "27届秋招"
    elif re.search(r"2026|26届", text):
        batch = "26届校招"
    else:
        batch = "校招职位"
    extra = {
        "education": {5000: "本科", 4000: "硕士", 3000: "博士"}.get(d.get("eduLevel"), ""),
        "major": "",
        "industry": "、".join(industry) or "",
        "salary": _fmt_salary(d),
    }
    return {
        "company": company,
        "type": _norm_type(company, industry, guoqi_dict),
        "location": "、".join(d.get("jobCityList") or [d.get("jobCity")] or []),
        "positions": positions,
        "publish_date": _parse_time(d.get("createTime")) or _parse_time(
            d.get("refreshTime")
        ),
        "deadline": _parse_time(d.get("deliverEnd")),
        "link": JOB_DETAIL % d.get("id"),
        "source": "nowcoder_jobs",
        "batch": batch,
        "deadline_note": "",
        "extra": extra,
    }


def _fmt_salary(d):
    lo, hi, mon = d.get("salaryMin"), d.get("salaryMax"), d.get("salaryMonth")
    if not lo:
        return ""
    unit = "K/月" if (lo or 0) < 100 else "元/月"
    if hi and hi > lo:
        return "%s-%s%s" % (lo, hi, unit)
    return "%s%s" % (lo, unit)


def fetch(max_pages=20, session=None, guoqi_dict=None):
    """抓牛客校招职位(岗位级)。返回 (items, total)。"""
    items = []
    seen = set()
    session = session or requests.Session()
    guoqi_dict = guoqi_dict or {}
    total = None
    page = 1
    while page <= max_pages:
        try:
            data = _fetch_page(page, session=session)
        except requests.RequestException:
            break
        total = data.get("totalCount", total)
        datas = data.get("datas") or []
        if not datas:
            break
        for d in datas:
            item = _build_item(d, guoqi_dict)
            key = (item["company"], item["positions"][0], item["deadline"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
        if page >= data.get("totalPage", 0):
            break
        page += 1
        time.sleep(0.3)
    return items, total
