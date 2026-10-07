# Globalna kratownica PCB — infrastruktura PCB-012A

Ten moduł **nie jest włączony do FDTD**. Nie ma przełącznika CLI. Aktywne
Gerbery, siatka, materiały, XML i domyślne ustawienia pozostają bez zmian.
Nie należy przekazywać nowego typu do obecnego adaptera openEMS.

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

`source_json` przechowuje niemutowalną kopię zaimportowanego modelu wraz
z wartościami i SHA256. `.provenance` oraz `.as_dict()` zwracają odłączone
kopie JSON. Funkcja nie zmienia żadnego pliku ani źródłowego PcbGeometry.
Nie ma jeszcze geometrii powietrza/PML ani osi siatki w tym nowym typie;
następne moduły mają użyć tej samej kratownicy do wszystkich ich granic.

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
EM ani gotowość nowej reprezentacji do aktualnego solvera.

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
