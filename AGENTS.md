# Instrukcje pracy nad antenna_solver_gpt

## Cel i stan pracy

Najpierw przeczytaj `goal.md`, `history.md` i `docs/architecture.md`.
`goal.md` jest źródłem wymagań; parametry maszynowe znajdują się w `parameters/`.
Bieżący cel: parametryczna symulacja Quadosa 8 przy 1420 MHz, z możliwością
dodania innych anten bez zmiany zasad działania rdzenia.

Platforma docelowa użytkownika: natywny Windows 11. Instrukcje uruchamiania
mają używać środowiska `.venv` i składni aktualnej powłoki użytkownika.
Instalacja i import zostały potwierdzone w CMD; PowerShell również jest dostępny.
Git, Python i VS Code są już zainstalowane. Interpreter: CPython 3.14.0, 64-bit AMD64.
Wybrany solver to openEMS. Lokalizacja paczki podana przez użytkownika:
`C:\dev\openems\openEMS`. Instrukcja instalacji: `docs/windows-setup.md`.
Nie wymagaj WSL, zmiany systemu ani uv. Użytkownik potwierdził import
openEMS 0.37.0rc3 i CSXCAD na Windowsie 2026-09-28. Walidacja obliczeniowa
pozostaje otwarta; sam import ani pierwszy solve nie kończą integracji M2.

NEC2++ / PyNEC nie jest częścią implementacji. Kontrakty przeniesiono na
openEMS: konfiguracja i manifest mają wersję 2. Wymiarów źródłowych nie zmieniono.
Potwierdzone środowisko zapisano w `docs/windows-setup.md`.

M1 jest zaimplementowane: generator, walidacja, edytor i eksport geometrii.
Adapter openEMS, impedancja i pole dalekie są kodem eksperymentalnym:
Użytkownik ukończył przebieg 20260928T004231Z_902d497594 na Windowsie.
Bilans mocy PEC wykazuje deficyt 12,15%; niezależne całkowanie surowych NF2FF
potwierdza odczyt, ale przyczyna fizyczna/numeryczna pozostaje otwarta.
Najpierw diagnostyka mocy (docs/power-audit.md), potem skalowanie i zbieżność.
Nie przedstawiaj M2 jako zakończonego. Prądy promiennika i mapy E/H są
jeszcze niezaimplementowane; żądanie tych danych musi kończyć się jawnym błędem.
Pasywne sondy portu i powierzchnie diagnostyczne nie zaliczają M3.

## Zasady architektury

- `core` nie zna Quadosa, API openEMS ani interfejsu graficznego.
- Modele anten generują geometrię i porty; nie uruchamiają solvera.
- Adapter solvera przelicza jednostki i konwencje we własnej granicy.
- Parametry nie są zaszyte w kodzie. Każdy wynik zawiera ich rozwiązaną kopię.
- Wizualizacja czyta zapisane wyniki. Zmiana fazy animacji nie uruchamia solvera.
- Dodanie nowej anteny nie powinno wymagać specjalnych warunków w rdzeniu.
- Na początek jeden pakiet Pythona; solver działa w lokalnym procesie potomnym.
  Nie dodawaj
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
