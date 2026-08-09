# -*- coding: utf-8 -*-
"""牛客网校招日程适配器。

API: POST https://www.nowcoder.com/np-api/u/school-schedule/list-card
无登录、无 cookie 即可用,分页取全量。

收录时间用 wangshenUpdateTime(页面"XX.XX收录"),缺省回退 updateTime。
企业性质推断(三层):
  1. property_map:按 propertyId 分组抓取建立的 companyId -> 性质 映射
  2. guoqi_dict:国聘源维护的 公司名 -> 性质 词典(data/company_natures.json)
  3. 关键词/行业兜底
"""
import datetime
import time

import requests

API = "https://www.nowcoder.com/np-api/u/school-schedule/list-card"
SUPPORT_API = "https://www.nowcoder.com/np-api/u/school-schedule/support"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nowcoder.com/school/schedule",
    "Content-Type": "application/x-www-form-urlencoded",
}

PROPERTY_IDS = {"国企": 2830, "外企": 2834, "民企": 4712, "事业单位": 4713}
PROPERTY_PAGES = 10

TYPE_KEYWORDS = [
    (("银行", "农信社", "信用社", "农商行"), "银行"),
    (("证券", "保险", "基金", "期货", "信托"), "银行/金融"),
    (("研究院", "设计院", "研究所", "科学院", "工程院"), "研究所"),
    (("大学", "学院", "学校"), "事业单位"),
]

# 央企国企名称特征:中字头 + 国资体系常见称谓
GUOQI_NAME_HINTS = ("中国", "中粮", "中储", "中冶", "中建", "中铁", "中交", "中航",
                    "中船", "中核", "中电", "中科", "中铝", "中化", "中国信科",
                    "国家电网", "国家能源", "国家电投", "国家铁路", "国投",
                    "华润", "招商局", "光大", "中信", "保利", "联通", "移动",
                    "电信", "铁塔", "航天", "兵器", "电子科技", "一汽", "东风",
                    "长安", "宝武", "鞍钢", "首钢", "三峡", "华能", "大唐",
                    "国电", "中广核", "中石油", "中石化", "中海油", "中国邮政",
                    "国家开发", "进出口银行", "农业发展", "工行", "农行", "中行",
                    "建行", "交行", "邮储")
BANK_NAMES = ("银行", "农信社", "信用社", "农商行")


def _fetch_page(page, page_size=50, session=None, property_id=None, tab=1, batch_id=None):
    s = session or requests.Session()
    data_payload = {"tab": tab, "page": page, "pageSize": page_size}
    if property_id:
        data_payload["propertyId"] = property_id
    if batch_id:
        data_payload["batchId"] = batch_id
    resp = s.post(API, headers=HEADERS, data=data_payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError("nowcoder API error: %s" % data)
    return data["data"]


def _parse_time(ms):
    if not ms:
        return None
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def _norm_type(company_id, company_name, industry_list, property_map, guoqi_dict):
    """企业类型推断。property_map(牛客) > guoqi_dict(国聘词典) > 关键词兜底。"""
    prop = property_map.get(str(company_id)) if company_id is not None else None
    if prop == "国企":
        return "国企/央企"
    if prop == "外企":
        return "外企"
    if prop == "事业单位":
        return "事业单位"
    if prop == "民企":
        return "民企"

    name = company_name or ""
    if name in guoqi_dict:
        return guoqi_dict[name]

    if any(k in name for k in BANK_NAMES):
        return "银行"
    for keys, t in TYPE_KEYWORDS:
        if any(k in name for k in keys):
            return t
    if any(k in name for k in GUOQI_NAME_HINTS):
        return "国企/央企"
    text = " ".join(industry_list or [])
    if any(k in text for k in ("银行", "证券", "保险")):
        return "银行/金融"
    if any(k in text for k in ("游戏", "互联网", "软件", "电商")):
        return "互联网"
    return "民企"


def _property_map(session):
    """抓取各性质的公司,建立 companyId -> 性质 映射。"""
    result = {}
    for prop, pid in PROPERTY_IDS.items():
        try:
            for page in range(1, PROPERTY_PAGES + 1):
                data = _fetch_page(page, page_size=50, session=session, property_id=pid)
                for d in data.get("datas") or []:
                    result[d.get("companyId")] = prop
                if page >= data.get("totalPage", 0):
                    break
                time.sleep(0.2)
        except requests.RequestException:
            continue
    return result


def _build_item(d, property_map, guoqi_dict):
    ad = d.get("adInfo") or {}
    raw_url = ad.get("rawUrl") or d.get("sourceInformation") or d.get(
        "customWangshenLink"
    )
    if raw_url:
        raw_url = raw_url.replace("&amp;", "&")
    industry = d.get("industryList") or []
    begin = _parse_time(d.get("wangshenBeginDate"))
    end = _parse_time(d.get("wangshenEndDate"))
    collected = _parse_time(d.get("wangshenUpdateTime")) or _parse_time(
        d.get("updateTime")
    ) or begin
    batch = d.get("batchName") or ""
    return {
        "company": d.get("name"),
        "type": _norm_type(
            d.get("companyId"), d.get("name"), industry, property_map, guoqi_dict
        ),
        "location": "、".join(d.get("cityList") or []),
        "positions": d.get("careerNameList") or [],
        "publish_date": collected,
        "deadline": end,
        "link": raw_url,
        "source": "nowcoder",
        "batch": batch,
        "deadline_note": "",
    }


AUTUMN_BATCH_IDS = [1200, 1203, 1206, 1209, 1210]  # 26/27届、27提前批、27秋招、27届校招、27届秋招


def fetch(max_pages=40, property_map=None, session=None, guoqi_dict=None):
    """抓取牛客校招日程数据。返回 (items, total)。"""
    items = []
    seen = set()
    session = session or requests.Session()
    if property_map is None:
        property_map = _property_map(session)
    guoqi_dict = guoqi_dict or {}
    total = None

    def grab(batch_id=None, tab=1, limit=max_pages):
        nonlocal total
        page = 1
        while page <= limit:
            try:
                data = _fetch_page(
                    page, session=session, tab=tab, batch_id=batch_id
                )
            except requests.RequestException:
                break
            if total is None:
                total = data.get("totalCount")
            datas = data.get("datas") or []
            for d in datas:
                item = _build_item(d, property_map, guoqi_dict)
                key = (
                    item["company"],
                    item["batch"],
                    item["deadline"],
                    tuple(sorted(item["positions"])) if item["positions"] else "()",
                )
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
            if page >= data.get("totalPage", 0):
                break
            page += 1
            time.sleep(0.3)

    for bid in AUTUMN_BATCH_IDS:
        grab(batch_id=bid)
    grab(tab=1, limit=min(max_pages, 20))
    return items, total
