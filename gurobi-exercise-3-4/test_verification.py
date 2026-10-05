"""Verify the solution with exhaustive machine orders and negative tests.

Run AFTER solve_jsp.py: python test_verification.py
The enumeration does not call Gurobi or reuse the MILP equations.
"""
import copy
import itertools
import json
from pathlib import Path

from gurobipy import GRB
from solve_jsp import build_model, load_instance, validate_schedule


def enumerate_machine_orders(ops, precedence):
    machines = sorted({o["machine"] for o in ops.values()})
    choices = [list(itertools.permutations(
        [name for name, op in ops.items() if op["machine"] == machine]))
        for machine in machines]
    best, tested, feasible = float("inf"), 0, 0
    for orders in itertools.product(*choices):
        tested += 1
        edges = set(precedence)
        for sequence in orders:
            edges.update(zip(sequence, sequence[1:]))
        successors = {o: [] for o in ops}
        indegree = dict.fromkeys(ops, 0)
        for u, v in edges:
            successors[u].append(v)
            indegree[v] += 1
        queue = [o for o in ops if indegree[o] == 0]
        start = dict.fromkeys(ops, 0)
        processed = 0
        while queue:
            u = queue.pop()
            processed += 1
            for v in successors[u]:
                start[v] = max(start[v], start[u] + ops[u]["duration"])
                indegree[v] -= 1
                if indegree[v] == 0:
                    queue.append(v)
        if processed != len(ops):
            continue  # Directed cycle: impossible processing order.
        feasible += 1
        best = min(best, max(start[o] + ops[o]["duration"] for o in ops))
    return tested, feasible, best


def expect_invalid(ops, precedence, rows, objective):
    try:
        validate_schedule(ops, precedence, rows, objective)
    except ValueError:
        return True
    raise AssertionError("The deliberately invalid schedule was accepted.")


def main():
    root = Path(__file__).resolve().parent
    _, ops, precedence, pairs = load_instance(root / "instance.json")
    result = json.loads((root / "results/result.json").read_text(encoding="utf-8"))
    validate_schedule(ops, precedence, result["schedule"], result["objective"])
    tested, feasible, best = enumerate_machine_orders(ops, precedence)
    assert tested == 72 and best == 12
    assert result["status"] == "OPTIMAL" and abs(result["objective"] - best) < 1e-6
    assert abs(result["best_bound"] - best) < 1e-6 and result["mip_gap"] == 0
    assert (result["variables"], result["binary_variables"], result["constraints"]) == (16, 7, 27)

    wrong_machine = copy.deepcopy(result["schedule"])
    wrong_machine[0]["machine"] = "M2"
    expect_invalid(ops, precedence, wrong_machine, best)
    wrong_order = copy.deepcopy(result["schedule"])
    row = next(r for r in wrong_order if r["operation"] == "O12")
    row.update(start=0, finish=5)
    expect_invalid(ops, precedence, wrong_order, best)
    overlap = copy.deepcopy(result["schedule"])
    row = next(r for r in overlap if r["operation"] == "O31")
    row.update(start=0, finish=3)
    expect_invalid(ops, precedence, overlap, best)

    # A deadline below the analytic job-chain bound must be infeasible.
    model, _, cmax, _, _ = build_model(ops, precedence, pairs)
    model.Params.OutputFlag = 0
    model.Params.Threads = 1
    model.addConstr(cmax <= 11, name="impossible_deadline")
    model.optimize()
    assert model.Status == GRB.INFEASIBLE and model.SolCount == 0
    model.dispose()
    summary = {"result": "PASS", "machine_order_combinations": tested,
               "acyclic_combinations": feasible, "enumerated_optimum": best,
               "analytic_lower_bound": 12,
               "checks": ["schedule_feasibility", "exhaustive_optimality",
                          "model_counts", "reject_wrong_machine",
                          "reject_precedence_violation", "reject_machine_overlap",
                          "deadline_11_is_infeasible"]}
    (root / "results/verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
