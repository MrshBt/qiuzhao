# -*- coding: utf-8 -*-
"""新疆师范大学就业指导中心适配器(官方本地源)。

抓取 https://jyzdzx.xjnu.edu.cn/zpxx.htm 招聘信息列表页,提取招聘公告/微信转载文章。
列表结构:<ul class="text-list2"> <li><a href=...><div class="date2"><p>日</p><span>年-月</span></div>
<h3>标题</h3></a></li> ...
"""
import datetime
import logging
import re

import requests

log = logging.getLogger("xinjiang")

HOME = "https://jyzdzx.xjnu.edu.cn/"
LIST_PAGE = "https://jyzdzx.xjnu.edu.cn/zpxx.htm"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

XJ_SOURCES = ("新疆", "乌鲁木齐", "兵团", "阿克苏", "喀什", "和田", "伊犁",
              "塔城", "昌吉", "巴州", "阿勒泰", "哈密", "克拉玛依", "吐鲁番",
              "博州", "克州", "石河子")


def _abs(href):
    if not href:
        return None
    if href.startswith("http"):
        return href
    return HOME + href.lstrip("/")


def _parse_list(html):
    """解析招聘信息列表,返回 [(title, link, date)]。"""
    items = []
    m = re.search(r'<ul class="text-list2">(.*?)</ul>', html, re.S)
    if not m:
        return items
    for li in re.findall(r"<li>(.*?)</li>", m.group(1), re.S):
        am = re.search(r'<a[^>]*href="([^"]+)"', li)
        if not am:
            continue
        tm = re.search(r"<h3[^>]*>(.*?)</h3>", li, re.S)
        if not tm:
            continue
        title = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
        if not title:
            continue
        dm = re.search(r'<span>(\d{4})-(\d{2})</span>', li)
        dom = re.search(r"<p>(\d{1,2})</p>", li)
        if not dm:
            continue
        year, month = int(dm.group(1)), int(dm.group(2))
        day = int(dom.group(1)) if dom else 1
        try:
            date = datetime.date(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            date = "%04d-%02d-%02d" % (year, month, 1)
        items.append((title, _abs(am.group(1)), date))
    return items


def fetch(max_pages=3, session=None, guoqi_dict=None):
    """抓取新疆师大就业指导中心招聘信息。返回 (items, total)。"""
    items = []
    seen = set()
    session = requests.Session()
    try:
        resp = session.get(LIST_PAGE, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
    except requests.RequestException as e:
        log.warning("新疆就业网访问失败: %s", e)
        return items, 0
    rows = _parse_list(resp.text)
    for title, link, date in rows:
        key = (title, date)
        if key in seen:
            continue
        seen.add(key)
        local = any(k in title for k in XJ_SOURCES)
        items.append(
            {
                "company": "新疆本地招聘",
                "type": "事业单位",
                "location": "新疆" if local else "新疆(及全国)",
                "positions": [title],
                "publish_date": date,
                "deadline": None,
                "link": link,
                "source": "xinjiang",
                "batch": "本地招聘",
                "deadline_note": "",
            }
        )
    return items, len(items)
