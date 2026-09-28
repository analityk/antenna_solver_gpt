# antenna_solver_gpt

Lokalny program do parametrycznego modelowania anten. Pierwszy model to
**Quados 8 przy dokładnie 1420 MHz**, z czterema połączonymi gałęziami
i skończonym reflektorem. Silnik obliczeniowy: **openEMS** na Windows 11.

**Działa generator, edytor wymiarów i eksport geometrii (M1).**
Adapter openEMS oraz odczyt impedancji i pola dalekiego są zaimplementowane;
użytkownik ukończył przebiegi na Windowsie. Lokalny pomiar pracy źródła
wyjaśnia niemal cały pozorny deficyt mocy 12,15%: różnica względem strumienia
zewnętrznego wynosi 0,102%. Znaleziono błąd granic wymuszenia na siatce.
Wariant aligned_feed wykonano na Windowsie: poprawka granic działa, bilans
pracy i strumienia pozostaje zgodny do 0,101%. Pojedynczy pomiar U·I nadal
różni się od pracy lokalnej o 5,085% swojego odniesienia; kontrola portu
i walidacja M2 pozostają otwarte.
Nie ma jeszcze zweryfikowanych wyników anteny, map E/H, prądów ani animacji.

## Pierwsze uruchomienie — CMD

W istniejącej kopii użytkownika, z już zainstalowanym openEMS:

```bat
cd /d C:\dev\antenna_solver_gpt\antenna_solver_gpt
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m antenna_lab preview
```

Instalacja `-e .` łączy pakiet z kodem w tej kopii repozytorium. Obecna wersja
wymaga również katalogów `schemas/` i `parameters/` z repozytorium; nie jest
przeznaczona do instalacji jako samodzielny wheel.
Pełna instrukcja środowiska: [Windows 11](docs/windows-setup.md).

Edytor pokazuje antenę z przodu i z boku. Wymiary podajesz w mm, częstotliwość
w MHz. Pisanie, wklejanie i przechodzenie Tabem nie przelicza modelu i nie
odrysowuje wykresu. **Enter** lub **Zastosuj** zatwierdza wszystkie pola
oraz włączenie/wyłączenie reflektora. Komunikat przypomina o niezastosowanych
zmianach. Zmiana częstotliwości zachowuje wymiary; **Skaluj…** jest osobną operacją.
Kolory oznaczają odcinki A–F, nie rozkład prądu. Edytor nie uruchamia FDTD.

| Przycisk | Co zapisuje | Do czego służy |
| --- | --- | --- |
| **Wczytaj parametry…** | Nic; odczytuje wybrany JSON | Zastępuje pola i podgląd zapisanym wariantem; błędny plik lub anulowanie zachowuje bieżącą edycję |
| **Zapisz parametry (.json)…** | Jeden plik ustawień w wybranym miejscu | Ponowna edycja lub obliczenia tego wariantu przez opcję --config |
| **Eksportuj geometrię** | Nowy folder z modelem, rysunkiem PNG, parametrami i dokumentacją przebiegu | Obejrzenie i zachowanie konkretnej konstrukcji; bez obliczeń openEMS |

Zapis i eksport najpierw zatwierdzają bieżące pola. Błędny lub niekompletny
wpis blokuje zapis; program nie zapisuje wówczas poprzedniego modelu jako nowego.
Po sukcesie ścieżkę można skopiować z pola pod komunikatem.
Po wczytaniu pliku **Przywróć początkowe** wraca do wczytanego wariantu.

## Polecenia

W poniższych poleceniach używaj `.\.venv\Scripts\python.exe`:

| Polecenie | Działanie |
| --- | --- |
| `-m antenna_lab preview` | Edytor wymiarów i widoki xy/yz |
| `-m antenna_lab check` | Kontrola geometrii i plan siatki, bez openEMS |
| `-m antenna_lab geometry` | Nowy katalog z geometrią, konfiguracją i PNG |
| `-m antenna_lab prepare` | Import openEMS i zapis pełnego XML, bez obliczeń FDTD |
| `-m antenna_lab run` | Eksperymentalne FDTD oraz zapis impedancji i pola dalekiego |
| `-m antenna_lab report wariant_01.json --open` | HTML z obliczeń zapisanej geometrii; działa także ze starszymi wynikami |
| `-m antenna_lab report --latest --open` | Interaktywny HTML z najnowszej ukończonej symulacji, bez FDTD |

Przykłady wariantów:

```bat
.\.venv\Scripts\python.exe -m antenna_lab preview --set-mm C=75 --set-mm D=80
.\.venv\Scripts\python.exe -m antenna_lab geometry --no-reflector
.\.venv\Scripts\python.exe -m antenna_lab prepare --config parameters\quados8_variant.json
```

Opcje `--frequency-mhz 1500` i `--scale-to-mhz 1500` oznaczają odpowiednio
zmianę częstotliwości bez zmiany anteny oraz jawne skalowanie wszystkich
wymiarów. Nie można użyć ich jednocześnie.

