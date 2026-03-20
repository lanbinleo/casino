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

## 参数建议

- 想先看通路：用 `quick`。
- 想默认稳定一些：用 `balanced`。
- 想增加泛化：扩大 `bet-set`、`validation-bet-set`、`stack-set`。
- 进化式冠军长期不变：提高 `--random-injection` 或 `--mutation-sigma`。
- CFR 曲线太早停滞：优先增加 `--iterations`。
- 结果波动太大：提高 `--eval-repeats` 和 `--validation-repeats`。

## 输出文件

每次训练默认会在 `fire_station_ai/runs/` 下生成独立目录，包含：

- `summary.json`
  训练摘要。
- `best_policy.json`
  可被运行时加载的策略文件。
- `insight_zh.txt`
  自动中文解读。

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

## 验证命令

```bash
python -m compileall casino.py fire_station_ai
python -m fire_station_ai.train --preset quick
python -m fire_station_ai.cfr_train --preset quick
```
