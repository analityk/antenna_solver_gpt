# Kolejność implementacji

Najbliższa praca przygotowawcza: migracja szczegółowych kontraktów M0 z NEC
na openEMS zgodnie z `goal.md`. Nie implementować wycofanych założeń NEC.

1. **M1 — model geometryczny.** Typy rdzenia, odczyt konfiguracji, generator
   Quadosa, eksport geometrii i podgląd. Sprawdzenie długości, portu, symetrii
   i połączeń. Bez wyników elektromagnetycznych na tym etapie.
2. **M2 — pierwsze obliczenia.** Adapter openEMS, kontrolny dipol, port,
   dyskretyzacja, prądy, impedancja i charakterystyka. Sprawdzenie zbieżności
   Quadosa i jawne oznaczenie niepewności rekonstrukcji.
3. **M3 — pola i dokumentacja wyniku.** Kompleksowe E/H, maski, stałe skale
   porównawcze, fazy 0–180° i pełna animacja okresu. Kontrakt outcomes.
4. **M4 — aplikacja lokalna.** Edycja parametrów, uruchamianie/anulowanie
   obliczeń, porównanie wariantów C/D/H i odczyt wcześniejszych przebiegów.

Kolejne anteny, pełniejszy reflektor i balun są rozszerzeniami po osiągnięciu
użytecznej wersji dla Quadosa. Decyzje o frameworku GUI, instalacji na systemie
użytkownika i dystrybucji solvera podejmujemy w odpowiednim etapie, bez
dodawania zależności na zapas. Nie wykonujemy benchmarków.
