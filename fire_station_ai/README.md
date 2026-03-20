# Fire Station AI Sandbox

这个目录提供“火烧洋油站”的独立训练环境、终端训练器和 Casino 桥接器。

## 目录

- `env.py`
  纯逻辑环境，可脱离终端界面跑单手模拟。
- `trainer.py`
  进化式训练核心。
- `train.py`
  进化式训练入口。
- `cfr.py`
  CFR / regret matching 训练核心与策略表运行时。
- `cfr_train.py`
  CFR / regret matching 训练入口。
- `arena.py`
  让保存模型两两对打并导出排行榜 JSON。
- `arena_viewer.html`
  静态 Arena 看板，直接读取 `arena.json`。
- `batch_train.py`
  批量训练入口，可按参数组合批量生成模型。
- `runtime.py`
  读取保存模型，并把动作桥接回 `casino.py`。
- `naming.py`
  模型代号词库。
- `runs/`
  默认训练输出目录。

## 直接可用

进化式训练：

```bash
python -m fire_station_ai.train --preset balanced
```

CFR / regret matching：

```bash
python -m fire_station_ai.cfr_train --preset balanced
```

Arena 排行榜：

```bash
python -m fire_station_ai.arena --top 6
```

批量训练：

```bash
python -m fire_station_ai.batch_train --profile mini --seeds 18,42
```

快速试跑：

```bash
python -m fire_station_ai.train --preset quick
python -m fire_station_ai.cfr_train --preset quick
```

## 常用预设

- `quick`
  快速确认流程是否正常。
- `balanced`
  默认推荐，速度和稳定性较平衡。
- `robust`
  更重视泛化，训练更久。

## 进化式训练常用参数

```bash
python -m fire_station_ai.train ^
  --preset robust ^
  --seed 7 ^
  --bet-set 5,10,25 ^
  --validation-bet-set 5,10,25,50
```

- `--generations`
  训练多少代。
- `--population-size`
  每代候选数量。
- `--elite-count`
  每代保留的精英数量。
- `--hands-per-eval`
  单次评估的对局手数。
- `--validation-hands`
  验证局手数。
- `--mutation-sigma`
  变异强度。
- `--random-injection`
  每代随机新血比例。
- `--bet-set`
  训练底注集合。
- `--validation-bet-set`
  验证底注集合。
- `--init-mode`
  初始中心策略，支持 `default / random / blend`。

## CFR 训练常用参数

```bash
python -m fire_station_ai.cfr_train ^
  --preset robust ^
  --seed 7 ^
  --bet-set 5,10,25 ^
  --validation-bet-set 5,10,25,50 ^
  --stack-set 700,1000,1500
```

- `--iterations`
  自博弈训练轮数。
- `--checkpoint-interval`
  每隔多少轮做一次评估和记录。
- `--hands-per-eval`
  训练池评估手数。
- `--validation-hands`
  验证手数。
- `--bet-set`
  训练底注集合。
- `--validation-bet-set`
  验证底注集合。
- `--stack-set`
  训练时采样的筹码集合。
- `--workers`
  评估并行进程数，`0` 代表自动。

## 参数建议

- 想先看通路：用 `quick`。
- 想默认稳定一些：用 `balanced`。
- 想增加泛化：扩大 `bet-set`、`validation-bet-set`、`stack-set`。
- 进化式冠军长期不变：提高 `--random-injection` 或 `--mutation-sigma`。
- CFR 曲线太早停滞：优先增加 `--iterations`。
- 结果波动太大：提高 `--eval-repeats` 和 `--validation-repeats`。
- 想利用 CPU 并行：给 CFR 或 Arena 传 `--workers 0` 或显式进程数。

## 输出文件

每次训练默认会在 `fire_station_ai/runs/` 下生成独立目录，包含：

- `summary.json`
  训练摘要。
- `best_policy.json`
  可被运行时加载的策略文件。
- `insight_zh.txt`
  自动中文解读。
- `arena.json`
  Arena 两两对打排行榜与明细。

保存出来的模型会带一个中文代号，Casino 里会直接显示这个名字。

## 在 Casino 里使用训练模型

进入“火烧洋油站”后，在选底注界面输入：

- `M`
  打开决策核心选择

你可以在这里切换：

- `规则庄家`
- 进化式训练模型
- CFR 训练模型

训练模型保存在 `fire_station_ai/runs/` 下时，`casino.py` 会通过 `runtime.py` 自动发现并加载。

## Arena 用法

默认取最新模型：

```bash
python -m fire_station_ai.arena --top 6
```

指定模型代号关键词：

```bash
python -m fire_station_ai.arena --models 暗牌,皇家,弃牌
```

常用参数：

- `--hands`
  每组对打计划手数。
- `--repeats`
  每组重复次数。
- `--bet-set`
  Arena 使用的底注集合。
- `--stack-set`
  Arena 使用的筹码集合。
- `--workers`
  并行进程数，`0` 代表自动。
- `--top`
  直接取最新的前 N 个模型。
- `--models`
  按代号或路径关键词筛选模型。

Arena 跑完后会生成：

- `fire_station_ai/runs/arena_.../arena.json`
- `fire_station_ai/runs/arena_index.json`
  供 `arena_viewer.html` 自动列出已有 Arena 结果。

静态查看页：

- 打开 [arena_viewer.html](/d:/Desktop/BoringGame/fire_station_ai/arena_viewer.html)
- 或在浏览器访问 `fire_station_ai/arena_viewer.html?json=fire_station_ai/runs/arena_xxx/arena.json`
- 页面里可以直接切换已有 Arena，并按 Elo、积分、EV、手胜率等字段重新排序。

## 批量训练

默认会对每组参数分别跑两个 seed：

- `18`
- `42`

直接运行：

```bash
python -m fire_station_ai.batch_train --profile mini --seeds 18,42
```

如果你想先把现有 `runs/` 归档掉再开新一批：

```bash
python -m fire_station_ai.batch_train --profile mini --seeds 18,42 --archive-existing
```

当前支持的批次档位：

- `mini`
  较快，适合先跑一轮看结果。
- `standard`
  组合更多，时间更长。

批量脚本会：

- 把批次清单写到 `fire_station_ai/runs/batch_.../manifest.json`
- 把逐项结果写到 `results.json`
- 把最终摘要写到 `summary.json`

归档时会把旧结果移到：

- `fire_station_ai/run_archives/archive_...`

## 验证命令

```bash
python -m compileall casino.py fire_station_ai
python -m fire_station_ai.train --preset quick
python -m fire_station_ai.cfr_train --preset quick
python -m fire_station_ai.arena --top 4 --hands 20 --repeats 1
```
