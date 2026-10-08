# PCB: katalog Gerberów → pojedynczy FDTD → raport lokalny

Podstawowym wejściem jest katalog, nie plik JSON. Program rozpoznaje top copper,
obrys, maskę, pastę, sitodruk, dolną/wewnętrzną miedź i pliki wierceń.
Gerbonara 1.6.3 parsuje RS-274X i metadane FileFunction; nazwy/rozszerzenia
konwencjonalne uzupełniają role. Lista plików, role, SHA256 i pominięcia są
zapisywane w import.json oraz summary.json. Przeglądany jest bezpośrednio
wskazany katalog (bez rekurencji).

Wymagane są dokładnie jedna górna miedź i jeden użyteczny zamknięty obrys.
Niejednoznaczność wyświetla nazwy kandydatów. Maska, pasta i sitodruk zostają
zidentyfikowane i pominięte. Konfiguracja v1 dopuszcza tylko górną miedź;
wersja v2 jawnie określa cały stackup, w tym dolną i wewnętrzną miedź.
Wiercenia i Gerber bez ustalonej roli blokują przebieg.

Shapely 2.1.x składa regiony, pady oraz linie/łuki o kołowym przekroju pisaka:
dark dodaje, clear odejmuje w kolejności obiektów/prymitywów z Gerbonara.
Każdy połączony obszar w jednej warstwie daje jeden CopperPolygon. Miedź
z różnych warstw nigdy nie jest sumowana. GKO opisuje środek linii
obrysu, nie krawędź pisaka. Importer przelicza współrzędne na SI; potem
istniejąca transformacja normalizuje port dokładnie raz.


## Rozdzielczość geometrii (PCB-012C)

`--geometry-resolution-um {100,10,1,0.1}` domyślnie wynosi **10 µm**,
także przy wejściu legacy JSON. Python: `run_gerber_control(...,
geometry_resolution_um=10)`. Wartość określa dokładność modelu CAD,
a nie rozdzielczość komórki FDTD. Profil preview/design/verify pozostaje
niezależny. 10 µm geometrii **nie tworzy siatki 10 µm**.

Przed PCB-012C produkcja używała znormalizowanej surowej geometrii.
Teraz normalizacja zachodzi raz, potem projekcja i audyt topologii, po czym
ta sama modelowana geometria trafia do istniejącego meshera, portu,
elementów, pól i XML/FDTD. Nie zmieniono meshera ani polityki EM.

```bat
set "PY=.\.venv\Scripts\python.exe"
set "CSXCAD_INSTALL_PATH=C:\dev\openems\openEMS"
set "GERBERS=gerbs\emtest4"
set "PCB_CONFIG=parameters\pcb_fr4_2layer_pth.json"

%PY% -m antenna_lab.pcb.gerber_control "%GERBERS%" ^
  --pcb-config "%PCB_CONFIG%" ^
  --geometry-resolution-um 10 ^
  --quality preview ^
  --center-mhz 2000 ^
  --cutoff-mhz 1000 ^
  --sweep-start-mhz 1500 ^
  --sweep-stop-mhz 2500 ^
  --sweep-step-mhz 10 ^
  --prepare-only
```

Usuń `--prepare-only`, aby wykonać jeden normalny solve.
`--geometry-resolution-um 1` wybiera większą wierność CAD, nie dokładniejszy
profil EM. Wariant 100 µm jest bardzo zgrubny: audyt może go odrzucić.
emtest4 przy 100 µm traci pełny kontakt CSRC (szerokość portu 0,9 mm,
miedzi 0,8 mm); program zatrzymuje się przed siatką/native i nie ponawia
automatycznie przy 10 µm. Dobierz dokładniejszy wariant jawnie.

Pliki pochodzenia są rozdzielone:

- `geometry.source.json`: import przed normalizacją;
- `geometry.normalized_source.json`: normalizacja przed projekcją;
- `geometry.json`: rzeczywisty model przekazany do solvera;
- `import.json` i `summary.json`: blok `geometry_resolution`, audyt,
  przesunięcia i ograniczona liczba przykładów.

Przy odrzuconej projekcji nie powstaje `geometry.json` udający poprawny model;
źródła i audyt błędu pozostają zapisane. Hashe dotyczą niezmienionych plików
CAD. Raport offline pokazuje rozdzielczość, status topologii i modelowane
wymiary CSRC/wierceń. R/L/C i parametry materiałów nie podlegają projekcji.

Preflight i przygotowanie natywne muszą zwrócić identyczną siatkę;
rozbieżność blokuje Run. Przebiegi mają oddzielne katalogi, brak współdzielonego
cache geometrii/siatki/wyników; nie jest potrzebna nowa warstwa cache.

Akceptacja bez FDTD przy powyższych częstotliwościach:
po PCB-012E emtest4 raw 270480 → **214935 (69×89×35)**, impuls 30446 kroków,
6543911010 aktualizacji komórek; emtest3 raw 99750 → **102900 (60×49×35)**.
Z, kontakty PTH, źródło i RLC zachowane. To test kontraktu, nie zbieżności.

Source CAD precision is not simulation accuracy.

## Uruchomienie w CMD

```bat
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e .
set "CSXCAD_INSTALL_PATH=C:\dev\openems\openEMS"

.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control gerbs\emstest ^
  --quality preview ^
  --sweep-start-mhz 1260 --sweep-stop-mhz 1580 --sweep-step-mhz 5

.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control gerbs\emstest2 ^
  --quality preview --center-mhz 2000 --cutoff-mhz 625 ^
  --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10
```

Każde wywołanie tworzy nowy katalog outcomes/pcb_gerber. `--output` wymaga
pustego/nowego katalogu. `--prepare-only` kończy po XML, bez FDTD i raportu
widma. Dostępne są też jawne `--frequencies-mhz` i `--loss-reference-mhz`.

## Założenia fizyczne i port

Bez `--pcb-config` używane są jawnie drukowane i zapisane **założenia unverified**:
laminat 1,6 mm, epsilon_r=4,3, loss_tangent=0,018; miedź PEC, nominalnie
35 µm i 58000000 S/m (grubość i przewodność nie są modelowane w PEC).
Gerbery nie określają tych parametrów. Opcjonalny plik opisuje wyłącznie
fizykę, bez nazw Gerberów — ten sam plik działa z każdym katalogiem:

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control gerbs\emstest2 ^
  --pcb-config parameters\pcb_fr4_1p6.json --quality preview ^
  --center-mhz 2000 --cutoff-mhz 625 ^
  --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10
