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
Kontrola source_work z 450 parami sond jest ukończona na Windowsie; poprawka
limitu UCRT została potwierdzona. Przy pierwotnym odniesieniu portu 1 W praca
lokalna netto wynosi 0,879386295 W, strumień zewnętrzny 0,878490162 W.
Pozorny deficyt 12,15% względem pojedynczego U·I maleje do 0,102% względem
pracy lokalnej. To nie jest jeszcze walidacja impedancji i zysku.
Znaleziono błąd adaptera: zaokrąglone kotwice siatki leżą minimalnie poza
niezaokrąglonym boxem źródła; opór obejmuje 450 krawędzi, wymuszenie tylko 270.
Pozostałe 180 krawędzi ma zmierzony wkład ujemny zgodny z samym oporem.
Nowy wariant parameters/quados8_1420mhz_aligned_feed.json ustawia
solver.port_mesh_alignment=mesh_anchors i przekazuje dokładne granice siatki
do AddLumpedPort. Użytkownik ukończył ten wariant natywnie: 450 dodatnich
wkładów pracy, zero ujemnych; ta sama geometria i siatka. Praca 0,949145539 W,
strumień zewnętrzny 0,948187885 W, różnica 0,10090% względem pracy.
Pomiar pojedynczego U·I nadal daje 1 W, czyli rozbieżność 5,085% względem
tego odniesienia. Poprawka granic jest potwierdzona, pomiar mocy portu nadal
wymaga rozwiązania. Z=67,701−j95,621 Ω i SWR200=3,6975 są robocze.
Kierunkowość na osi wynosi 17,5100 dBi w obu przebiegach; porównanie względem
lokalnej pracy daje około 17,5056 dBi, ale nie zastępuje kontroli zbieżności.
Brak opcji/legacy zachowuje stare źródło do odtwarzania; nie traktuj go jako
poprawionego modelu. Nie wymuszaj bilansu renormalizacją i nie zatwierdzaj
starego ani nowego SWR/zysku. Nie poprawiaj Z mnożnikiem bilansu mocy.
Powtarzanie aligned_feed bez zmiany hipotezy nie rozwiąże niejednorodnego
pomiaru portu; dane już to wykazały. Następny eksperyment wymaga jawnej
definicji bardziej lokalnego zasilania i jego kontroli. Potem zbieżność
i strojenie (docs/power-audit.md). Błąd otwarcia pliku zatrzymuje pracownika.
Analiza geometrii wskazuje dwie nadmiarowe kule przy (±G/2,0,H), całkowicie
wewnątrz dwóch przeciwległych walców A. Pozostałe 46 ma własne próbki E.
To wyjaśnia dwa ostrzeżenia Sphere; nie jest pełnym natywnym audytem połączeń.
Nie przedstawiaj M2 jako zakończonego. Prądy promiennika i mapy E/H są
jeszcze niezaimplementowane; żądanie tych danych musi kończyć się jawnym błędem.
Pasywne sondy portu i powierzchnie diagnostyczne nie zaliczają M3.

## Zasady architektury

- `core` nie zna Quadosa, API openEMS ani interfejsu graficznego.
- Modele anten generują geometrię i porty; nie uruchamiają solvera.
- Adapter solvera przelicza jednostki i konwencje we własnej granicy.
- Parametry nie są zaszyte w kodzie. Każdy wynik zawiera ich rozwiązaną kopię.
- Wizualizacja czyta zapisane wyniki. Zmiana fazy animacji nie uruchamia solvera.
- `report` tworzy samodzielny HTML offline z istniejących wyników; opis
  w `docs/reports.md`. Ręczne raporty zapisuj poza ukończonym przebiegiem.
  Automatyczny raport powstaje przed zamknięciem manifestu nowego `run`;
  błąd prezentacji nie może unieważnić udanego FDTD. Suwak impedancji nie
  zmienia częstotliwości bilansu ani pola dalekiego. Nie zatwierdzaj modelu
  automatycznie na podstawie zgodności bilansu i nie koryguj Z/zysku.
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
