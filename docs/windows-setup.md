# Środowisko lokalne — Windows 11

Stan: instrukcja przygotowania podstawowego środowiska. Repozytorium jest
na etapie M0; aplikacja i natywny adapter solvera nie są jeszcze gotowe.
Użytkownik ma już Git, Python i VS Code. Korzystamy z PowerShella.

## 1. Odczyt interpretera

```powershell
py -c "import sys, struct; print(sys.version); print('bits:', struct.calcsize('P') * 8); print(sys.executable)"
py -m pip --version
```

Pierwsze polecenie pokazuje dokładną wersję i architekturę interpretera,
drugie przypisany do niego pip. Samo `pip list` nie określa tych danych.
Docelowy solver wymaga 64-bitowego Pythona. Metadane PyNEC 2.3.4 wymagają
Pythona co najmniej 3.11; zgodność konkretnej wersji z naszym pakietem Windows
musi zostać potwierdzona. Python 3.12 pozostaje kandydatem, nie powodem do
usuwania lub podmieniania istniejącego interpretera.

## 2. Kopia repozytorium

Jeśli projekt nie został jeszcze pobrany, w wybranym katalogu roboczym:

```powershell
git clone https://github.com/analityk/quados_nec2-.git
Set-Location quados_nec2-
```

Jeśli już istnieje, otwórz jego katalog w VS Code. Kolejne polecenia wykonuj
w katalogu repozytorium, po ustaleniu właściwego interpretera.

## 3. Oddzielne środowisko

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install numpy matplotlib pillow pytest jsonschema
```

Polecenia korzystają bezpośrednio z interpretera `.venv`; aktywacja skryptem
PowerShell nie jest potrzebna. W VS Code wybierz `Python: Select Interpreter`
i wskaż `.venv\Scripts\python.exe`.

To przygotowanie bibliotek pomocniczych, bez solvera. Zestaw wersji nie jest
jeszcze zamrożony; plik zależności projektu powstanie wraz z implementacją.
Pillow obecne w globalnej instalacji nie jest automatycznie obecne w `.venv`.
Nie trzeba kopiować pozostałych globalnych pakietów do tego projektu.

## 4. Natywny solver — zadanie integracyjne

PyNEC 2.3.4 ma gotowe pakiety dla Linuxa i macOS ARM64, ale wydanie sprawdzone
2026-09-28 nie ma wheel Windows. Metadane mówią o Pythonie >= 3.11.
Obecny `setup.py` upstream ma flagi GCC `-fPIC` i `-lstdc++`; jego obecność
w źródłach nie stanowi potwierdzenia kompilacji przez MSVC.

Do samodzielnego budowania natywnego kodu przewidujemy Microsoft C++ Build
Tools z MSVC i Windows SDK, a zależnie od ścieżki również CMake oraz SWIG.
Nie jest to jeszcze sprawdzona recepta instalacji PyNEC. Celem integracji M2
jest dostarczenie powtarzalnej ścieżki instalacji dla ustalonego Pythona.
Gotowy pakiet binarny powinien ograniczyć wymagania narzędziowe użytkownika.

Potwierdzenie samego importu nie kończy M2: po nim potrzebny jest przypadek
kontrolny solvera. Nie prowadzimy benchmarków.

## Źródła

- [Python venv](https://docs.python.org/3/library/venv.html)
- [PyNEC 2.3.4 — pliki i metadane](https://pypi.org/project/PyNEC/2.3.4/)
- [Upstream setup.py](https://github.com/tmolteno/python-necpp/blob/master/PyNEC/setup.py),
  sprawdzony blob `e6b489c0c467fb6d5fe16054eabe9c822a2831c3`.
- [Upstream pyproject.toml](https://github.com/tmolteno/python-necpp/blob/master/PyNEC/pyproject.toml),
  sprawdzony blob `841e02ee1fd32fdef6e04c1ef060dfad2bb60856`.
