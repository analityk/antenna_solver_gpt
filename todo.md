# TODO — PCB: aktualny stan i następne kroki

Stan na 2026-10-21. Ten plik opisuje bieżący kierunek rozwoju rdzenia PCB po
PCB-015C0.1. Priorytetem jest workflow użytkownika oparty o EasyEDA source PCB;
Gerber/Excellon pozostają ważnym, ale opcjonalnym artefaktem produkcyjnym.

## Stan potwierdzony

### FAST / reduced quasi-TEM

Istnieje osobny solver `antenna_lab.pcb.reduced_control`, który nie uruchamia
openEMS/FDTD. Obsługuje podstawową sieć TL + idealne R/L/C, ground-PTH jako
jawną aproksymację, bottom-ground setback oraz fail-closed dla nieobsługiwanej
topologii i sprzężeń.

PCB-015C0/C0.1 zachowało Gerberowe Line/Arc jako provenance i usunęło fałszywe
`stroke_not_preserved` wynikające z porównywania dwóch niezależnie
skwantyzowanych reprezentacji. Commity C0.1:

- `a3fb155cca227a09033dc487834bc3102f208d75`
- `95796d5be7d22aa9d41dd8f24e13e1f3e79adb58`
- `0a6cad98311345eff5b4119ce6da8e1cf2b63162`

Na realnym lokalnym `test_spirala.zip` użytkownik potwierdził po C0.1 następny
jawny blocker:

`Reduced source route Arc unsupported: top:route_000009 ...; no guessed TL arc.`

To potwierdza, że route-survival/projection nie jest już bieżącym blockerem.

## Zmiana architektury: EasyEDA source-first

Dalszy rozwój rdzenia nie ma odtwarzać semantyki projektu z Gerberów, jeżeli
dostępny jest plik source PCB z EasyEDA.

Kontrakt:

1. **EasyEDA source PCB jest źródłem prawdy o intencji projektowej i semantyce**:
   nets, Line/Arc, szerokości, signed sweep, warstwy, vias, pady/piny, stackup,
   board geometry i inne jawne dane CAD.
2. **FAST ma działać również bez Gerberów.** Brak Gerber/Excellon nie jest
   błędem, jeżeli source PCB zawiera wystarczające dane do żądanego modelu.
3. **Gerber/Excellon są opcjonalną walidacją artefaktu produkcyjnego.** Gdy są
   dostarczone, służą do sprawdzenia, czy eksport odpowiada source, a nie do
   nadpisywania lub rekonstruowania source.
4. Reconciliation używa **jawnego parametru użytkownika** określającego
   dopuszczalną różnicę geometryczną, np. `manufacturing_tolerance_um`.
   Przykładowe 10 µm jest wartością podaną przez użytkownika dla konkretnej
   pracy, nie globalnym defaultem fizycznym ani stałą w kodzie.
5. Odchyłka <= ustawiona tolerancja jest akceptowana jako zgodny eksport;
   przekroczenie tolerancji ma dawać jednoznaczny mismatch/fail zgodnie z
   polityką wywołania. Tolerancja reconciliation nie jest snappingiem,
   geometry-resolution ani rozdzielczością siatki EM.
6. Rdzeń nie narzuca realizmu produkcji PCB. Source może opisywać również
   nietypowe/umowne konstrukcje, np. bardzo gruby dielektryk o epsilon_r≈1,
   jeżeli jest to świadomy model użytkownika.
7. Gerber-only route provenance z PCB-015C0/C0.1 pozostaje fallbackiem i
   materiałem diagnostycznym. Nie jest teraz priorytetem rozwoju.

## Priorytety implementacji

### P0 — PCB-015D0: minimalny parser EasyEDA source PCB do jawnego IR

Celem jest parser source-first, nie pełna implementacja całego formatu EasyEDA.

Pierwszy checkpoint ma:

