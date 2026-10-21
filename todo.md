# TODO — PCB: aktualny stan i następne kroki

Stan na 2026-10-21. **Decyzja użytkownika: podstawowym wejściem geometrii
PCB jest kompletny projekt EasyEDA Pro V2 `.epro`** (ZIP z `project.json`,
`PCB/*.epcb`, `FOOTPRINT/*.efoo`). Pojedynczy `.epcb` służy do
diagnostyki/kompatybilności, a Gerber/Excellon wyłącznie do opcjonalnej
weryfikacji artefaktu produkcyjnego. Importer D4 `.epro` jest zaimplementowany w ograniczonym profilu;
canonical serpentyny sprawdzony, cała geometria PSU nadal niewspierana.

## Obowiązujący kontrakt projektu — decyzja użytkownika

1. O **geometrii fizycznej** rozstrzyga **footprint instancji PCB**,
   umieszczony/ewentualnie ręcznie zmieniony przez projektanta.
   Nigdy nie podmieniaj go na biblioteczny footprint `Device`.
2. Dla **niepolaryzowanych elementów pasywnych** użytkownik świadomie
   wybiera footprinty rodziny rezystorów (`R0603` i analogiczne
   rozmiary), także dla kondensatorów. `CSRC: PCB R0603` i
   `Device C0603` to **stan poprawny i zamierzony**, bez
   ostrzeżenia o konflikcie. Model 3D pochodzi od komponentu,
   niezależnie od footprintu elektrycznego.
3. **`refdes=CSRC`, `Value=0`** identyfikuje pierwsze źródło
   sygnału; liczba to **indeks źródła**, nie pojemność.
   Dalsze jawnie oznaczone źródła mają wartości `1, 2, 3, ...`
   (o 1 większe od poprzedniego). Nie wymyślaj ich refdes.
   `C1` i wszystkie inne kondensatory nieoznaczone jako źródło
   to normalne kondensatory; ich `Value`, `Device` ani
   `Footprint` same nie ustanawiają roli źródła.
4. Model i kontakty pochodzą z `.epro` i jego `.efoo`:
   `COMPONENT` → jawny footprint PCB → `PAD` →
   `PAD_NET`, z obrotem, odbiciem warstwy i jednostkami SI.
   `Device` może służyć pomocniczemu indeksowaniu bibliotek
   **tylko gdy nie nadpisuje jawnej decyzji PCB**.
   Oddzielnie audytować geometrię/elektrykę i dane do wizualizacji 3D.
5. Source-only oznacza **bez Gerbera**, a nie bez bibliotek.
   Brak zależności zgłaszaj jawnie; nie twórz geometrii z Gerbera.

## Aktualna kolejność implementacji — od najbliższego zadania

**D4 DONE dla wspieranego profilu i canonical serpentyny; PARTIAL dla PSU.**

- ZIP/CRC/limity/strict JSON, wybór PCB, biblioteki `.efoo` i embedded,
  nadrzędność PCB nad Device, kontrola PAD ID+number, SI transform i source_index.
- SMD RECT/circle/OVAL; round through pad z jawną metalizacją i otworem.
  Top/bottom/jeden dielektryk; unknown geometry fail-closed.
- `spirala.epro` jest w `gerbs/emtest4`: 2/2 komponenty, 4/4 mapowania,
  cztery rzeczywiste pady R0603, kontakty, port, PTH i explicit R1 sprawdzone.
- `test_psu.epro` jest w `gerbs/test_psu`: 291/291 i 906/906 resolve PASS,
  34 embedded / 257 library (3 Device fallback). Physical canonical FAIL CLOSED:
  pusty NET w PCB record 145; dalej starsze footprinty 1.3/1.7, slots,
  rozbudowane pours/stackup. Nie jest to potwierdzona geometria/FAST PSU.
- Sprawdzenia D4: 11 testów pierwszego checkpointu, następnie 25 testów
  projektu+legacy .epcb, następnie 3 celowane testy (THT/serpentyna/source index).
  Każdy zestaw PASS; bez pełnej suite i native/FDTD.

**PCB-015D3 DONE — geometria, metryka i graf semantic ARC dla spirali:**
5 LINE + 7 ARC netu A, długość 36.373621555 mm przed/po projekcji.
Promień i signed sweep źródła; projektowane węzły nie wyznaczają nowego okręgu.
Zachowane kontakty, 2 ground-PTH, jawny testowy R1 oraz source_index=0.
`spirala_NNN` działa także dla inspekcji; checkpoint nazw `b9c9987`.
**TERAZ — PCB-015C (OPEN):** fizyczne pairwise/curved coupling wyłącznie spirali.
Pierwszy blocker: `curved coupling analysis unsupported`; 7 ARC i 5 skośnych
LINE mają niewspierane sprzężenia. Powstaje graf, nigdy pozornie poprawne Z/S11.
Krzywiznowa korekta parametrów przekroju pozostaje jawnie niezamodelowana.
**Poza aktualnym zakresem:** PSU i dalsza zgodność D4; nie analizować/testować
bez nowego polecenia użytkownika.
D2 source/manufacturing reconciliation nadal opcjonalne. Pełny zakres/CLI:
[docs/pcb-easyeda.md](docs/pcb-easyeda.md).

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

## Wcześniejszy kontrakt bazowy: EasyEDA source-first (rozszerzony powyżej o .epro)

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

### Dawne P0 — PCB-015D0: parser pojedynczego source PCB (DONE: ograniczony profil)

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

### Dawne P1 — PCB-015D1: ograniczony source-only canonical i FAST (PARTIAL)

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

### P3 — PCB-015D3: semantic Line/Arc transmission-line graph (DONE dla spirali)

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

Aktualny krok to **PCB-015C curved/pairwise coupling dla spirali**. D4 canonical serpentyny
nie wymaga Gerbera. Starsze wpisy D0/D1 i audyty przed D4 są w history.md;
nie traktować ich dawnych braków bibliotek jako aktualnego blockera.
