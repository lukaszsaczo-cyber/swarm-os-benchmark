# Status walidacji

## Zrobione

- architektura 10 agentów SWARM_OS kontra 10 kontrolnych,
- rozłączny i sparowany przydział 160 zadań,
- obsługa rzeczywistych liczników tokenów Anthropic API,
- rzeczywiste wykonanie kodu i testów,
- liczenie wszystkich prób, randomizacja kolejności i wznowienie po przerwaniu,
- pamięć SWARM_OS kontrolowana stanem `fuel/memory/A/Q`,
- kontrola bez pamięci między zadaniami,
- bootstrap klastrowy, próg 20% i non-inferiority jakości,
- komplet surowych danych, manifest, checkpoint i raport,
- zgodność z Claude Sonnet 5: domyślne próbkowanie bez parametru `temperature`,
- 10/10 testów jednostkowych oraz pełny test offline 10×16.

## Jeszcze niewykonane

Pełny płatny przebieg na Claude API nie został jeszcze wykonany. Klucz API jest skonfigurowany jako sekret użytkownika Codespaces i nie znajduje się w repozytorium. Wynik procentowy powstanie dopiero po uruchomieniu oficjalnego HumanEval.
