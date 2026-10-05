import argparse
import csv
import hashlib
import json
import math
import platform
from itertools import combinations
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB


def load_instance(path):
    """Read jobs in precedence order and reject malformed input."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data.get("jobs"):
        raise ValueError("At least one job is required.")
    operations, precedence, seen_jobs = {}, [], set()
    for job in data["jobs"]:
        if job["id"] in seen_jobs or not job["operations"]:
            raise ValueError("Job IDs must be unique and jobs nonempty.")
        seen_jobs.add(job["id"])
        previous = None
        for op in job["operations"]:
            name, duration = op["id"], op["duration"]
            if name in operations:
                raise ValueError("Operation IDs must be unique.")
            if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                    or not math.isfinite(duration) or duration <= 0):
                raise ValueError("Durations must be finite and positive.")
            operations[name] = {**op, "job": job["id"]}
            if previous is not None:
                precedence.append((previous, name))
            previous = name
    # Store each unordered same-machine pair exactly once.
    pairs = [(u, v) for u, v in combinations(operations, 2)
             if operations[u]["machine"] == operations[v]["machine"]]
    return data, operations, precedence, pairs


def validate_schedule(operations, precedence, rows, makespan, tol=1e-6):
    """Independent feasibility checks, without using model constraints."""
    if len(rows) != len(operations) or {r["operation"] for r in rows} != set(operations):
        raise ValueError("Missing, duplicate, or unknown operations.")
    by_id = {r["operation"]: r for r in rows}
    for name, op in operations.items():
        row = by_id[name]
        if not all(math.isfinite(row[k]) for k in ("start", "finish")):
            raise ValueError("Non-finite schedule time.")
        if row["machine"] != op["machine"] or row["start"] < -tol:
            raise ValueError("Wrong machine or negative start.")
        if abs(row["finish"] - row["start"] - op["duration"]) > tol:
            raise ValueError("Incorrect processing duration.")
    for u, v in precedence:
        if by_id[u]["finish"] > by_id[v]["start"] + tol:
            raise ValueError(f"Precedence violation: {u} before {v}.")
    for machine in {o["machine"] for o in operations.values()}:
        ordered = sorted((r for r in rows if r["machine"] == machine),
                         key=lambda r: r["start"])
        for left, right in zip(ordered, ordered[1:]):
            if left["finish"] > right["start"] + tol:
                raise ValueError(f"Machine overlap on {machine}.")
    if not math.isfinite(makespan) or abs(max(r["finish"] for r in rows) - makespan) > tol:
        raise ValueError("Makespan does not equal the maximum finish time.")


def build_model(operations, precedence, pairs):
    # H is a valid horizon: processing all jobs serially is feasible.
    horizon = sum(op["duration"] for op in operations.values())
    model = gp.Model("Ho2024_small_JSP")
    start = model.addVars(list(operations), lb=0,
                         ub={o: horizon - operations[o]["duration"] for o in operations},
                         vtype=GRB.CONTINUOUS, name="s")
    makespan = model.addVar(lb=0, ub=horizon, name="Cmax")
    # y[u,v]=1 means operation u must finish before v starts.
    order = model.addVars(pairs, vtype=GRB.BINARY, name="y")
    model.setObjective(makespan, GRB.MINIMIZE)

    for u, v in precedence:
        model.addConstr(start[v] >= start[u] + operations[u]["duration"],
                        name=f"precedence_{u}_{v}")
    for u, v in pairs:
        model.addConstr(start[v] >= start[u] + operations[u]["duration"]
                        - horizon * (1 - order[u, v]), name=f"before_{u}_{v}")
        model.addConstr(start[u] >= start[v] + operations[v]["duration"]
                        - horizon * order[u, v], name=f"after_{u}_{v}")
    for op in operations:
        model.addConstr(makespan >= start[op] + operations[op]["duration"],
                        name=f"completion_{op}")
    return model, start, makespan, order, horizon


def main():
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=folder / "instance.json")
    parser.add_argument("--output", type=Path, default=folder / "results")
    args = parser.parse_args()
    data, ops, precedence, pairs = load_instance(args.data)
    args.output.mkdir(parents=True, exist_ok=True)
    model, start, cmax, order, horizon = build_model(ops, precedence, pairs)
    model.Params.Threads = 1
    model.Params.Seed = 0
    model.Params.MIPGap = 0
    model.Params.TimeLimit = 60
    model.Params.LogFile = str(args.output / "gurobi.log")
    model.write(str(args.output / "model.lp"))
    model.optimize()

    status_names = {GRB.OPTIMAL: "OPTIMAL", GRB.INFEASIBLE: "INFEASIBLE",
                    GRB.INF_OR_UNBD: "INF_OR_UNBD", GRB.UNBOUNDED: "UNBOUNDED",
                    GRB.TIME_LIMIT: "TIME_LIMIT", GRB.INTERRUPTED: "INTERRUPTED"}
    result = {
        "instance": data["name"], "source": data["source"],
        "python_version": platform.python_version(),
        "gurobi_version": ".".join(map(str, gp.gurobi.version())),
        "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "status_code": model.Status,
        "status": status_names.get(model.Status, f"STATUS_{model.Status}"),
        "optimality_established": model.Status == GRB.OPTIMAL,
        "solution_count": model.SolCount, "runtime_seconds": model.Runtime,
        "parameters": {"Threads": 1, "Seed": 0, "MIPGap": 0, "TimeLimit": 60},
        "horizon": horizon, "variables": model.NumVars,
        "binary_variables": model.NumBinVars, "constraints": model.NumConstrs,
    }
    # Do NOT read .X or .ObjVal unless an incumbent solution exists.
    if model.SolCount > 0:
        rows = [{"operation": name, "job": op["job"], "machine": op["machine"],
                 "duration": op["duration"], "start": start[name].X,
                 "finish": start[name].X + op["duration"]} for name, op in ops.items()]
        validate_schedule(ops, precedence, rows, cmax.X)
        result.update(objective=model.ObjVal, best_bound=model.ObjBound,
                      mip_gap=model.MIPGap, schedule=rows,
                      ordering_variables={f"{u},{v}": order[u, v].X for u, v in pairs},
                      all_variable_values={v.VarName: v.X for v in model.getVars()},
                      validation="PASS")
        with (args.output / "schedule.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        model.write(str(args.output / "solution.sol"))
        print("\nOperation  Machine  Start  Finish")
        for row in rows:
            print(f"{row['operation']:9}  {row['machine']:7}  {row['start']:5g}  {row['finish']:6g}")
        print("Ordering variables:", result["ordering_variables"])
        print(f"Objective={model.ObjVal:g}; bound={model.ObjBound:g}; gap={model.MIPGap:g}")
        print("Independent feasibility validation: PASS")
    print(f"Status: {result['status']}; optimality established: {result['optimality_established']}")
    (args.output / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    model.dispose()


if __name__ == "__main__":
    try:
        main()
    except gp.GurobiError as error:
        raise SystemExit(f"Gurobi error {error.errno}: {error}. No successful solve is claimed.")
