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
| `solvers/openems.py` | Materiały, port, FDTD XML, impedancja i NF2FF | Jedyne miejsce zależne od natywnego API |
| `app/` | Edytor Matplotlib, zapis wariantów i eksport | Sterowanie geometrią |
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

Każdy przebieg otrzymuje unikalny katalog. Zawiera rozwiązaną konfigurację,
schematy, archiwum kodu źródłowego, wersję Git (jeśli jest dostępna), geometrię
i manifest. Kopia konfiguracji nie zależy od późniejszych zmian w edytorze.
Nie zapisujemy środowiska procesu, danych kont ani całego katalogu roboczego.

Proces główny przechwytuje log, kod wyjścia i Ctrl+C. Po zakończeniu zapisuje
stan oraz skróty plików. Zakończone przebiegi nie są używane ponownie do solve.
Wersja 2 rozdziela etap (`geometry`, `openems_input`, `simulation`), stan
wykonania i status fizycznej walidacji. `completed` nie oznacza `passed`.

## Stan i platforma

M1 i podstawowy edytor są zaimplementowane. Adapter M2 jest eksperymentalny;
nie wykonano tutaj obliczenia natywnym openEMS. Na Windowsie użytkownika
potwierdzono import CPython 3.14.0/openEMS 0.37.0rc3/CSXCAD 0.7.0rc3.
Następny krok to `prepare`, potem przypadek kontrolny i zbieżność.
Mapy E/H i prądy wymagają dalszej implementacji; adapter odrzuca ich żądanie.

CPU Ryzen 7 7800X3D, RAM 32 GB, Windows 11. Instrukcje używają CMD i `.venv`.
Nie wymagamy WSL, uv ani GPU. Pole `threads=0` pozostawia wybór openEMS;
`max_cells` ogranicza rozmiar siatki, ale nie jest gwarancją zużycia RAM.
Nie wykonujemy benchmarków ani prognoz czasów obliczeń.
