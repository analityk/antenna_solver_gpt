# Raport stanu i przekazania projektu — migracja

**Data przeglądu:** 2026-10-21 (Europe/Warsaw)  
**Repozytorium:** `analityk/antenna_solver_gpt`  
**Gałąź:** `main`  
**Punkt odniesienia przed dodaniem raportu:** `76d8e51bb3fd291386c88db45f4d7052b916b04d`  
**Status projektu:** rozwijany; implementacje częściowe i niezweryfikowane fizycznie należy odróżniać od zakończonych checkpointów kodu.

## Streszczenie

Projekt `antenna_lab` rozpoczął się od parametrycznego modelowania anten (Quados 8 i biquad przy 1420 MHz) z wykorzystaniem natywnego openEMS na Windows 11. Ten tor nadal istnieje, ale **aktualny ciężar rozwoju przeniósł się na analizę PCB**, w szczególności szybki, przybliżony solver `FAST / reduced quasi-TEM`.

Kluczową decyzją z 2026-10-21 jest **EasyEDA source-first**: oryginalny projekt PCB dostarcza semantyki linii, łuków, sieci, warstw, przelotek i komponentów; eksporty Gerber/Excellon są opcjonalnym materiałem do weryfikacji produkcyjnej, nie nadrzędnym źródłem topologii. Parser EasyEDA (PCB-015D0) oraz częściowa ścieżka source-only do modelu FAST (PCB-015D1) zostały opublikowane. Na syntetycznym, kompletnym projekcie source-only solver wykonał obliczenie bez Gerberów. **Rzeczywista serpentyna nie ma jeszcze wiarygodnego wyniku FAST**: najpierw brakuje geometrii footprintu komponentów CSRC/R1, a później blokują niezaimplementowany model Arc TL i sprzężenia mikropaskowe.

Przegląd opiera się na treści repozytorium i zapisanych wynikach wcześniejszych sprawdzeń; **podczas tworzenia niniejszego raportu nie uruchamiano testów, obliczeń ani benchmarków**.

## 1. Architektura i dwa tory obliczeniowe

- Jeden pakiet Pythona `antenna_lab`, rozdzielający konfigurację i geometrię, modele anten, adaptery solverów, zapis wyników i wizualizację. Rdzeń nie ma zależeć od konkretnej anteny, openEMS ani GUI.
- **Antena / full-wave:** generatory Quados 8 i biquad; adapter openEMS, FDTD, siatka/PML, diagnostyka źródła i mocy, impedancja, pole dalekie, przekroje E/H, raport HTML offline. M1 (generator, edytor, eksport i walidacja geometrii) jest zaimplementowany. Integracja obliczeniowa i jej walidacja fizyczna nie są zamknięte.
- **PCB / FAST:** odrębny solver `antenna_lab.pcb.reduced_control`, bez uruchamiania openEMS, 3-D FDTD i PML. Korzysta z grafu linii transmisyjnych oraz idealnych R/L/C. Jest szybkim modelem przybliżonym, **nie zamiennikiem zweryfikowanego full-wave**.
- Wyniki, parametry i manifesty mają zachowywać pochodzenie danych. Nie wolno utożsamiać statusu `completed` ze zweryfikowaną fizyką, korygować bilansu sztuczną renormalizacją ani przedstawiać braku danych jako zera.
- Platformą docelową jest natywny Windows 11, CPython 3.14 i projektowe `.venv`. Nie wymagamy WSL ani `uv`.

## 2. Co zostało zrobione w module PCB

### Wcześniejszy tor Gerber — PCB-015C0/C0.1

Importer zachowuje źródłowe trasy Line/Arc i ich provenance, a po projekcji geometrii weryfikuje ich własność i obecność w końcowej miedzi. Usunięto fałszywe `stroke_not_preserved`, które wynikało z porównania niezależnie skwantyzowanych reprezentacji. W lokalnym `test_spirala.zip` po tej poprawce następną rzeczywistą przeszkodą stał się jawny komunikat:

`Reduced source route Arc unsupported: top:route_000009 ...; no guessed TL arc.`

Tor Gerber-only nadal funkcjonuje jako fallback i diagnostyka, ale nie jest już priorytetem rozwoju.

### PCB-015D0 — parser EasyEDA source-first

