# SWARM_OS — ostateczna walidacja 10 agentów kontra 10 agentów

To jest właściwa uprząż do testu, który został wcześniej ustalony: **10 agentów sterowanych przez SWARM_OS kontra 10 zwykłych agentów**, z pomiarem rzeczywistych tokenów Claude API i rzeczywistym wykonaniem testów kodu.

## Co ten projekt mierzy

- prawdziwe `input_tokens` i `output_tokens` zwrócone przez Anthropic API,
- wszystkie tokeny ze wszystkich prób, nie tylko końcowej odpowiedzi,
- skuteczność kodu w testach jednostkowych,
- liczbę prób i czas,
- różnicę 10 sparowanych klastrów agentów,
- 95% przedziały ufności i twardy werdykt wobec progu 20%.

Nie ma tu przelicznika `linie × 4`, losowanego pass rate ani z góry wpisanej przewagi SWARM_OS.

## Zamrożony projekt ostateczny

- 10 agentów SWARM_OS,
- 10 agentów kontrolnych,
- 20 niezależnych instancji wykonuje się sekwencyjnie dla kontroli kosztu i limitów API; niezależność stanu, a nie równoczesność, definiuje agenta,
- 16 różnych zadań na każdą parę,
- 160 sparowanych obserwacji na warunek,
- maksymalnie 3 próby na zadanie,
- przypięty model `claude-sonnet-4-6`,
- domyślne próbkowanie modelu (parametr `temperature` jest pominięty identycznie w obu warunkach),
- prompt caching wyłączony,
- maksymalnie 960 wywołań API w najgorszym przypadku.

Pełna reguła jest zamrożona w [`PREREGISTRATION.md`](PREREGISTRATION.md).

## Ważna poprawka zgodności z Claude Sonnet 4.6

Przed pierwszym przebiegiem API protokół poprawiono technicznie: Claude Sonnet 4.6 odrzuca niedomyślne parametry próbkowania, dlatego `temperature` jest pomijane w obu warunkach. Hipoteza, przydział zadań, progi, liczba agentów i reguła werdyktu nie zostały zmienione.

## Instalacja

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Ustaw klucz lokalnie. Klucz nie jest zapisywany do logów:

```bash
export ANTHROPIC_API_KEY='...'
```

## Przygotowanie oficjalnego HumanEval

Zainstaluj autoryzowaną kopię oficjalnego repozytorium i wyeksportuj dane:

```bash
pip install git+https://github.com/openai/human-eval.git
python scripts/prepare_humaneval.py --output data/HumanEval.jsonl
```

Projekt wymaga co najmniej 160 zadań. Oryginalny HumanEval zawiera 164.

## Najpierw pokaż plan bez kosztów

```bash
python -m swarm_validation.cli plan \
  --config examples/final_protocol.json \
  --tasks data/HumanEval.jsonl \
  --output-dir results/live-2026-08-02
```

## Uruchomienie prawdziwego testu

```bash
python -m swarm_validation.cli run \
  --config examples/final_protocol.json \
  --tasks data/HumanEval.jsonl \
  --output-dir results/live-2026-08-02 \
  --confirm-live-run RUN_10X10_CLAUDE_VALIDATION
```

Po przerwaniu można wznowić:

```bash
python -m swarm_validation.cli run \
  --config examples/final_protocol.json \
  --tasks data/HumanEval.jsonl \
  --output-dir results/live-2026-08-02 \
  --resume \
  --confirm-live-run RUN_10X10_CLAUDE_VALIDATION
```

## Pliki dowodowe

- `manifest.json` — hash zbioru, pełna konfiguracja i przydział zadań,
- `attempts.jsonl` — każdy prompt, wynik, kod, tokeny i test,
- `outcomes.jsonl` — wynik każdego sparowanego zadania,
- `checkpoint.json` — stan do wznowienia,
- `report.json` — dane końcowe,
- `report.md` — czytelny raport i werdykt.

## Bezpieczeństwo

Kod wygenerowany przez model jest nieufny. Wbudowane limity procesu ograniczają ryzyko, ale nie są pełnym sandboxem. Ostateczny przebieg należy wykonywać w jednorazowym kontenerze lub maszynie wirtualnej bez sekretów i bez dostępu do sieci dla procesu testującego. Sam proces wywołujący Anthropic API oczywiście potrzebuje sieci i klucza.

## Najważniejsza granica

Samo przejście testów uprzęży nie potwierdza 20%. Potwierdzenie powstaje dopiero po pełnym przebiegu Claude API, gdy `report.md` wyda `CONFIRMED` według wcześniej zamrożonych reguł.

## Test offline uprzęży

`python scripts/offline_harness_check.py` wykonuje pełny układ 10×16 na sztucznym dostawcy. Wstrzyknięte 25% służy wyłącznie do sprawdzenia logiki raportu i **nie jest wynikiem Claude ani dowodem przewagi systemu**.
