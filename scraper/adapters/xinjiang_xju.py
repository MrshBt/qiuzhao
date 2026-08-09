# -*- coding: utf-8 -*-
"""新疆大学就业网适配器(官方本地源)。

抓取 https://job.xju.edu.cn/Web/Employ/NetEmployList 网络招聘列表,
以及首页校外招聘公告。
"""
import logging
import re

import requests

log = logging.getLogger("xinjiang_xju")

HOME = "https://job.xju.edu.cn"
NET_LIST = HOME + "/Web/Employ/NetEmployList"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

XJ_SOURCES = ("新疆", "乌鲁木齐", "兵团", "阿克苏", "喀什", "和田", "伊犁",
              "塔城", "昌吉", "巴州", "阿勒泰", "哈密", "克拉玛依", "吐鲁番",
              "博州", "克州", "石河子")


def _abs(url):
    if not url:
        return None
    if url.startswith("http"):
        return url
    return HOME + url if url.startswith("/") else HOME + "/" + url


def _parse_net_list(html):
    """解析网络招聘列表(table 结构),返回 [(company, title, location, date, link)]。"""
    items = []
    m = re.search(r'<table[^>]*class="[^"]*jobInfo-table[^"]*"[^>]*>(.*?)</table>',
                  html, re.S)
    if not m:
        return items
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 6:
            continue
        am = re.search(r'<a[^>]*href="([^"]+)"', tds[0])
        if not am:
            continue
        company = re.sub(r"<[^>]+>", "", tds[0]).strip()
        title = re.sub(r"<[^>]+>", "", tds[1]).strip()
        location = re.sub(r"<[^>]+>", "", tds[2]).strip()
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", re.sub(r"<[^>]+>", "", tds[5]))
        date = dm.group(1) if dm else None
        if not company or not title or not date:
            continue
        items.append((company, title, location, date, _abs(am.group(1))))
    return items


def _norm_type(company, guoqi_dict):
    name = company or ""
    if name in guoqi_dict:
        return guoqi_dict[name]
    if any(k in name for k in ("银行", "农信社", "信用社", "农商行")):
        return "银行"
    if any(k in name for k in ("研究院", "设计院", "研究所", "科学院")):
        return "研究所"
    if any(k in name for k in ("学院", "学校", "组织部", "人社局", "公安局", "市人民政府", "县委")):
        return "事业单位"
    return "民企"


def fetch(max_pages=3, session=None, guoqi_dict=None):
    """抓取新疆大学就业网网络招聘。返回 (items, total)。"""
    items = []
    session = session or requests.Session()
    guoqi_dict = guoqi_dict or {}
    try:
        resp = session.get(NET_LIST, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
    except requests.RequestException as e:
        log.warning("新疆大学就业网访问失败: %s", e)
        return items, 0
    seen = set()
    for company, title, location, date, url in _parse_net_list(resp.text):
        if not company or not title:
            continue
        if not date:
            continue  # 无发布日期的为导航杂项,跳过
        key = (company, title, date)
        if key in seen:
            continue
        seen.add(key)
        local = any(k in (title + company + (location or "")) for k in XJ_SOURCES)
        items.append(
            {
                "company": company,
                "type": _norm_type(company, guoqi_dict),
                "location": location or ("新疆" if local else ""),
                "positions": [title],
                "publish_date": date,
                "deadline": None,
                "link": url,
                "source": "xinjiang_xju",
                "batch": "本地招聘",
                "deadline_note": "",
            }
        )
    return items, len(items)
