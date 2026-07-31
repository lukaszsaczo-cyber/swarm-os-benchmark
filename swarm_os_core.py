"""
SWARM_OS Core - Homeostatyczny Silnik Agentow
Wersja publiczna (benchmark) - pokazuje mechanizm, nie ukrywa logiki
"""

class Task:
    def __init__(self, payload, priority=1):
        self.payload = payload
        self.priority = priority

class TaskResult:
    def __init__(self, W, Z, attempts, lines, state, fuel, memory, pass_rate):
        self.W = W  # jakosc (pass rate)
        self.Z = Z  # koszt (tokeny)
        self.attempts = attempts
        self.lines = lines
        self.state = state
        self.fuel = fuel
        self.memory = memory
        self.pass_rate = pass_rate

class SectorAgent:
    """Agent stateful z pamiecia organizacyjna"""
    def __init__(self, sector_id, E=0.9, kappa=1.4, rho=0.6, rate=0.25,
                 threshold=0.16, alpha=0.1, erosion=0.05):
        self.sector_id = sector_id
        self.E = E
        self.kappa = kappa
        self.rho = rho
        self.rate = rate
        self.threshold = threshold
        self.alpha = alpha
        self.erosion = erosion
        self.fuel = 1.0
        self.memory = 0.0
        self.entropy = 0.0
        self.state = 'A'
        self.solved_count = 0

    def solve(self, task_data):
        """Rozwiazanie zadania z learning curve"""
        difficulty = task_data['difficulty']
        lines_base = task_data['lines_base']

        # Efektywna trudnosc maleje z pamiecia (uczenie sie wzorcow)
        memory_bonus = min(self.memory * 3, difficulty - 1)
        effective_diff = max(1, difficulty - memory_bonus)

        # Mniej prob = mniejszy koszt
        attempts = effective_diff
        lines = lines_base + attempts * 2

        # Jakosc: im mniej prob, tym wyzszy pass rate
        pass_rate = min(0.95, 0.5 + (memory_bonus * 0.1))

        # Bilans paliwa
        W = pass_rate  # jakosc jako W
        dW = abs(W - 0.5)  # zmiana od baseline
        self.fuel += (self.E - self.kappa * W - self.rho * dW) * self.rate

        if self.fuel > 0:
            self.memory += self.alpha * self.fuel
        else:
            self.memory *= (1 - self.erosion)

        self.memory = max(0, min(2, self.memory))

        # Koszt Z: lines * attempts * complexity
        complexity = 2.0 if self.memory > 0.2 else 2.5
        Z = lines * attempts * complexity

        # Bramka Q
        if self.fuel < self.kappa * W * self.rate or W < 0.3:
            self.state = 'Q'
            self.fuel = 0.5
            self.memory *= 0.5
        else:
            self.state = 'A'
            self.solved_count += 1

        return TaskResult(W, Z, attempts, lines, self.state,
                         round(self.fuel, 3), round(self.memory, 3), pass_rate)

class StatelessAgent:
    """Agent bez pamieci - kazde zadanie od zera"""
    def solve(self, task_data):
        difficulty = task_data['difficulty']
        lines_base = task_data['lines_base']

        attempts = difficulty  # zawsze pelna trudnosc
        lines = lines_base + attempts * 2
        pass_rate = 0.6  # stala, bez uczenia sie
        complexity = 2.5  # zawsze pelny
        Z = lines * attempts * complexity

        return TaskResult(pass_rate, Z, attempts, lines, 'A', 0.0, 0.0, pass_rate)
