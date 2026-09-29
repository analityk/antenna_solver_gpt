# Architektura

Jeden pakiet Pythona `antenna_lab`, lokalny interfejs i natywny openEMS.
Geometria oraz konfiguracja są niezależne od solvera. Instalacja jest obecnie
edycyjna (`pip install -e .`) w kopii repozytorium: stąd pobierane są schematy
i domyślne parametry. Samodzielna dystrybucja wheel nie jest jeszcze obsługiwana.

| Moduł | Implementacja | Granica odpowiedzialności |
| --- | --- | --- |
| `core/config.py` | JSON Schema v2, wartości skończone, warianty, skalowanie | Bez nazw wymiarów konkretnej anteny |
| `core/geometry.py` | Wire, Plate, Port, Geometry, topologia i kolizje | Geometria SI, bez siatki FDTD |
| `core/runs.py` | RunRecord, konfiguracja, schematy, kod i skróty artefaktów | Bez wyników zastępczych |
| `core/catalog.py` | Czytelne nazwy wariantów i wyszukiwanie ukończonych obliczeń po geometrii | Bez solvera i bez modyfikacji historycznych wyników |
| `antennas/` | Rejestr i generatory Quados8 oraz biquada | Bez importu openEMS |
| `solvers/mesh.py` | Niejednorodna siatka kartezjańska, PML, kontrola limitu | Bez zmian wymiarów anteny |
| `solvers/feed.py` | Granice portu i audyt pokrycia krawędzi przez box wymuszenia | Korekta zaokrągleń w adapterze; bez zmiany siatki |
| `solvers/openems.py` | Materiały, port, FDTD XML, impedancja i NF2FF | Główny adapter natywnego API |
| `solvers/power.py` | Pasywne sondy, odczyt HDF5, strumień mocy, widmo portu | Diagnostyka adaptera; bez wymuszania bilansu |
| `solvers/source_work.py` | Lokalne pary U/I, kontrola indeksów i sumowania, praca źródła | Pasywna diagnostyka siatki; bez korekty portu |
| `solvers/native_io.py` | Limit UCRT i sprawdzenie równoczesnego otwierania plików sond | Obsługa procesu Windows; bez zmian modelu |
| `app/` | Formularz Tk/ttk, podgląd Matplotlib, zapis parametrów i eksport | Sterowanie geometrią |
| `visualization/` | Rysunki, wykresy CSV/NPZ i HTML | Bez wywołań solvera |
| `visualization/report_data.py` | Odczyt wyników, wybór ukończonego przebiegu, opcjonalna DFT portu | Bez importu natywnego openEMS |
| `visualization/report.py`, `report_assets.py` | Samodzielny HTML, wykresy, lokalne sterowanie i diagnostyka | Bez sieci, API, zmiany danych i automatycznego zatwierdzania fizyki |
| `cli.py` | Polecenia i proces potomny solvera | Log, przerwanie i stan przebiegu |

Konfiguracja przechodzi przez generator anteny do geometrii, następnie przez
adapter do zapisanych danych. Wizualizacja odczytuje pliki. Obecny generator
zwraca zwykły obiekt Geometry; dodanie modelu wymaga generatora, schematu
i wpisu w rejestrze, bez specjalnych warunków w rdzeniu.
Edytor buduje pola z `dimensions_m`; wczytanie innego modelu odtwarza
formularz wymiarów i zmienia etykiety. Biquad używa istniejącego portu +x
oraz płyty PEC, bez nowego adaptera solvera i bez zmian siatki.

## Przebiegi

`geometry` zapisuje wyłącznie geometrię. `prepare` używa natywnych bibliotek
do utworzenia XML, ale nie wywołuje Run. `run` wykonuje FDTD, postprocessing
i raport. Biblioteki natywne są importowane dopiero w procesie potomnym
uruchomionym tym samym interpreterem, co polecenie główne.
Opcjonalne `solver.power_diagnostics` dodaje pasywne monitory i po solve
zapisuje diagnostykę oraz paczkę ZIP. Zarówno zwykłe, jak i diagnostyczne
symulacje tworzą raport i wykresy przed zamknięciem manifestu. Błąd raportu
zapisuje ostrzeżenie i nie zmienia udanego FDTD na `failed`.

