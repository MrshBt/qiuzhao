# -*- coding: utf-8 -*-
"""合并与去重。

策略:
- 自动源(nowcoder/iguopin/xinjiang/wechat)每次全量抓取,按 (source, company, positions, deadline) 去重
- 与旧数据 data/jobs.json 增量合并:自动源条目按 (source, link) 去重,手动源条目按 (company, title) 去重
- 空结果保护:自动源返回 0 条时保留旧数据
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
JOBS_FILE = os.path.join(DATA_DIR, "jobs.json")
MANUAL_DIR = os.path.join(DATA_DIR, "manual")


def load_manual():
    """加载 data/manual/*.json 手动录入的条目(解析失败的文件跳过)。"""
    import logging

    log = logging.getLogger("merge")
    items = []
    if not os.path.isdir(MANUAL_DIR):
        return items
    for fn in sorted(os.listdir(MANUAL_DIR)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(MANUAL_DIR, fn)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.warning("手动录入文件解析失败 %s: %s", fn, e)
            continue
        if isinstance(data, list):
            items.extend(data)
        elif isinstance(data, dict) and isinstance(data.get("items"), list):
            items.extend(data["items"])
    for it in items:
        it["source"] = "manual"
        it["batch"] = it.get("batch") or "手动录入"
    return items


def load_old():
    if not os.path.isfile(JOBS_FILE):
        return []
    with open(JOBS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("items", data) if isinstance(data, dict) else data


def _dedup(items, key_fn):
    seen = set()
    out = []
    for it in items:
        key = key_fn(it)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def merge(auto_items, manual_items, old_items):
    """合并自动源、手动源与旧数据。

    自动源条目以 link 为主键去重;手动源以 (company, title) 去重;
    旧数据中已不存在的自动源条目保留(历史快照),但标记 stale 由前端降权。
    """
    merged = []
    seen_auto = set()
    seen_manual = set()

    auto_items = _dedup(
        auto_items,
        lambda x: (
            x["source"],
            x.get("company"),
            x.get("batch"),
            x.get("publish_date"),
            x.get("deadline"),
            tuple(sorted(x.get("positions", []))),
        ),
    )
    for it in auto_items:
        if it.get("source") != "manual":
            seen_auto.add(
                (
                    it.get("company"),
                    it.get("batch"),
                    it.get("publish_date"),
                    it.get("deadline"),
                )
            )
        merged.append(it)

    for it in manual_items:
        key = (it.get("company"), "".join(it.get("positions", [])))
        if key in seen_manual:
            continue
        seen_manual.add(key)
        merged.append(it)

    for it in old_items:
        src = it.get("source")
        if src == "manual":
            key = (it.get("company"), "".join(it.get("positions", [])))
            if key in seen_manual:
                continue
            seen_manual.add(key)
            merged.append(it)
        elif (
            it.get("company"),
            it.get("batch"),
            it.get("publish_date"),
            it.get("deadline"),
        ) not in seen_auto:
            if not _fresh(it):
                continue  # 自动源旧条目(>90 天)直接清理
            it = dict(it)
            it["stale"] = True
            merged.append(it)
    return merged


def _fresh(it, days=90):
    """自动源旧条目超过 days 天直接丢弃。"""
    p = it.get("publish_date") or it.get("deadline")
    if not p:
        return True
    try:
        import datetime

        d = datetime.datetime.strptime(str(p)[:10], "%Y-%m-%d")
        return (datetime.datetime.now() - d).days <= days
    except ValueError:
        return True


def save(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {
        "updated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(items),
        "items": items,
    }
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return JOBS_FILE
