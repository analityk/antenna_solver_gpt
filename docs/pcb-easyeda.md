# EasyEDA source-first — PCB-015D4

Pełny projekt **`.epro` jest obsługiwanym wejściem** w ograniczonym profilu
EasyEDA Pro V2: `project.json`, `PCB/*.epcb`, `FOOTPRINT/*.efoo`, również
embedded FOOTPRINT. Dotychczasowe samodzielne `.epcb` i Gerber pozostają
kompatybilne. Import nie eksportuje ani nie odczytuje pośredniego Gerbera.

## Wiele warstw EasyEDA — fizyczne LAYER_PHYS bez warstw technologicznych (2026-10-23)

Importer rozpoznaje faktyczny stos z **kolejności rekordów LAYER_PHYS**:
TOP / SUBSTRATE / SIGNAL lub PLANE / SUBSTRATE / ... / BOTTOM.
Predefiniowane, nieużywane numery InnerXX nie tworzą miedzi.
Górna miedź ma z=0, kolejne powierzchnie leżą na granicach kolejnych
dielektryków poniżej zera. Wszystkie miedzi są oddzielnymi powierzchniami
PEC bez geometrycznej grubości; rzeczywiste grubości z CAD pozostają
jedynie metadanymi materiału. Model zachowuje źródłowe ID warstw,
grubości, ślady, pady, POURED z otworami oraz przelotki. Otwory PTH
wymagają dotychczasowej **jawnej** grubości galwanizacji.

Fizyczne warstwy SUBSTRATE są jedynymi dielektrykami FDTD.
Silk, pasta, stencil, solder mask i inne jednoznacznie znane warstwy
pomocnicze **nie są modelowane**. Maska antylutownicza pozostaje
odłożona do jawnego przyszłego modelu przybliżonej przenikalności
efektywnej; nie zmieniaj dziś εr podłoża przez ukryty współczynnik.
Nieznane typy warstw fizycznych są blokowane zamiast automatycznie
pomijane.

**Nie wolno zgadywać εr:** w realnym `stripline1.epro` trzy dielektryki
(361, 362, 363) mają εr=0 w LAYER_PHYS. Jest to brak danych
elektromagnetycznych, nie fizyczna εr=0. `--inspect-source` zachowuje
i wypisuje stos wraz z listą brakujących wartości, a PREPARE-ONLY/FDTD
zostaje zatrzymany, dopóki użytkownik świadomie ich nie uzupełni.
W GUI służy do tego zakładka **Warstwy EM** z polami εr/tanδ. Odpowiada
temu opcjonalna jawna flaga CLI powtarzana dla każdej warstwy:

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.easyeda_control --easyeda-project gerbs\stripline1\stripline1.epro --quality design --geometry-resolution-um 10 --fields-mhz 1000 2000 --center-mhz 1500 --cutoff-mhz 1400 --sweep-start-mhz 1000 --sweep-stop-mhz 2000 --sweep-step-mhz 100 --pth-plating-um 25 --dielectric-material 361:4.2:0.02 --dielectric-material 362:4.2:0.02 --dielectric-material 363:4.2:0.02 --prepare-only
```

Wartości **4.2/0.02 i 25 µm są wyłącznie przykładem jawnych
założeń użytkownika, nie danymi z `.epro` ani zweryfikowanym materiałem**.
Źródłowe εr/tanδ z poprawnego CAD mają pierwszeństwo, jeśli nie ma
jawnych nadpisań. Użytkownik może też użyć `dielectrics` w pełnym
`--source-config` (wtedy nie łączyć z oddzielnymi flagami).

Test regresyjny `tests/test_pcb_easyeda_stackup.py` analizuje prawdziwy
`gerbs/stripline1/stripline1.epro`: TOP(1), Inner1(15), Inner2(16),
BOTTOM(2) i trzy SUBSTRATE(361,362,363). Sam poprawny import geometryczny
nie oznacza poprawności S11; nadal wymagane są audyty portu, siatki,
weryfikacja czasu FDTD i zbieżność EM.

## Automatyczne source-config z pełnego projektu .epro

Nowy tryb źródłowy **nie wymaga** ręcznego `--source-config`. Dla dokładnie
jednego oznaczonego źródła CAD (CSRC / Solver Role=source) bierze source_index
ze źródła. Wartości R/L/C czyta najpierw z atrybutu `Value` instancji PCB,
a gdy jest nieobecny, z jej jawnie powiązanego Device. Typ wynika z
jednoznacznej jednostki wartości, a NIE z footprintu. Niejednoznaczne lub
sprzeczne wartości powodują błąd przed FDTD.

Kontroler zapisuje automatycznie `source-config.resolved.json` w katalogu
przebiegu oraz pochodzenie wartości w `import.json`. `--source-config`
nadal umożliwia użycie własnej, pełnej konfiguracji bez automatycznych zmian.

Dodatkowo **samodzielny generator działa bez parsowania geometrii** (może
więc przygotować JSON również dla archiwum z nieobsługiwanym rysunkowym
rekordem DIMENSION, choć samo FDTD nadal wymaga obsługi tego rekordu):

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.easyeda_auto_config --easyeda-project gerbs\dif400\dif400.epro --output parameters\dif400_source.local.json
```

