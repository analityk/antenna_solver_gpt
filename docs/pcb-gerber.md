# PCB-010A: pierwszy import EasyEDA

Importer czyta wyłącznie jawnie wskazane pliki top copper i board outline.
Gerbonara 1.6.3 parsuje RS-274X; Shapely 2.1.x łączy nachodzące i stykające
się powierzchnie. Regiony, pady oraz linie/łuki o kołowym przekroju pisaka
wchodzą do tej samej sumy miedzi. Każda rozłączna wyspa daje jeden rekord
CopperPolygon. GKO opisuje linię środka zamkniętego obrysu, nie zewnętrzną
krawędź pisaka. Współrzędne zostają przeliczone na metry na granicy importera,
a następnie normalizowane dokładnie raz istniejącą transformacją portu.

## Instalacja i uruchomienie w CMD

```bat
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e .
set "CSXCAD_INSTALL_PATH=C:\dev\openems\openEMS"
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gerber_control parameters\pcb_easyeda_stroked_feed.json --prepare-only
```

To przygotowuje XML, bez FDTD. Aby wykonać pojedynczy przebieg, usuń
`--prepare-only`. Każde wywołanie tworzy nowy katalog w `outcomes/pcb_gerber`.
Opcjonalny `--output` wymaga pustego/nowego katalogu. Dostępne są te same
opcje częstotliwości co w pcb.control: `--center-mhz`, `--cutoff-mhz`,
`--frequencies-mhz`, `--loss-reference-mhz`.

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

## Istotna różnica między podanymi wymiarami a rzeczywistym GTL

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
  0,86401 mm i cała miedź pozostają bez zmian. To konfiguracja wskazana
  w poleceniu powyżej. Nie jest wynikiem automatycznego wykrywania portu.

Obie konfiguracje używają startowych parametrów laminatu 1,6 mm, epsilon_r
4,3 i tan(delta) 0,018. Gerber ich nie określa — należy wpisać rzeczywiste
wartości w pcb.json przed interpretacją wyników.

## Wyniki i ograniczenia

`geometry.source.json`, `geometry.json` i `import.json` zachowują geometrię
źródłową/znormalizowaną, transformację, rozwiązane parametry, SHA256 plików,
wersje bibliotek i założenia. `native/model.xml` jest przygotowanym modelem.
Po solve powstają `impedance.csv` i `summary.json`; po błędzie pliki natywne
pozostają, a import_failure.json opisuje błąd. Status walidacji: unverified.

Model: miedź górna PEC o zerowej grubości; bez dolnej miedzi, przelotek,
soldermaski, sitodruku, pasty i chropowatości. Parametry laminatu pochodzą
z konfiguracji. Grubość/przewodność miedzi pozostają metadanymi wejściowymi.

Krzywe są aproksymowane odcinkami z budżetem błędu geometrycznego 0,1 um.
Usuwanie pozostałości operacji geometrycznych ma tolerancję 1 pm, bez
zaokrąglania do siatki. To nie deklaracja dokładności elektromagnetycznej.
Importer odrzuca clear/negative polarity, otwory w końcowych poligonach,
połączenia wyłącznie punktowe, inne niż kołowe pisaki linii oraz
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
