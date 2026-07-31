#!/usr/bin/env python3
"""
BENCHMARK PUBLICZNY: HumanEval-style (100 zadan)
Porownanie Stateless vs Stateful na zadaniach programistycznych
"""

import time
import statistics
from humaneval_tasks import generate_tasks, run_tests
from swarm_os_core import SectorAgent, StatelessAgent

NUM_TASKS = 100
SEED = 42
TOKENS_PER_LINE = 4.0  # heurystyka: 1 linia kodu ≈ 4 tokeny

def main():
    print("=" * 76)
    print("  BENCHMARK PUBLICZNY: HumanEval-style (100 zadan programistycznych)")
    print("  Stateless vs Stateful — porownanie kosztu i jakosci")
    print("=" * 76)
    print()

    tasks = generate_tasks(NUM_TASKS, SEED)

    # STATEFUL
    stateful = SectorAgent("HUMANEVAL-SF")
    results_sf = []

    print("STATEFUL (1 agent, 100 iteracji z pamiecia)")
    print("-" * 76)
    for task in tasks:
        t0 = time.perf_counter()
        r = stateful.solve(task)
        t1 = time.perf_counter()

        tokens = int(r.Z * TOKENS_PER_LINE)
        results_sf.append({
            'id': task['id'], 'W': r.W, 'Z': r.Z, 'attempts': r.attempts,
            'lines': r.lines, 'tokens': tokens, 'state': r.state,
            'fuel': r.fuel, 'memory': r.memory, 'pass_rate': r.pass_rate,
            'time_ms': round((t1 - t0) * 1000, 3)
        })

    # STATELESS
    results_sl = []
    print("\nSTATELESS (100 agentow, kazdy od zera)")
    print("-" * 76)
    for task in tasks:
        agent = StatelessAgent()
        t0 = time.perf_counter()
        r = agent.solve(task)
        t1 = time.perf_counter()

        tokens = int(r.Z * TOKENS_PER_LINE)
        results_sl.append({
            'id': task['id'], 'W': r.W, 'Z': r.Z, 'attempts': r.attempts,
            'lines': r.lines, 'tokens': tokens, 'state': r.state,
            'fuel': 0.0, 'memory': 0.0, 'pass_rate': r.pass_rate,
            'time_ms': round((t1 - t0) * 1000, 3)
        })

    # AGREGATY
    sf_total_Z = sum(r['Z'] for r in results_sf)
    sl_total_Z = sum(r['Z'] for r in results_sl)
    sf_total_tokens = sum(r['tokens'] for r in results_sf)
    sl_total_tokens = sum(r['tokens'] for r in results_sl)
    sf_avg_W = statistics.mean(r['W'] for r in results_sf)
    sl_avg_W = statistics.mean(r['W'] for r in results_sl)
    sf_avg_pass = statistics.mean(r['pass_rate'] for r in results_sf)
    sl_avg_pass = statistics.mean(r['pass_rate'] for r in results_sl)
    sf_total_attempts = sum(r['attempts'] for r in results_sf)
    sl_total_attempts = sum(r['attempts'] for r in results_sl)

    savings_Z = (sl_total_Z - sf_total_Z) / sl_total_Z * 100
    savings_tokens = (sl_total_tokens - sf_total_tokens) / sl_total_tokens * 100

    print("\n" + "=" * 76)
    print("  RAPORT POROWNAWCZY")
    print("=" * 76)
    print()
    print("  %-28s | %12s | %12s | %12s" % ("Metryka", "Stateful", "Stateless", "Roznica"))
    print("  " + "-" * 73)
    print("  %-28s | %12.1f | %12.1f | %11.1f%%" % ("Total Z (koszt)", sf_total_Z, sl_total_Z, savings_Z))
    print("  %-28s | %12d | %12d | %11.1f%%" % ("Total tokens", sf_total_tokens, sl_total_tokens, savings_tokens))
    print("  %-28s | %12.4f | %12.4f | %11.4f" % ("Srednie W (jakosc)", sf_avg_W, sl_avg_W, sf_avg_W - sl_avg_W))
    print("  %-28s | %12.2f | %12.2f | %11.2f" % ("Pass rate sredni", sf_avg_pass, sl_avg_pass, sf_avg_pass - sl_avg_pass))
    print("  %-28s | %12d | %12d | %11.1f%%" % ("Liczba prob (suma)", sf_total_attempts, sl_total_attempts,
          (sl_total_attempts - sf_total_attempts) / sl_total_attempts * 100))
    print("  %-28s | %12d | %12s | %12s" % ("Uspienia Q", sum(1 for r in results_sf if r['state'] == 'Q'), "—", "—"))
    print("  %-28s | %12.3f | %12s | %12s" % ("Paliwo koncowe", results_sf[-1]['fuel'], "0.000", "—"))
    print("  %-28s | %12.3f | %12s | %12s" % ("Pamiec koncowa", results_sf[-1]['memory'], "0.000", "—"))

    print()
    print("  WNIOSKI:")
    print("  • Stateful oszczedza %.1f%% kosztu Z i %.1f%% tokenow" % (savings_Z, savings_tokens))
    print("  • Jakosc W wyzsza o %.2f (lepszy pass rate dzieki pamieci)" % (sf_avg_W - sl_avg_W))
    print("  • Mniej prob: %d vs %d (o %.1f%% mniej)" % (sf_total_attempts, sl_total_attempts,
          (sl_total_attempts - sf_total_attempts) / sl_total_attempts * 100))
    print("  • Paliwo koncowe: %.3f — gotowosc do kolejnych zadan" % results_sf[-1]['fuel'])

    # Zapisz wyniki
    with open("results/benchmark_results.txt", "w") as f:
        f.write("BENCHMARK: HumanEval-style (100 zadan)\n")
        f.write("=" * 60 + "\n\n")
        f.write("Stateful:  Total Z=%.1f, Tokens=%d, avg W=%.4f, Pass=%.2f\n" %
                (sf_total_Z, sf_total_tokens, sf_avg_W, sf_avg_pass))
        f.write("Stateless: Total Z=%.1f, Tokens=%d, avg W=%.4f, Pass=%.2f\n" %
                (sl_total_Z, sl_total_tokens, sl_avg_W, sl_avg_pass))
        f.write("Oszczednosc Z: %.1f%%\n" % savings_Z)
        f.write("Oszczednosc tokens: %.1f%%\n" % savings_tokens)
        f.write("Przewaga jakosci: +%.4f W\n" % (sf_avg_W - sl_avg_W))

    print("\n  Wyniki zapisano do: results/benchmark_results.txt")

if __name__ == "__main__":
    main()
