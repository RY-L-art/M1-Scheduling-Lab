## M1 最適化アルゴリズム特論 
Exercise3.4 2026.10.03

从给的 15 篇论文中，选择 Ho et al. (2024) 的基础 JSP。不是说全面评比后它在 15 篇里数学上最简单，而是它有清楚、已学习过的问题定义和原文小实例，足够满足此次作业。

出处：Section II-A，印刷页 14704（PDF 第 2 页）；数据：Table 1(a)，印刷页 14705（PDF 第 3 页）。只用 JSP 的表 (a)。

原论文的方法是强化学习；本次作业的方法是将同一个优化问题写成混合整数线性规划并交给 Gurobi。

## 四项要求对应哪些文件

1. 来源、页码、问题介绍与兴趣：`REPORT.md` 第 1 节。
2. 集合、参数、变量、目标和约束：`REPORT.md` 第 2 节。
3. gurobipy 代码与数据：`solve_jsp.py`、`instance.json`、`requirements.txt`。
4. 状态、目标、变量、最优性与解释：`REPORT.md` 第 4 节和 `results/`。


## 在这台电脑上运行

在本文件所在文件夹打开 VS Code，然后在 PowerShell 终端运行：

```powershell
..\gurobi-exercise-venv\Scripts\python.exe solve_jsp.py
..\gurobi-exercise-venv\Scripts\python.exe test_verification.py
```

本次新建了独立环境 `work/gurobi-exercise-venv`，安装 gurobipy 13.0.3；没有改动之前的强化学习环境、源论文或作者代码。


## 代码按什么顺序看

1. `instance.json`：每个作业的 operations 列表顺序就是工序先后顺序；machine 是固定数据，duration 是固定加工时长。
2. `load_instance`：读数据，整理 8 个工序、5 个前后关系、7 个同机冲突对。
3. `build_model`：定义开始时间 s、总完工时间 Cmax、同机先后变量 y；添加约束后最小化 Cmax。
4. `model.optimize()`：Gurobi 开始求解，不是在训练神经网络。
5. `model.Status`：检查是否最优；`SolCount`：检查有没有解；变量 `.X`：读取求出的值。
6. `validate_schedule`：不用模型约束对象，重新检查结果是否合法。
7. `test_verification.py`：通过枚举与反例进一步检查结果，不是第二套强化学习算法。

## 模型最容易混淆的地方

- 3 个作业、3 台机器，但只有 8 道工序：J3 只有两道。
- s 是需要求的开始时间，p 是已经给定的加工时长。结束时间 = s + p。
- y 是二元变量，决定同一机器上两个工序的先后；不代表机器是否被选择，因为 JSP 的机器已经指定。
- y=1 时约束 u 先 v 后，y=0 时反过来。两条 big-M 约束分别负责一个方向。
- H=26 是全部加工时长之和，是足够大的安全时间范围；它不是我们预先设定的最优答案。
- Cmax ≥ 每道工序的结束时间；再最小化 Cmax，才能得到最后完成时刻。
- 开始时间可以用连续变量，不必全部设为整数；此例输入为整数，求出的排程也为整数。
- 原文没有明确说时间单位是分钟，所以报告使用 time units。

## 本次实际结果

Gurobi 状态 OPTIMAL（代码 2），目标 12，下界 12，gap=0%。

最优性的直观证明：J1 的三道工序必须依次加工，3+5+4=12，所以任何排程至少要 12。程序找到一个满足所有约束、总时长恰为 12 的排程，故最优。

不要只记“运行成功”。先能解释为什么不可能做到 11，再回头看 Gurobi 怎样表达这些约束。

## 留存与重跑

完整结果保存在 results；重跑默认更新结果文件，日志可能追加。想保留另一轮，使用 `solve_jsp.py --output results_run2`。测试脚本默认检查最初的 results。对于新数据，最好用新的输出目录，避免无解时误看旧的 CSV/SOL。

版本和哈希记录在 result.json，供核对运行所用代码与数据；(不必在初学阶段背这些字段.)