- rozpoznać format/wersję (`DOCTYPE`, `HEAD`, potrzebne ustawienia jednostek),
- zachować warstwy i fizykę warstw (`LAYER`, `LAYER_PHYS`),
- zachować nets (`NET`),
- parsować semantyczne `LINE` i `ARC` bez rekonstrukcji z polygonu,
- dla `ARC` zachować endpointy, signed sweep, width, layer, net i source ID,
- parsować `VIA` i podstawowe przypisanie net/layer,
- parsować `PAD_NET` i minimalne dane potrzebne do source/component contacts,
- zachować provenance: source file, hash, record ID/index i wersję formatu,
- przeliczyć dane przestrzenne do SI dokładnie na granicy parsera,
- nie zgadywać jednostek; jeśli format/wersja nie wystarcza do jednoznacznej
  interpretacji, parser ma zgłosić konkretny brak zamiast heurystycznie skalować,
- zachować deterministyczny, strict-JSON-compatible IR.

Nieznane rekordy nie muszą być implementowane, jeśli nie są potrzebne do
żądanego modelu. Nie wolno jednak cicho zignorować rekordu, który może zmieniać
używaną topologię, materiał albo geometrię aktywnej warstwy.

### P1 — PCB-015D1: source-only canonical PCB model i FAST

Zbudować z EasyEDA source wystarczający canonical PCB model, aby reduced solver
mógł działać **bez żadnego Gerbera**.

Zakres ma objąć co najmniej dane potrzebne dla aktualnej klasy projektów:

- board outline,
- top/bottom copper primitives potrzebne dla aktywnej trasy i reference plane,
- Line/Arc route graph z nets,
- vias,
- stackup/materials,
- source/component contacts wymagane przez istniejący reduced solver.

Dla polygonów/pourów parser ma korzystać z semantyki source EasyEDA, a nie
generować Gerbera pośrednio i odczytywać go ponownie.

Source-only path ma zachować fail-closed dla brakujących danych istotnych dla
konkretnego solve, ale sam brak Gerbera nie może powodować odmowy.

### P2 — PCB-015D2: opcjonalny EasyEDA ↔ Gerber/Excellon reconciliation

Jeżeli użytkownik poda Gerber/Excellon, porównać artefakt produkcyjny z modelem
source.

Wymagania:

- tolerancja jest parametrem użytkownika, nie stałą,
- parametr musi być zapisany w summary/provenance wyniku,
- porównanie ma być feature-aware, a nie vertex-to-vertex tessellation equality,
- Line: axis/endpoints/width/envelope,
- Arc: source signed sweep/radius/width/envelope,
- Via: centre/drill/outer/contact,
- board/pours: coverage/topology w zakresie wspieranym przez checkpoint,
- mismatch raportuje feature/source ID, wielkość odchyłki i ustawiony limit,
- odchyłka poniżej limitu jest akceptowana,
- reconciliation nie modyfikuje source geometry i nie snapuje source do Gerbera,
- brak Gerberów oznacza `manufacturing_validation=not_requested/not_available`,
  a nie błąd source-only solve.

Nie używać tej tolerancji jako tolerancji FAST, meshera ani geometry-resolution.

### P3 — PCB-015D3: semantic Line/Arc transmission-line graph

Po source-first parserze FAST ma brać długość i topologię z prymitywów CAD.

- Line: długość z endpointów source.
- Arc: długość z semantycznego promienia i signed sweep; nie odtwarzać kąta z
  tessellated Gerber polygonu ani z niezależnie kwantyzowanych trzech punktów.
- Curvature/bend discontinuity może pozostać jawnie pominiętym efektem w
  pierwszej wersji, ale długość elektryczna łuku nie może zniknąć ani być chordą.
- Graph continuity i net ownership pochodzą z source semantics, z fail-closed
  dla niejednoznaczności.

### P4 — PCB-015C: pairwise coupled microstrip

Dopiero po semantic route graph:

- nie ignorować równoległych/zbliżonych fragmentów,
- nie używać arbitralnego współczynnika sprzężenia,
- wyznaczać coupled-line parameters metodą fizyczną (C/C0→L lub udokumentowany
  even/odd),
- splitować sekcje tam, gdzie zmienia się stan sprzężenia,
- fail closed dla topologii wykraczającej poza obsługiwany model.

To pozostaje głównym brakującym elementem fizyki FAST dla serpentyny.

### P5 — wydajność i ekonomiczny full-wave

