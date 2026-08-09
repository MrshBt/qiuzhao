# 秋招信息每日汇总

每日自动汇总秋招企业信息,部署在 GitHub Pages,数据每日 08:00(北京时间)自动更新。

在线访问:部署后为 `https://<你的GitHub用户名>.github.io/<仓库名>/`

## 功能

- 自动抓取 6 个信息源:
  | 来源 | 类型 | 说明 |
  |---|---|---|
  | 牛客校招日程 | 自动 | 27届秋招/提前批等企业级信息,含官网投递链接 |
  | 牛客校招职位 | 自动 | 岗位级信息,含薪资、学历、投递起止时间 |
  | 国聘网 | 自动 | 央企/国企/银行岗位,含学历、专业、截止时间 |
  | 新疆师大就业指导中心 | 自动 | 新疆本地招聘公告(官方) |
  | 新疆大学就业网 | 自动 | 网络招聘岗位列表(官方) |
  | 微信公众号(国资小新等) | 尽力而为 | 搜狗微信搜索,常被反爬拦截,以手动录入为主 |
- 企业类型自动推断(牛客性质映射 + 国聘性质词典 + 关键词兜底三层),词典存 `data/company_natures.json`,随每日运行累积
- 筛选(均支持多选):企业类型 / 工作地点 / 批次(27届秋招等) / 来源 / 关键词(企业名、岗位、专业)
- 排序:按发布时间(新→旧)或截止时间(近→远)
- 快捷筛选:一周内新发布、只看未截止
- 已投递标记、收藏(localStorage,本地保存)
- 筛选条件自动同步到 URL,可分享
- 已截止自动置灰置底,临近截止红色提醒
- RSS 订阅:`data/feed.xml`

## 手动录入(微信公众号来源)

公众号信息无法自动爬取(搜狗反爬),按模板每周手动补充:

```bash
cp scraper/manual_template.json data/manual/2026-08-07.json
# 编辑该文件,填写公众号里看到的秋招信息
```

字段说明:
- `company`:企业名称
- `type`:国企/央企 | 银行 | 银行/金融 | 外企 | 民企 | 互联网 | 研究所 | 事业单位
- `location`:工作地点,多个用顿号
- `positions`:岗位列表
- `publish_date` / `deadline`:日期 `YYYY-MM-DD`,截止时间可为空
- `link`:原文链接(公众号文章链接)
- `batch`:如 `27届秋招`
- `note`:备注(如"来自国资小新公众号")

## 部署步骤

1. 新建 GitHub 仓库,把本目录推上去
2. 仓库 Settings → Pages → Source 选择 **GitHub Actions**
3. 手动触发一次:仓库 Actions → **Daily Qiuzhao Scraper** → Run workflow
4. 之后每天 08:00 自动更新。爬虫失败会自动在仓库创建 issue 提醒

## 本地运行

```bash
pip install -r scraper/requirements.txt
python scraper/main.py            # 全量更新 data/jobs.json 和 data/feed.xml
python scraper/main.py --sources nowcoder   # 只跑指定源
python scraper/main.py --pages 10           # 限制页数(测试)
```

本地预览前端:用任意静态服务器打开 `index.html`(直接双击文件浏览器可能限制 fetch 本地 json,建议 `python -m http.server 8000`)。

## 目录结构

```
index.html                    前端单页
data/jobs.json                数据(生成)
data/feed.xml                 RSS(生成)
data/company_natures.json     企业性质词典(生成,持续累积)
data/manual/                  手动录入
scraper/
  main.py                     入口
  merge.py                    合并去重 + 空数据保护 + 旧数据清理
  model.py                    schema 校验
  adapters/
    nowcoder.py               牛客校招日程
    nowcoder_jobs.py          牛客校招职位
    iguopin.py                国聘网
    xinjiang.py               新疆师大就业网
    xinjiang_xju.py           新疆大学就业网
    wechat.py                 微信公众号(尽力而为)
  manual_template.json        手动录入模板
.github/workflows/daily.yml   每日定时任务 + 部署
```

## 免责声明

数据来自公开信息源,仅供求职参考,请以各企业官方发布为准。抓取频率已做限速控制。
