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
| preview | 10 | 2 | 2/2 | 0,10 | 6 | 1e-3 | 50000 | false |
| design | 15 | 3 | 2/2 | 0,15 | 6 | 1e-4 | 75000 | false |
| verify | 20 | 4 | 4/4 | 0,25 | 8 | 1e-5 | 120000 | true |

To profile numeryczne, nie certyfikaty dokładności. Miedź CSXCAD, wymiary
portu, laminat i żądane częstotliwości pozostają identyczne.
Wybór profilu nie uruchamia macierzy ani dodatkowych przebiegów.

### Kotwice ekonomicznej siatki

Polityka `gerber_economical_v1` zachowuje dokładnie granice płytki i zewnętrzne
granice materiałów, końce i środek portu X, krawędzie i środek portu Y oraz
oba interfejsy laminatu, w tym literalne z=0. Nie przesuwa żadnego poligonu.

Najpierw zachowuje krytyczne współrzędne. Następnie rozpatruje minimum i
maksimum bounding box każdej wyspy miedzi w kolejności współrzędnych/ID.
W `verify` na końcu rozpatruje także środki bounding box; preview/design
je pomijają. Kandydat zostaje usunięty, jeżeli odległość od dowolnej już
zachowanej kotwicy jest mniejsza niż 0,5 razy mniejsza z rozdzielczości
lokalnych obu kotwic. Lokalna rozdzielczość to krok XY laminatu poza zakresem
portu, a wewnątrz zakresu portu — minimum tego kroku i kroku portu danej osi.
Równość z progiem jest dopuszczalna. Takie same reguły ochrony obowiązują
wszystkie profile; krytycznych kotwic nigdy nie usuwa się dla oszczędności.

`summary.json` zapisuje `mesh_anchor_policy` i listę
`suppressed_noncritical_anchors`: oś, współrzędną SI, ID miedzi, rodzaj,
powód, a dla konfliktu także sąsiada, odległość i próg. Współrzędne
identyczne z zachowanymi liniami nie są raportowane jako usunięte.
Usunięcie kotwicy nie oznacza usunięcia krawędzi fizycznej. Dodatkowy audyt
poligonów nie pozwala, aby rzadka siatka ukryła miedź wewnątrz szczeliny
portu (z dotychczasową tolerancją geometryczną 1e-10 m).

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

Ani otwory, ani fizyczna grubość conducting sheet nie dodają linii siatki.
Po ich instalacji wykonywany jest dokładny audyt zamrożonych osi i jednostki.
Zmiana obrysu lub rozłączenie miedzi przez clear może zmienić dotychczasowe
kotwice bounding-box przewodników; nie jest to dodatkowe zagęszczanie otworów.
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