Plik nie jest nadpisywany, jeżeli już istnieje. Brak informacji fizycznych
nie jest wypełniany automatycznie. Jeśli projekt ma PTH, a brak zapisanej
grubości galwanizacji, jawnie wybierz wartość np. `--pth-plating-um 25`
(**wyłącznie świadome założenie użytkownika, nie odczyt CAD**). Można ją podać
bezpośrednio w `easyeda_control` bez pliku JSON. Wartości R/L/C nadal są
idealne; brak modeli pasożytniczych nie jest uzupełniany z biblioteki 3D.

Przykład PREPARE-ONLY bez pliku konfiguracyjnego, dla projektu bez PTH:

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.easyeda_control --easyeda-project gerbs\dif400\dif400.epro --quality preview --geometry-resolution-um 10 --fields-mhz 1500 2000 --prepare-only --center-mhz 2000 --cutoff-mhz 1900 --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10
```

Brak obsługi `DIMENSION` jest osobnym ograniczeniem parsera, nie jest
naprawiany przez generator source-config.

## Source full-wave — most D4 → istniejący PCB openEMS (2026-10-22)

FAST/coupling jest zamrożony. `antenna_lab.pcb.easyeda_control` przyjmuje
`.epro` i opcjonalny `--source-config` (automatyka opisana powyżej). Korzysta z D4, walidacji canonical,
jednej normalizacji i istniejącej geometry resolution. Następnie wywołuje
`make_gerber_mesh_anchor_plan` / `make_pcb_domain_mesh(gerber_quality=...)`:
historyczna nazwa oznacza istniejący feature-aware mesher CopperPolygon,
nie odczyt Gerberów. Nie ma fallbacku ani reconciliation z Gerber/Excellon.
Materiał/stackup i PEC pozostają ze source. Brak jawnej wartości elementu
pasywnego blokuje pełny solve; CSRC=0 pozostaje źródłem, nie kondensatorem.

Profile i argumenty openEMS pochodzą z `parameters/openems_profiles.toml` oraz
istniejącego `resolve_profile`/`approve_profile`. Są te same `--quality`,
`--openems-config`, `--openems-set`, `--yes`, `--no-fields`, `--fields-mhz`,
center/cutoff/frequencies/sweep. Nie zmieniono limitów, grading, paddingu/PML,
feature compaction, portu, PTH, RLC ani równań. Duża siatka/istniejący guard
ma być raportowany, nigdy automatycznie łagodzony.

Przykład **jawnych założeń testowych**, do zapisania przez użytkownika jako
`parameters/spirala_source.local.json`. 25 µm i 49.9 Ω nie są odczytem z CAD;
zastąp je własnymi jawnymi danymi, jeśli odbiegają od zamierzonego eksperymentu:

```json
{
  "port": {"mode": "source", "source_index": 0},
  "drills": {"pth_model": "solid_pec_equivalent", "pth_plating_um": 25},
  "component_values": {"R1": {"kind": "R", "value": "49.9ohm"}}
}
```

Windows CMD, najpierw przygotowanie (bez Run):

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.easyeda_control --easyeda-project gerbs\emtest4\spirala.epro --source-config parameters\spirala_source.local.json --quality preview --geometry-resolution-um 10 --prepare-only --center-mhz 2000 --cutoff-mhz 1900 --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10
```

