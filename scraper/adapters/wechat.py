# -*- coding: utf-8 -*-
"""微信公众号适配器(尽力而为)。

搜狗微信文章搜索通常会被反爬拦截(返回空壳页),此适配器设计为:
1. 尝试搜狗微信文章搜索
2. 解析失败返回空列表并记录原因,不影响其他源
微信公众号信息的主要途径是手动录入 data/manual/*.json。
"""
import logging
import re

import requests

log = logging.getLogger("wechat")

SEARCH_URL = "https://weixin.sogou.com/weixin"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://weixin.sogou.com/",
}

KEYWORDS = ("27届秋招", "2027届秋招", "秋季校园招聘", "校招启动")


def _parse_article_list(html):
    """解析搜狗微信文章列表。返回 [(title, account, link, time)]。"""
    items = []
    for m in re.finditer(
        r'<li[^>]*class="[^"]*news-list[^"]*"[^>]*>(.*?)</li>', html, re.S
    ):
        block = m.group(1)
        tm = re.search(r'<a[^>]*href="([^"]+)"[^>]*target="_blank"[^>]*>(.*?)</a>',
                       block, re.S)
        if not tm:
            continue
        url = tm.group(1)
        title = re.sub(r"<[^>]+>", "", tm.group(2))
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            continue
        acc = re.search(r'class="account"[^>]*>(.*?)</a>', block, re.S)
        account = re.sub(r"<[^>]+>", "", acc.group(1)).strip() if acc else ""
        t = re.search(r'(\d+天前|刚刚|\d+小时前|\d+月\d+日|\d{4}-\d{2}-\d{2})', block)
        when = t.group(1) if t else ""
        items.append((title, account, url, when))
    return items


def fetch(session=None, guoqi_dict=None):
    """尝试从搜狗微信搜索抓取校招相关公众号文章。返回 (items, error)。"""
    s = session or requests.Session()
    items = []
    error = None
    for kw in KEYWORDS:
        try:
            resp = s.get(
                SEARCH_URL,
                params={"type": 1, "query": kw, "ie": "utf8"},
                headers=HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            html = resp.text
            if "antispider" in html or len(html) < 20000:
                continue
            rows = _parse_article_list(html)
            for title, account, link, when in rows:
                items.append(
                    {
                        "company": account or "微信公众号",
                        "type": None,
                        "location": "",
                        "positions": [title],
                        "publish_date": None,
                        "deadline": None,
                        "link": link,
                        "source": "wechat",
                        "batch": "公众号",
                        "deadline_note": "",
                        "extra": {"account": account, "publish_note": when},
                    }
                )
        except requests.RequestException as e:
            error = str(e)
            break
    if not items:
        log.warning("wechat: 搜狗微信搜索未返回可解析内容(可能被反爬): %s", error)
    return items, error
