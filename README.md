# antenna_solver_gpt

Projekt do parametrycznego modelowania i symulacji anten. Pierwszy model:
**Quados 8 przy 1420 MHz**. Docelowo wspólny rdzeń, różne generatory anten,
wymienne adaptery solverów i odtwarzalne wyniki.

**Stan: M0 — fundament projektu.** Są wymagania, parametry i kontrakt wyników.
Wybrany silnik obliczeniowy: **openEMS**, natywnie na Windows 11.
Generator geometrii, adapter openEMS i aplikacja nie są jeszcze zaimplementowane.
W tym repozytorium nie ma jeszcze wyników symulacji Quadosa.

Decyzja o openEMS zastępuje wcześniejszy plan użycia NEC2++.
Szczegółowe kontrakty M0 związane z NEC wymagają migracji przed implementacją;
ich status opisuje [goal.md](goal.md). Nie są gotowym wejściem openEMS.

## Mapa projektu

| Ścieżka | Odpowiedzialność |
| --- | --- |
| `AGENTS.md` | Instrukcje dla kolejnych prac nad projektem |
| `goal.md` | Zakres, model fizyczny, wymiary, wyniki i kryteria zakończenia |
| `history.md` | Większe zmiany i ocena ich wpływu |
| `src/antenna_lab/core/` | Wspólne pojęcia geometrii, portu i wyniku |
| `src/antenna_lab/antennas/` | Modele anten, początkowo Quados 8 |
| `src/antenna_lab/solvers/` | Integracja z openEMS |
| `src/antenna_lab/visualization/` | Mapy, charakterystyki i animacje z danych |
| `src/antenna_lab/app/` | Docelowy lokalny interfejs i sterowanie zadaniami |
| `parameters/` | Jawne konfiguracje eksperymentów i dane źródłowe |
| `outcomes/` | Kontrakt katalogu wyników; właściwe przebiegi pomijane przez Git |
| `schemas/` | Schematy JSON konfiguracji i manifestu wyników |
| `docs/` | Architektura, geometria, założenia i plan implementacji |

## Dokumenty startowe

- [Cel i wymagania](goal.md)
- [Historia decyzji](history.md)
- [Architektura](docs/architecture.md)
- [Konstrukcja geometrii Quadosa](docs/quados8-geometry.md)
- [Kontrakt plików wynikowych](outcomes/README.md)
- [Kolejność implementacji](docs/roadmap.md)
- [Przygotowanie środowiska Windows 11](docs/windows-setup.md)
- [Źródła i pochodzenie danych](docs/sources.md)

Konfiguracja `parameters/quados8_1420mhz.json` zawiera jawne, przeskalowane
wymiary początkowe. Skalowanie z 2450 MHz jest założeniem roboczym i nie
oznacza, że antena została dostrojona lub zweryfikowana przy 1420 MHz.

Repozytorium: [analityk/antenna_solver_gpt](https://github.com/analityk/antenna_solver_gpt).
Nazwa pakietu `antenna_lab` pozostaje ogólna, żeby kolejne anteny korzystały
z tego samego rdzenia. Kod i dokumentacja mają być rozwijane w tym repozytorium.
