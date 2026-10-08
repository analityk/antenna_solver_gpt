# Rozdzielczość geometrii PCB — PCB-012A/012B/012C

Od PCB-012C produkcyjny `pcb.gerber_control` używa domyślnie **10 µm**
rozdzielczości geometrii. Wybór `--geometry-resolution-um {100,10,1,0.1}`
jest niezależny od preview/design/verify. Typ tickowy po audycie materializuje
się do zwykłego PcbGeometry; adapter nie dostaje nowego typu geometrii.

Przed PCB-012C produkcja korzystała ze znormalizowanej surowej geometrii.
Zmiana domyślna może zmienić koszt siatki. Nie jest deklaracją zbieżności.
**10 µm geometrii nie tworzy siatki 10 µm**: stare reguły EM nadal wyznaczają
kroki float; legalne są kroki mniejsze od rozdzielczości geometrii i linie
niepokrywające się z kratownicą geometrii.

## Arytmetyka i reprezentacja

`antenna_lab.pcb.grid.PcbGrid(quantum_nm=10000)` wybiera 10 µm.
Obsługiwane wartości w nanometrach: `100000`, `10000`, `1000`, `100`
(czyli 100, 10, 1 i 0,1 µm). Wszystkie współrzędne w
`QuantizedPcbGeometry` są całkowitymi tickami. Typy są zamrożone, kolekcje
są krotkami. Metry powstają wyłącznie na granicy wejścia/raportu/eksportu.

`nearest_tick(metres)` zaokrągla połowy od zera, symetrycznie dla znaków.
`floor_tick()` i `ceil_tick()` mają zwykłą semantykę matematyczną także dla
liczb ujemnych. String i Decimal zachowują dokładną wartość dziesiętną.
Dla wejściowego float stosowana jest jawna osłona dwóch ULP przy granicy
całkowitego/połówkowego ticka: ślad arytmetyki binarnej nie zmienia remisu.
To nie jest tolerancja łączenia geometrii; istniejące tolerancje są nietknięte.

```python
from decimal import Decimal
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.quantization import quantize_pcb_geometry, QuantizationError

grid = PcbGrid(10000)
assert grid.nearest_tick(Decimal('0.000155')) == 16
assert grid.nearest_tick(Decimal('-0.000155')) == -16
assert grid.to_metres(35) == 0.00035

# physical_geometry pochodzi z istniejącego importera. Brak uruchomienia solvera.
try:
    tick_geometry, audit = quantize_pcb_geometry(physical_geometry, grid)
except QuantizationError as error:
    audit = error.audit  # FAIL; żaden model solvera nie zostaje zwrócony.
```

## Zakres projekcji

Kwantyzowane są obrysy PCB i dielektryków, miedź z otworami, położenia
warstw, piny, styki, okna kontaktowe, port, pozycje i kołowe wymiary wierceń.
Nie ma osobnej reguły rozdzielczości elementów RLC.

Grubości kolejnych dielektryków otrzymują całkowitą liczbę ticków, po czym
interfejsy są akumulowane od z=0. Miedź korzysta z tych samych płaszczyzn.
Warstwa znikająca do zera jest błędem. Parametry elektryczne i materiałowe,
w tym **grubość materiałowa conducting sheet**, pozostają niezmienione.

Dla koła parametrem geometrycznym jest promień: zaokrąglamy go do ticka,
a średnica modelowana wynosi dokładnie dwa promienie. Zapobiega to promieniom
połówkowym. Średnica źródłowa pozostaje w provenance; raport ujawnia również
jej zmianę. Promień solid PEC via jest kwantyzowany niezależnie od promienia
wiercenia; grubość galwanizacji jest zachowanym wejściem źródłowym, nie nową
geometrią powłoki. Nie dopuszczamy zerowych promieni.

`source_json` przechowuje niemutowalną kopię modelu podanego do kwantyzacji
(w kandydacie: po normalizacji), wraz z wartościami i SHA256.
`.provenance` oraz `.as_dict()` zwracają odłączone
kopie JSON. Funkcja nie zmienia żadnego pliku ani źródłowego PcbGeometry.
Ten typ opisuje wyłącznie geometrię PCB, nie powietrze/PML ani osie FDTD.
Nie wymaga się kwantyzowania wyników działania meshera.

## Audyt