Po użytecznym source-first FAST wrócić do optymalizacji preparation, domeny,
viewerów i minimalnej liczby FDTD. Nie mieszać tego z parserem EasyEDA.

## Zasady dalszej pracy

1. Source EasyEDA jest nadrzędny dla semantyki projektowej, gdy jest dostępny.
2. Gerber/Excellon jest artefaktem produkcyjnym i opcjonalnym dowodem zgodności.
3. Source-only ma działać bez Gerberów.
4. Manufacturing tolerance ustawia użytkownik dla konkretnego workflow; 10 µm
   nie jest globalną prawdą projektu.
5. Nie rekonstruować z Gerbera informacji, które source podaje jawnie.
6. Unsupported/missing semantics -> jawny fail, nie heurystyczne zgadywanie.
7. Geometry resolution, manufacturing reconciliation i mesh EM są trzema
   niezależnymi kontraktami.
8. Full-wave DESIGN/VERIFY pozostaje arbitrem efektów 3-D, ale nie warunkiem
   codziennego FAST.
9. Testy lokalne użytkownika są tanie; testy zdalnego agenta są kosztowne.
   Agent preferuje analizę statyczną i najmniejszy bezpośredni zestaw testów.
10. Znaczącą pracę commitować i publikować na `origin/main` przed drogimi
    testami. PASS/PARTIAL/FAIL nie blokuje checkpointu/pusha.

Najbliższy krok po checkpointach D0/D1: **jawna geometria zewnętrznego footprintu
CSRC/R1 i adapter kontaktów komponentów**, następnie semantic Arc TL oraz
pairwise/curved coupling. Nie rekonstruować brakującego footprintu z Gerbera.
D2 reconciliation pozostaje opcjonalne i nie jest implementowane.

**Zależności footprintów — nowy wynik 2026-10-21:** pełny
`test_psu.epro` (udostępniony w rozmowie; **nie w repo**) okazał się
archiwum ZIP EasyEDA V2 z `project.json`, `PCB/`, 46 plikami `.efoo`
i 77 `.esym`. Statycznie rozwiązano 291/291 instancji COMPONENT
oraz 906/906 przypisań PAD_NET (254 przez bibliotekę, 34 przez
wbudowane footprinty, 3 przez atrybut Device). Wcześniejsze 169
brakujących definicji dotyczyło **samego** `test_psu.epcb`, nie
całego eksportu. Pierwszy krok programistyczny: obsługa importu
projektu `.epro`, biblioteki `.efoo`, mapy `project.json`,
źródłowych pads/net i instancji wraz z geometrią i audytem.
Pełny projekt źródłowy `test_spirala` nadal nie jest dostępny;
jego fingerprint `e8bf627583724bdebefbaa0be79b0d2f`
nie wolno odzyskiwać z obcego projektu ani z Gerbera.
Szczegóły `docs/pcb-easyeda.md`; Arc i coupling pozostają kolejne.

### Checkpoint D0/D1 — 2026-10-21

Działa source-only parser PCB 1.8/editor 2.2.x, neutralny IR i ograniczony
canonical layout (top / jeden dielektryk / bottom, R/L outline, materializowany
POURED, absolutne RECT PAD, Line/Arc, VIA z jawną metalizacją). CLI:
`reduced_control --easyeda-source ... --inspect-source` nie wymaga portu/Gerbera.
Kompletny syntetyczny source z explicit port przeszedł FAST bez Gerberów;
11 testów w test_pcb_easyeda.py PASS na pierwszym checkpointcie integracji.

Realny dodany do repo test_spirala.epcb: parser i layout PASS, 198 rekordów,
6 LINE, 7 ARC, 2 VIA, obrys ~25 mm, substrate ~0.2 mm / epsilon_r=4.5.
Canonical layout jawnie niekompletny: brak geometrii footprintu o hashu
`e8bf627583724bdebefbaa0be79b0d2f` dla CSRC/R1. Nie wykonano solve ani native.
Dla bezpośrednich PADów źródłowych jeden route junction w padzie może być
idealnym terminalem, bez zgadywania lead length i bez parasitics.
Opis units/ograniczeń: docs/pcb-easyeda.md. Brak Gerbera = not_requested.

