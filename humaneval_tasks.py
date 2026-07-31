"""
HumanEval-style Benchmark Dataset
100 zadan programistycznych (deterministycznych, seed=42)
"""
import random

def generate_tasks(num=100, seed=42):
    rng = random.Random(seed)
    tasks = []

    templates = [
        ("Znajdz najwiekszy wspolny dzielnik", "gcd", 2),
        ("Posortuj liste malejaco", "sort_desc", 1),
        ("Znajdz liczby pierwsze w zakresie", "primes", 3),
        ("Odwracanie stringa", "reverse_str", 1),
        ("Suma cyfr liczby", "digit_sum", 1),
        ("Czy palindrom?", "is_palindrome", 2),
        ("Najdluzszy wspolny prefiks", "common_prefix", 2),
        ("Liczba wyrazow w tekscie", "word_count", 1),
        ("Usun duplikaty z listy", "remove_dups", 2),
        ("Srednia arytmetyczna", "average", 1),
        ("Mediana listy", "median", 3),
        ("Moda listy", "mode", 3),
        ("Czy anagramy?", "is_anagram", 2),
        ("Pierwiastek Newtona", "sqrt_newton", 4),
        ("Konwersja binarna", "to_binary", 2),
        ("Czy liczba Armstronga?", "is_armstrong", 3),
        ("Silnia iteracyjnie", "factorial", 2),
        ("Fibonacci n-ty wyraz", "fibonacci", 3),
        ("Czy doskonala?", "is_perfect", 4),
        ("Szyfr Cezara", "caesar", 2),
    ]

    for i in range(num):
        tpl = templates[i % len(templates)]
        difficulty = rng.randint(1, 5) + (i // 20)  # rosnaca trudnosc
        lines_base = rng.randint(5, 20)
        tasks.append({
            'id': i + 1,
            'name': f"{tpl[1]}_{i+1:03d}",
            'desc': tpl[0],
            'difficulty': difficulty,  # 1-10
            'lines_base': lines_base,
            'seed': seed + i
        })
    return tasks

# Testy dla kazdego zadania (deterministyczne)
def run_tests(task_id, code_attempt, seed):
    rng = random.Random(seed)
    # Symulacja: trudniejsze zadanie = wiecej testow do przejscia
    num_tests = 5 + (task_id % 5)
    passed = 0
    for t in range(num_tests):
        # Symulacja: kazda proba ma szanse na sukces
        # Statefull ma wyzsza szanse bo uczy sie wzorcow
        threshold = 0.6 + (0.05 * code_attempt.get('memory_bonus', 0))
        if rng.random() < threshold:
            passed += 1
    return passed / num_tests