Dopiero po inspekcji prepare, ten sam tor uruchamia istniejący FDTD:

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.easyeda_control --easyeda-project gerbs\emtest4\spirala.epro --source-config parameters\spirala_source.local.json --quality preview --geometry-resolution-um 10 --center-mhz 2000 --cutoff-mhz 1900 --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10
```

Domyślnie `outcomes/pcb_easyeda/spirala_NNN`; jawny `--output` ma pierwszeństwo,
a istniejące niepuste wyniki są odrzucane. Zapisane snapshots: project.source,
component_bindings, source_ir, source_model, geometry.source,
geometry.normalized_source, geometry, import i summary (JSON). Przy odmowie
pozostają dane uzyskane do danego etapu, `failed_stage` i dokładny błąd.
`geometry.json` powstaje dopiero po udanej projekcji. Controller przechowuje
snapshots do wyjścia, ponieważ istniejący run_control_model wymaga początkowo
pustego katalogu. Przygotowanie daje `native/model.xml`; solve korzysta ze
starych CSV/statystyk/pól/raportu, bez nowej pętli Run. Błąd raportu jest best-effort.

`summary/import`: design_source=easyeda_project, manufacturing_validation=
not_requested, archive SHA/PCB ID/source SHA, jawne source-config, profil,
geometry resolution i mesh/cost. Prepared/ukończenie nie zatwierdza fizyki.
**Sprawdzenia bez native: 5 testów mostu + 1 regresja Gerber CLI PASS.**
Syntetyczny .epro korzysta z rzeczywistego feature-aware mesha/preflight;
XML i wynik są atrapami granicy native. Realna spirala przechodzi D4,
normalizację i projekcję do granicy planu kotwic. Pełnej siatki spirali tutaj
nie liczono, jej cell_count oraz natywny XML/FDTD pozostają **niezweryfikowane**.
Uruchom Windows prepare-only, zapisz koszt lub dokładny guard. Nie optymalizować
kosztu siatki w ramach tego checkpointu.

## Aktualne użycie i wynik D4

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-project gerbs\emtest4\spirala.epro --inspect-source
```

Przy wielu PCB podaj `--source-pcb-id UUID` z mapy `project.json.pcbs`.
Powstają `project.source.json` (pełny detached manifest/records/hash),
`component_bindings.json` (wybrana biblioteka, PAD ID/number/net),
`source_ir.json`, `source_model.json`, `import.json` i `summary.json`.
Inspekcja materializuje pady, union miedzi per warstwa/net i audyt kontaktów;
nie tworzy Z/S11. Wyjątek zapisuje `status=failed` i przyczynę, a dostępne
wcześniejsze snapshots pozostają. Nieobecny/niewspierany dokument nie staje
się domyślną geometrią.

**Spirala: canonical PASS, nie electromagnetic PASS.** Archiwum w Git:
`gerbs/emtest4/spirala.epro`. Rzeczywiste 2 COMPONENT / 4 PAD_NET / 4 pady
R0603, 6 LINE / 7 ARC / 2 VIA, nety A/B i 4 conductors. CSRC ma source_index=0.
Potwierdzono kontakt wszystkich czterech padów, PcbGeometry, normalizację
oraz — przy jawnych testowych założeniach metalizacji i R1 — port i PTH.
D3 wyznacza 5 LINE + 7 ARC aktywnego netu A, 36.373621555 mm osi.
Graf zapisuje `reduced_model.json`; solve odmawia na `curved coupling analysis
unsupported` (PCB-015C), nie emituje Z/S11. 2 ground-PTH oraz R1 pozostają
w grafie. Parametry 25 µm i 49,9 Ω były jawne, wyłącznie testowe.
Automatyczny katalog to `outcomes/pcb_reduced/spirala_NNN`, także dla inspekcji.
Nie nadpisuje dawnych wyników; `--output` ma pierwszeństwo.

**PSU: identity PASS, physical canonical UNSUPPORTED.** Archiwum
`gerbs/test_psu/test_psu.epro`: kod potwierdził 291 komponentów, 906 mapowań
numer+ID, 288 jawnych footprintów PCB + 3 fallback Device; 257 bibliotek
zewnętrznych + 34 embedded. Pierwsza odmowa fizycznego parsera: pusty `NET`
(PCB record 145). Są też biblioteki 1.3/1.7, slots i bogatsze pours/stackup;
nie uznano ich za obsługiwane. 291/906 nie jest dowodem kontaktów PSU.

## Bezpieczeństwo i zakres geometrii

