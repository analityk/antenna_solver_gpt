# EasyEDA source-first — PCB-015D0/D1

Source PCB jest nadrzędny. Gerber/Excellon nie jest wymagany; brak eksportu
produkcyjnego oznacza `manufacturing_validation=not_requested`.

## Format i jednostki

Obsługiwany profil: JSON arrays per line, DOCTYPE PCB 1.8, editorVersion 2.2.x.
Nieznany dialect/version jest odrzucany zamiast zgadywania skali. Parser
zachowuje pełne raw records, indeksy linii, ID i SHA256 niezmienionych bajtów.

Centralna konwersja w `pcb/easyeda.py`: PCB Line/Arc/Via/Poly/Pour i grubości
LAYER_PHYS używają mil (25.4 µm). Współrzędne materializowanego POURED używają
10 mil (254 µm). CANVAS określa tylko display unit. Nie stosujemy rounding
KiCada ani jego inwersji osi do ekranowego układu PCB; canonical XY zachowuje
źródłowy +Y w górę, signed sweep dodatni CCW. R zaczyna się w lewym górnym rogu,
a wysokość biegnie w stronę -Y. Semicircle ±180° ma środek w połowie cięciwy.

Podstawa, nie dopasowanie skali do wymiarów użytkownika:

- [Oficjalny format EasyEDA Pro V2](https://github.com/easyeda/easyeda-file-format-v2/tree/63f38c2758cbe2456e8b5c7e76469369430d94af/docs/en/pcb): pola LINE/ARC/VIA, CANVAS, polygon-system, LAYER_PHYS.
- [Importer KiCad EasyEDA Pro](https://gitlab.com/kicad/code/kicad/-/tree/master/pcbnew/pcb_io/easyedapro), sprawdzony 2026-10-21: `ScaleSize` 25400 nm/unit, `ScalePos` z inwersją do układu KiCad, ARC center z signed angle, R height ze znakiem minus, POURED `ptScale=10`.
- [Dokumentacja importera KiCad](https://dev-docs.kicad.org/en/import-formats/easyeda/index.html#_easyeda_pro_format).

Ogólna dokumentacja V2 mówi 0.01 inch bez rozróżnienia PCB/schematic. Nie
przenosimy tego domyślnie na wszystkie rekordy PCB: implementacja importera
potwierdza rozdzielone skale. Nie jest to EasyEDA Standard ani format Pro V3.

## Zakres checkpointu parsera

DOCTYPE, HEAD, CANVAS, LAYER, LAYER_PHYS, NET, LINE, ARC, VIA, PAD_NET,
COMPONENT i ATTR. POLY/POUR: niezaokrąglone R (dowolny obrót) i proste kontury
L; POURED: pojedynczy wypełniony, niestrokowany kontur. Raw pola pozostają
niezmienione. Unknown records są zachowane i blokują canonical solve, chyba że
są rozpoznanym metadata edytora lub mają prefiks META_. Unsupported footprint,
complex fill rule czy thermal-spoke nie stają się domyślnie pełną miedzią.

Materiał nie jest oceniany jako „typowa PCB”: epsilon_r=1 i gruby dielektryk
są legalne. Zakres przybliżenia microstrip nadal należy do solvera, nie parsera.
Arc zachowuje signed sweep i mathematically derived center; nie ma jeszcze
modelu TL łuku ani pairwise/curved coupling. Gerber-only fallback bez zmian.

## Source-only CLI i canonical checkpoint D1

Inspekcja semantyki i dostępnego modelu, bez wymogu portu:

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-source gerbs\realpcb_microstrip\test_spirala.epcb --inspect-source
```

Zapisuje `source_ir.json` (w tym raw records), `source_model.json` (obrys,
stackup, miedź per net/layer, routes, vias, zależności footprintów), `import.json`
i `summary.json`. `source_inspected` nie oznacza ukończonego solve ani pełnego
modelu kontaktów. Zależności są wypisane w konsoli i zapisane w metadata.

Solve dla obsługiwanego source z kompletnymi padami i kontaktami:

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-source projekt.epcb --source-config source-contacts.json
```

Jawny override opisuje kontakty w źródłowym układzie XY, w mm:

```json
{"port":{"mode":"explicit","negative_mm":[-2.032,0],"positive_mm":[2.032,0],"width_mm":0.508}}
```

Opcjonalne `drills` ma istniejące pola `pth_plating_um` i
`pth_model="solid_pec_equivalent"`. VIA podaje średnicę otworu i pada, **nie**
grubość metalizacji. Nie zgadujemy jej z annular ring. Model PTH pozostaje
istniejącą aproksymacją. Inner/blind/buried spans nie są obsługiwane tym adapterem.

D1 obsługuje jeden dielektryk między top/bottom, source LINE/ARC, materializowany
POURED, absolutne niezaokrąglone SMD PAD RECT i through VIA z jawną metalizacją.
COMPONENT/PAD_NET/ATTR zachowują intencję; zewnętrzny footprint jest szukany pod
jawnym hashem w `FOOTPRINT/<hash>.efoo` obok source lub katalogu projektu.
Brak footprintu blokuje solve precyzyjnym missing-source-dependency; znaleziony
zewnętrzny footprint również wymaga przyszłego adaptera instancji. Nie udajemy
obsługi elementów przez pominięcie ich padów lub wartości.

Pad z jednym semantic route junction może być idealnym equipotential terminalem:
pełny fizyczny contact/gap nadal przechodzi audyt, pad musi należeć do tego samego
conductora. Pad electrical length i parasitics są jawnie pominięte, nie zgadywane
jako dodatkowa TL. Wiele junctions w padzie -> błąd. Źródłowe nets kontrolują
zwarcia; final physical polygons kontrolują ownership. Source routes i pady
przechodzą istniejącą normalizację i geometry resolution; ID/net/signed sweep
nie są odzyskiwane z polygonów. Fizyczny audyt projekcji pozostaje obowiązkowy.

Nie wdrożono D2 ani publicznego parametru manufacturing tolerance. Nie ma
ukrytego domyślnego limitu; source-only zapisuje `not_requested`. Gerber ZIP/
katalog nadal działa przez dotychczasowy argument pozycyjny. Full-wave bez zmian.


## Sprawdzenie checkpointu 2026-10-21

11 testów w `test_pcb_easyeda.py` PASS: parser, jednostki, signed sweeps,
VIA, nietypowy dielektryk, błędy, brak footprintu, source-only FAST z idealnymi
padami, projekcja/normalizacja i guard Arc. Realny `test_spirala.epcb` dodany
przez użytkownika do repo: odczyt + canonical layout PASS (198 records,
6 Line / 7 Arc / 2 Via). Brakuje geometrii footprintu CSRC/R1
`e8bf627583724bdebefbaa0be79b0d2f`; canonical output zachowuje ten brak,
nie jest pełnym modelem fizycznym do solve. Pełny source nie był zmieniany.
Nie sprawdzano `test_spirala.zip`, nie uruchamiano FDTD ani pełnej suite.

## Audyt brakujących footprintów w plikach source — 2026-10-21

**Wniosek:** brak geometrii w pojedynczym `.epcb` nie dowodzi uszkodzenia
projektu ani związku z rodzajem montażu SMD/THT. Dokument PCB zapisuje
`COMPONENT` (pozycja, warstwa, obrót), atrybut `Footprint` (identyfikator)
oraz `PAD_NET` (numer pada, net i opcjonalny lokalny ID), lecz definicje
kształtów padów mogą być osobnymi dokumentami `FOOTPRINT/*.efoo`.
Format projektu EasyEDA Pro wiąże je przez `project.json`. Oficjalna
instrukcja **File → Project Save as (local)** opisuje lokalny eksport
archiwum projektu zawierającego biblioteki. Z tego powodu przed tworzeniem
adaptera należy najpierw uzyskać i zinwentaryzować pełny eksport projektu
EasyEDA, nie tylko pojedyncze `.epcb` czy ZIP z Gerberami.

Źródła formatu i eksportu:
- https://github.com/easyeda/easyeda-file-format-v2/blob/main/docs/en/general/project-json.md
- https://github.com/easyeda/easyeda-file-format-v2/blob/main/docs/en/pcb/package/component.md
- https://prodocs.easyeda.com/en/import-export/export-easyeda-pro/

**Dowody z plików repozytorium (statyczna inspekcja, nie test solvera):**

- `gerbs/realpcb_microstrip/test_spirala.epcb`: 1 dokument PCB,
  2 `COMPONENT` (CSRC/R1), 4 `PAD_NET`, zero rekordów `PAD`
  i zero `DOCTYPE FOOTPRINT`. Oba komponenty odsyłają do
  `e8bf627583724bdebefbaa0be79b0d2f`; geometria footprintu nie jest
  dostępna w samym pliku ani w katalogu tego przypadku w repo.
- `gerbs/test_psu/test_psu.epcb`: **nietypowy dokument złożony**:
  34 bloki `DOCTYPE FOOTPRINT` przed jednym `DOCTYPE PCB`.
  Bloki mają nazwy: 31 × `Test-Point-0.5mm`, 1 × złącze przewlekane
  `HDR-TH_2P-P2.54-V-F`, 1 × `R0603`, 1 × `G0603`.
  PCB zawiera 291 `COMPONENT`, 906 `PAD_NET` i 9 samodzielnych `PAD`.
  Po dopasowaniu zarówno `HEAD.uuid`, jak i `HEAD.source` 119 instancji
  wskazuje dostępną definicję, 169 wskazuje identyfikatory bez definicji
  w tym pliku, 3 nie mają rozpoznanego atrybutu `Footprint`.
  Istnienie bloku footprintu **nie oznacza jeszcze**, że obecny parser
  potrafi go przetworzyć i zinstancjonować.
- W tym pliku nazwane definicje pasywne to `R0603` i `G0603`,
  nie `0805`. Nie wyciągać wniosków o dostępności definicji 0805
  z samych rysunków/śladów miedzi ani z przykładowej nazwy w dokumentacji.
  Widać równocześnie definicję THT i braki wśród dwupadowych R/C, więc
  **SMD/THT nie jest regułą kompletności**.

**Kontrakt następnego etapu:** przyjmować albo pojedyncze PCB + katalog
zależności footprintów, albo pełny archiwalny projekt z `project.json`
i `FOOTPRINT/<uuid>.efoo` (po zbadaniu rzeczywistego układu eksportu).
Rejestrować i weryfikować mapowanie `COMPONENT → Footprint UUID/source →
PAD (ID i numer) → PAD_NET`, uwzględnić transformację instancji, stronę
płytki, pady SMD oraz pady przewlekane z wierceniem i metalizacją. Nigdy
nie nadawać miedzi zarysowi obudowy lub silkscreenowi ani nie wytwarzać
brakujących padów z Gerbera. Sam preambułowy `FOOTPRINT` w nietypowym pliku
złożonym nie może być automatycznie uznany za standardowe `.epcb`.

**Stan implementacji po audycie:** bez zmian. Parser D0 obsługuje pojedyncze
`DOCTYPE PCB`; D1 jedynie wykrywa zależności i odmawia solve bez geometrii.
Nie dodano obsługi archiwów projektu, parsera `.efoo` ani nowej fizyki.

### Odczyt pełnego eksportu `test_psu.epro` — checkpoint analityczny 2026-10-21

Użytkownik udostępnił `test_psu.epro` jako załącznik rozmowy. Sprawdzono
rzeczywiste bajty pliku i integralność ZIP: **jest to prawidłowe archiwum ZIP**,
nie nieznana binarka. Uwaga o trwałości: ten załącznik **nie został dodany do
repozytorium** i może być niedostępny dla nowego czatu. Identyfikator kontrolny
SHA256 archiwum:
`659e3eacb05b4f91645bab3f621723adf85d14f56505aa6962e7d3f60a770982`.

W środku są: `project.json`, 1 `PCB/<uuid>.epcb`, **46** `FOOTPRINT/*.efoo`,
**77** `SYMBOL/*.esym` oraz katalogi pomocnicze. Łącznie 125 plików
i 9 wpisów katalogowych, 134 elementy ZIP. `project.json` indeksuje
46 footprintów, 77 symboli i 77 definicji device. Wewnętrzne PCB nadal
zawiera 34 wbudowane dokumenty typu FOOTPRINT przed jednym dokumentem PCB.
Jest to format EasyEDA Pro **V2** (`DOCTYPE ... 1.8`, editor 2.2.x),
nie V3/`.epro2`.

**Kontrola kompletności referencji w tym pełnym projekcie:**
- **291/291** instancji `COMPONENT` ma odszukiwaną definicję footprintu:
  254 przez bezpośredni identyfikator do `.efoo`, 34 przez `HEAD.uuid`
  osadzonego FOOTPRINT, a 3 `F/F1/F3` przez identyfikator `Device`
  i jego atrybut `Footprint` w `project.json`.
- **906/906** rekordów `PAD_NET` znajduje odpowiadający numer pola `PAD`
  w swojej definicji. To potwierdzenie dostępności semantyki pinów i
  geometrii bibliotecznej, **nie** poprawności transformacji, fizycznych
  połączeń, stackupu ani skutecznego solve.
- `R1206` ma rzeczywiste prostokątne pola lutownicze. Kondensator
  `CAP-TH_BD18.0-P7.5-D0.8-FD` zawiera pady z otworami. Dostępne są
  także m.in. `QFN-24`, `QFN-16`, `LQFP-144`; nie znaleziono
  nazwanego footprintu `0805`. Typ SMD/THT/QFN nie decyduje
  o brakach w samym `.epcb`.

**Znaczenie wcześniejszych liczb 119/169/3:** dotyczyły
`test_psu.epcb` rozpatrywanego **bez biblioteki projektu**.
Brakujące w nim 169 definicji rozwiązują pliki archiwum; 3 instancje
bez bezpośredniego atrybutu rozwiązują się przez mapę `Device`.
Nie należy dalej opisywać 169 referencji jako brakujących
w pełnym `test_psu.epro`.

**Dalsza implementacja:** importer ma dostać osobną ścieżkę do
`.epro` (bezpieczny odczyt ZIP w pamięci, `project.json`, indeks bibliotek,
wyodrębnienie właściwego bloku PCB przy złożonych plikach, parser `.efoo`,
identyfikatory i numerację PAD, fallback `Device`, transformacja do SI,
warstwy i rodzaje padów). Osobno zweryfikować wielowarstwowe i THT,
a następnie fizyczny contact/net audit. Nie uznawać 291/291 oraz 906/906
za zaliczony FAST. `test_spirala.epcb` nadal nie ma swojej pełnej
biblioteki: do uruchomienia tego przypadku potrzebny odpowiadający
mu eksport projektu, nie biblioteka z innego PCB.

Sprawdzenia przy tym checkpointcie: poprawne otwarcie/test CRC ZIP,
odczyt JSON, inwentaryzacja wszystkich ścieżek, indeksów, komponentów,
rekordów PAD/PAD_NET i statyczna kontrola ich zgodności. Nie wykonywano
testów programu, FDTD, benchmarków ani natywnego solve.
