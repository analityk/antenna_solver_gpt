# Historia większych zmian

Historia opisuje skutki decyzji, nie zastępuje historii commitów Git.

## 2026-09-28 — M0: wydzielenie projektu Antenna Lab

**Powód:** użytkownik wymaga osobnego, rozwijalnego projektu GitHub,
instrukcji `AGENTS.md`, wymagań `goal.md` i oceny większych zmian w tym pliku.

**Zmiana:** przygotowano strukturę rdzenia, modeli anten, adapterów solvera,
parametrów, wizualizacji, aplikacji i wyników. Dodano konfigurację Quadosa 8
przy dokładnie 1420 MHz, źródłowe wymiary, szkic konstrukcji geometrii oraz
kontrakt outcomes i schematy JSON. Zakres tej zmiany to fundament projektu.

**Wpływ na fizykę i wyniki:** nie wykonano nowej symulacji. Konfiguracja
startowa używa skali 2450/1420, z jawnym niepotwierdzonym założeniem
częstotliwości bazowej. Nie przeniesiono wyniku zysku double biquada na Quadosa.
Siatka reflektora, port idealny i brak baluna są jawnymi uproszczeniami.

**Wpływ na architekturę:** zależności NEC2++ mają pozostać w adapterze;
nowa antena ma dostarczać geometrię, a wizualizacja czytać wspólny format danych.
Nie powstał jeszcze wykonywalny symulator ani interfejs.

**Wpływ na zgodność i odtwarzalność:** pierwsza wersja schematów to 1.
Wymagany manifest zapisuje wersję kodu, solvera, konfigurację i listę artefaktów.
Brak wcześniejszych publicznych formatów do migracji.

**Sprawdzenie:** dane z rysunku zestawiono z A–H i wymiarami reflektora;
obliczono skalowanie i sumę długości gałęzi. Sprawdzono składnię JSON,
wymagane pola konfiguracji, zgodność wymiarów oraz lokalne odsyłacze i ścieżki.

**Ograniczenia i dalsza praca:** topologia opisana w dokumentacji wymaga
implementacji i kontroli numerycznej. Wygenerowane charakterystyki jeszcze
nie istnieją. Użytkownik utworzył puste repozytorium `analityk/quados_nec2-`
i udostępnił je do zapisu. Ten komplet plików tworzy jego fundament.

## 2026-09-28 — zawężenie zakresu: bez benchmarków

**Powód:** bezpośrednia instrukcja użytkownika podczas przygotowywania projektu.

**Zmiana:** usunięto benchmarki z planu i z zakresu aktualnej implementacji.
Nie dodano ich kodu ani nie uruchomiono obciążeń pomiarowych.

**Wpływ:** praca skupia się na wymaganiach i strukturze projektu. Parametry
komputera użytkownika pozostają informacją projektową, bez prognoz czasów
i bez obietnicy użycia wszystkich rdzeni lub GPU przez pojedyncze obliczenie.
Kontrola poprawności fizycznej przyszłych wyników nadal jest wymagana.

## Wzór kolejnego wpisu

- Data i krótka nazwa zmiany.
- Powód oraz powiązany cel lub problem.
- Co rzeczywiście zmieniono.
- Wpływ na fizykę i dotychczasowe wyniki.
- Wpływ na architekturę, formaty i odtwarzalność.
- Wykonane sprawdzenia i ich rezultat.
- Ograniczenia, migracje lub konieczność ponownego przeliczenia wyników.
