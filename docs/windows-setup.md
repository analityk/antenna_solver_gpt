# Środowisko lokalne — Windows 11 i openEMS

Projekt: `antenna_solver_gpt`. Stan: M0, przed implementacją modelu i adaptera.
Użytkownik ma Git, VS Code oraz CPython 3.14.0, 64-bit AMD64.
Poniższe polecenia są przeznaczone dla PowerShella.

## 1. Paczka openEMS

Używamy [oficjalnej paczki openEMS 0.37.0-rc3 MSVC dla Windows x64](https://github.com/thliebig/openEMS-Project/releases/tag/v0.37.0-rc3).
To wydanie RC z gotowymi modułami Pythona cp314.
Podana przez użytkownika lokalizacja to `C:\dev\openems\openEMS`.
W tym katalogu powinny znajdować się `openEMS.exe`, `CSXCAD.dll`
oraz podkatalog `python` z plikami `.whl`.

## 2. Folder projektu

Jeśli lokalna kopia jeszcze nie istnieje, w wybranym katalogu roboczym:

```powershell
git clone https://github.com/analityk/antenna_solver_gpt.git
Set-Location antenna_solver_gpt
```

Jeśli kopia istnieje, otwórz jej katalog w VS Code i użyj terminala w tym katalogu.
Nazwa lokalnego folderu jest niezależna od nazwy repozytorium na GitHubie.
W istniejącej kopii zaktualizuj adres zdalny po zmianie nazwy:

```powershell
git remote set-url origin https://github.com/analityk/antenna_solver_gpt.git
```

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

To zestaw do uruchomienia silnika. Pełny plik zależności aplikacji i przypięte
wersje powstaną przy implementacji. Nie kopiujemy globalnego `pip list`.

## 5. Lokalizacja bibliotek DLL

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

Oczekiwany wynik to wersja openEMS i `CSXCAD: OK`. Wynik tego polecenia
na komputerze użytkownika nie został jeszcze otrzymany. Potwierdzenie importu
nie jest potwierdzeniem poprawności modelu anteny; kontrola fizyczna należy do M2.
Nie wykonujemy benchmarków.

## Źródła

- [Python 3.14 — venv](https://docs.python.org/3.14/library/venv.html)
- [openEMS 0.37.0-rc3 — wydanie Windows](https://github.com/thliebig/openEMS-Project/releases/tag/v0.37.0-rc3)
- [Instrukcja Python dołączona do tego wydania](https://github.com/thliebig/openEMS-Project/blob/v0.37.0-rc3/.github/windows-package/python/README.txt),
  sprawdzony blob `1a60d93b2a61d182f66f7d7a50b3f7227cec6031`.
