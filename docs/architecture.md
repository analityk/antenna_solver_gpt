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

NEC2++ / PyNEC jest bazą pierwszego modelu drutowego. Wersja zależności ma być
przypięta podczas uruchomienia adaptera; działanie konkretnego builda musi
zostać potwierdzone. Istniejący eksperyment używał PyNEC 2.3.4, ale nie stanowi
to testu integracji z tym nowym projektem. FR w tym wrapperze przyjmuje MHz;
na zewnątrz adaptera zawsze używamy Hz i sprawdzamy częstotliwość w wyniku.

openEMS jest możliwym przyszłym adapterem dla pełniejszej geometrii i
dielektryków, bez zobowiązania do jego implementacji w pierwszej wersji.
Nie zakładamy, że wyniki dwóch metod są równoważne bez porównania modeli.

## Lokalna praca i zasoby

Docelowe obliczenia mają działać na komputerze użytkownika. Zgłoszona
konfiguracja: Ryzen 7 7800X3D, 32 GB RAM, GeForce GTX 1660 Ti 6 GB.
System docelowy: natywny Windows 11. Użytkownik posiada Git, Python i VS Code.
Stosujemy PowerShell oraz projektowe `.venv` z pip. Dokładna wersja Pythona
i jego architektura wymagają potwierdzenia; nie przenosimy do projektu całej
listy pakietów z globalnego środowiska użytkownika. WSL i uv nie są wymagane.

Instalacja adaptera na Windowsie jest otwartym zadaniem M2. Wydanie PyNEC
2.3.4 na PyPI nie udostępnia wheel dla Windowsa. Sprawdzony upstream
`PyNEC/setup.py` zawiera flagi `-fPIC` i `-lstdc++`, więc sama obecność MSVC
nie dowodzi, że standardowa kompilacja pakietu się powiedzie. Sposób budowania
i dystrybucji trzeba potwierdzić na Windowsie i przypiąć do wersji kodu.
Instrukcja podstawowego środowiska: [Windows 11](windows-setup.md).

Pierwszy adapter używa CPU. Obsługa GPU i dobór optymalnej liczby procesów
są poza bieżącym zakresem. Przyszłe serie obliczeń powinny mieć ograniczenie
współbieżności i możliwość anulowania, bez założenia, że 16 wątków sprzętowych
oznacza 16 niezależnych zadań naraz. Benchmarki nie są częścią projektu na M0.

## Zapis i wersjonowanie

Git przechowuje kod, wymagania, konfiguracje i schematy. Duże outcomes są
lokalnymi artefaktami przebiegów. Każdy przebieg ma manifest ze skrótami plików,
wersją solvera i rewizją kodu. Zmiana schematu nie może po cichu zmieniać
interpretacji już zapisanych pól, osi lub fazy.
