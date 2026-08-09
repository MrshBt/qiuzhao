# -*- coding: utf-8 -*-
"""数据模型与 schema 校验。"""
import datetime

REQUIRED = ("company", "type", "location", "positions", "publish_date",
            "deadline", "link", "source", "batch")

VALID_SOURCES = ("nowcoder", "nowcoder_jobs", "iguopin", "xinjiang",
                 "xinjiang_xju", "wechat", "manual")
VALID_TYPES = ("国企/央企", "银行", "银行/金融", "外企", "民企", "互联网",
               "研究所", "事业单位")


def validate_item(item):
    """校验单个条目,返回错误列表(空列表=合法)。"""
    errors = []
    if not item.get("company"):
        errors.append("company 为空")
    if item.get("source") not in VALID_SOURCES:
        errors.append("source 非法: %s" % item.get("source"))
    for field in ("publish_date", "deadline"):
        v = item.get(field)
        if v:
            try:
                datetime.datetime.strptime(v[:10], "%Y-%m-%d")
            except ValueError:
                errors.append("%s 日期格式非法: %s" % (field, v))
    return errors


def normalize(item):
    """规范化条目字段类型。"""
    out = dict(item)
    for f in ("positions",):
        if not isinstance(out.get(f), list):
            out[f] = [out.get(f)] if out.get(f) else []
    out["positions"] = [str(p).strip() for p in out.get("positions", []) if str(p).strip()]
    for f in ("location",):
        if not out.get(f):
            out[f] = ""
    for f in ("publish_date", "deadline"):
        if out.get(f):
            out[f] = str(out[f])[:10]
        else:
            out[f] = None
    if not out.get("type"):
        out["type"] = None
    if "extra" not in out:
        out["extra"] = {}
    return out