ZIP odczytywany w pamięci, bez ekstrakcji. Sprawdzane CRC wszystkich plików,
duplikaty (także case-insensitive), traversal/absolutne ścieżki, symlinki,
szyfrowanie i strict JSON (również duplicate keys/NaN/Inf). Limity zapisane
w provenance: 128 MiB archiwum, 64 MiB/member, 256 MiB łącznie, 4096 members,
1 mln linii/document, compression ratio 1000. To limity importu, nie fizyka.

PCB: DOCTYPE 1.8, editor 2.2.x. FOOTPRINT 1.8 może nie mieć HEAD i może mieć
puste separatory `[]`. Starsze 1.3/1.7 są indeksowane tylko dla kontroli
referencji; użycie ich geometrii kończy się jawnym błędem. Dokładny UUID ma
pierwszeństwo przed aliasem HEAD.source; wieloznaczny alias jest błędem.
Jawny Footprint PCB wygrywa nad Device, również jeśli Device nie istnieje.
Fallback Device jest możliwy tylko przy braku jawnego Footprint. Model 3D
nigdy nie wybiera miedzi.

Pady: RECT bez rounded corners, okrągły ELLIPSE/ROUND, OVAL; warstwy top/bottom.
Round through PAD wymaga MULTI i jawnego plated=0/1; holes są odejmowane także
od pourów. Per-layer padstack, slots, custom polygons i nieznane fizyczne
prymitywy footprintu są odrzucane. Znane artwork mask/paste/silk/model są
pomijane z zapisem IDs; raw zostaje. Specyfikacja:
[PAD](https://github.com/easyeda/easyeda-file-format-v2/blob/63f38c2758cbe2456e8b5c7e76469369430d94af/docs/en/pcb/primitives/pad.md),
[COMPONENT/PAD_NET](https://github.com/easyeda/easyeda-file-format-v2/blob/63f38c2758cbe2456e8b5c7e76469369430d94af/docs/en/pcb/package/component.md).

Transformacja: lokalny obrót pada → jego lokalny środek → dla bottom odbicie
lokalnego Y → CCW obrót instancji → pozycja PCB. Zmienia się strona top/bottom;
THT pozostaje through. Źródłowy układ +Y-up i skala mil zachowane; dla ćwierć
obrotu współczynniki dokładne 0/±1. Jest to odpowiednik `Flip TOP_BOTTOM` i
`SetOrientationDegrees` importera KiCad Pro po uwzględnieniu jego screen-Y.
Offset round drill jest w osiach pada. Nie dodano snappingu ani nowej tolerancji.
Krzywe padów używają dotychczasowego `CURVE_ERROR_M` importera.

Fizyczny audyt: finalna miedź jest unionem per net/layer; przecięcie różnych
netów jest zwarciem. Każdy pad/stroke musi mieć dokładnie jednego właściciela.
Kontakty padów są zapisywane jako rzeczywiste przecięcia; izolowany pad nie
zyskuje fikcyjnego połączenia. Przynależność PTH do warstw sprawdzana geometrycznie,
a metalizacja nie może dotknąć obcego netu. Otwór nie ujawnia grubości plating.
Top/bottom i jeden dielektryk to nadal zakres canonical; epsilon_r=1 i duża
grubość są legalne, bez narzuconej typowej FR4.

## Jawny kontrakt elektryczny FAST

`--source-config` może podać istniejący port explicit albo wybrać jawne źródło:

```json
{
  "port": {"mode": "source", "source_index": 0},
  "drills": {"pth_model": "solid_pec_equivalent", "pth_plating_um": 25},
  "component_values": {"R1": {"kind": "R", "value": "49.9ohm"}}
}
```

To **przykładowe jawne założenia**, nie odczytana/zweryfikowana grubość plating
ani automatyczna elektryka Device. Port source wymaga dwóch prostokątnych,
osiowych top SMD padów 1/2; rzeczywista szczelina pochodzi z union miedzi,
a pełna szerokość i pusty interior przechodzą istniejący audyt. Oblique/custom
contacts wymagają dalszej implementacji; explicit port pozostaje obsługiwany.
R/L/C są idealne, wartości z jednostkami podaje `component_values`. Brakujący
model elektryczny nie jest pomijany w solve. Indeks CSRC nie jest pojemnością.
Dalsze źródła można jawnie oznaczyć `Solver Role=source`; indeksy muszą być
unikalne i ciągłe od zera. Canonical zachowuje je, lecz obecny FAST przyjmuje
jedno wzbudzenie i odrzuca wiele źródeł. RLC/źródła nie są wywodzone z 3D.

PTH solver używa wyłącznie dotychczasowego solid PEC equivalent i jawnego
plating; NPTH nie jest połączeniem (FAST nadal nie obsługuje NPTH).
Full-wave/mesh/PML nie zostały zmienione. D3 Arc TL, PCB-015C coupling i D2
manufacturing reconciliation pozostają OPEN. Gerber nie jest fallbackiem.

## Reguły projektanta: nadrzędność footprintu PCB i specjalne źródła

**To jest kontrakt użytkownika, nie domniemany standard EasyEDA.**

- **Geometria miedzi i padów**: liczy się footprint faktycznie wybrany
  i umieszczony przez projektanta w dokumencie PCB. Nazwa/footprint
  z bibliotecznego `Device` nie może nadpisać tego wyboru;
  gdy `Device` wskazuje inną rodzinę footprintów,
  **nie zgłaszaj konfliktu wyłącznie na tej podstawie**.
  Niezgodność dopiero między geometrią rzeczywistego PCB
  i wskazanym plikiem `.efoo` to rzecz wymagająca audytu.
- Dla **niepolaryzowanych pasywnych** elementów użytkownik
  ręcznie wybiera obudowy rodziny rezystorów niezależnie
  od rodzaju R/C, np. footprint **`R0603` dla kondensatora**
  zamiast bibliotecznego `C0603`. To świadoma zasada
  unifikacji wymiarów padów. Decyzja o konkretnym
  footprintcie zawsze należy do użytkownika; nie wymuszaj
  zmiany na `R*` automatem ani nie zgaduj geometrii.
- **Model/bryła 3D** jest powiązany z komponentem/Device
  i nie wybiera fizycznego footprintu używanego
  w analizie elektromagnetycznej. Różnica modelu 3D
  i nazwy obudowy bibliotecznej nie jest kolizją padów.
- **`CSRC` z `Value=0` oznacza źródło sygnału nr 0.**
  `0` jest indeksem źródła, a **nie pojemnością 0 F**.
  Kolejne **jawnie oznaczone** źródła, jeśli zostaną
  dodane, mają indeksy `1, 2, 3, ...`
  (każdy większy od poprzedniego o 1). Nazwy
  przyszłych źródeł nie zostały określone —
  nie traktuj dowolnego `C*` lub kondensatora
  z `Value=0` jako źródła.
- Kondensator `C1` i każdy inny nieoznaczony jako
  źródło kondensator to **zwykły element pasywny**.
  Dane `Device C0603/100 nF` nie nadają
  `CSRC` roli kondensatora; definicja
  `CSRC/Value=0` nadaje mu rolę wzbudzenia.
  Parametry portu i jego sposób wymuszenia muszą
  pozostać jawne w kontrakcie solvera.
- Przy resolverze `COMPONENT → FOOTPRINT → PAD → PAD_NET`
  rozdzielaj **geometrię PCB**, **tożsamość/rolę
  elementu** i **prezentację 3D**. Dopuszczaj `Device`
  jako wtórny indeks, jeśli **brak** jawnego footprintu
  instancji, rozwiązanie jest jednoznaczne i nie
  zmienia rzeczywistej geometrii. Brak informacji
  zgłaszaj fail-closed, bez zastępowania gerberem.

**Konkretna serpentyna**: `CSRC` i `R1`
w PCB wskazują ten sam `R0603` (pady e8/e7).
Biblioteczna definicja CSRC wskazuje `C0603`:
to **zgodne z regułą użytkownika**, nie konflikt.
Poprzednie raporty używały słowa „rozbieżność”,
gdy nie znaliśmy tej konwencji — poniższa
starsza obserwacja geometrii pozostaje historycznym
dowodem, ale nie jest błędem projektowym.

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

## Zakres parsera pojedynczego .epcb (legacy D0/D1)

DOCTYPE, HEAD, CANVAS, LAYER, LAYER_PHYS, NET, LINE, ARC, VIA, PAD_NET,
COMPONENT i ATTR. POLY: niezaokrąglone R (dowolny obrót) i proste
kontury L. POUR / POURED: **wiele konturów L/R/ARC/CARC**
(także jawne R isCCW, signed arcs oraz przejścia ARC ↔ L) z regułą
nonzero, z aproksymacją krzywizny do 0,1 µm przed siatkowaniem
(oddzielne wyspy, dziury według orientacji/winding); tylko prawdziwe
materializowane wypełnienie POURED jest fizyczną miedzią, a POUR wyznacza
granicę. POURED nadal wymaga fill=true i stroke=0; termiczne spoke,
grid fill, cubic Bezier/CIRCLE oraz niepoprawne kontury pozostają
jawnym UNSUPPORTED. Dla wielu wysp osobne fizyczne identyfikatory przewodnika
nie zmieniają pierwotnych ID/rekordów źródłowych.
Raw pola, wartości i źródłowe SHA pozostają niezmienione. Unknown records
są zachowane i blokują canonical solve, chyba że są rozpoznanym metadata
edytora lub mają prefiks META_. Nie ma topologicznego repair ani domyślnej
zamiany nieznanego wypełnienia na pełną miedź.

Przypadek regresyjny z repozytorium `gerbs/stripline1/stripline1.epro`
(dodany 2026-10-23): `POURED e102` (PCB record 230) zawiera duży
prostokąt i pięć otworów z dwóch `ARC 180`; `POURED e103`
(PCB record 234) zawiera prostokąt i pięć zaokrąglonych otworów
z naprzemiennymi `ARC 90` i `L`. Samo odblokowanie `len(paths)>1`
nie wystarcza: kontury należy fizycznie odtworzyć. Test źródłowego
archiwum jest w `tests/test_pcb_easyeda.py`. Ten projekt zawiera
13 `LAYER_PHYS` i wewnętrzne pola miedzi na warstwie 16: poprawny
import konturów **nie oznacza** jeszcze obsługi jego stackupu ani
gotowości do FDTD. Obecny model canonical dopuszcza tylko top / jeden
substrate / bottom; nie wolno pomijać dodatkowych warstw przy solve. Dokumentacja formatu:
[Complex Polygon](https://github.com/easyeda/easyeda-file-format-v2/blob/main/docs/en/pcb/polygon-system/complex-polygon.md),
[POURED](https://github.com/easyeda/easyeda-file-format-v2/blob/main/docs/en/pcb/polygon-system/poured.md).

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


## Historyczne sprawdzenia przed D4 — nie bieżący stan

Poniższe audyty dokumentują etap przed dodaniem archiwów i implementacją D4.
Uwagi o braku archiwów w Git/importera nie opisują już aktualnego kodu.

### Sprawdzenie checkpointu 2026-10-21

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

### Pełny projekt serpentyny `spirala.epro` — audyt źródła 2026-10-21

Użytkownik przekazał **w załączniku rozmowy, a nie w repozytorium** plik
`spirala.epro` (9410 bajtów, SHA256
`d94187520eaf519afd6fa3ba8625a3aa43d2b03a9a9178a924ac98586e504132`). Plik ma nagłówek ZIP, poprawny spis treści i CRC
(`ZipFile.testzip() = None`); zawiera `project.json`, 1 dokument PCB
(`PCB/c057cdd3b5394bc0ae3ac7797c9d7554.epcb`), dwie definicje
footprintów `.efoo` i dwa symbole `.esym`. Wewnętrzny plik PCB ma
198 rekordów: 2 `COMPONENT`, 4 `PAD_NET`, 6 `LINE`, 7 `ARC`,
2 `VIA` i 1 `POURED`. Kontrola rekordów z repozytoryjnym
`gerbs/realpcb_microstrip/test_spirala.epcb` potwierdza zgodność
zawartości grup rekordów (CRC32 dla każdego typu, w kolejności w ramach
typu), choć **całe bajty pliku nie są identyczne** (inna kolejność
przeplatania typów rekordów).

**Rozwiązano brakującą zależność na poziomie danych wejściowych:**
`FOOTPRINT/e8bf627583724bdebefbaa0be79b0d2f.efoo`
ma `DOCTYPE FOOTPRINT 1.8`, nazwę biblioteczną `R0603`
i dwa pady prostokątne SMD (bez otworów):
- nr **2**, ID `e7`, lokalne `(+29.66, 0)` mil,
  prostokąt `31.751 × 34.016` mil;
- nr **1**, ID `e8`, lokalne `(-29.66, 0)` mil,
  ten sam prostokąt.
Po obrocie instancji **+90°** oba `COMPONENT` przypisują
pad 1 do netu `A` i pad 2 do `B`, a każdy rekord `PAD_NET`
zgadza się **zarówno numerem, jak i ID pada**. Środki kontaktów w mm
(PCB source 1 mil = 0.0254 mm):
- `CSRC` (2.921, 13.716 mm): pad 1 `A` = (2.921, 12.962636),
  pad 2 `B` = (2.921, 14.469364);
- `R1` (20.32, 13.716 mm): pad 1 `A` = (20.32, 12.962636),
  pad 2 `B` = (20.32, 14.469364).

Net `A` tworzy serię 7 `ARC` i 5 `LINE` między padami A;
obliczona wyłącznie **geometryczna** suma długości środkowych
(łuki z chord + signed sweep) to ok. **36.3736 mm**, bez efektów
sprzężeń/zakrętów. Net `B` ma m.in. dolny `POURED` i
2 przelotki: lewa przez krótki `LINE` dochodzi do padu CSRC B,
prawa leży wewnątrz padu R1 B (odchyłka środka ok. 0.34 mil).
Te relacje są sprawdzeniem statycznym; fizyczny audyt kontaktów,
plating VIA, układu warstw i ograniczeń modelu FAST nadal jest konieczny.

**Wyjaśniony świadomy wybór footprintu i źródła:**
instancja `CSRC` ma płytkowy `Footprint=R0603`,
choć `Device=9031e3536a2e4419aaeb7e74753ecfcc`
w `project.json` wskazuje `C0603`
(`56832cdf4ece4990869c9dd017ff7c16.efoo`).
Geometrie faktycznie różnią się: `R0603` ma lokalne
środki padów ±29.66 mil i 31.751 × 34.016 mil,
a `C0603` ±27.56 mil i 31.496 × 35.433 mil.
**To NIE jest konflikt:** projektant ręcznie
wybiera `R0603` dla niepolaryzowanych elementów.
Do modelu geometrii należy więc wziąć **tylko
rzeczywiste `R0603` z instancji PCB**.
`CSRC` ma `Value="0"`, czyli źródło nr 0,
nie kondensator 0 F ani biblioteczny kondensator
**100 nF**. R1 ma w Device nominalnie **49.9 Ω**;
to nie uzasadnia automatycznej podmiany
jawnej konfiguracji elektrycznej.
Nie zgłaszaj ostrzeżeń o niezgodności Device/PCB
dla takiej zamierzonej praktyki i nie
zmieniaj geometrii na podstawie Device.

**Stan implementacji:** źródłowa geometria CSRC/R1 jest dostępna
w załączniku `.epro`, ale obecny parser przyjmuje pojedynczy
`DOCTYPE PCB`, a `easyeda_model.py` nie instancjonuje `.efoo`.
Przygotować bezpieczny import `.epro` i projektowy resolver,
obsłużyć także profil `.efoo` bez wymaganego `HEAD`,
import padów z pozycji lokalnej do SI, identyfikatory PAD_NET i
jawny audyt. Po tym **7 Arc TL oraz pairwise coupling wciąż
blokują pełny wynik rzeczywistej serpentyny**. Nie dodano
`spirala.epro` do Git; kolejny agent musi uzyskać ten załącznik
ponownie albo użytkownik musi dopuścić wersjonowanie małej próbki.

**Sprawdzenia:** tylko odczyt archiwum, CRC, JSON, porównanie klas
rekordów, resolve 2/2 footprintów i 4/4 PAD_NET oraz matematyka
geometrii, bez uruchamiania kodu projektu, pełnej suite,
natywnego FDTD lub benchmarków.


## Ponowne przetwarzanie full-wave

EasyEDA i Gerber używają wspólnego kontraktu [pcb-postprocess.md](pcb-postprocess.md).
`pcb-run.json` zapisuje pełną specyfikację przed Run. CLI `pcb.postprocess`
nie wymaga ponownego importu .epro ani FDTD. Błąd statystyk nie blokuje
odczytu portu; status zakończenia czasowego pozostaje wtedy niepotwierdzony.
Pola i raport mają oddzielne statusy. Legacy bez wymaganych artefaktów jest
odrzucany z listą braków — nie odtwarzamy parametrów z bieżącego profilu.

Raporty pól z .epro korzystają ze wspólnego ROI PCB: domyślnie active+geometry,
−40 dB, margines 1 mm. Nowy kadr można otrzymać poleceniem `report` na zapisanych
wynikach, bez ponownego importu ani FDTD. Kontrakt i opcje: [fields.md](fields.md).