Osobne `report` czyta wcześniejsze wyniki i zapisuje nowy HTML poza katalogiem
przebiegu (`outcomes/reports`). Nie zmienia starych manifestów ani raportów.
`--latest` wybiera tylko `simulation/completed`, na podstawie czasu manifestu.
Podanie pliku JSON wariantu wybiera wyniki zgodnej geometrii, modelu
fizycznego i częstotliwości. Preferowane są identyczne ustawienia symulacji
i solvera; wybór innych ustawień jest jawnie komunikowany. Katalogowanie
czyta zapisane konfiguracje, dzięki czemu obsługuje również starsze przebiegi.
Widmo pochodzi z gęstego CSV, zwykłego CSV lub summary; przy pojedynczym
punkcie i dostępnych surowych sondach portu może użyć ich DFT. To czysty
odczyt NumPy z `solvers/power.py`, bez przygotowania modelu i bez Run.
CSS/JS są częścią modułu Python, więc trafiają również do `source.zip`.

Każdy przebieg otrzymuje unikalny katalog. Jego nazwa zaczyna się od nazwy
pliku wariantu, dalej zawiera czas UTC
i losowy identyfikator. Manifest dodaje opcjonalne `variant_name` oraz
`geometry_sha256`; stare manifesty v2 pozostają obsługiwane.
Katalog zawiera rozwiązaną konfigurację, schematy, archiwum kodu źródłowego,
wersję Git (jeśli jest dostępna), geometrię
i manifest. Kopia konfiguracji nie zależy od późniejszych zmian w edytorze.
Nie zapisujemy środowiska procesu, danych kont ani całego katalogu roboczego.

Proces główny przechwytuje log, kod wyjścia i Ctrl+C. Po zakończeniu zapisuje
stan oraz skróty plików. Zakończone przebiegi nie są używane ponownie do solve.
Przed Run pracownik liczy sondy w XML, podnosi w razie potrzeby limit strumieni
UCRT i sprawdza otwarcie odpowiedniej liczby strumieni C. Wynik zapisuje
w manifest.solver.native_io. Natywny komunikat `Can't open file:` powoduje
natychmiastowe zakończenie pracownika i status failed; częściowe pliki zostają.
Wersja 2 rozdziela etap (`geometry`, `openems_input`, `simulation`), stan
wykonania i status fizycznej walidacji. `completed` nie oznacza `passed`.

## Stan i platforma

M1 i podstawowy edytor są zaimplementowane. Adapter M2 jest eksperymentalny;
nie wykonano tutaj obliczenia natywnym openEMS. Na Windowsie użytkownika
potwierdzono import CPython 3.14.0/openEMS 0.37.0rc3/CSXCAD 0.7.0rc3.
Użytkownik ukończył FDTD i kontrolę 450 lokalnych par sond na Windowsie;
poprawka UCRT działa. Lokalna praca źródła i strumień zewnętrzny różnią się
o 0,102%, co wyjaśnia niemal cały pozorny deficyt 12,15% względem starego U·I.
Wariant aligned_feed wykonano natywnie: 450 dodatnich lokalnych wkładów,
praca 0,949145539 W i strumień zewnętrzny 0,948187885 W. Poprawka granic działa;
pomiar pojedynczego U·I nadal różni się od pracy o 5,085% odniesienia portu.
Przypadek referencyjny, definicja/pomiar portu i zbieżność pozostają otwarte.
Mapy E/H i prądy wymagają dalszej implementacji; adapter odrzuca ich żądanie.

CPU Ryzen 7 7800X3D, RAM 32 GB, Windows 11. Instrukcje używają CMD i `.venv`.
Nie wymagamy WSL, uv ani GPU. Pole `threads=0` pozostawia wybór openEMS;
`max_cells` ogranicza rozmiar siatki, ale nie jest gwarancją zużycia RAM.
Nie wykonujemy benchmarków ani prognoz czasów obliczeń.

## Interakcja edytora

Pola są kontrolkami Tk/ttk poza obszarem Matplotlib. Zmiana tekstu wyłącznie
oznacza formularz jako niezastosowany. Enter/Zastosuj waliduje komplet pól
i atomowo zastępuje poprawny model. Tab lub utrata fokusu nie uruchamia apply.
EditorState zachowuje pełną precyzję nietkniętych wartości. Zmiana samej
częstotliwości nie przebudowuje geometrii; zatwierdzenie bez zmian nie rysuje
ponownie wykresu. Eksport PNG używa FigureCanvasAgg bez dodatkowego okna.