Usuwane są tylko kolejne identyczne wierzchołki tickowe (także powtórzone
zamknięcie pierścienia). Nie ma `make_valid`, wygładzania ani naprawy buforem.
Zanik wielokąta, otworu, szczeliny lub wymiaru powoduje błąd. Kontrole obejmują:
ważność obrysów i otworów, liczby obszarów/otworów na warstwie i dla każdego
rekordu miedzi, kontakty pomiędzy rekordami, własność końców portu i elementów,
pustą szczelinę, pełny kontakt portu, połączenia przelotek z konkretną miedzią,
wyjście wiercenia poza płytkę oraz kolizje wierceń i portu.

Audyt wykorzystuje istniejący Shapely na współrzędnych tickowych, z limitem
wartości 2**52 dla dokładnego przeniesienia liczb całkowitych do backendu.
Kontakty PTH używają analitycznej odległości od obszaru miedzi; NPTH odejmuje
koło aproksymowane 128 odcinkami na ćwiartkę, jak dotychczasowe widoki.
Bufor koła reprezentuje otwór — nie służy naprawie niepoprawnego wielokąta.

Metadane liczą **wystąpienia skalarów przestrzennych**, nie unikalne punkty
ani węzły przyszłej siatki. Alias starego substrate i surowe provenance nie
są liczone ponownie. Maksimum XY uwzględnia euklidesowe przesunięcia punktów
oraz zmiany wymiarów. Maksimum Z uwzględnia również skumulowane przesunięcia
interfejsów. Przykładów jest najwyżej 20; wynik jest deterministyczny.

PASS oznacza zachowanie sprawdzanej topologii, **nie** dokładność obliczeń
EM; gotowość eksportu sprawdza osobno istniejący adapter.

Audyt porównuje również relacje połączenia wszystkich sprawdzanych terminali
przez miedź i PTH. Dzięki temu sama zgodność liczby obszarów nie może ukryć
przeniesienia rozcięcia NPTH lub zwarcia inną ścieżką.

## Diagnostyka danych produkcyjnych, q = 10 µm

Odłączony audyt na geometrii zaimportowanej z fizycznym
`parameters/pcb_fr4_2layer_pth.json`, bez normalizacji i bez FDTD:

| Dane | Zmienione / zbadane wartości przestrzenne | Maks. ruch XY | Maks. zmiana Z | Topologia |
| --- | ---: | ---: | ---: | --- |
| emtest3 | 550 / 577 | 6,820704 µm | 0 | PASS |
| emtest4 | 4540 / 4566 | 7,019105 µm | 0 | PASS |

W emtest3 zachowano po jednym obszarze miedzi na top/bottom; w emtest4
cztery na top i jeden na bottom. W obu zachowano kontakt PTH top–bottom.
Przykłady projekcji: 4,393995 → 4,390000 mm (emtest3),
13,365880 → 13,370000 mm (emtest4), 10,245430 → 10,250000 mm (arytmetyka).
Nie zmieniono źródeł ani ich SHA256. Nie wykonano migracji aktywnego solvera;
jego komórki i koszt FDTD nie ulegają zmianie w tym tickecie.

## PCB-012B: rozdzielczość geometrii przed istniejącym mesherem

**Wycofano eksperyment integer-tick FDTD mesh z 9b72de4.** Usunięto osobny
mesher tickowy i jego testy. Liczby całkowite są teraz reprezentacją geometrii
na etapie jej upraszczania, nie wymogiem na osie ani komórki FDTD.

Rozdzielczość geometrii oznacza: „nie reprezentuj szczegółów przestrzennych
CAD dokładniej niż ta skala”. Rozdzielczość EM wynika osobno z długości fali,
portu, podłoża, gradingu i wybranego profilu preview/design/verify. Komórka
może mieć 1 mm albo mniej niż rozdzielczość geometrii. Linia 137,43 µm jest
legalna. Nie ma warunku `cell >= geometry_resolution` ani wymogu całkowitych
wielokrotności tej rozdzielczości w siatce. Precyzja zapisu CAD nie oznacza
dokładności fizycznej ani dokładności symulacji.

Wyłącznie jawna ścieżka wewnętrzna/testowa:

```python
from antenna_lab.pcb.bundle import load_bundle_geometry
from antenna_lab.pcb.grid import PcbGrid
from antenna_lab.pcb.geometry_resolution import prepare_geometry_resolution_candidate
from antenna_lab.pcb.gerber_quality import gerber_quality_settings

_, source, import_info = load_bundle_geometry(
    'gerbs/emtest4', 'parameters/pcb_fr4_2layer_pth.json')
settings, _ = gerber_quality_settings(
    'preview', excitation_center_hz=2e9, excitation_cutoff_hz=1e9,
    result_frequency_hz=tuple(f*1e6 for f in range(1500, 2501, 10)))
candidate = prepare_geometry_resolution_candidate(
    source, settings, grid=PcbGrid(10000), quality='preview')
```