Wdrożono parser ograniczonego profilu EasyEDA Pro: `DOCTYPE PCB 1.8`, `editorVersion 2.2.x`, rekordy m.in. `HEAD`, `LAYER`, `LAYER_PHYS`, `NET`, `LINE`, `ARC`, `VIA`, `PAD_NET`, `COMPONENT` i `ATTR`, wybrane `POLY/POUR/POURED`. Powstaje deterministyczny, niezależny semantic IR.

Zachowane są surowe rekordy, indeksy, identyfikatory, SHA256 pliku, nety, szerokości, kierunek/signed sweep łuku i informacja o stackupie. Konwersja jednostek następuje na granicy parsera: wartości PCB w mil (25,4 µm), materializowane ścieżki POURED w 10 mil (254 µm); `CANVAS` oznacza jednostki wyświetlania. Nie ma dopasowywania skali „na oko”. Nieobsługiwane istotne rekordy lub niejednoznaczne znaczenie danych muszą zgłaszać ograniczenie, a nie zostać milcząco zignorowane.

### PCB-015D1 — częściowy model canonical/source-only i integracja FAST

Zaimplementowano budowę obrazu fizycznego PCB bez rundy eksport/import Gerbera: obrys, ograniczony stackup top–jeden dielektryk–bottom, per-net miedź, materializowany POURED, wybrane RECT pads, VIA z jawną metalizacją, provenance linii/łuków, kontrolę zwarć i audyt geometrii.

Dostępne CLI:
```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-source gerbs\realpcb_microstrip\test_spirala.epcb --inspect-source
```

Tryb `--inspect-source` zapisuje m.in. `source_ir.json`, `source_model.json`, `import.json` i `summary.json`, także przy niekompletnym modelu i bez portu. To inspekcja, **nie zakończone obliczenie**. Dla kompletnego obsługiwanego projektu istnieje ścieżka `--easyeda-source ... --source-config ...` z jawnym opisem kontaktów. Brak Gerberów oznacza `manufacturing_validation=not_requested`, nie błąd.

D1 świadomie nie instancjonuje zewnętrznych footprintów COMPONENT. Jeśli komponent wymaga `FOOTPRINT/<hash>.efoo`, brak tego pliku jest zgłaszany jako brak zależności. Nawet znalezienie pliku wymaga przyszłego adaptera jego instancji. Nie są zgadywane brakujące kontakty, lead length ani pasożyty.

### Aktualna fizyka i jej granice

Reduced solver obsługuje wspierane, jednoznaczne odcinki microstrip (model Hammerstad–Jensen), idealne R/L/C, zweryfikowaną miedź bottom jako odniesienie, setback i określony model ground-PTH jako **idealne połączenie z masą**. Sieć jest częstotliwościowa i w przyjętym przybliżeniu bezstratna poza jawnymi rezystorami.

Nie uwzględniono m.in. strat laminatu i przewodnika, promieniowania, efektów 3-D zakrętów, pasożytów padów/obudów, dyspersji i ogólnego sprzężenia nieoddzielonych sekcji. **Pairwise coupled microstrip pozostaje niezaimplementowane**. Zbliżone równoległe odcinki i inne niewspierane topologie powodują fail-closed; nie generuje się pozornie poprawnego CSV przy pominiętej istotnej fizyce. Semantyka Arc jest przechowywana, lecz **nie ma modelu elektrycznej długości łuku w FAST**.

## 3. Wynik dla rzeczywistej serpentyny i aktualny blocker

Dla pliku `gerbs/realpcb_microstrip/test_spirala.epcb` dotychczas potwierdzono:

- 198 rekordów, w tym 6 LINE, 7 ARC i 2 VIA;
- 4 dostępne regiony miedzi;
- rozmiar płytki około 25,0000008 mm;
- dielektryk około 0,1999996 mm, `epsilon_r=4.5`;
- parser i budowa **częściowego** canonical layout zakończyły się powodzeniem.

SHA256 tego źródła zapisany w historii:
`e528f2a4ac1a1957a45e48806bc93da8b42e4af4a0f1da27cd84ce26714d0c4b`.

**Bezpośrednia przeszkoda:** CSRC/R1 odwołują się do nieobecnej geometrii footprintu `e8bf627583724bdebefbaa0be79b0d2f`. Nie ma bezpiecznej podstawy do odtworzenia tych padów i kontaktów przez zgadywanie lub rekonstrukcję z Gerbera. Nie wykonano pełnego solve serpentyny ani natywnego FDTD dla tego przypadku w opisanych checkpointach. Po rozwiązaniu footprintów trzeba jeszcze obsłużyć Arc TL oraz sprzężenia; obecny brak wyniku nie oznacza niepowodzenia parsera.

