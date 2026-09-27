# Instrukcje pracy nad Antenna Lab

## Cel i stan pracy

Najpierw przeczytaj `goal.md`, `history.md` i `docs/architecture.md`.
`goal.md` jest źródłem wymagań; parametry maszynowe znajdują się w `parameters/`.
Bieżący cel: parametryczna symulacja Quadosa 8 przy 1420 MHz, z możliwością
dodania innych anten bez zmiany zasad działania rdzenia.

Repozytorium na etapie M0 zawiera wymagania, strukturę i kontrakty danych.
Nie przedstawiaj szkieletu jako działającego symulatora ani pustych katalogów
jako zaimplementowanych modułów. Stan każdego etapu jest w `goal.md`.

## Zasady architektury

- `core` nie zna Quadosa, PyNEC ani interfejsu graficznego.
- Modele anten generują geometrię i porty; nie uruchamiają solvera.
- Adapter solvera przelicza jednostki i konwencje we własnej granicy.
- Parametry nie są zaszyte w kodzie. Każdy wynik zawiera ich rozwiązaną kopię.
- Wizualizacja czyta zapisane wyniki. Zmiana fazy animacji nie uruchamia solvera.
- Dodanie nowej anteny nie powinno wymagać specjalnych warunków w rdzeniu.
- Na początek jeden pakiet Pythona i jeden lokalny proces aplikacji. Nie dodawaj
  mikroserwisów, klastra, zewnętrznej bazy ani chmury bez konkretnej potrzeby.

## Rzetelność obliczeń

- W rdzeniu stosuj SI: m, Hz, V, A, W. Milimetry i MHz służą interfejsowi.
- Ustalona konwencja fazowa: część rzeczywista F · exp(+j · faza).
- Zachowuj surowe zespolone prądy i pola. Obraz nie zastępuje danych.
- Rozróżniaj kierunkowość, zysk i zysk uwzględniający niedopasowanie.
- Rozróżniaj impedancję anteny, impedancję odniesienia i transformację baluna.
- Siatki przewodów PEC nie nazywaj ciągłą blachą. Braku dielektryków, kabla,
  strat lub skończonej grubości nie ukrywaj w opisie wyniku.
- Nie dopasowuj modelu do oczekiwanego 17,6 dBi. To wartość referencyjna,
  a nie kryterium, które wolno wymuszać.
- Nie publikuj wyniku jako zweryfikowanego bez jawnej kontroli geometrii,
  źródła, jednostek, normalizacji i zbieżności istotnych wielkości.
- Brak wyniku zapisuj jako brak danych wraz z przyczyną, nigdy jako zero.

## Historia zmian i sprawdzanie

Każda większa zmiana wymaga wpisu w `history.md`: przyczyna, zakres, wpływ
na fizykę/wyniki, wpływ na formaty i odtwarzalność, wykonane sprawdzenia oraz
ograniczenia. Nie opisuj przyszłej pracy jako zakończonej.

Sprawdzaj ryzyka wynikające z konkretnej zmiany. Nie twórz testów, które jedynie
powtarzają implementację. Dla samej dokumentacji wystarcza kontrola jej spójności.
Użytkownik wykluczył benchmarki: nie twórz ani nie uruchamiaj ich bez nowej
instrukcji użytkownika. Nie wracaj do szacowania czasu na jego komputerze.

Wyniki dużych obliczeń są poza zwykłą historią Git; wersjonowane są konfiguracje,
schematy, kod i niewielkie, świadomie wybrane dane referencyjne. Nie dodawaj
danych dostępowych, lokalnych konfiguracji kont ani całego środowiska procesu.

## Sposób pracy

Instrukcje użytkownika mają pierwszeństwo. Dokumentacja dla użytkownika jest
po polsku, nazwy w kodzie po angielsku. Zachowuj istniejące zmiany użytkownika.
Nie twórz autonomicznie nowych agentów ani rozbudowanych procesów pracy.
W katalogach z własnym `AGENTS.md` obowiązują również instrukcje lokalne.