Pierwszy krok integracji na komputerze użytkownika to `prepare`. Sukces
potwierdza utworzenie wejścia, nie poprawność elektromagnetyczną modelu.
Polecenie `run` działa w osobnym procesie; **Ctrl+C** przerywa obliczenie.
Każde uruchomienie zapisuje osobny katalog `outcomes/runs/<run_id>/`.
Nazwa nowego katalogu zaczyna się od nazwy pliku wariantu, np.
`quados8_variant_sz4__20260928T221500Z_0123456789`. Data UTC i końcowy
identyfikator rozróżniają ponowne obliczenia bez nadpisywania wyników.
Wyniki pozostają **unverified** do kontroli źródła, przypadku referencyjnego
i zbieżności siatki. Nie wykonujemy benchmarków.

## Raport lokalny — także dla wcześniejszych wyników

```bat
git pull --ff-only
.\.venv\Scripts\python.exe -m antenna_lab report --latest --open
```

Polecenie wybiera najnowszą **ukończoną symulację**, tworzy nowy samodzielny
HTML w `outcomes/reports/` i otwiera go w przeglądarce. Nie uruchamia openEMS,
nie wysyła danych i nie używa API ani tokenów. Działa z już zainstalowanymi
zależnościami. Starsze wyniki i ich manifesty pozostają niezmienione.

Raport ma suwak częstotliwości, zmianę Zref, R/X, SWR, S11, CSV, przejścia
X przez zero, zapisane przekroje kierunkowe, bilans mocy i ostrzeżenia.
Pola dalekie i diagnostyka mają własne, jawnie podane częstotliwości; suwak
impedancji ich nie przelicza. Brakujących danych nie zastępuje zerami.
Kolejne `run` tworzą `report.html` automatycznie, również z diagnostyką mocy.
Szczegóły i wybór konkretnego przebiegu: [raporty HTML](docs/reports.md).

## Model i dokumentacja

Przed zmianą skali anteny sprawdzamy zasilanie. Poniższy wariant jest już
ukończonym eksperymentem kontrolnym. Konfiguracja zachowuje wymiary, siatkę,
opór i impuls, ale uzgadnia granice portu z kotwicami siatki: wymuszenie
obejmuje wszystkie 450 krawędzi zamiast 270. To zmiana dyskretnego źródła.

```bat
.\.venv\Scripts\python.exe -m antenna_lab run --config parameters\quados8_1420mhz_aligned_feed.json
```

To nowy przebieg FDTD. Oprócz raportu HTML zapisuje `power_balance.json`,
widmo impedancji 1400–1440 MHz co 0,25 MHz i małą paczkę `power_diagnostics.zip`
w nowym katalogu wyników. Ten krok częstotliwości dotyczy odczytu przebiegów
portu, nie dodatkowych symulacji ani deklaracji dokładności. Szczegóły i
interpretacja: [diagnostyka mocy](docs/power-audit.md).
Przed Run zapisuje także `feed_grid_coverage.json`; komunikat powinien podać
450/450 krawędzi. Starsze konfiguracje bez `port_mesh_alignment` zachowują
wadliwe granice źródła do porównań i zgłaszają ostrzeżenie. Poprawka wymaga
`mesh_anchors`; nie zmienia wcześniej zapisanych wyników ani normalizacji.
Ponowne wykonanie tego samego wariantu nie jest potrzebne do analizy
rozbieżności. Następny eksperyment dotyczy definicji i pomiaru portu;
ustalenia są w [diagnostyce mocy](docs/power-audit.md).

Promiennik jest sumą cylindrów PEC ze złączami kulistymi. Reflektor jest
pełną płytą PEC o zadanej grubości. Port różnicowy ma odniesienie 200 Ω;
to nie założona impedancja anteny. Balun, kabel, straty i wsporniki są poza modelem.
Wymiary startowe przeskalowano z roboczo przyjętych 2450 MHz. Nie są projektem
anteny dostrojonej i potwierdzonej pomiarem przy 1420 MHz.

| Ścieżka | Odpowiedzialność |
| --- | --- |
| [goal.md](goal.md), [history.md](history.md), `AGENTS.md` | Wymagania, decyzje i instrukcje pracy |
| `src/antenna_lab/core/` | Geometria, walidacja, konfiguracje i zapis przebiegów |
| `src/antenna_lab/antennas/` | Generatory konkretnych anten |
| `src/antenna_lab/solvers/` | Siatka i adapter openEMS |
| `src/antenna_lab/app/`, `src/antenna_lab/visualization/` | Edytor, wykresy i raport |
| `parameters/`, `schemas/` | Wymiary źródłowe, warianty i kontrakty JSON |
| [outcomes/README.md](outcomes/README.md) | Kontrakt zapisanych danych |
| [docs/architecture.md](docs/architecture.md) | Granice modułów |
| [docs/openems-model.md](docs/openems-model.md) | Dyskretyzacja, port i normalizacja |
| [docs/quados8-geometry.md](docs/quados8-geometry.md) | Dokładna konstrukcja gałęzi |
| [docs/roadmap.md](docs/roadmap.md), [docs/sources.md](docs/sources.md) | Dalsze etapy i źródła |

Sprawdzenia kodu bez natywnego solvera:

```bat
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testy geometrii i zapisu nie zastępują kontroli fizycznej anteny.
