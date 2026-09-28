# Kolejność implementacji

1. **M1 — ukończona implementacja geometrii.** Rdzeń, konfiguracja v2,
   generator Quadosa, kontrola długości i połączeń, eksport oraz lokalny edytor.
2. **M2 — adapter napisany, walidacja otwarta.** Najpierw `prepare` na Windowsie,
   następnie kontrolny dipol, weryfikacja portu i normalizacji, obliczenie
   Quadosa oraz co najmniej trzy poziomy dyskretyzacji. Odczyt prądów pozostaje
   do implementacji; sam port i pole dalekie nie zamykają tego etapu.
3. **M3 — pola.** Zespolone E/H, maski PEC i obszarów niewiarygodnych, stałe
   skale, fazy 0–180° co 30° oraz pełny okres animacji. Dane przed obrazami.
4. **M4 — rozwinięcie interfejsu.** Edycja parametrów już działa. Pozostają
   sterowanie obliczeniami z okna, serie C/D/H, porównanie wariantów
   i przegląd wcześniejszych wyników.

Kolejne anteny, materiały stratne, wsporniki i balun są późniejszymi
rozszerzeniami. Reflektor w aktualnym modelu jest pełną płytą PEC.
Benchmarki, prace nad GPU i hosting nie należą do zakresu.