Kolejność: istniejący import → jedna istniejąca normalizacja → PCB-012A
`quantize_pcb_geometry` i audyt → `materialize_quantized_geometry` → zwykłe
`PcbGeometry` w metrach → niezmienione `make_gerber_mesh_anchor_plan` oraz
`make_pcb_domain_mesh`. Następuje pełny dotychczasowy audyt portu i boxów
elementów. Sam helper diagnostyczny nie tworzy XML, natywnych obiektów ani Run.
Produkcja korzysta ze wspólnego `apply_geometry_resolution(normalized, grid)`;
powyższy przykład pozostaje odłączony i niczego nie zapisuje.

Materializacja konwertuje ticki na metry raz. R/L/C, epsilon, straty,
przewodność, materiałowa grubość conducting sheet, identyfikatory i hashe
pozostają niezmienione. Surowa geometria przed normalizacją i transformacja
są oddzielnymi danymi pochodzenia. Dane źródłowe nie odtwarzają kotwic.

PTH wymaga jawnego rekordu `QuantizedPcbDrill`, dziedziczącego po zwykłym
`PcbDrill`: zachowuje średnicę źródłową i zastosowaną rozdzielczość.
Walidator sprawdza **dokładną projekcję PCB-012A** średnicy i promienia,
zamiast wymuszać dawną zależność na już kwantyzowanych liczbach. Przykład:
średnica źródłowa 0,305 mm → modelowana 0,30 mm, promień zewnętrzny
0,1775 mm → 0,18 mm; wejście galwanizacji nadal wynosi 25 µm.
Nie zmieniamy galwanizacji na 30 µm, żeby sztucznie odtworzyć starą sumę.
Kontakty z miedzią, kolizje, liczba warstw i własność terminali są nadal
sprawdzane. Zwykły `PcbDrill` zachowuje stary kontrakt i identyczny zapis JSON.

Diagnostyka `geometry_and_mesh` dla każdej osi rozdziela:

- `minimum_geometry_anchor_separation_m`: odstęp między różnymi fizycznymi
  współrzędnymi modelu, wraz z właścicielami/kategoriami najbliższej pary;
- `minimum_mesh_step_m`: rzeczywisty minimalny krok końcowej siatki EM.

Zbiór diagnostyczny geometrii zawiera m.in. wierzchołki, styki, środki/extrema
wierceń i interfejsy. **Nie oznacza** uczynienia wszystkich wierzchołków
kotwicami siatki. PCB-012G chroni szerokości miedzi/otworów przez kompaktowe cechy i audyt
reprezentacji brzegów, bez wymogu linii na każdej granicy; szczegóły:
docs/pcb-gerber.md, feature_aware_copper_v3. Nie zaliczamy numerycznych środków bbox, powietrza i PML do źródłowej
geometrii. Pochodne powierzchnie portu są raportowane bez dodatkowego
zaokrąglania; przy nieparzystej szerokości tickowej mogą mieć połówkowe
położenie — diagnostyka nie ukrywa tego przez zmianę modelu.

`format_modeled_mm` formatuje wyłącznie geometrię odpowiednio do skali
(10 µm → dwa miejsca w mm). Nie służy do częstotliwości ani R/L/C.
Pełne dane źródłowe pozostają dostępne jako provenance.

## Wyniki odłączonego eksperymentu po normalizacji

Ten sam config `pcb_fr4_2layer_pth.json`, preview, center 2000 MHz,
cutoff 1000 MHz, wyniki 1500–2500 MHz co 10 MHz. Zero przebiegów FDTD.
Koszt oznacza optymistyczne minimum przejścia impulsu, nie czas obliczeń.

| emtest4: rozdzielczość geometrii | Topologia | Kształt | Komórki | Min. siatki XYZ [µm] | Min. współrzędnych geometrii XYZ [µm] | Kroki impulsu | Aktualizacje komórek |
| --- | --- | --- | ---: | --- | --- | ---: | ---: |
| raw | PASS | 84×98×35 | 288120 | 54,026667 / 28,06 / 800 | 1,735e-12 / 1,735e-12 / 1600 (resztki float) | 34507 | 9942156840 |
| 100 µm | FAIL | — | — | — | — | — | — |
| 10 µm | PASS | 69×81×35 | 195615 | 83,333333 / 30 / 800 | 10 / 10 / 1600 | 30446 | 5955694290 |
| 1 µm | PASS | 84×98×35 | 288120 | 54 / 28 / 800 | 1 / 1 / 1600 | 34568 | 9959732160 |
| 0,1 µm | PASS | 84×96×35 | 282240 | 54,016667 / 28,1 / 800 | 0,1 / 0,1 / 1600 | 34469 | 9728530560 |

