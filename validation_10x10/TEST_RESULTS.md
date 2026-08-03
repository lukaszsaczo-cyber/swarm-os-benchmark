# Wyniki kontroli technicznej

**Data:** 2026-08-02

## Testy jednostkowe

- 10/10 zaliczonych.
- Obejmują wykonanie poprawnego i błędnego kodu, normalizację odpowiedzi, rozłączny przydział zadań, pamięć SWARM_OS, regułę 20%, odrzucenie wyniku 10%, pełny przebieg 10×10, wznowienie po przerwaniu oraz zgodność próbkowania Claude Sonnet 4.6.

## Pełny test uprzęży 10 × 16

- 10 agentów SWARM_OS × 16 zadań = 160 obserwacji.
- 10 agentów kontrolnych × 16 zadań = 160 obserwacji.
- 320 zapisanych wyników i 320 prób.
- Przydział rozłączny, porównanie sparowane.
- Checkpoint i raport wygenerowane prawidłowo.

Dostawca w tym teście był sztuczny i celowo zwracał 25% mniej tokenów dla SWARM_OS. Wynik sprawdza wyłącznie działanie uprzęży i algorytmu statystycznego; nie jest wynikiem Claude.

## Granica

Pełny przebieg Claude API nie został jeszcze wykonany.
