# 实验数据与来源

## StudentBench

本仓库附上实际运行使用的 329 个 StudentBench 文件。原数据由 Curtis Northcutt、Inaara Hasmani、Kevin Feng、Trevor Khangi、Andreas Plesner 和 Jonas Mueller 发布，使用 CC BY 4.0 许可。固定版本为 `304c8d63c726e72b60510bba3a44454fc0726721`。下表各目录保存从该版本取得的原始字节，文件在本地按用途命名。筛查、教法版本、教案补充、重放回复和评分是本项目的产物，存放在 `experiments/` 下。[原数据与论文引用](https://huggingface.co/datasets/handshake-ai-research/studentbench/tree/304c8d63c726e72b60510bba3a44454fc0726721) · [作者的数据说明](https://huggingface.co/datasets/handshake-ai-research/studentbench) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

| 数据目录 | 实际用途 | 原路径和 SHA-256 校验清单 |
| --- | --- | --- |
| [studentbench-pilot](raw/studentbench-pilot/) | 首轮课堂轨迹、独立作答和题库 | [先导数据清单](../experiments/lesson_revision_pilot/studentbench_sources.json) |
| [studentbench-reasons](raw/studentbench-reasons/) | Gemini 组历史课堂，用于提取教学片段及后续独立作答 | [建库数据清单](../experiments/reason_ablation/sources.json) |
| [studentbench-native](raw/studentbench-native/) | 官方导师提示、题库、课程基线和首轮重放 | [原策略与基线文件](../experiments/reason_ablation/native_sources.json) |
| [studentbench-grounded](raw/studentbench-grounded/) | GRE 数学 GPT-5.4 mini 组的课堂记录、学生资料与原教案 | [32 场实验来源](../experiments/grounded_tutor/sources.json) · [24 场实验来源](../experiments/evidence_revision/sources.json) |

## Scaffolded Error Correction

围栏案例的数据、字段字典和作者的 R 分析脚本通过 Git 子模块固定在 `98c52a668fc6ba76fa330eb9539ab893616111ba`。在仓库根目录运行下面两条命令，即可将五个原文件按其实验校验值准备到 `data/raw/sec/`。已有子模块时，脚本直接从本机 Git 对象读取原始字节。[作者原仓库](https://github.com/the-oak-lab/scaffolded-error-correction/tree/98c52a668fc6ba76fa330eb9539ab893616111ba) · [来源与校验值](sec_source.json)

```sh
git submodule update --init data/scaffolded-error-correction
python scripts/fetch_sec.py
```

## 复算已发布的比较

在仓库根目录安装 Python 依赖并运行下列命令，可以使用已保存的课堂和 48 条正式回复核对最新一轮的教案设计与评分汇总。这两步均在本地运行。

```sh
python -m pip install ".[grounded]"
python scripts/run_grounded_tutor.py prepare --evidence-revision
python scripts/run_grounded_tutor.py summarize --evidence-revision
```