Zmiany/badane skalary: 100 µm: 4548/4566, 10 µm: 4548/4566,
1 µm: 4518/4566, 0,1 µm: 4511/4566. Maksymalna zmiana XY wraz z wymiarami:
odpowiednio 95; 6,934854; 1; 0,069619 µm. Maksymalna zmiana Z: 0.
95 µm dotyczy średnicy wyprowadzonej z promienia, nie przesunięcia punktu.

FAIL 100 µm jest prawidłowy: szerokość CSRC rośnie do 0,9 mm, podczas gdy
kwantyzowane powierzchnie kontaktowe miedzi obejmują 0,8 mm. Obie pełne
powierzchnie kontaktu przestają się mieścić. Komunikat audytu wskazuje
`port.negative` i `port.positive: full-width contact disconnected`.
Należy wybrać 10 µm lub dokładniej; nie generujemy siatki po tym błędzie.

Przy 10 µm zachowane są jedno CSRC, C1=100 pF, L1=18 nH, R1=49,9 Ω,
własność pinów/sieci, styki elementów i PTH top–bottom. Końce CSRC:
±0,35012 → ±0,35 mm; szerokość 0,8640064 → 0,86 mm. C1: współrzędne
końców X −4,04101/−4,34099 → −4,04/−4,34 mm. Wartości elektryczne są
kopiowane bez zaokrąglania. Boxy elementów używają istniejących poprzecznych
komórek i pierwszej komórki powietrza; ich numeryczne krawędzie nie muszą
pokrywać się z kratownicą geometrii. Oś Z jest identyczna jak w raw.

emtest3: raw 57×50×35=99750 → 10 µm 60×49×35=102900 (+3,16%).
Minima siatki: raw 350,12/385,800686/800 µm → 350/387,1875/800 µm.
Minima współrzędnych geometrii po projekcji: 10/10/1600 µm.
Przed projekcją: 1,735e-12/5,421e-14/1600 µm; pierwsze dwie liczby to
numeryczne różnice współrzędnych krzywych i powierzchni, nie dokładność PCB.
Kroki impulsu: 3483 → 3478; aktualizacje: 347429250 → 357886200.
Zmiany: 563/577, max XY 6,710696 µm, max Z 0. Zachowano dokładną rotację
ortogonalną i jeden zdeduplikowany PTH z kontaktami top–bottom.

Żaden poprawny topologicznie przypadek nie przekracza progu +5% komórek.
Wariant podstawowy emtest4 10 µm zmniejsza liczbę komórek o około 32,1%.
To potwierdzenie architektury i audytów, nie zbieżności fizycznego solve.



## PCB-012F: modelowana geometria jest nadrzędna wobec optymalizacji siatki

Rozdzielczość geometrii najpierw kwantyzuje fizyczny model. Siatka EM nie może
potem usuwać szerokości przewodników ani szczelin, które tę projekcję przetrwały.
Przykład przy 10 µm: 0,376 → 0,38 mm i 0,384 → 0,38 mm; równocześnie
0,25 → 0,25 mm i 0,38 → 0,38 mm muszą pozostać rozróżnialne. Testy używają
stałego środka, z granicami projektowanymi niezależnie; inne położenie środka
może zmienić zaokrąglenie granic. Nie zaokrąglamy ponownie modelu w mesherze.

To dwa niezależne parametry: wierność CAD i rozdzielczość długości fali FDTD.
Nie przywrócono siatki integer-tick ani globalnych komórek 10 µm. Między
krytycznymi kotwicami są dowolne linie float. Od PCB-012G granica miedzi może
leżeć wewnątrz komórki (reguła thirds lub audytowana reprezentacja subkomórkowa).
Szerokości pozostają jawnie audytowane; krzywe mają konserwatywny audyt obwiedni.
Jeśli audyt lub limit kosztu nie pozwala reprezentować modelu, przygotowanie
zatrzymuje się przed native. Nie podmienia go na tańszą geometrię.
