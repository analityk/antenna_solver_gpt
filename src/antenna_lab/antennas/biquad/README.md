# Biquad

Klasyczny biquad: dwa romby, łącznie osiem odcinków drutu, wspólna szczelina
zasilania i opcjonalny płaski reflektor. To odrębny model `biquad`.

| Parametr | Znaczenie |
| --- | --- |
| S | Długość osi każdego z ośmiu odcinków |
| G | Odległość środków zacisków zasilania; prześwit między kulami = G − średnica |
| H | Odległość osi drutu od przedniej powierzchni reflektora |
| wire_diameter | Średnica drutu i kul węzłowych |
| reflector_length / width / thickness | Wymiary skończonej płyty PEC; długość wzdłuż y |

Wszystkie wymiary JSON są w metrach, edytor wyświetla mm. Zaciski są
na x = ±G/2, y = 0, z = H. Każda gałąź łączy zaciski czterema odcinkami S,
a obie są odbiciami względem y = 0. Nie ma metalowego mostka w szczelinie.
Żeby zachować długość wszystkich ośmiu boków, skończona szczelina nieznacznie
odkształca kąty rombów. Przy q = S/sqrt(2) skrajne boczne wierzchołki mają
x = ±(q + G/2), y = ±q; końce leżą na x = 0,
y = ±[q + sqrt(S² − (q + G/2)²)]. Generator sprawdza możliwość domknięcia,
prześwit portu, połączenia i kolizje.

Konfiguracja `parameters/biquad_1420mhz.json` używa S = długość fali / 4
(52,7804 mm), H = długość fali / 8 (26,3902 mm), G = 6 mm i drutu 3 mm.
Reflektor ma 211,1214 × 211,1214 × 2 mm. To punkt startowy, bez strojenia
i bez obietnicy impedancji lub zysku. Zref wynosi 50 Ω; nie oznacza to,
że antena została dopasowana do 50 Ω.

Źródło koncepcji dwóch kwadratów i ośmiu boków około ćwierć fali:
[Trevor Marshall — Biquad](https://trevormarshall.com/biquad.htm).
Nasza konstrukcja to idealizacja ze skończoną szczeliną, a nie dokładna kopia
tego zasilacza z koncentrykiem, rurką i obrzeżem reflektora.

Model korzysta z istniejącego eksperymentalnego portu różnicowego,
`mesh_anchors`, siatki oraz diagnostyki mocy. Nie zawiera kabla, baluna ani
strat materiałowych. Walidacja portu i zbieżności pozostaje otwarta.
Raport domyślnie pokazuje widmo 1200–1650 MHz co 0,25 MHz; pole dalekie
i bilans są obliczane przy 1420 MHz. Map E/H nadal nie zaimplementowano.

```bat
.\.venv\Scripts\python.exe -m antenna_lab preview --config parameters\biquad_1420mhz.json
.\.venv\Scripts\python.exe -m antenna_lab check --config parameters\biquad_1420mhz.json
.\.venv\Scripts\python.exe -m antenna_lab run --config parameters\biquad_1420mhz.json
.\.venv\Scripts\python.exe -m antenna_lab report biquad_1420mhz.json --open
```

Po zmianach w edytorze zapisz wariant pod nową nazwą i użyj jej w `--config`
oraz w `report`. Przycisk wczytywania pozwala przełączać Quadosa i biquad.
