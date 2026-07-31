"""Deterministic regression check for the synthetic simulation."""

from statistics import mean

from humaneval_tasks import generate_tasks
from swarm_os_core import SectorAgent, StatelessAgent

EXPECTED = {
    "sf_z": 14217.6,
    "sl_z": 30280.0,
    "sf_tokens": 56833,
    "sl_tokens": 121120,
    "sf_w": 0.6668,
    "sl_w": 0.6000,
    "q_count": 10,
}


def close(actual: float, expected: float, tolerance: float = 0.00005) -> bool:
    return abs(actual - expected) <= tolerance


def main() -> None:
    tasks = generate_tasks(100, 42)
    stateful = SectorAgent("VERIFY")

    sf = [stateful.solve(task) for task in tasks]
    sl = [StatelessAgent().solve(task) for task in tasks]

    actual = {
        "sf_z": round(sum(item.Z for item in sf), 1),
        "sl_z": round(sum(item.Z for item in sl), 1),
        "sf_tokens": sum(int(item.Z * 4.0) for item in sf),
        "sl_tokens": sum(int(item.Z * 4.0) for item in sl),
        "sf_w": round(mean(item.W for item in sf), 4),
        "sl_w": round(mean(item.W for item in sl), 4),
        "q_count": sum(item.state == "Q" for item in sf),
    }

    failures = []
    for key, expected in EXPECTED.items():
        value = actual[key]
        ok = close(value, expected) if isinstance(expected, float) else value == expected
        print(f"{key:10s}: actual={value!r} expected={expected!r} {'OK' if ok else 'FAIL'}")
        if not ok:
            failures.append(key)

    if failures:
        raise SystemExit(f"Regression mismatch: {', '.join(failures)}")

    print("All deterministic checks passed.")


if __name__ == "__main__":
    main()