```

Schemat: schemas/pcb-physical.schema.json. Przykład parameters/pcb_fr4_1p6.json:

```json
{
  "schema_version": 1,
  "substrate": {"thickness_mm": 1.6, "epsilon_r": 4.3, "loss_tangent": 0.018},
  "copper": {"thickness_um": 35, "conductivity_s_m": 58000000, "model": "pec"},
  "port": {"mode": "auto"}
}
```

Auto obsługuje dokładnie dwa zgodne prostokątne pady typu flash, ustawione
poziomo lub pionowo. Pady wyznaczają oś, środek i szerokość. Przecięcie osi
z **pełną sumą górnej miedzi** wyznacza rzeczywistą szczelinę. Potem sprawdzane są
całe powierzchnie styku i pusty prostokątny port oraz dotychczasowy audyt
siatki. Tolerancja geometryczna pozostaje 1e-10 m, bez przesuwania geometrii.
W emstest szczelina ma 0,64412 mm; w emstest2 0,70024 mm przy szerokości
0,86401 mm. Port pionowy normalizuje się do +X tak samo jak poziomy.

Oba końce mogą należeć do tej samej miedzi, np. pętli emstest2. Połączenie
odległą ścieżką nie oznacza wypełnienia lokalnej szczeliny. Miedź w szczelinie
lub brak pełnego styku blokują przebieg. Nie są wyznaczane ogólne sieci PCB.

Jeżeli auto jest niejednoznaczne, użyj jawnego portu w układzie Gerbera,
w milimetrach, np. dla emstest:

```json
"port": {
  "mode": "explicit",
  "negative_mm": [12.22288, 12.57300],
  "positive_mm": [12.86700, 12.57300],
  "width_mm": 0.86401
}
```

Starsze polecenie z JSON-em zawierającym `files` nadal działa, np.
`python -m antenna_lab.pcb.gerber_control parameters\pcb_easyeda_stroked_feed.json`.
To osobny format zgodności wstecznej; nie łącz go z `--pcb-config`.

## Raport lokalny

Udany solve automatycznie tworzy report.html i plots/geometry.png,
plots/impedance.png, plots/s11.png, plots/swr.png. Konsola wypisuje
`Raport HTML: ...`. Błąd prezentacji zapisuje ostrzeżenie; nie unieważnia FDTD.
Raport współdzieli renderer, CSS, JS i interaktywne widmo z raportem anteny.
Wszystkie obrazy/skrypty są osadzone; nie ma internetu ani serwera.
Geometria pochodzi z geometry.json, widmo z impedance.csv/summary.json;
Gerbery i natywne biblioteki nie są potrzebne do odtworzenia:

```bat
.\.venv\Scripts\python.exe -m antenna_lab report outcomes\pcb_gerber\NAZWA_PRZEBIEGU --open
```

Jak w istniejących raportach antenowych, ręczna regeneracja zapisuje nowy
HTML w outcomes/reports, nie nadpisuje ukończonego przebiegu. Raport pokazuje
próbkowane minima, przedziały zmiany znaku X, ostrzeżenie o minimum na granicy,
założenia, SHA256, profil i stan wykonania. Zmiana Zref w części interaktywnej
nie zmienia statycznych wykresów/minimów dla zapisanego Zref. E/H pojawiają się po jawnym --fields-mhz. NF2FF i bilans mocy nie są zapisywane;
braków nie zastępują fikcyjne dane.

## Profile jakości (PCB-010B)

`--quality preview|design|verify` dotyczy wyłącznie gerber_control.
Domyślny profil to `design`; komendy syntetyczne i diagnostyczne nie zmieniają się.

| Profil | Komórki/falę | Laminat Z | Port gap/width | Padding | PML | EndCriteria | Limit kroków | exact_endcriteria |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| preview | 10 | 2 | 2/2 | 0,10 | 6 | 1e-3 | 1000000000 | false |
| design | 15 | 3 | 2/2 | 0,15 | 6 | 1e-4 | 1000000000 | false |
| verify | 20 | 4 | 4/4 | 0,25 | 8 | 1e-5 | 1000000000 | true |

To profile numeryczne, nie certyfikaty dokładności. Miedź CSXCAD, wymiary
portu, laminat i żądane częstotliwości pozostają identyczne.
Wybór profilu nie uruchamia macierzy ani dodatkowych przebiegów.

### Wierność geometrii miedzi — PCB-012G

Polityka `feature_aware_copper_v3` zastępuje dokładne kotwiczenie wszystkich
prostoliniowych granic z PCB-012F. Modelowane polygony pozostają niezmienione.
Port, komponenty, środki wierceń i interfejsy zachowują krytyczne kotwice.
Nie powstaje globalna krata ani linia dla każdego wierzchołka Gerbera.

Scalamy współliniowe odcinki i parujemy granice rzeczywistych przekrojów miedzi
oraz szczelin. Wspólna długość odcinków musi wynosić co najmniej W/2 dla
prostoliniowego właściciela, a 2W dla właściciela z krzywymi (W to szerokość).
Krótkie schodki aproksymacji łuku nie stają się osobnymi ścieżkami.

Stosujemy udokumentowaną regułę openEMS: **1/3 komórki w metalu, 2/3 poza
metalem**. Dla szerokości W kandydat komórki brzegowej wynosi 3W/5 dla miedzi,
3W/7 dla szczeliny, ograniczony przez maksimum EM / 1,5. Reguła:
https://docs.openems.de/en/latest/concepts/mesh.html oraz przykład
https://github.com/thliebig/openEMS/blob/master/matlab/examples/antennas/Patch_Antenna.m.
Konflikt z krytycznymi liniami nie przesuwa geometrii: pozostaje dokładna linia
brzegowa albo rozdzielona reprezentacja subkomórkowa. Końcowy audyt mierzy
rzeczywisty udział metalu; nie zakłada, że grading zachował początkowe thirds.
Dla alternatywy subkomórkowej komórka brzegowa ma najwyżej W/2; cecha zawiera
co najmniej dwie linie wewnętrzne, a odstęp między nimi nie przekracza 0,6W.
Metadane zapisują granice, sąsiednie linie, udział metalu, odtworzoną szerokość,
właścicieli i powód wyboru metody. To polityka dyskretyzacji, nie dowód zbieżności.

Krzywe pozostają ciągłymi polygonami. Strefa łuku dostaje rozdzielczość
wynikającą z rozpoznanej szerokości przewodnika; pomocniczo z minimum krótkiego
boku bbox i 2*pole/obwód. To tylko kandydat skali. Konserwatywny audyt obwiedni
komórek wewnętrznych i przecinających miedź sprawdza wszystkie warstwy,
liczbę obszarów/otworów, własność otworów i brak zwarcia odrębnych przewodników.
Nie odtwarza natywnego zajęcia Yee. Brak dowodu lub przekroczenie istniejącego
budżetu audytu miliona komórek XY zatrzymuje przygotowanie przed native.

Przy q=10 µm 0,376/0,384 mm daje 0,38 mm, lecz 0,25/0,38 pozostają różne;
analogicznie szczeliny. Geometria jest nadrzędna, ale nie każda jej granica musi
być linią siatki. Nie usuwamy cech według długości fali. Numeryczne środki bbox
można pominąć; tolerancje geometrii i kotwic krytycznych pozostają niezmienione.
`mesh_anchor_policy` i `copper_mesh_fidelity` zawierają cechy, skompaktowane
odcinki, metody reprezentacji, strefy krzywe, minimalne kroki XY z sąsiednimi
kotwicami oraz wyniki audytu. Bezpośrednio promowanych wierzchołków: zero.

#### Test1: odłączony audyt PCB-012G

q=10 µm, center 2 GHz, cutoff 1 GHz, sweep 1500–2500 MHz/10 MHz:

| Profil | Kształt | Komórki (PCB-012F → G) | Min XYZ [µm] | Minimum kroków impulsu |
| --- | --- | ---: | --- | ---: |
| preview | 109×170×45 | 3971025 → 833850 | 10 / 30 / 100 | 90937 |
| design | 130×182×58 | 4422210 → 1372280 | 10 / 30 / 66,6667 | 91442 |

Oba audyty cech, komponentów i portu PASS. 103 wierzchołki źródłowe, 45
skompaktowanych odcinków, 36 redundantnych segmentów i 6 sparowanych cech.
Reprezentacje granic: 6 aligned, 6 resolved_subcell, 0 thirds. Minimum X
pochodzi ze środków wierceń 0,75/0,76 mm; Y z wiercenia −0,03 mm i środka
źródła 0. Nie usuwamy tych różnych krytycznych współrzędnych. Budżety impulsu
50000/75000 nadal są przekroczone; profile nie zostały zmienione.

Kandydat design z cutoff 1900 MHz ma 128×161×71 = 1463168 komórek i minimum
48128 kroków impulsu przy budżecie 75000. Test produkcyjnego prepare z atrapami
native osiąga `prepared`; lokalna próba rzeczywista zatrzymała się na braku
openEMS. Nie uruchomiono FDTD. Komenda Windows do przygotowania:

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control ^
  gerbs\realpcb_microstrip\test1.zip ^
  --geometry-resolution-um 10 --quality design ^
  --center-mhz 2000 --cutoff-mhz 1900 ^
  --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10 ^
  --prepare-only
```

### Kontrola kosztu i zakończenia

Z ukończonej siatki, przed załadowaniem natywnego API, liczone są min_dx,
min_dy, min_dz i górna granica CFL:
`dt = 1 / (C0 * sqrt(1/min_dx² + 1/min_dy² + 1/min_dz²))`.
Czas impulsu Gaussa wynosi `9 / (pi * cutoff_hz)`. Minimalna liczba kroków
to zaokrąglony w górę iloraz czasu impulsu i granicy CFL; iloczyn tej liczby
oraz liczby komórek jest wskaźnikiem minimalnego kosztu. To optymistyczna
dolna granica samego wymuszenia: natywny krok może być mniejszy, a wygasanie
pól wymaga dodatkowych kroków. Nie jest to prognoza czasu pracy komputera.

Jeżeli nawet ta dolna granica osiąga limit kroków, przebieg jest blokowany
przed natywnym API, także przy --prepare-only. Błąd wskazuje potrzebę
przeglądu rozdzielczości/krytycznych kotwic lub jawnego budżetu kroków.
Nie ma automatycznego podnoszenia limitów ani zmiany częstotliwości.