Na `main` dodano także 2026-10-21 w commicie `bc886490909bcac2914224c555bc597d8d469820` nowy zestaw `gerbs/test_psu/test_psu.epcb` i `gerbs/test_psu/psu.zip`. Jest to **nowy materiał wejściowy w repozytorium**, ale w przeczytanych raportach nie ma jeszcze potwierdzenia jego analizy ani wyniku FAST; nie należy domniemywać jego obsługi.

## 4. Najbliższy plan rozwoju

1. **Teraz — adapter zewnętrznych footprintów i kontaktów komponentów:** wczytywanie jawnie wskazanej geometrii `.efoo` dla CSRC/R1, przypisanie padów/pinów do netów i fizycznych conductorów, transformacje instancji, weryfikacja kontaktów i zwarć, jawne błędy brakujących danych. To obecny blocker realnego source.
2. **Następnie — PCB-015D3, semantyczny graf Line/Arc TL:** zachowanie topologii i liczenie długości łuków z promienia oraz signed sweep, bez zastępowania łuku cięciwą lub tessellacją z Gerbera.
3. **Dalej — PCB-015C, pairwise coupled microstrip:** fizyczny model sprzężonych linii (np. parametry macierzy C/C0 lub udokumentowany even/odd), właściwy podział sekcji i kontrola topologii; dla rzeczywistej serpentyny to podstawowy nierozwiązany element fizyki FAST.
4. **Osobno — PCB-015D2, opcjonalne EasyEDA ↔ Gerber/Excellon reconciliation:** feature-aware kontrola zgodności eksportu z source. Limit `manufacturing_tolerance_um` ma podawać użytkownik dla konkretnego workflow; przykładowe 10 µm nie jest globalną stałą ani tolerancją FAST/mesha.
5. **Po uzyskaniu użytecznego FAST:** prace nad kosztem preparation, siatką/domeną, viewerami i oszczędnym użyciem full-wave DESIGN/VERIFY.

Kolejność opiera się na końcowym, aktualnym wpisie `todo.md`: footprint/contact → Arc → sprzężenia. D2 jest odłożone i opcjonalne, mimo że w starszej liście priorytetów ma numer P2.

## 5. Stan starszego toru antenowego i openEMS

- Quados 8 i biquad przy 1420 MHz mają generatory, parametry, edytor i eksport; istnieją adapter openEMS, diagnostyka mocy, pola E/H w przekrojach oraz statyczne diagramy fazowe i raport HTML offline.
- Na natywnym Windowsie użytkownika potwierdzono import openEMS 0.37.0rc3/CSXCAD i wykonano przebiegi FDTD. Adapter pozostaje jednak eksperymentalny.
- Pierwotny audyt źródła wykazał niezgodne zaokrąglenie granic siatki/portu: opór obejmował 450 krawędzi, wymuszenie 270. W wariancie `aligned_feed` uzyskano 450 dodatnich wkładów.
- W `aligned_feed` lokalna praca netto wynosi **0,949145539 W**, strumień zewnętrzny **0,948187885 W**; ich względna różnica to około **0,10090%**. Pojedyncze odniesienie `U·I = 1 W` nadal różni się od lokalnej pracy o **5,085%** tego odniesienia.
- Te pomiary potwierdzają poprawę granic źródła i bilansu lokalnej pracy, **nie stanowią walidacji impedancji, SWR ani zysku**. Pozostają: lepsza definicja i pomiar portu, kontrola zbieżności i przypadek referencyjny. Wyników nie wolno poprawiać współczynnikiem bilansu.
- Prądy promiennika i pełnookresowa animacja nie są zaimplementowane. Dostępne statyczne pola E/H także wymagają natywnej walidacji. M2/M3 nie należy ogłaszać jako ukończonych.

## 6. Testy i poziom pewności

**Wyniki historyczne z `history.md` (nie uruchamiane podczas tego przeglądu):**

