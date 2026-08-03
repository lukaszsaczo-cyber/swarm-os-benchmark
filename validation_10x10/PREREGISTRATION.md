# Prerejestracja ostatecznej walidacji SWARM_OS 10 × 10

**Data zamrożenia protokołu:** 2026-08-01  
**Cel:** sprawdzić, czy 10 agentów sterowanych przez SWARM_OS zużywa co najmniej 20% mniej rzeczywistych tokenów API niż 10 agentów kontrolnych przy porównywalnej skuteczności.

## Hipoteza główna

SWARM_OS osiąga co najmniej 20% redukcji łącznej liczby tokenów dostawcy względem kontroli. Łączna liczba tokenów obejmuje wszystkie próby: `input_tokens + output_tokens + cache_creation_input_tokens + cache_read_input_tokens`. Prompt caching jest wyłączony w obu warunkach.

## Projekt

- 10 sparowanych agentów SWARM_OS.
- 10 sparowanych agentów kontrolnych.
- Instancje są niezależne, ale wykonywane sekwencyjnie; równoległość nie jest częścią hipotezy.
- 16 zadań na parę agentów, razem 160 różnych zadań.
- Zadania są losowo dzielone na 10 rozłącznych zestawów z zamrożonym ziarnem `20260801`.
- Para o tym samym numerze otrzymuje identyczne zadania w identycznej kolejności.
- Kolejność wywołania SWARM/kontrola dla każdego zadania jest randomizowana z ziarnem `330016`, aby ograniczyć wpływ chwilowych zmian usługi.
- Ten sam przypięty model, temperatura, limit wyjścia i maksymalna liczba prób.
- Maksymalnie 3 próby na zadanie. Każda próba i jej tokeny są liczone.
- Wynik zadania pochodzi wyłącznie z rzeczywistego uruchomienia kodu i testów.

## Warunki

### SWARM_OS

Agent zachowuje między zadaniami ograniczoną pamięć semantyczną. Liczba dostępnych wpisów pamięci jest sterowana stanem publicznego silnika homeostatycznego (`fuel`, `memory`, `A/Q`). Wartość `W` jest zastąpiona pomiarem rzeczywistym: 1 po zaliczeniu testów, 0 po niezaliczeniu. Jest to jawny adapter pomiarowy, a nie ukryta symulacja pass rate.

### Kontrola

Agent zaczyna każde nowe zadanie bez pamięci poprzednich zadań. W obrębie jednego zadania może otrzymać ten sam komunikat błędu przy ponownej próbie co SWARM_OS.

## Główny punkt końcowy

`redukcja = 1 - tokeny_SWARM / tokeny_kontrola`

Przedział ufności jest liczony bootstrapem klastrowym na poziomie 10 par agentów, ponieważ wyniki zadań jednego agenta nie są niezależne.

## Kryterium jakości

Różnica skuteczności `pass_rate_SWARM - pass_rate_kontrola` nie może mieć dolnej granicy 95% przedziału niższej niż `-0,02`.

## Reguła werdyktu

Wynik `CONFIRMED` wymaga jednocześnie:

1. pełnego przebiegu 10 × 10,
2. dolnej granicy 95% CI redukcji tokenów >= 20%,
3. dolnej granicy 95% CI różnicy skuteczności >= -2 p.p.,
4. kompletnego zapisu rzeczywistych tokenów dla każdej próby.

Każdy inny wynik to `NOT_CONFIRMED`. Punktowy wynik 20% bez odpowiednio mocnego przedziału ufności nie wystarcza.

## Zakaz zmian po zobaczeniu wyniku

Po rozpoczęciu wywołań API nie wolno zmieniać modelu, promptów, limitów, ziaren, zbioru zadań, definicji tokenów, marginesu jakości ani reguły werdyktu. Każda zmiana wymaga nowej wersji protokołu i nowego przebiegu.

## Granica interpretacji

Potwierdzenie dotyczy wyłącznie modelu, zbioru, konfiguracji i daty testu. Nie oznacza absolutnej pewności ani automatycznej przewagi na innych zadaniach.

## Aneks techniczny przed pierwszym wywołaniem API — 2026-08-02

Nie wykonano jeszcze żadnego płatnego wywołania ani nie zobaczono wyniku. Claude Sonnet 4.6 wymaga domyślnych parametrów próbkowania, dlatego pole `temperature` zmieniono z `0.0` na `null`, co oznacza pominięcie tego parametru w API identycznie dla SWARM_OS i kontroli. Nie zmieniono modelu, zadań, ziaren, liczby prób, metryk, progu 20%, marginesu jakości ani reguły werdyktu.
