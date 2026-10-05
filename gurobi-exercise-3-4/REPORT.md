# Exercise 3.4: A Small Job-Shop Scheduling Problem Solved with Gurobi

Prepared for Runye Liu | 2 October 2026

## 1. Source, problem description, and motivation

**Source:** K.-H. Ho, J.-Y. Cheng, J.-H. Wu, F. Chiang, Y.-C. Chen, Y.-Y. Wu, and I.-C. Wu, “Residual Scheduling: A New Reinforcement Learning Approach to Solving Job Shop Scheduling Problem,” *IEEE Access*, vol. 12, pp. 14703–14718, 2024. DOI: [10.1109/ACCESS.2024.3357969](https://doi.org/10.1109/ACCESS.2024.3357969).

The JSP definition is in **Section II-A, p. 14704**. The numerical data are taken from **Table 1(a), p. 14705**. These are PDF pages **2 and 3**, respectively. Figure 1(a), p. 14705, illustrates a schedule with makespan 12.

The problem is to schedule a set of operations on machines. Each operation has a fixed processing time and a designated machine. Operations of a job must follow their prescribed order. A machine processes at most one operation at a time, and processing cannot be interrupted. All jobs and machines are available at time zero. There are no setup times, breakdowns, transportation times, or due dates in this instance. The objective is to minimize the completion time of the last operation, called the **makespan**.

This problem interests me because my current study concerns manufacturing scheduling and reinforcement learning. Solving a small instance exactly helps me understand the feasibility constraints and the distinction between a feasible schedule and a proven optimal one before studying learned scheduling policies.

**Scope:** This exercise uses the paper's JSP problem and its original example data. The MILP below is a standard disjunctive reformulation constructed for this exercise; it is **not a verbatim formulation from the paper**, and the implementation does **not** reproduce its GNN or reinforcement-learning algorithm.

## 2. Numerical instance and mathematical model

### 2.1 Data

The three jobs contain 3, 3, and 2 operations, so there are **8 operations**, not 9. Processing times use the source's unspecified time unit; they are not assumed to be minutes.

| Job | First operation | Second operation | Third operation |
|---|---|---|---|
| J1 | O11: M1, 3 | O12: M3, 5 | O13: M2, 4 |
| J2 | O21: M3, 2 | O22: M2, 4 | O23: M1, 3 |
| J3 | O31: M1, 3 | O32: M3, 2 | — |

The complete machine-readable data are in `instance.json`. O11 denotes the paper's operation O_(1,1), and similarly for the other operations.

### 2.2 Sets and parameters

- \(J=\{1,2,3\}\): jobs.
- \(\mathcal M=\{M_1,M_2,M_3\}\): machines.
- \(\mathcal O=\{O_{11},O_{12},O_{13},O_{21},O_{22},O_{23},O_{31},O_{32}\}\): operations.
- \(p_o>0\): processing time of operation \(o\).
- \(m_o\in\mathcal M\): designated machine of operation \(o\); it is a parameter, not a decision.
- \(A=\{(O_{11},O_{12}),(O_{12},O_{13}),(O_{21},O_{22}),(O_{22},O_{23}),(O_{31},O_{32})\}\): immediate precedence pairs.
- \(P\): pairs of distinct operations on the same machine, with each unordered pair represented exactly once in the listed orientation.

For this instance:

\[
\begin{aligned}
P=\{&(O_{11},O_{23}),(O_{11},O_{31}),(O_{12},O_{21}),\\
    &(O_{12},O_{32}),(O_{13},O_{22}),(O_{21},O_{32}),(O_{23},O_{31})\}.
\end{aligned}
\]

Use the planning horizon and big-M constant

\[
H=\sum_{o\in\mathcal O}p_o=26.
\]

This is valid because processing the jobs one at a time, respecting each job's order, gives a feasible schedule of length 26. Thus, restricting the search to schedules finishing within H does not exclude an optimum.

### 2.3 Decision variables

- \(s_o\in[0,H-p_o]\): continuous start time of operation \(o\).
- \(C_{\max}\in[0,H]\): continuous makespan variable.
- \(y_{uv}\in\{0,1\}\), for \((u,v)\in P\): 1 if u is before v on their common machine, and 0 if v is before u.

Completion times are derived as \(s_o+p_o\); no separate completion-time variables are needed. The model has **9 continuous variables and 7 binary variables**.

### 2.4 Objective

\[
\min C_{\max}.
\]

### 2.5 Constraints

**Within-job precedence:**

\[
s_v\ge s_u+p_u,\qquad (u,v)\in A.
\]

An operation cannot start before its predecessor finishes.

**No overlap on the same machine:**

\[
s_v\ge s_u+p_u-H(1-y_{uv}),\qquad (u,v)\in P,
\]

\[
s_u\ge s_v+p_v-Hy_{uv},\qquad (u,v)\in P.
\]

When \(y_{uv}=1\), the first inequality enforces u before v. When \(y_{uv}=0\), the second enforces v before u. The other inequality is inactive: all finishes are at most H and all starts are nonnegative, so subtracting H is sufficient. These constraints select an order without allowing preemption or overlap.

**Makespan:**

\[
C_{\max}\ge s_o+p_o,\qquad o\in\mathcal O.
\]

**Variable domains:**

\[
0\le s_o\le H-p_o,\quad 0\le C_{\max}\le H,\quad y_{uv}\in\{0,1\}.
\]

There are **27 linear constraints**: 5 precedence, 14 machine-ordering, and 8 makespan constraints. Variable bounds are not included in this count.

## 3. Implementation and reproducibility

The complete implementation is `solve_jsp.py`; input data are in `instance.json`. Only `gurobipy` and the Python standard library are required.

After opening a terminal in the project folder, run:

```powershell
python -m pip install -r requirements.txt
python solve_jsp.py
python test_verification.py
```

Use a compatible Python interpreter with a usable Gurobi license. This run used **Python 3.14.7** and **Gurobi 13.0.3**, with the small-model restricted non-production license supplied with the package. No paid license or cloud compute was purchased. Gurobi documents pip installation and the included small-model license in its [installation guide](https://support.gurobi.com/hc/en-us/articles/360044290292-How-do-I-install-Gurobi-for-Python).

Parameters: `Threads=1`, `Seed=0`, `MIPGap=0`, and `TimeLimit=60` seconds. The implementation checks solution availability before reading decision values. If a time limit is reached, a feasible incumbent is not mislabeled as optimal.

Files produced in `results/`:

- `model.lp`: exported MILP, readable without running the code.
- `gurobi.log`: solver log.
- `solution.sol`: all 16 decision variable values.
- `schedule.csv`: the operation schedule.
- `result.json`: status, objective, bound, gap, parameters, versions, input/code hashes, and decision values.
- `verification.json`: independent verification results, produced by the test script.

Running the solver again updates its result files; the Gurobi log may append another run. Use `--output another_results_folder` to preserve a separate run. Do not mix old solution files with a new run that has no solution; `result.json` and its status are authoritative for the current run.

## 4. Optimization results and interpretation

### 4.1 Solver status

The actual Gurobi run returned:

| Quantity | Value |
|---|---:|
| Optimization status | OPTIMAL |
| Status code | 2 |
| Objective value | 12 |
| Best bound | 12 |
| Relative MIP gap | 0% |
| Variables | 16 |
| Binary variables | 7 |
| Linear constraints | 27 |

Gurobi established optimality for this model to its numerical tolerances. A separate analytic proof below establishes the exact value 12 for the stated instance.

### 4.2 Decision variable values

| Operation | Machine | Duration | Start variable value | Finish (derived) |
|---|---|---:|---:|---:|
| O11 | M1 | 3 | 0 | 3 |
| O12 | M3 | 5 | 3 | 8 |
| O13 | M2 | 4 | 8 | 12 |
| O21 | M3 | 2 | 0 | 2 |
| O22 | M2 | 4 | 2 | 6 |
| O23 | M1 | 3 | 6 | 9 |
| O31 | M1 | 3 | 3 | 6 |
| O32 | M3 | 2 | 8 | 10 |

\(C_{\max}=12\).

| Binary variable | Value | Meaning |
|---|---:|---|
| y[O11,O23] | 1 | O11 before O23 |
| y[O11,O31] | 1 | O11 before O31 |
| y[O12,O21] | 0 | O21 before O12 |
| y[O12,O32] | 1 | O12 before O32 |
| y[O13,O22] | 0 | O22 before O13 |
| y[O21,O32] | 1 | O21 before O32 |
| y[O23,O31] | 0 | O31 before O23 |

Solver output may display `-0.0`; this represents zero, not a different binary value. Multiple optimal schedules may exist, so a different software version can return different start times with the same optimal objective.

### 4.3 Interpretation and optimality proof

Machine M1 executes O11 during [0,3), O31 during [3,6), and O23 during [6,9). Machine M2 executes O22 during [2,6) and O13 during [8,12). Machine M3 executes O21 during [0,2), O12 during [3,8), and O32 during [8,10). Intervals may touch at endpoints without overlapping.

All precedence constraints are respected. J1 completes at 12, J2 at 9, and J3 at 10. Therefore, all work is finished by time 12.

For any feasible schedule, the three operations of J1 must be processed sequentially and take

\[
3+5+4=12
\]

time units. Nonnegative start times imply \(C_{\max}\ge12\). The returned feasible schedule achieves 12; hence it is globally optimal for this instance.

### 4.4 Independent verification

The solver script separately checks operation coverage, machine assignments, processing durations, nonnegative starts, within-job precedence, machine non-overlap, and the makespan.

The verification script also enumerates all \(3!\times2!\times3!=72\) possible machine-order combinations. For each acyclic combination, it computes earliest starts using the precedence graph, independently of the MILP equations, and verifies that the minimum makespan is 12. Deliberately invalid schedules test the checker. Adding the constraint \(C_{\max}\le11\) is additionally tested and found infeasible.

## Conclusion

A small JSP from a research paper was expressed as a MILP and solved using `gurobipy`. The optimal makespan is **12 time units**, confirmed by the solver, independent checks, and a job-chain lower-bound proof. This is an exact solution of a small instance, not a claim that all JSP instances are easy or that the paper's reinforcement-learning method has been reproduced.
