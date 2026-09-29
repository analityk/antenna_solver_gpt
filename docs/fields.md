# Diagramy pól E/H

Obsługiwane modele: biquad i Quados 8. Ten sam adapter zapisuje wszystkie
trzy zespolone składowe E i H; diagram przedstawia wybrane podpisane składowe.

## Uruchomienie w CMD

```bat
git pull --ff-only
.\.venv\Scripts\python.exe -m antenna_lab run --config parameters\biquad_1420mhz.json --fields
.\.venv\Scripts\python.exe -m antenna_lab report biquad_1420mhz.json --open
```

Dla Quadosa lub własnego wariantu podmień nazwę JSON w obu poleceniach.
`--fields` działa też z `check` i `prepare`. Nie zmienia wymiarów anteny,
liczby komórek, źródła ani siatki; dodaje sześć pasywnych zapisów 2D
(E i H w trzech przekrojach). Zwiększa pracę zapisu/DFT, nie wykonuje
oddzielnego FDTD dla każdej fazy. Nie zapisuje pełnego filmu ani objętości 3D.

Diagramy powstają automatycznie na końcu run w HTML i w `plots/fields_*.png`.
Raport ma przy każdym diagramie odnośnik „Pobierz diagram PNG”.
Zmiana faz lub składowych wykorzystuje już policzone dane:

```bat
.\.venv\Scripts\python.exe -m antenna_lab report biquad_1420mhz.json --phase-step 15 --open
.\.venv\Scripts\python.exe -m antenna_lab report biquad_1420mhz.json --phase-step 30 --field-components x z --open
```

Druga komenda wybiera E_x i H_z we wszystkich przekrojach. Do wyboru każda
para x/y/z. Bez opcji fazy pochodzą z `requested_outputs.phase_degrees`
(domyślnie 0–180° co 30°). `--phase-step 15` tworzy 13 wierszy, `30` — 7.
Raport dla dawnego przebiegu bez pól pokazuje brak danych: nie odtworzy
rozkładu bliskiego z samej impedancji lub NF2FF. Potrzebny jest nowy run.

## Płaszczyzny i kolory

- `xy_front`: widok przed promiennikiem; domyślnie 20 mm przed osiami drutów.
  Długa oś y jest pozioma, x pionowa. Domyślny diagram: E_x oraz H_z.
- `xz`: przez środek portu, przy stałym y; domyślnie E_x i H_y.
- `yz`: przez środek portu, przy stałym x; domyślnie E_x i H_y.

Położenie jest przyciągane do najbliższej istniejącej linii siatki. Diagram
podaje położenie żądane i faktyczne. Pole leży w pokazanym przekroju,
a linie przewodów i reflektora są rzutem geometrii. To nie jest mapa
prądu powierzchniowego ani pole obliczone dokładnie na powierzchni metalu.
H_z pokazuje lokalne pole pętli, nie główną składową fali biegnącej w +z.

Przykład zmiany odległości mapy przed anteną:

```bat
.\.venv\Scripts\python.exe -m antenna_lab run --config parameters\biquad_1420mhz.json --fields --front-offset-mm 10
```

Przesunięcie przekroju wymaga nowego zapisu FDTD. Opcja trafia do rozwiązanego
JSON jako `requested_outputs.field_front_offset_m`; domyślnie 0.02 m.
Można również wpisać wybrane nazwy do `requested_outputs.field_planes`.
Własna konfiguracja z tym polem nie potrzebuje flagi `--fields`.

Czerwony oznacza dodatnią składową, niebieski ujemną, biały zero. E ma
jednostkę V/m, H na diagramie mA/m (w plikach A/m). Skala sym-log uwidacznia
słabsze pole; jest symetryczna względem zera i stała między fazami danej
składowej/częstotliwości. Granica wynika z maksymalnej amplitudy fazora,
bez przycinania silnych wartości i bez skalowania każdej klatki osobno.
Diagramy różnych anten mają osobne skale — porównuj liczby na legendach.

## Konwencje i ograniczenia

openEMS zapisuje transformaty impulsu w HDF5 (typy 10 i 11, interpolacja
do węzłów, dump_mode=1). DFT używa własnych znaczników czasu E i H;
adapter nie dodaje drugiej korekty półkroku H. Oba pola dostają ten sam
zespolony mnożnik z `port_spectra.npz`: amplituda dla żądanej mocy
odniesienia i faza dodatniego maksimum napięcia portu.
Klatka to część rzeczywista fazora pomnożonego przez exp(+j·faza).
180° musi odwracać znak względem 0°. Podany czas to faza podzielona przez
360° i częstotliwość, a nie czas uruchamiania impulsu.

To normalizacja do pojedynczego pomiaru U/I portu, którego rozbieżność
z pracą lokalną pozostaje otwarta. Nie korygujemy bilansu ani zysku obrazem.
Status pozostaje unverified; nie wykonano jeszcze natywnej kontroli
tych przekrojów na Windowsie ani testu zbieżności pola dla anteny.

Interpolacja pól na granicach PEC bywa niewiarygodna. Szare obszary to
geometria metalu, obwiednia o szerokości jednej lokalnej przekątnej komórki
oraz idealne źródło z takim otoczeniem. To konserwatywna maska geometryczna,
nie dokładna mapa metalowych voxeli openEMS. Próbki maskowane są NaN,
a nie zerami. Wszystkie surowe próbki pozostają w HDF5.
Prądy przewodów i animacja pełnego okresu nadal nie są obsługiwane.

## Zapis danych

- `field_layout.json`: żądane/faktyczne położenia, zakresy, kształty i nazwy HDF5.
- `openems/fields_<przekrój>_E.h5`, `..._H.h5`: surowe zespolone widma.
- `fields/metadata.json`: kontrakt pól v1, jednostki, maski i normalizacja.
- `fields/<przekrój>.npz`: `frequency_hz`, `x_m/y_m/z_m`,
  `E_v_per_m`, `H_a_per_m` o osiach [częstotliwość, składowa xyz, x, y, z];
  oś prostopadła ma długość 1. `mask` ma osie [x,y,z] i bity 1=metal,
  2=otoczenie interpolacji, 4=źródło z otoczeniem. Zapisano również
  `normalization_factor`, `reference_power_w`, `phasor_convention` i `array_order`.

Brak pliku, inna siatka E/H, zła kolejność lub częstotliwość są błędem;
nie zastępuje się ich zerami ani domyślnym wykresem. Limit zapisu wynosi
4 mln punktów przestrzennych × częstotliwości łącznie we wszystkich płaszczyznach.
Fazy generowane z tych samych fazorów nie powiększają tego limitu.

API sprawdzono w przypiętych źródłach CSXCAD/openEMS, opisanych w
[sources.md](sources.md). Sprawdzenia syntetycznymi danymi obejmują znak
i referencję fazy, proporcje fali płaskiej, maskowanie, zapis/odczyt, skale
diagramów i niezmienność źródeł przy raportowaniu; nie są symulacją anteny.
