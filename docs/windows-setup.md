# Środowisko lokalne — Windows 11 i openEMS

Projekt: `antenna_solver_gpt`. Stan: M1 gotowe, adapter M2 do natywnej walidacji.
Użytkownik ma Git, VS Code oraz CPython 3.14.0, 64-bit AMD64.
Instalację i import potwierdzono w CMD dnia 2026-09-28 na podstawie logu
przesłanego przez użytkownika. Polecenia Pythona i Git działają także
w PowerShellu; różnice składni powłok oznaczono poniżej.

## 1. Paczka openEMS

Używamy [oficjalnej paczki openEMS 0.37.0-rc3 MSVC dla Windows x64](https://github.com/thliebig/openEMS-Project/releases/tag/v0.37.0-rc3).
To wydanie RC z gotowymi modułami Pythona cp314.
Podana przez użytkownika lokalizacja to `C:\dev\openems\openEMS`.
W tym katalogu powinny znajdować się `openEMS.exe`, `CSXCAD.dll`
oraz podkatalog `python` z plikami `.whl`.

## 2. Folder projektu

Jeśli lokalna kopia jeszcze nie istnieje, w wybranym katalogu nadrzędnym:

```powershell
git clone https://github.com/analityk/antenna_solver_gpt.git
cd antenna_solver_gpt
```

`git clone` tworzy nowy podfolder; po pobraniu trzeba do niego wejść.
Potwierdzona lokalna kopia użytkownika znajduje się w
`C:\dev\antenna_solver_gpt\antenna_solver_gpt`. W CMD przechodzi się do niej tak:

```bat
cd /d C:\dev\antenna_solver_gpt\antenna_solver_gpt
```

Jeśli kopia istnieje, otwórz jej katalog w VS Code i użyj terminala w tym katalogu.
Nazwa lokalnego folderu jest niezależna od nazwy repozytorium na GitHubie.
W kopii pobranej ze starego adresu zaktualizuj adres zdalny po zmianie nazwy:

```powershell
git remote set-url origin https://github.com/analityk/antenna_solver_gpt.git
```

Klonowanie z aktualnego adresu już ustawia właściwy `origin`.

## 3. Co oznacza .venv

`.venv` jest katalogiem z osobnym środowiskiem Pythona dla tego projektu.
Powstaje na bazie zainstalowanego Pythona i ma własny zestaw pakietów.
Instalacja bibliotek w tym środowisku nie zmienia globalnej listy pakietów
użytkownika. W Windows interpreter środowiska znajduje się pod
`.venv\Scripts\python.exe`, a biblioteki w `.venv\Lib\site-packages`.

Środowisko jest lokalne i pomijane przez Git. Nie umieszczaj w nim kodu projektu.
Gdy zmieni się ścieżka lokalnego folderu projektu, środowisko należy odtworzyć
w nowym miejscu. Sama zmiana nazwy repozytorium na GitHubie go nie przenosi.

## 4. Utworzenie środowiska i instalacja modułów

W katalogu projektu:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install numpy h5py matplotlib
.\.venv\Scripts\python.exe -m pip install --no-index --find-links "C:\dev\openems\openEMS\python" openEMS
```

Ostatnie polecenie instaluje openEMS i CSXCAD z tej samej paczki co biblioteki
DLL. `pip` wybiera właściwe moduły dla interpretera. Zależności instalujemy
wcześniej, ponieważ `--no-index` ogranicza ostatni krok do plików lokalnych.
Polecenia z pełną ścieżką do `python.exe` działają bez aktywowania środowiska.
W VS Code wybierz `Python: Select Interpreter` → `.venv\Scripts\python.exe`.

To zestaw do uruchomienia silnika. Zależności aplikacji określa pyproject.toml;
instaluje je polecenie z sekcji 7. Nie kopiujemy globalnego pip list.

## 5. Lokalizacja bibliotek DLL

W CMD:

```bat
set "CSXCAD_INSTALL_PATH=C:\dev\openems\openEMS"
setx CSXCAD_INSTALL_PATH "C:\dev\openems\openEMS"
```

Albo w PowerShellu:

```powershell
$env:CSXCAD_INSTALL_PATH = "C:\dev\openems\openEMS"
setx CSXCAD_INSTALL_PATH "C:\dev\openems\openEMS"
```

Pierwsze polecenie ustawia zmienną w bieżącym terminalu. Drugie zapisuje ją
dla przyszłych sesji użytkownika. Uruchom ponownie VS Code, aby nowe procesy
uruchamiane z edytora odziedziczyły zapisane ustawienie.
Ścieżka ma wskazywać katalog z `CSXCAD.dll`, a nie jego podkatalog `python`.

## 6. Sprawdzenie importu

```powershell
.\.venv\Scripts\python.exe -c "import openEMS, CSXCAD; print('openEMS:', openEMS.__version__); print('CSXCAD: OK')"
```

Użytkownik otrzymał w CMD 2026-09-28:

```text
openEMS: 0.37.0rc3
CSXCAD: OK
```

Potwierdza to import modułów wraz z wymaganymi przy imporcie bibliotekami
natywnymi w projektowym `.venv`. Nie wykonano jeszcze obliczeniowego przypadku
kontrolnego ani symulacji Quadosa. Kontrola fizyczna należy do M2.
Nie wykonujemy benchmarków.

## 7. Instalacja i uruchomienie programu

W CMD, w już utworzonym środowisku:

```bat
cd /d C:\dev\antenna_solver_gpt\antenna_solver_gpt
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m antenna_lab preview
```

Nie trzeba ponownie instalować openEMS ani tworzyć .venv. Edytor powinien
pokazać wymiary i dwa rzuty anteny. Zmiana C/D przesuwa sekcje, zachowując E.
Można zapisać wariant JSON i eksport geometrii.

Po zamknięciu okna przygotuj wejście solvera:

```bat
.\.venv\Scripts\python.exe -m antenna_lab prepare
```

Oczekiwany komunikat: `Wejście openEMS przygotowane.`, następnie ścieżka
katalogu z `openems\model.xml`, geometrią i logiem. To pierwszy krok kontroli
integracji na Windowsie; nie uruchamia FDTD. W razie błędu zachowaj komunikat
i `solver.log`. Udane przygotowanie nie zalicza fizycznej walidacji M2.

Polecenie uruchamiające właściwe obliczenie jest dostępne eksperymentalnie:

```bat
.\.venv\Scripts\python.exe -m antenna_lab run
```

Ctrl+C przerywa przebieg. Nie uruchamiaj kilku obliczeń naraz na tym etapie.
Zapisany raport i wyniki będą oznaczone jako unverified; nie wykonano jeszcze
kontroli dipola ani zbieżności Quadosa. Opis modelu: [openEMS](openems-model.md).

## Potwierdzone środowisko

Wersje z logu instalacji i wyniku importu przesłanych przez użytkownika:

| Składnik | Wersja |
| --- | --- |
| CPython | 3.14.0, 64-bit AMD64 |
| openEMS | 0.37.0rc3 |
| CSXCAD | 0.7.0rc3 |
| pip | 26.2.1 |
| NumPy | 2.5.3 |
| h5py | 3.16.0 |
| Matplotlib | 3.11.2 |

To zapis zaobserwowanej konfiguracji, a nie pełny plik z zamrożonymi
zależnościami aplikacji. Instalacja binarna openEMS znajduje się poza repozytorium;
moduły Pythona zainstalowano w `.venv` lokalnej kopii projektu.

## Źródła

- [Python 3.14 — venv](https://docs.python.org/3.14/library/venv.html)
- [openEMS 0.37.0-rc3 — wydanie Windows](https://github.com/thliebig/openEMS-Project/releases/tag/v0.37.0-rc3)
- [Instrukcja Python dołączona do tego wydania](https://github.com/thliebig/openEMS-Project/blob/v0.37.0-rc3/.github/windows-package/python/README.txt),
  sprawdzony blob `1a60d93b2a61d182f66f7d7a50b3f7227cec6031`.
