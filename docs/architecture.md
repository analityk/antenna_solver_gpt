# Architektura

## Granice modułów

Na początek jeden pakiet Pythona `antenna_lab`. Solver numeryczny jest osobną
zależnością natywną, a nie implementacją równań Maxwella pisaną od zera.

| Moduł | Przyjmuje | Zwraca | Nie odpowiada za |
| --- | --- | --- | --- |
| `core` | Geometrię, parametry, porty, żądanie obliczeń | Wspólne obiekty danych i walidację | Nazwy anten i API solverów |
| `antennas` | Parametry konkretnej anteny | Geometrię w SI, porty, opis założeń | Wyniki elektromagnetyczne |
| `solvers` | Geometrię, częstotliwości, siatki próbek | Prądy, impedancje, pola, komunikaty | Parametryzację Quadosa i GUI |
| `visualization` | Zapisane wyniki, fazę, zakres widoku | Wykresy, mapy, animacje | Ponowne rozwiązywanie anteny |
| `app` | Wybory użytkownika | Zadania obliczeń i podgląd wyników | Alternatywne implementacje fizyki |

Przepływ: konfiguracja → generator anteny → geometria → adapter solvera
→ zapis outcomes → wizualizacja. Interfejs steruje przepływem, ale rdzeń
pozostaje użyteczny bez przeglądarki.

## Podstawowe kontrakty

- `AntennaModel`: identyfikator, wersja generatora, schemat parametrów oraz
  operacja budowania geometrii. Bez wymaganego dziedziczenia z klas solvera.
- `Geometry`: węzły, przewody, połączenia, porty, materiały, oznaczenia części
  anteny i przybliżenia. Geometria idealna oddzielona od dyskretyzacji solvera.
- `SolverAdapter`: deklaruje obsługiwane możliwości; brak funkcji jest jawnym
  błędem, a nie pustym wynikiem udającym powodzenie.
- `RunRequest`: kopia parametrów, częstotliwości, normalizacja, zakres danych
  i ustawienia dyskretyzacji. Po rozpoczęciu przebiegu nie jest modyfikowany.
- `RunResult`: odsyłacze do danych, metryki, stan kontroli i pochodzenie.

Typy i nazwy metod zostaną ustalone podczas M1. M0 nie wprowadza pozornego
API z funkcjami zwracającymi atrapy danych.

## Pierwszy adapter

Pierwszym i obecnie jedynym wybranym solverem jest openEMS. NEC2++ / PyNEC
nie będzie implementowany. Biblioteki openEMS i CSXCAD pozostają w adapterze;
rdzeń oraz generatory anten nie zależą bezpośrednio od ich API.

Przed implementacją trzeba przenieść wcześniejsze kontrakty M0 na model
openEMS: geometrię materiałów, siatkę FDTD, port, granice obszaru, odczyt
prądów i pól oraz odtwarzalne pliki wejściowe. Lista nieaktywnych kontraktów
NEC jest w `goal.md`. Samo zastąpienie nazwy biblioteki nie kończy tej migracji.

## Lokalna praca i zasoby

Docelowe obliczenia mają działać na komputerze użytkownika. Zgłoszona
konfiguracja: Ryzen 7 7800X3D, 32 GB RAM, GeForce GTX 1660 Ti 6 GB.
System docelowy: natywny Windows 11. Użytkownik posiada Git, Python i VS Code.
Stosujemy CMD lub PowerShell oraz projektowe `.venv` z pip. Użytkownik potwierdził
CPython 3.14.0, 64-bit AMD64. Nie przenosimy do projektu całej listy pakietów
z globalnego środowiska użytkownika. WSL i uv nie są wymagane.

Instrukcja instalacji korzysta z oficjalnej paczki openEMS 0.37.0-rc3 MSVC
z modułami cp314 dla Windows x64. To wydanie RC. Podana lokalizacja paczki:
`C:\dev\openems\openEMS`. Użytkownik potwierdził import openEMS 0.37.0rc3
i CSXCAD w CMD dnia 2026-09-28. Adapter i obliczeniowy przypadek kontrolny
pozostają do implementacji oraz sprawdzenia. Instrukcja: [Windows 11](windows-setup.md).

Pierwszy adapter używa CPU. Obsługa GPU i dobór optymalnej liczby procesów
są poza bieżącym zakresem. Przyszłe serie obliczeń powinny mieć ograniczenie
współbieżności i możliwość anulowania, bez założenia, że 16 wątków sprzętowych
oznacza 16 niezależnych zadań naraz. Benchmarki nie są częścią projektu na M0.

## Zapis i wersjonowanie

Git przechowuje kod, wymagania, konfiguracje i schematy. Duże outcomes są
lokalnymi artefaktami przebiegów. Każdy przebieg ma manifest ze skrótami plików,
wersją solvera i rewizją kodu. Zmiana schematu nie może po cichu zmieniać
interpretacji już zapisanych pól, osi lub fazy.