- `python -X utf8 -m unittest test_pcb_easyeda -v`: **11 PASS**. Wśród nich syntetyczny source-only FAST bez Gerbera.
- Trzy wybrane regresje po dalszych poprawkach: **3 PASS**, dotyczące guardu inner physical layer, zachowania detached provenance w projekcji i deterministycznego wyznaczania długości L/U.
- Brak potwierdzenia pełnej suite, natywnego openEMS/FDTD, rozległych prób prepare-only i pełnego solve realnej serpentyny w tych checkpointach.
- Testy 11+3 nie dowodzą pełnej poprawności elektromagnetycznej realnej płytki.

**Sprawdzenia w tym zadaniu:** odczyt i porównanie aktualnej dokumentacji, historii oraz metadanych ostatnich commitów/gałęzi. Nie wykonywano lokalnego kodu, testów, benchmarków ani FDTD. Ocena jest audytem stanu zapisów i repozytorium, nie nową walidacją numeryczną.

## 7. Zasady dalszej pracy / ryzyka przekazania

- **Source EasyEDA jest nadrzędny dla intencji projektowej; Gerber jest opcjonalnym świadectwem produkcyjnym.** Nie nadpisuj source ani nie rekonstruuj znanej semantyki z tessellacji.
- **Fail-closed:** brak komponentów, materiału, topologii, nieobsługiwany Arc/coupling lub niejednoznaczna skala mają być jawnym ograniczeniem, a nie szacowaną geometrią lub cichym pominięciem.
- Rozdzielaj trzy różne pojęcia: `geometry-resolution`, `manufacturing_tolerance` i rozdzielczość siatki FDTD. Nie wprowadzaj ukrytej uniwersalnej tolerancji 10 µm.
- Preserve provenance: wersję dialektu, rekordy, ID, net, źródłowy hash, jednostki, kopię rozstrzygniętych parametrów i przyczyny braków.
- Nie uznawaj źródłowego `POUR` boundary za rzeczywiste wypełnienie bez `POURED`; nie wyprowadzaj metalizacji VIA z samego annular ring; nie dodawaj „idealnych” elementów poza jawnym zakresem przybliżenia.
- Uruchomienia na docelowym Windows używają `.venv`; repo stosuje `unittest`. Pełne polecenie testowe wskazane w `AGENTS.md` to `.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v`. Benchmarki są wykluczone bez osobnego polecenia.
- Znaczącą pracę dokumentuj i publikuj na `origin/main`, ale nie utożsamiaj publikacji checkpointu z PASS wszystkich testów. Nie ruszaj niepowiązanej pracy użytkownika.

## 8. Niedawna historia na `main`

- `13c927675f9a0b8793957e6001c3ceebc14a9b18` / `19a714db9fb0ac19a0336608a085c981bf4ceacf` — zmiana roadmapy i kontraktu na EasyEDA source-first.
- `7503ac1737dfaa7ae8a85144c110b516bf4bc277` — D0, parser semantyczny.
- `26180121f7e799480b907d80fb3dbb754c48ed38` — D1, połączenie source-only z FAST.
- `68f7e443ec5800ffbe03457f8cdba4a01f487016` / `edd572a146152c81ed33039a9dc0bcc36fa652f8` — zapis wąskiej weryfikacji i guardów.
- `bc886490909bcac2914224c555bc597d8d469820` — dodanie testowego źródła PCB i ZIP dla `test_psu`.
- `76d8e51bb3fd291386c88db45f4d7052b916b04d` — HEAD `main` w chwili przeglądu, merge.

## Dokumenty źródłowe

- [`AGENTS.md`](AGENTS.md) — reguły pracy, architektura, granice walidacji i publikacja.
- [`todo.md`](todo.md) — bieżący priorytet i konkretny blocker po D0/D1.
- [`history.md`](history.md) — wyniki kolejnych checkpointów i 11+3 testów.
- [`docs/pcb-reduced.md`](docs/pcb-reduced.md) — kontrakt i ograniczenia FAST.
- [`docs/pcb-easyeda.md`](docs/pcb-easyeda.md) — profil parsera, jednostki, CLI i zależności footprintów.
- [`docs/architecture.md`](docs/architecture.md) — architektura pakietu i tor openEMS.
- [`goal.md`](goal.md) — pierwotne wymagania, stan symulacji anten i ograniczenia fizyczne.

**Zakres zapisu tego zadania:** wyłącznie nowy plik `migracja.md`. Nie zmieniano `history.md`, `todo.md`, kodu, testów, parametrów ani pozostałych plików. Jest to stan na wskazanym HEAD przed zapisaniem niniejszego raportu.
