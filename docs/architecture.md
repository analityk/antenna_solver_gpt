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
| `antennas/` | Rejestr modeli i deterministyczny generator Quados8 | Bez importu openEMS |
| `solvers/mesh.py` | Niejednorodna siatka kartezjańska, PML, kontrola limitu | Bez zmian wymiarów anteny |
| `solvers/feed.py` | Granice portu i audyt pokrycia krawędzi przez box wymuszenia | Korekta zaokrągleń w adapterze; bez zmiany siatki |
| `solvers/openems.py` | Materiały, port, FDTD XML, impedancja i NF2FF | Główny adapter natywnego API |
| `solvers/power.py` | Pasywne sondy, odczyt HDF5, strumień mocy, widmo portu | Diagnostyka adaptera; bez wymuszania bilansu |
| `solvers/source_work.py` | Lokalne pary U/I, kontrola indeksów i sumowania, praca źródła | Pasywna diagnostyka siatki; bez korekty portu |
| `solvers/native_io.py` | Limit UCRT i sprawdzenie równoczesnego otwierania plików sond | Obsługa procesu Windows; bez zmian modelu |
| `app/` | Formularz Tk/ttk, podgląd Matplotlib, zapis parametrów i eksport | Sterowanie geometrią |
| `visualization/` | Rysunki, wykresy CSV/NPZ i HTML | Bez wywołań solvera |
| `cli.py` | Polecenia i proces potomny solvera | Log, przerwanie i stan przebiegu |

Konfiguracja przechodzi przez generator anteny do geometrii, następnie przez
adapter do zapisanych danych. Wizualizacja odczytuje pliki. Obecny generator
zwraca zwykły obiekt Geometry; dodanie modelu wymaga generatora, schematu
i wpisu w rejestrze, bez specjalnych warunków w rdzeniu.

## Przebiegi

`geometry` zapisuje wyłącznie geometrię. `prepare` używa natywnych bibliotek
do utworzenia XML, ale nie wywołuje Run. `run` wykonuje FDTD, postprocessing
i raport. Biblioteki natywne są importowane dopiero w procesie potomnym
uruchomionym tym samym interpreterem, co polecenie główne.
Opcjonalne `solver.power_diagnostics` dodaje pasywne monitory i po solve
zapisuje diagnostykę oraz paczkę ZIP, pomijając raport i wykresy wynikowe.

Każdy przebieg otrzymuje unikalny katalog. Zawiera rozwiązaną konfigurację,
schematy, archiwum kodu źródłowego, wersję Git (jeśli jest dostępna), geometrię
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
Wariant aligned_feed poprawia wykrytą różnicę granic siatki i wymuszenia;
nie wykonano go jeszcze natywnie. Przypadek referencyjny, kontrola portu
i sprawdzenie zbieżności pozostają otwarte.
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
