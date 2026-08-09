# -*- coding: utf-8 -*-
"""秋招信息爬虫入口。

用法:
    python main.py                # 全量抓取并更新 data/jobs.json
    python main.py --sources nowcoder,iguopin
    python main.py --pages 20     # 限制每源页数(测试用)

流程:
1. 各适配器抓取(单个失败不影响其他)
2. 合并手动录入 data/manual/*.json
3. schema 校验 + 规范化
4. 与旧数据合并去重(空结果保护)
5. 写 data/jobs.json + 生成 data/feed.xml(RSS)
"""
import argparse
import datetime
import json
import logging
import os
import sys
import time

import merge as merger
from adapters import iguopin, nowcoder, nowcoder_jobs, wechat, xinjiang, xinjiang_xju

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("main")

ADAPTERS = {
    "nowcoder": nowcoder.fetch,
    "nowcoder_jobs": nowcoder_jobs.fetch,
    "iguopin": iguopin.fetch,
    "xinjiang": xinjiang.fetch,
    "xinjiang_xju": xinjiang_xju.fetch,
    "wechat": wechat.fetch,
}

NATURES_FILE = os.path.join(merger.DATA_DIR, "company_natures.json")


def _keep(it):
    """保留秋招相关条目:批次含 秋招/提前批/补录/27/2027,或 60 天内收录。

    注意:不含"校招"泛称(牛客职位源用它标记所有岗位,会导致老职位漏过)。
    """
    batch = it.get("batch") or ""
    publish = it.get("publish_date") or ""
    if any(k in batch for k in ("实习", "暑期")):
        return False
    if any(k in batch for k in ("秋招", "提前批", "补", "27", "2027")):
        return True
    try:
        d = datetime.datetime.strptime(publish[:10], "%Y-%m-%d")
        return (datetime.datetime.now() - d).days <= 60
    except (ValueError, TypeError):
        return False


def load_natures():
    """加载国聘性质词典(公司名 -> 性质)。"""
    if os.path.isfile(NATURES_FILE):
        try:
            with open(NATURES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("性质词典读取失败: %s", e)
    return {}


def fetch_all(sources, pages, guoqi_dict):
    results = {}
    for name in sources:
        fn = ADAPTERS[name]
        try:
            t0 = time.time()
            kwargs = {"guoqi_dict": guoqi_dict}
            if name != "wechat":
                kwargs["max_pages"] = pages
            items, total = fn(**kwargs)
            results[name] = items
            log.info("%s: %d 条(耗时 %.1fs, total=%s)",
                     name, len(items), time.time() - t0, total)
        except Exception as e:
            log.error("%s 抓取失败: %s", name, e)
            results[name] = None
    return results


def build_rss(items, updated_at):
    """生成 RSS 2.0 XML(倒序前 100 条)。"""
    from xml.sax.saxutils import escape

    def _d(v):
        return v or "未注明"

    def _link(it):
        if not it.get("link"):
            return it.get("link") or ""
        return escape(str(it["link"]))

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">',
        "<channel>",
        "<title>秋招信息每日汇总</title>",
        "<link>https://example.github.io/qiuzhao/</link>",
        "<description>每日自动汇总秋招企业信息(牛客、国聘、新疆就业网等)</description>",
        "<language>zh-cn</language>",
        "<lastBuildDate>%s</lastBuildDate>" % updated_at,
    ]
    for it in items[:100]:
        title = "%s - %s %s" % (it.get("company"), _d(it.get("batch")),
                                "、".join(it.get("positions", [])))
        desc = "类型:%s | 地点:%s | 发布时间:%s | 截止:%s" % (
            _d(it.get("type")), _d(it.get("location")), _d(it.get("publish_date")),
            _d(it.get("deadline")),
        )
        out.append("<item>")
        out.append("<title>%s</title>" % escape(title))
        out.append("<link>%s</link>" % _link(it))
        out.append("<guid>%s</guid>" % _link(it))
        out.append("<description>%s</description>" % escape(desc))
        out.append("<pubDate>%s</pubDate>" % escape(_d(it.get("publish_date"))))
        out.append("</item>")
    out.append("</channel>")
    out.append("</rss>")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources",
                        default="nowcoder,nowcoder_jobs,iguopin,xinjiang,xinjiang_xju,wechat")
    parser.add_argument("--pages", type=int, default=40)
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    # 先跑国聘收集性质词典,供其他源推断企业类型
    guoqi_dict = load_natures()
    iguopin_items = []
    if "iguopin" in sources:
        try:
            iguopin_items, _ = iguopin.fetch(max_pages=min(args.pages, 30))
            guoqi_dict = iguopin.collect_natures(iguopin_items, NATURES_FILE)
            log.info("性质词典更新: %d 家企业", len(guoqi_dict))
        except Exception as e:
            log.error("国聘词典收集失败: %s", e)
            iguopin_items = []

    fetch_sources = [s for s in sources if s != "iguopin"]
    results = fetch_all(fetch_sources, args.pages, guoqi_dict)
    results["iguopin"] = iguopin_items

    auto_items = []
    for name in sources:
        if results.get(name):
            auto_items.extend(results[name])

    manual_items = merger.load_manual()
    log.info("手动录入 %d 条", len(manual_items))

    all_items = auto_items + manual_items
    no_company = [it for it in all_items if not it.get("company")]
    if no_company:
        log.warning("丢弃无企业名称条目 %d 条(示例: %s)",
                    len(no_company), no_company[0])
    all_items = [it for it in all_items if it.get("company")]

    filtered = [it for it in all_items if _keep(it)]
    if len(filtered) < len(all_items):
        log.info("批次/时间过滤: %d -> %d 条", len(all_items), len(filtered))
    all_items = filtered
    if not all_items:
        log.warning("所有源均无数据,跳过(空结果保护)")
        sys.exit(1)

    from model import normalize, validate_item
    valid = []
    for it in all_items:
        it = normalize(it)
        errs = validate_item(it)
        if errs:
            log.warning("条目校验失败(%s): %s", it.get("company"), errs)
            continue
        valid.append(it)

    old = merger.load_old()
    log.info("旧数据 %d 条", len(old))
    if not valid and old:
        log.warning("本次抓取为空,保留旧数据")
        return

    merged = merger.merge(valid, manual_items, old)
    merged.sort(
        key=lambda x: (x.get("publish_date") or "0000-00-00", x.get("company") or ""),
        reverse=True,
    )

    path = merger.save(merged)
    updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    feed = os.path.join(merger.DATA_DIR, "feed.xml")
    with open(feed, "w", encoding="utf-8") as f:
        f.write(build_rss(merged, updated))
    log.info("已保存 %d 条 -> %s", len(merged), path)
    log.info("RSS 已生成 -> %s", feed)


if __name__ == "__main__":
    main()