Wszystkie profile używają dump_statistics=True. Osiągnięcie max_timesteps
kończy się statusem failed / max_timesteps_reached przed CalcPort;
nie powstaje ukończony wynik impedancji. Sukces ma termination_status
completed_before_limit i rzeczywistą actual_iterations. Przy samym XML
termination_status to not_run, a actual_iterations to null. Brak prawidłowych
statystyk nie może dać statusu completed. Wynik pozostaje unverified.

## Historyczne konfiguracje emstest i rzeczywisty GTL

Repozytorium zawiera pliki użytkownika w `gerbs/emstest`. Nie są częścią
zmiany PCB-010A. W rzeczywistym GTL regiony mają odstęp 0,87820 mm, ale
każdy ich obrys jest dodatkowo narysowany pisakiem o szerokości 0,2032 mm.
Te linie również oznaczają miedź i nie można ich odrzucić.

Prawy region zaczyna się od X=12,96860 mm. Lewa krawędź jego linii ma więc
X=12,86700 mm. Prawy pad zaczyna się dopiero od X=12,92312 mm, wewnątrz
tego przewodnika. Lewy pad kończy się na X=12,22288 mm. Rzeczywista szczelina
wzdłuż całej szerokości tego portu wynosi zatem 0,64412 mm.

- `parameters/pcb_easyeda_requested.json` zachowuje podane pierwotnie
  końce [12,22288; 12,57300] i [12,92312; 12,57300] mm. Import geometrii
  przechodzi, lecz audyt portu wykrywa miedź w szczelinie i blokuje solver.
- `parameters/pcb_easyeda_stroked_feed.json` jest osobnym, jawnym wariantem:
  zmienia tylko dodatni koniec na [12,86700; 12,57300] mm. Szerokość
  0,86401 mm i cała miedź pozostają bez zmian. To historyczny jawny
  wariant; wejście katalogowe obecnie wykrywa tę szczelinę automatycznie.

Obie konfiguracje używają startowych parametrów laminatu 1,6 mm, epsilon_r
4,3 i tan(delta) 0,018. Gerber ich nie określa — należy wpisać rzeczywiste
wartości w opcjonalnej konfiguracji fizycznej przed interpretacją wyników.

## Wyniki i ograniczenia

`geometry.source.json`, `geometry.json` i `import.json` zachowują geometrię
źródłową/znormalizowaną, transformację, rozwiązane parametry, SHA256 plików,
wersje bibliotek i założenia. `native/model.xml` jest przygotowanym modelem.
Po solve powstają `impedance.csv` i `summary.json`; po błędzie pliki natywne
pozostają, a import_failure.json opisuje błąd. Status walidacji: unverified.

Model v1: miedź górna płaska. Model v2: jawne warstwy miedzi i dielektryków.
Miedź może być PEC lub conducting sheet; bez przelotek, soldermaski,
sitodruku, pasty i chropowatości. Parametry laminatu pochodzą
z konfiguracji. W PEC grubość/przewodność są wyłącznie metadanymi; w conducting sheet są parametrami materiału powierzchniowego.

Krzywe są aproksymowane odcinkami z budżetem błędu geometrycznego 0,1 um.
Usuwanie pozostałości operacji geometrycznych ma tolerancję 1 pm, bez
zaokrąglania do siatki. To nie deklaracja dokładności elektromagnetycznej.
Importer składa dark/clear w kolejności i zachowuje otwory miedzi. Nadal
odrzuca połączenia wyłącznie punktowe, inne niż kołowe pisaki linii oraz
niejednoznaczne/otwarte/wielokrotne obrysy. Nie wypełnia otworów ani nie
naprawia uszkodzonych kształtów. Ostrzeżenia parsera są błędami importu,
aby pominięte polecenia nie dawały pozornie poprawnego modelu.

API graficzne: [Gerbonara 1.6.3](https://gerbolyze.gitlab.io/gerbonara/object-api.html).
Testy używają własnych minimalnych Gerberów i atrap natywnego solvera.
Rzeczywiste GTL/GKO sprawdzono przez import, normalizację i audyt siatki/portu;
natywne FDTD tej płytki wymaga uruchomienia lokalnego na Windowsie.

## Gęsty sweep z jednego przebiegu (PCB-010C)

`--sweep-start-mhz 1260 --sweep-stop-mhz 1580 --sweep-step-mhz 5`
wybiera 65 częstotliwości dla jednego Run i jednego CalcPort. Wszystkie trzy
argumenty są wymagane razem; nie można łączyć ich z `--frequencies-mhz`.
Domyślne częstotliwości i profile jakości pozostają bez zmian. Obowiązuje
istniejący zakres jakości impulsu; sweep nie zmienia centrum ani cutoff.

Punkty powstają na regularnej siatce start + i × step. Koniec jest włączony,
jeśli trafia w krok; inaczej ostatni punkt jest poniżej stop (bez dodatkowego
krótszego kroku). W summary.json `sweep` zapisuje żądany i rzeczywisty zakres,
krok, liczbę punktów oraz tę zasadę. Sama liczba próbek nie zmienia siatki;
zmiana najniższej częstotliwości nadal wpływa na padding zgodnie z istniejącą
polityką. Impedance.csv pozostaje jedyną tabelą per częstotliwość.

`minimum_s11`, `minimum_swr`, `minimum_abs_reactance` opisują wyłącznie
próbki (przy remisie pierwsza). `reactance_crossings` zawiera sąsiednie
przedziały o przeciwnych znakach X lub dokładnym zerze na którymś końcu.
Dokładne zero wewnątrz szeregu może wystąpić w dwóch przedziałach; także
przedział o obu końcach równych zero jest zapisany. Nie interpolujemy rezonansu.
Dla dokładnego S11=0 pole s11_db jest null (−∞ dB), zachowując ścisły JSON.


## Pola E/H i odtwarzanie fazy (PCB-010E)

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control gerbs\emstest2 ^
  --quality preview ^
  --center-mhz 2000 --cutoff-mhz 625 ^
  --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10 ^
  --fields-mhz 2000
```

`--fields-mhz` wybiera 1–3 unikalne, dodatnie, skończone częstotliwości
wewnątrz zadeklarowanego pasma center ± cutoff. Nie muszą występować w sweepie
impedancji. Obowiązuje nadal **jeden Run**. Jeden CalcPort oblicza sumę zbiorów
częstotliwości sweepu i pól; impedance.csv zawiera wyłącznie żądany sweep.
Pominięcie --fields-mhz zachowuje dotychczasowy przebieg i raport.

Przed XML/Run instalowane są pasywne zrzuty FD E (10) i H (11), dump_mode=1
(interpolacja do węzłów), HDF5. Zrzuty otrzymują tylko częstotliwości pól,
nie cały sweep. Nie ma filmu kroków czasowych ani objętości 3D.

Trzy przekroje korzystają wyłącznie z istniejących linii, ściśle poza PML:

- xy_air: pierwsza dodatnia linia Z powyżej miedzi, bez próbkowania na powierzchni miedzi;
- xz_feed: najbliższa istniejąca linia Y do fizycznego środka portu;
- yz_feed: najbliższa istniejąca linia X do fizycznego środka portu.

Wszystkie osie styczne kończą się przed początkiem PML. Metadane zapisują
politykę, żądaną i rzeczywistą pozycję, rozmiar przekroju i pliki natywne.
Nie dodaje się ani nie przesuwa linii siatki. Geometria, port, wymuszenie,
PML oraz profil jakości pozostają bez zmian; koszt rośnie jedynie o DFT/I/O.
Przed solverem konsola podaje częstotliwości, płaszczyzny i liczbę zespolonych
próbek składowych. Wspólny limit infrastruktury wynosi 4 mln punktów
przestrzennych × częstotliwości (po 6 składowych E/H), sumowanych po przekrojach.

Po udanym zakończeniu powstają:

- fields/metadata.json;
- fields/xy_air.npz, fields/xz_feed.npz, fields/yz_feed.npz;
- plots/fields_xy_air_0.png, fields_xz_feed_0.png, fields_yz_feed_0.png
  (indeks _1/_2 dla następnych częstotliwości).

NPZ: frequency_hz, x_m/y_m/z_m, pełne zespolone E_v_per_m i H_a_per_m,
mask, normalization_factor, port_voltage_phasor, reference_voltage_v,
phasor_convention i array_order. Kolejność tablic pól:
`frequency, component_xyz, x, y, z`, z pojedynczą próbką osi normalnej.
Surowe native/fields_<plane>_E.h5 i _H.h5 pozostają nietknięte.

Odniesieniem jest natywne całkowite napięcie portu uf_tot dla każdej
częstotliwości pola. E/H mnożymy przez `1 / uf_tot`, otrzymując port
**1∠0 V**, bez normalizacji do mocy przyjętej. Zapisywane są oryginalne
zespolone napięcia i czynniki. Zero/nieskończone napięcie powoduje błąd.
Jednostki: **E: V/m per 1 V port; H: A/m per 1 V port**. Konwencja:
`real(F * exp(+j * phase))`; faza zero to dodatnie maksimum napięcia portu.

Siatki E i H oraz wszystkich częstotliwości muszą być identyczne; nie są
interpolowane przy eksporcie. Porównanie natywnych współrzędnych z planem
uwzględnia zapis float32 (rtol 1e-6, atol 1e-10 m), ale zapisane współrzędne
pozostają natywne, bez snapowania. Pełna maska jest konserwatywną oceną
geometrii: bit 1 miedź z=0, bit 2 otoczenie o jednej lokalnej przekątnej komórki,
bit 4 prostokąt źródła z takim halo. Odległość jest liczona do rzeczywistych
poligonów i powierzchni portu. To nie natywna zajętość komórek Yee. Laminat
nie jest maskowany. Próbki objęte maską mają NaN w oderwanych NPZ; JSON
pozostaje ścisły, bez NaN/Inf. Pierwszy przekrój nad metalem może mieć znaczny
obszar maski — nie należy go odczytywać jako brak pola fizycznego.

Raport dodaje „Pola E/H — przebieg jednego okresu”: suwak i Play/Pause,
fazy 0°, 30°, …, 330° z pętlą do 0° oraz czas `phase / 360 / f` w ns.
Ruch na ekranie jest celowo spowolniony. Nie uruchamia solvera. Każda
płaszczyzna/częstotliwość ma własny odtwarzacz:

- xy_air: Ex/Ey jako wektor, tło podpisane Ex; obok podpisane Hz;
- xz_feed: Ex/Ez jako wektor, tło Ex; obok Hy;
- yz_feed: Ey/Ez jako wektor, tło Ey; obok Hx.

Skale symetryczne symlog są stałe dla wszystkich faz jednej składowej
i częstotliwości, wyznaczone z pełnej niezamaskowanej obwiedni fazora.
W XY nakładany jest rzut miedzi, płytki i portu; pionowe cięcia pokazują
przecięcia miedzi/portu i interfejsy laminatu. Strzałki są deterministycznie
rozrzedzane w przestrzeni. Przeglądarka dostaje najwyżej 80×80 próbek mapy;
pełne NPZ nie są zmieniane. Kontaktowe PNG pokazują 0°, 90°, 180°, 270°.

Ręczne `python -m antenna_lab report outcomes\pcb_gerber\RUN --open`
odtwarza wszystko z geometry.json i fields/*.npz/metadata.json, bez Gerberów
ani openEMS. `--phase-step 15` zmienia wyłącznie prezentację do 24 faz.
Brak dumpów w starym przebiegu wymaga nowego obliczenia z --fields-mhz;
raport nie może odzyskać pól, których solver nie zapisał. Wyniki nadal unverified.


## Miedź o skończonej przewodności (PCB-011A)

Domyślny model pozostaje `pec` (`AddMetal`). Do fizycznego wariantu użyj
`--pcb-config parameters\pcb_fr4_1p6_realistic.json`. Przykład zawiera
`copper.model=conducting_sheet`, 35 µm i 58 MS/m oraz FR4 1,6 mm,
epsilon_r=4,3, loss_tangent=0,018. To jawne **założenia unverified**,
nie dane potwierdzone przez producenta laminatu.

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control gerbs\emstest2 ^
  --pcb-config parameters\pcb_fr4_1p6_realistic.json ^
  --quality preview ^
  --center-mhz 2000 ^
  --cutoff-mhz 625 ^
  --sweep-start-mhz 1500 ^
  --sweep-stop-mhz 2500 ^
  --sweep-step-mhz 10 ^
  --fields-mhz 2000
```

Adapter tworzy `AddConductingSheet('pcb_top_copper_sheet', conductivity=58e6,
thickness=35e-6)` i instaluje te same płaskie poligony przy dokładnym z=0.
Skończona grubość jest parametrem modelu powierzchniowego, **nie bryłą 3D**.
Nie powstają linie Z ani kotwice zależne od grubości. Dla tej samej geometrii,
częstotliwości i jakości osie, liczba komórek i oszacowanie CFL są identyczne
z PEC. Nie oznacza to gwarancji identycznego czasu wykonania lub zaniku energii.
Model strat może zmienić impedancję i pola; nie uruchamiamy automatycznie
żadnego drugiego obliczenia. Porównanie wykonaj osobnymi przebiegami,
zmieniając wyłącznie `copper.model` w fizycznej konfiguracji.

summary.json i preparation.geometry zawierają `copper_model`,
`copper_thickness_m`, `copper_conductivity_s_m` oraz
`copper_sheet_conductance_s = conductivity * thickness` (tu 2030 S).
Dla PEC podane wartości pozostają zapisane, ale są jawnie nieużywane przez
solver. Raport offline pokazuje model oraz parametry. E/H pozostają
normalizowane do napięcia portu; konserwatywna maska płaskiej miedzi i portu
obowiązuje także dla conducting sheet, bez zmiany próbkowania i animacji.
Nie dodano soldermask, dolnej miedzi, przelotek ani chropowatości.
Starsza konfiguracja JSON zawierająca ścieżki Gerberów nadal obsługuje PEC;
wybór conducting sheet jest częścią fizycznej konfiguracji wejścia katalogowego.


## Wielowarstwowy stackup (PCB-011B, physical schema v2)

`parameters/pcb_fr4_4layer.json` to przykład czterech warstw. Parametry FR4
pozostają **założeniami unverified**, nie danymi producenta. Plik nie zawiera
nazw Gerberów. Przekaż katalog z dokładnie pasującymi warstwami, np.:

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control gerbs\moja_plytka_4layer ^
  --pcb-config parameters\pcb_fr4_4layer.json ^
  --quality preview --center-mhz 2000 --cutoff-mhz 625 ^
  --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10 ^
  --fields-mhz 2000
```

Schemat v2 zawiera `schema_version: 2`, tablicę `stackup` i `port`.
Element `copper` ma `role`, `model`, `thickness_um`, `conductivity_s_m`.
Element `dielectric` ma `name`, `thickness_mm`, `epsilon_r`, `loss_tangent`.
Wszystkie pola są wymagane. Obsługiwane modele miedzi to dokładnie `pec`
i `conducting_sheet`; grubości i przewodności muszą być dodatnie.

Stos zaczyna się od `top`, kończy na `bottom`, a role pośrednie mają kolejno
nazwy `inner1`, `inner2`, itd. Miedź rozdzielają dodatnie grubości dielektryka;
można opisać także kilka kolejnych dielektryków bez miedzi między nimi.
Nazwy dielektryków muszą być unikalne. Puste, niespójne lub błędne v2 są
odrzucane, nigdy konwertowane po cichu do v1.

Top leży dokładnie przy z=0. Kolejne współrzędne wynikają wyłącznie z sumy
głębokości dielektryków, bez zaokrąglania lub dodawania grubości miedzi:

| Warstwa przykładu | Z [mm] |
|---|---:|
| top | 0 |
| inner1 po prepreg 0,18 mm | −0,18 |
| inner2 po core 1,20 mm | −1,38 |
| bottom po prepreg 0,18 mm | −1,56 |

Rozpoznawane nazwy obejmują GTL/GBL, F_Cu/B_Cu, In1_Cu/In2_Cu,
InnerLayer1/InnerLayer2 oraz G1/G2 lub GP1/GP2. Metadane X2 FileFunction
z Gerbonara mają numery fizyczne: L1=top, L2=inner1, itd. Kolejność musi
być jednoznaczna i zgodna z nazwą, jeśli obie są podane. Brak, nadmiar,
duplikat, luka w numeracji lub konflikt powoduje błąd z nazwami plików.
Każda skonfigurowana rola musi mieć dokładnie jeden Gerber. Obrys nadal
musi być pojedynczym zamkniętym konturem. Dotychczasowe ograniczenia
geometrii Gerberów poza nową obsługą dark/clear i otworów miedzi pozostają.

Od PCB-011D v2 obsługuje okrągłe przelotowe PTH i NPTH z Excellon, zgodnie
z sekcją poniżej. V1 nadal odrzuca wiercenia. Brak plików wierceń **nie
potwierdza**, że model odwzorowuje kompletne fizyczne PCB. Maska, pasta
i sitodruk są wykrywane i pomijane.

Port obsługuje wyłącznie `layer: "top"` (wymagane zarówno dla auto, jak
explicit). Auto działa na dwóch prostokątnych flashach górnej miedzi.
Puste wnętrze i kontakt bada się tylko na top; miedź pod spodem jest
legalna. Odległa ścieżka tej samej górnej pętli nadal może łączyć oba końce.
Normalizacja XY jest wykonywana raz i obraca wszystkie warstwy razem.

Każdy dielektryk ma własny materiał constant-kappa i własny przedział Z;
nie uśredniamy epsilon_r. Każda miedź otrzymuje osobne AddMetal lub
AddConductingSheet i poligony na swoim Z. Model geometrii zawiera
`dielectric_layers`, `copper_layers` oraz `layer_role` przy każdym poligonie.
Starsze `substrate` jest widokiem pierwszego materiału wyłącznie dla zgodności;
solver i mesh używają pełnej listy, nie tego widoku jako całego laminatu.

Siatka zachowuje dokładnie wszystkie interfejsy i płaszczyzny miedzi.
Za bliskie interfejsy są odrzucane, nie scalane. Limity Z stosują długość fali właściwą dla materiału danego przedziału;
min_substrate_cells_z odnosi się do łącznej głębokości dielektryków, nie
ustanawia nowego minimum na każdą warstwę. Interfejsy mogą już spełniać ten
warunek bez dalszego podziału cienkiego prepregu. XY używa najkrótszej fali
w stosie, ponieważ
płaszczyzny kartezjańskie są wspólne. Grading, port i profile jakości są
niezmienione. Grubość conducting sheet dodaje **zero linii Z**. Cienki
prepreg może zwiększyć koszt i zmniejszyć CFL: preflight pokazuje to przed
native Run i blokuje przebieg, jeśli sam impuls nie mieści się w limicie kroków.

summary.json i preparation.geometry zapisują `resolved_stackup`: całkowitą
głębokość dielektryków, wszystkie Z, parametry materiałowe, kappa przy
częstotliwości odniesienia strat, parametry sheet i źródłowy SHA256 każdej
warstwy miedzi. geometry.json zachowuje pełne poligony i warstwy. Raport
odtwarza tabelę „Stackup” oraz `plots/stackup.png` bez Gerberów/openEMS.
Miedź na schemacie jest symboliczna — grubość kreski nie oznacza geometrii.
Widok z góry pokazuje top; cięcia XZ/YZ pokazują wszystkie interfejsy
laminatu, miedź na rzeczywistym Z i port top.

Maska E/H liczy odległość od każdej płaskiej miedzi na jej własnym Z,
nie od wspólnego rzutu wszystkich warstw. Nie maskuje dielektryków.
Pierwszy przekrój powietrzny pozostaje pierwszą dodatnią linią Z; fazy,
normalizacja do 1 V i liczba natywnych Run są niezmienione.

Brak --pcb-config, physical v1, legacy JSON ze ścieżkami, emstest/emstest2,
PEC/conducting_sheet, sweep i pola zachowują dotychczasowe działanie.
Nie dodano automatycznego badania zbieżności; wyniki pozostają unverified.


## Clear polarity, antipady i wycięcia miedzi (PCB-011C)

Każdy Gerber miedzi jest osobnym obrazem. Import zaczyna od pustej geometrii
i przechodzi przez obiekty oraz ich prymitywy z Gerbonara w kolejności pliku:
`dark → union`, `clear → difference`. Późniejsze dark może przywrócić wcześniej
usuniętą miedź. Nie stosujemy `union(dark) - union(clear)`. Regiony, flash,
kołowe linie/łuki używają istniejącego budżetu aproksymacji krzywych 0,1 µm
i cleanup 1 pm z zachowaniem topologii. Pusty, błędny lub niepoligonowy
wynik jest błędem, nie jest naprawiany. Ostrzeżenia parsera pozostają błędami.
Obrys płytki nadal wymaga jednego zewnętrznego konturu; NPTH są osobnymi cylindrami Excellon w v2 (PCB-011D).

`CopperPolygon.vertices_xy_m` pozostaje pierścieniem zewnętrznym.
Opcjonalne `holes_xy_m` zawiera pierścienie wewnętrzne w SI. Jeden połączony
przewodnik z wieloma otworami pozostaje jednym rekordem, z ID, rolą i Z.
Później przywrócona izolowana wyspa wewnątrz otworu jest osobnym przewodnikiem,
zgodnie z fizyczną topologią. Clear dochodzący do krawędzi daje wcięcie;
przecięcie całej płaszczyzny może dać rozłączne przewodniki. Normalizacja
obraca również otwory, bez zmiany Z lub wymiarów.

Wnętrze otworu nie należy do miedzi. Krawędź otworu zachowuje dotychczasową
tolerancję styku metalu — port może stykać się z nią tak jak z krawędzią
zewnętrzną. Pełny kontakt, pusty prostokąt i dyskretny audyt portu pozostają
obowiązkowe. Wszystkie te kontrole dotyczą wyłącznie top, nie rzutu miedzi
zakopanej. Prostokątne clear flashe nie są kandydatami dodatnich padów auto.

Adapter nadal instaluje zewnętrzne poligony PEC lub conducting sheet;
nie trianguluje całej płaszczyzny. Otwory otrzymują płaskie poligony materiału
`pcb_copper_clearance_air` (epsilon=1, kappa=0) na **tym samym Z**.
Priorytet zwykłej miedzi wynosi 10, jej clearance 11. Dla zagnieżdżonych
przywróconych wysp priorytety wynoszą kolejno 12/13, 14/15 itd. Każdy
clearance wygrywa ze swoim przewodnikiem macierzystym, ale nie kasuje
przywróconej wyspy. Głębokość zagnieżdżenia liczona jest tylko na tej samej
warstwie i Z. Wszystkie priorytety są zapisane w preparation.geometry.copper_clearances.

Grubość conducting sheet nie dodaje linii Z. Od PCB-012F granice otworów
mogą wymagać dodatkowych linii XY tak samo jak zewnętrzne granice miedzi.
Po instalacji nadal wykonywany jest dokładny audyt zamrożonych osi i jednostki.
Nie wprowadzono siatki o grubości miedzi ani dodatkowych przebiegów FDTD.

geometry.json przechowuje wszystkie pierścienie, role i Z. Dane
`copper_composition` w geometrii, import.json, summary.import i metadanych
przygotowania zawierają dla każdej warstwy liczbę prymitywów dark/clear,
końcowych przewodników i otworów. Liczymy prymitywy rozwinięte przez Gerbonara,
nie liczbę wierszy pliku. JSON nie zawiera obiektów parsera.

Maski E/H mierzą odległość do rzeczywistego poligonu z otworami na jego Z.
W dużym antipadzie próbki nie są metalem; konserwatywne halo jednej komórki
może nadal objąć wąski otwór lub próbki blisko innej warstwy. Substrat nie
jest maskowany. Normowanie do 1 V, fazy i pozycje przekrojów są niezmienione.
Rysunki z góry używają przezroczystych otworów w ścieżce złożonej, a pionowe
cięcia rzeczywistych przecięć poligonów; nie zamalowują otworów ani wysp.
Raport offline odtwarza je wyłącznie z zapisanej geometrii i wyników.

Obsługę okrągłych Excellon PTH/NPTH w v2 opisuje PCB-011D poniżej. Nadal brak soldermask, komponentów i chropowatości.
Model oraz priorytety warstw wymagają natywnej weryfikacji na Windows;
testy z atrapami nie potwierdzają fizycznej zbieżności. Status: unverified.


## PCB-011D — okrągłe przelotowe PTH i NPTH

W katalogu Gerberów można umieścić np. `Drill_PTH.drl` i `Drill_NPTH.drl`.
Gerbonara 1.6.3 parsuje Excellon (w tym jednostki, narzędzia i obiekty).
Klasyfikacja używa metadanych plating z parsera, komentarza X2 FileFunction
oraz konwencjonalnych nazw PTH/NPTH, plated/non-plated. Konflikt, nieznana
klasa, mieszane klasy w jednym pliku, pusty plik lub ostrzeżenie parsera
powodują błąd z nazwą źródła, z jednym wyjątkiem PCB-011D1: dokładny
komunikat `G90 header statement found after end of header` dla instrukcji
`G90` jest akceptowany i zapisany w `drill_sources[].compatibility_warnings`
(z nazwą źródła, instrukcją, pełnym tekstem i disposition
`accepted_gerbonara_compatibility_warning`). Źródłowy Excellon nie jest
przepisywany. Wszystkie inne ostrzeżenia parsera pozostają błędami.
Nie zgadujemy klasy ani formatu liczbowego.
Metadane zakresu warstw muszą wskazywać od top do bottom. Nie obsługujemy
slotów, frezowania, blind/buried/microvias ani nieokrągłych narzędzi.

Opcjonalny obiekt w fizycznej konfiguracji **schema_version: 2**:

```json
"drills": {
  "pth_plating_um": 25,
  "pth_model": "solid_pec_equivalent"
}
```

Jest obowiązkowy, gdy zestaw zawiera PTH; brak domyślnej ukrytej grubości
metalizacji. Dla samych NPTH nie jest potrzebny. Grubość musi być dodatnia
i skończona. Konfiguracja nie zawiera nazw plików. V1 oraz v2 bez wierceń
zachowują wcześniejszy model. 25 µm to jawne założenie, nie pomiar producenta.

PTH jest jednym walcem `AddCylinder` na `AddMetal('pcb_pth_solid_PEC')`,
od dokładnego z=0 do płaszczyzny bottom. Promień wynosi połowę średnicy
wiercenia plus grubość metalizacji. Nie jest to pusta powłoka ani walec
conducting sheet. Raport zapisuje dosłownie:

> PTH barrel model: solid PEC equivalent cylinder; plating losses and hollow barrel geometry are not modeled.

Warstwa ma kontakt, gdy fizyczny dysk walca przecina końcową miedź tej
warstwy po składaniu dark/clear. Antipad pozostaje otwarty poza dyskiem
przelotki. Wymagane są co najmniej dwa kontakty na różnych warstwach;
osierocony PTH jest błędem. Nie wnioskujemy sieci z nazw warstw.

NPTH to `AddCylinder` materiału `pcb_npth_air` (epsilon=1, kappa=0), przez
całą grubość dielektryków; usuwa też przypadkowo nachodzącą miedź.
Nie ma promienia przewodnika ani kontaktów elektrycznych. Priorytet PTH
jest o 1 większy od najwyższego priorytetu miedzi/prześwitów PCB-011C,
a NPTH o kolejny 1. Walce nie zmieniają siatki podczas instalacji; po nich
następuje dokładny audyt odczytu CSXCAD. Otwory przecinające port, wzajemnie
nachodzące lub wychodzące poza obrys są odrzucane w tej pierwszej wersji.

Siatka zachowuje dokładne X/Y środków każdego otworu, również w preview.
Kotwice są zapisane osobno jako `drill_centres_xy_m`. Nie dodajemy kotwic
promienia, grubości metalizacji, wierzchołków okręgu ani dodatkowych Z.
Zmiana grubości metalizacji nie zmienia osi ani liczby komórek. Wiele
różnych środków może podnieść koszt lub przekroczyć limit; istniejący
preflight zatrzyma zadanie przed Run, bez usuwania przelotek. Skrajnie
bliskie, różne krytyczne kotwice dają błąd zamiast scalenia. Samo zachowanie
środka walca nie potwierdza dokładności elektromagnetycznej jego promienia
na grubej siatce; wyniki nadal mają status unverified.

`geometry.json` zapisuje ID, środek w SI, średnicę, klasę, narzędzie,
SHA256, a dla PTH także grubość, promień równoważny i role kontaktów.
`import.json`/`summary.json` zapisują źródła, SHA256, klasy, średnice
narzędzi i liczby otworów. Numery narzędzi pochodzą z mapy przypiętego
parsera Gerbonara, nie z własnego parsera NC. Normalizacja XY obejmuje
środki razem z całą płytką dokładnie raz.

Maski pól obejmują rzeczywiste walce PTH i halo jednej lokalnej komórki;
NPTH usuwa maskę miedzi w otworze, lecz blisko jego brzegu nadal działa
konserwatywne halo sąsiedniej miedzi. Substrat nie jest maskowany. Przekroje
pionowe pokazują przecięte walce; widok XY oznacza obrysy otworów bez
zamalowywania pola. Fazy, płaszczyzny i odniesienie 1 V pozostają bez zmian.
Raport offline dodaje tabelę Drills / vias, oznaczenia PTH/NPTH z góry
oraz symboliczne walce w schemacie stackupu (X i grubość ścianki nie są
rysowane w skali). Nie potrzebuje źródłowych Excellonów ani openEMS.

API walca: [CSXCAD CSPrimCylinder](https://docs.openems.de/en/latest/python/CSXCAD/CSPrimitives/CSPrimCylinder.html).
Testy korzystają z atrap natywnych; nie uruchamiają FDTD ani macierzy zbieżności.


### PCB-011D2 — drill drawing to dokumentacja

`Gerber_DrillDrawingLayer.GDD` jest Gerberem dokumentacyjnym, nie plikiem NC.
Dla formatu rozpoznanego przez Gerbonara jako Gerber rozszerzenie `.GDD`
lub nazwa zawierająca `DrillDrawingLayer` daje rolę `drill_drawing` i
`disposition: omitted`. Plik i SHA256 pozostają w `discovered_files`, ale
nie trafia do parsera Excellon ani modelu PTH/NPTH.

Do ścieżki NC trafiają `.drl`/`.xln` oraz dane rozpoznane jako `excellon`.
Samo słowo `drill` w nazwie nie określa formatu. Nieznany plik tekstowy
pozostaje niesklasyfikowany. Inne Gerbery opisujące fizyczne wiercenia
w FileFunction są jawnie nieobsługiwane — nie próbujemy czytać ich jako
Excellon. Prawdziwe PTH/NPTH w tym samym katalogu działają jak wcześniej,
włącznie z niezmienionym wyjątkiem G90 z PCB-011D1.

### PCB-011D3 — pomocniczy eksport Through_Via

EasyEDA może zapisać ten sam PTH w `Drill_PTH_Through.DRL` oraz
`Drill_PTH_Through_Via.DRL`. Wszystkie źródła są normalnie parsowane przed
deduplikacją. Pomiędzy różnymi źródłami tłumimy tylko przelotowe PTH,
których odległość środków XY i różnica średnic nie przekraczają istniejącej
tolerancji geometrii PCB (1e-10 m). Nie uśredniamy ani nie zaokrąglamy
wymiarów. Właścicielem jest pierwsze źródło w deterministycznej kolejności
nazw (casefold, potem oryginalna nazwa i ścieżka). `Through.DRL` poprzedza
`Through_Via.DRL`; samo `Through_Via.DRL` pozostaje normalnie modelowane.
Porównania dotyczą zachowanego właściciela, bez łańcuchowego rozszerzania
tolerancji przez kolejne kopie.

Każdy wpis `drill_sources` zachowuje ścieżkę, SHA256 i surowe `hole_count`.
Dodano `modeled_hole_count` i `suppressed_duplicate_holes` z nazwą źródła,
narzędziem, XY, średnicą, `disposition: duplicate_pth_suppressed`,
`canonical_source` i `canonical_drill_id`. Tylko zachowane otwory trafiają
do PcbDrill, kotwic siatki, walców CSXCAD i maski pól.

PTH/NPTH w tym samym miejscu, różne średnice poza tolerancją oraz odrębne
nachodzące otwory pozostają błędami. Walidacja nakładania nie jest wyłączona.
Wyjątek G90 z PCB-011D1 pozostaje niezmieniony.

### PCB-011D4 — dokładne obroty ortogonalne

Dla źródłowego portu dokładnie +X/-X/+Y/-Y normalizacja po przesunięciu
środka stosuje współczynniki -1, 0, +1, również w transformacji odwrotnej.
Nie wykorzystuje przybliżonego cos(pi/2). Wspólne mapowanie obejmuje obrys,
wszystkie warstwy, otwory miedzi, port i środki wierceń. Nie ma snapowania,
zaokrąglania ani zmian tolerancji siatki/geometrii. Port ukośny nadal używa
atan2/cos/sin. Metadane transformacji zawierają `exact_orthogonal`; znacznik
zapobiega potraktowaniu prawdziwie ukośnego portu jako osiowego, gdy samo
atan2 zaokrągli się do kąta ćwierćobrotu. Stare metadane bez znacznika
zachowują dotychczasowe zachowanie trygonometryczne.

`parameters/pcb_fr4_2layer_pth.json` to jawne założenia: dwie warstwy
conducting sheet 35 µm, 58 MS/m, FR4 1,6 mm, epsilon_r=4,3, tan(delta)=0,018,
PTH solid PEC equivalent z metalizacją 25 µm. Nie są to dane producenta.
Przykład przygotowania bez FDTD (CMD):

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control gerbs\emtest3 ^
  --pcb-config parameters\pcb_fr4_2layer_pth.json ^
  --quality preview --center-mhz 2000 --cutoff-mhz 625 ^
  --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10 ^
  --prepare-only
```

## ENET + FlyingProbe: idealne R/C/L i źródło CSRC (PCB-011E)

W fizycznym schemacie v2 folder może zawierać jeden `*.enet` i jeden
`FlyingProbeTesting.json`. ENET wymaga pliku FlyingProbe; oba są zapisywane
z SHA256 w metadanych importu. Bez ENET dotychczasowe wykrywanie portu nie
zmienia się. Nie dopisuj nazw tych plików do konfiguracji fizycznej.

Elektrycznie używane są wyłącznie `props.Designator`, `props.Value` i `pins`.
Wspierane są dwupinowe R/C/L na górnej warstwie SMD, z osiami X/Y. Wartości
muszą być dodatnie, skończone i mieć jednostkę: R/Ω/ohm/mΩ/kΩ/MΩ,
F/pF/nF/uF/µF lub H/pH/nH/uH/µH/mH. Parametry katalogowe, tolerancja i DCR
nie zastępują Value. Dokładnie jeden `CSRC` z numerycznym Value=0 wskazuje
źródło (istniejący port odniesienia, zwykle 50 Ω), a nie kondensator 0 F.

FlyingProbe wiąże `REFDES_pin` z siecią i położeniem. Niezgodna sieć,
niejednoznaczny pin, dolna warstwa, THT lub ukośna para kończą import błędem.
Wpisy PAD nieobecne w ENET są ignorowane. Przerwę wyznacza końcowy obraz
miedzi po union/clear, nie krawędź apertury ani wymiar obudowy.

Każdy idealny R/C/L dodaje przed podziałem i gradingiem dwie krytyczne
podłużne kotwice styków oraz dwie poprzeczne granice modelowanego okna kontaktu.
Dla osi X są to X końców przerwy i min/max Y okna; dla osi Y odwrotnie.
Oszczędny filtr Gerber nie usuwa tych kotwic. Są wymaganiem siatki EM,
a nie zmianą rozdzielczości geometrii ani regularną kratą FDTD.
Podział/grading może dodać między nimi kolejne linie float.
Najmniejszy legalny istniejący przedział poprzeczny nadal musi mieścić się w obu
padach i mieć pełny kontakt oraz pustą przerwę. Końcowy audyt nadal odrzuca
niejednoznaczną miedź i kolizje ze źródłem, innym komponentem lub wierceniem.
Brak legalnej komórki wymaga sprawdzenia styków/padów lub jawnej polityki
siatki EM, nie wybierania drobniejszej rozdzielczości CAD. R/C/L używają `AddLumpedElement`,
`LEtype=1`, `caps=True` i boxa od z=0 do pierwszej istniejącej linii powietrza.
PEC end caps zapewniają kontakt z płaskimi padami; nie są modelem wyprowadzeń
obudowy. Nie powstają nowe kotwice Z. Zmiana wartości R/C/L nie zmienia siatki.
Sygnaturę porównano z przypiętym CSXCAD
[`dcdb62b`, CSPropLumpedElement](https://github.com/thliebig/CSXCAD/blob/dcdb62bcfd1111ee3594ba22d06089b41b380990/python/CSXCAD/CSProperties.pyx).
Testy atrap nie stanowią potwierdzenia natywnego kontaktu ani impedancji.

`geometry.json` przechowuje elementy, położenia i pochodzenie CSRC;
metadane przygotowania zawierają dokładne argumenty i boxy elementów.
Raport offline pokazuje tabelę **Ideal components** i znaczniki. Pola mają
oddzielny bit maski 8 dla boxów RLC z dotychczasowym halo jednej lokalnej
komórki. Przekroje pionowe pokazują rzeczywisty box solvera, nie obudowę.
Jeden Run i jeden CalcPort nadal obsługują cały eksperyment.

**Components are ideal lumped elements. Package parasitics, tolerance,
ESR/ESL/DCR and manufacturer frequency dependence are not modeled.**

Przygotowanie `emtest4` w Windows CMD (bez FDTD):

```bat
set "CSXCAD_INSTALL_PATH=C:\dev\openems\openEMS"
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control gerbs\emtest4 ^
  --pcb-config parameters\pcb_fr4_2layer_pth.json ^
  --quality preview --center-mhz 2000 --cutoff-mhz 1000 ^
  --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10 ^
  --prepare-only
```

Cutoff 1000 MHz jest tu **jawnym ustawieniem przykładu**, nie nowym domyślnym
parametrem. Dla cutoff 625 MHz preview potrzebuje co najmniej 55 210 kroków
na sam impuls i poprawnie odmawia startu przy limicie 50 000. Profil design
z tym samym cutoff mieści impuls w swoim limicie 75 000 (ukończenie zaniku
nadal wymaga sprawdzenia statystyk). Profile i zabezpieczenia nie zmieniły się.
Dla powyższego preview: 288 120 komórek, minimum 34 507 kroków impulsu;
bez kotwic elementów przy identycznym eksperymencie: 181 790 komórek.
Oś Z jest identyczna. To preflight, nie benchmark ani dowód zbieżności.

## Eksperyment ZIP i dziedziczenie wejść (PCB-012D)

Wejście `*.zip` (bez znaczenia wielkości liter) oznacza eksperyment z zewnętrzną
netlistą. Katalog oraz legacy JSON zachowują dotychczasowe zasady i **nie**
zaczynają szukać plików w rodzicach.

Dla ZIP wybieramy niezależnie netlistę i stackup: dokładnie jeden kandydat
lokalny wygrywa; przy braku szukamy tylko w jednym katalogu nadrzędnym.
Wielu kandydatów na rozpatrywanym poziomie oznacza błąd; nie szukamy dalej.
Brak na obu poziomach też oznacza błąd. Nie łączymy konfiguracji.
`--pcb-config` zastępuje automatyczny wybór stackupu (`explicit_cli`),
ale netlista nadal wymaga lokalnego lub nadrzędnego `.enet`.

Netlistą jest regularny plik `.enet`, bez wymaganego związku nazwy z ZIP.
Stackup rozpoznajemy po kontrakcie physical PCB lub strukturze EasyEDA Pro
`layerManagement` + `physicalStacking`; przypadkowe JSON i FlyingProbe nie są
kandydatami. ENET wewnątrz ZIP jest odrzucany. FlyingProbeTesting.json pochodzi
z ZIP. Zachowujemy oryginalną ścieżkę i katalog ENET, żeby przyszłe odnośniki
do modeli komponentów mogły być względem tego katalogu. Nie dodano modeli
pomiarowych komponentów.

Przykładowy układ: `family/common.enet`, `family/stackup.json`,
`family/variant/board.zip`. Lokalny `.enet` lub stackup w `variant` zastępuje
wyłącznie odpowiadające mu wejście rodzica.

ZIP pozostaje źródłem: `ZipMember` czyta pojedyncze wpisy przez ZipFile,
Gerbonara parsuje tekst przez `from_string`. Nie używamy extract/extractall,
nie powstają rozpakowane Gerbery w outcomes ani obok ZIP. Zwykłe katalogi
nadal korzystają z Path i dotychczasowego otwierania Gerbonara. Obsługiwany
jest korzeń archiwum albo jeden katalog opakowujący, nie łączenie drzew.

Limity: 4096 wpisów, 32 MiB na plik, 256 MiB sumy rozpakowanych danych,
512 MiB pliku ZIP. Odrzucamy traversal, ścieżki absolutne/Windows/UNC,
duplikaty po normalizacji separatorów i wielkości liter, symlinki/specjalne
wpisy, szyfrowanie i uszkodzenia. ZIP jest hashowany strumieniowo; każdy wpis
ma SHA256 swoich dokładnych nieskompresowanych bajtów. Metadane używają
`archive.zip::member`, bez ścieżek tymczasowych.

EasyEDA: Thickness oznacza mm; dla miedzi jest przeliczana na µm w kontrakcie
physical. Miedź/dielektryk muszą występować naprzemiennie od top do bottom.
Wewnętrzne aktywne warstwy otrzymują role inner1, inner2 itd. Maska, pasta i
sitodruk pozostają pominięte. Permittivity musi wynosić co najmniej 1;
nie zgadujemy epsilon z nazwy FR4. Loss Tangent=0 pozostaje zerem.
Conducting sheet, 58 MS/m oraz PTH 25 µm solid_pec_equivalent są jawnymi
założeniami projektu. Grubość miedzi nie tworzy komórek Z.

### Rzeczywisty test1 — wynik diagnostyczny

Lokalne `stacup.json` i `test1.enet` oraz ich warianty w jednym rodzicu dają
identyczną geometrię źródłową, normalizowaną, modelowaną i siatkę. Import ZIP
jest również identyczny z dawnym rozpakowanym katalogiem. Po tej kontroli
usunięto tylko kopię `gerbs/realpcb_microstrip/test1/`.

Stack: 35 µm Cu / 0,2 mm dielektryka, epsilon=4,5, tanδ=0 / 35 µm Cu.
Jeden CSRC, R1=49,9 Ω, dwa zdeduplikowane PTH top–bottom; topologia przy
10 µm PASS. Dla preview, center 2000 MHz, cutoff 1000 MHz, sweep
1500–2500 MHz co 10 MHz, po PCB-012E:

| Profil | Siatka | Komórki | Minimum XYZ [µm] | Minimum kroków impulsu | Aktualizacje komórek |
| --- | --- | ---: | --- | ---: | ---: |
| preview | 92×112×45 | 463680 | 10 / 30 / 100 | 90937 | 42165668160 |
| design | 98×126×58 | 716184 | 10 / 30 / 66,67 | 91442 | 65489297328 |

R1 przechodzi końcowy audyt styków w obu profilach przy geometrii 10 µm.
Dodatkowe granice okna kontaktu zmieniają siatkę XY; nie zmieniają geometrii,
wartości RLC, źródła ani osi Z. Wcześniejsze preview miało 356040 komórek,
ale nie pozwalało zainstalować R1.

**Prepare-only dochodzi do kosztu, po czym nadal odrzuca budżet impulsu:**
90937 > 50000 dla preview i 91442 > 75000 dla design. Jest to osobne
ograniczenie, poza naprawą kontaktów PCB-012E. Nie zmieniono profili ani
limitów kroków. Nie wykonano natywnego XML/FDTD dla tego wariantu.

Polecenie diagnostyczne Windows (zatrzymuje się na opisanym limicie impulsu;
analogicznie dla `--quality design`):

```bat
set "PY=.\.venv\Scripts\python.exe"
set "CSXCAD_INSTALL_PATH=C:\dev\openems\openEMS"
%PY% -m antenna_lab.pcb.gerber_control ^
  gerbs\realpcb_microstrip\test1.zip ^
  --geometry-resolution-um 10 ^
  --quality preview ^
  --center-mhz 2000 ^
  --cutoff-mhz 1000 ^
  --sweep-start-mhz 1500 ^
  --sweep-stop-mhz 2500 ^
  --sweep-step-mhz 10 ^
  --prepare-only
```


### Test1 po PCB-012F (bez FDTD)

10 µm, center 2 GHz, cutoff 1 GHz, wyniki 1,5–2,5 GHz co 10 MHz:

| Profil | Siatka | Komórki: PCB-012E → PCB-012F | Minimum XYZ [µm] | Minimum kroków impulsu |
| --- | --- | ---: | --- | ---: |
| preview | 333×265×45 | 463680 → 3971025 | 4,0722 / 4,1667 / 100 | 295026 |
| design | 345×221×58 | 716184 → 4422210 | 4,0722 / 8,3333 / 66,6667 | 235091 |

Zachowano 16 fizycznych współrzędnych X i 12 Y, pominięto 0. Audyt miedzi
oraz kontakt R1: PASS. Pomijane są tylko środki bbox. Limitu max_cells nie
przekroczono. Budżety impulsu 50000/75000 są nadal przekroczone; nie zmieniono
profili ani czasu zakończenia. Przyrost kosztu wynika z zachowania cech miedzi
i gradingu, nie globalnej kraty geometrii. Liczby wcześniejszych sekcji opisują
poprzednie polityki meshera i nie są oczekiwaniem dla PCB-012F.


## PCB-013A: jawne profile openEMS i zatwierdzanie przebiegu

Źródłem domyślnych preview/design/verify jest `parameters/openems_profiles.toml`.
Plik zawiera wszystkie kontrolowane parametry mesh/domain/BC/czasu/runtime oraz
komentarze. Zmiana pliku zmienia przyszłe przebiegi; `--openems-config PATH`
wybiera inny plik. Rozdzielczość geometrii CAD pozostaje osobną opcją.

NrTS (`max_timesteps`) to sufit bezpieczeństwa, nie czas obliczeń ani definicja
preview. Domyślnie każdy profil ma 1 miliard kroków. EndCriteria określa zanik
energii. MaxTime jest fizycznym czasem propagacji, nie czasem zegarowym; 0
wyłącza jego jawne ustawienie. Przy MaxTime pokazujemy przybliżone df=1/MaxTime,
nie obietnicę fizycznej dokładności widma. Limit krótszy niż impuls jest błędem.

Przed importem i meshingiem CLI pokazuje rozwiązany profil oraz pyta Y/N/E.
N kończy bez native. E pozwala zmieniać nazwy wypisanych parametrów (SI, np.
`excitation_center_hz`, `result_frequency_hz`, `loss_reference_frequency_hz`);
tablice podaje się jako `[1.5e9, 2e9, 2.5e9]`. Puste pole nazwy kończy edycję,
potem następuje walidacja i kolejne pytanie. Plik TOML nie jest nadpisywany.
`--openems-set key=value` można powtarzać. Pierwszeństwo: TOML, argumenty
częstotliwości eksperymentu, openems-set, edycja E. Zmiana center aktualizuje
domyślną częstotliwość pól; jawne częstotliwości/loss reference pozostają jawne.

Automatyzacja wymaga `--yes`; bez TTY program nie czeka na input.
`--prepare-only` pokazuje profil, ale nie pyta o zgodę. API Pythona nie pyta.
Przykład CMD (uruchomienie FDTD dopiero po własnym Y):

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control ^
  gerbs\realpcb_microstrip\test1.zip --quality preview ^
  --center-mhz 2000 --cutoff-mhz 1900 ^
  --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10
```

Pola domyślnie są ON na center, bez drugiego solve. `--fields-mhz` wybiera inne
częstotliwości, `--no-fields` jawnie wyłącza zapis. `disable_dumps=true` wymaga
braku żądanych pól. Raport odtwarza fazory co 15°, bez ponownego FDTD;
`report --phase-step 30` nadal nadpisuje prezentację. `summary.json` przechowuje
profil, ścieżkę/SHA256 TOML, rozwiązane parametry, nadpisania i sposób zgody;
raport pokazuje ten zapis offline.

AUTO TimeStep nie przekazuje argumentu TimeStep. Jawny krok wymaga CFL
(method=1) i nie może przekroczyć konserwatywnego limitu CFL ukończonej siatki
pomnożonego przez factor. Rennings (3) działa automatycznie; factor >0..1.
Nie zmieniamy siatki dla mieszanego BC: nieaktywne pasy PML są zwykłą przestrzenią,
a PEC/PMC/MUR leżą na zewnętrznej granicy. Metadane wskazują aktywne ściany PML.
Zmienia to fizykę brzegów tylko po jawnej zmianie użytkownika.

Statystyki domyślnie ON; przy OFF wynik ma `finished_unverified` oraz
`not_established_statistics_disabled`, nie potwierdzone zakończenie. Osiągnięcie
NrTS lub włączenie limitu MaxTime kończącego przed zanikiem jest wykrywane
przed CalcPort, jeżeli są statystyki. Profile nie są certyfikatem zbieżności.

API sprawdzono w dokumentacji openEMS 0.37.0-rc3 i przypiętym źródle:
https://docs.openems.de/en/latest/python/openEMS/openEMS.html
https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/openEMS.pyx
Syntetyczne komendy diagnostyczne zachowują dotychczasowe ustawienia; runtime
jest opcjonalnym, walidowanym obiektem w PcbSimulationSettings.
