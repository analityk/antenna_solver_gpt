# PCB-009E: lokalna wrażliwość zagęszczonej siatki

Eksperyment rozdziela pozostałą zmianę impedancji między thirds L2 i L3 na
wpływ rozdzielczości falowej, portu oraz Z laminatu. Nie zmienia domyślnego
trybu `aligned`, geometrii ani fizycznego portu 50 ohm.

```bat
set "CSXCAD_INSTALL_PATH=C:\dev\openems\openEMS"
.\.venv\Scripts\python.exe -m antenna_lab.pcb.refined_sensitivity
```

Obsługiwane są `--center-mhz`, `--cutoff-mhz`, `--frequencies-mhz`,
`--loss-reference-mhz` i opcjonalny `--output` wskazujący nowy/pusty katalog.
Domyślne pasmo: 1300/1420/1500 MHz, środek 1420 MHz, cutoff 200 MHz.

| Wariant (kolejność wykonania) | Komórki/długość fali | Port gap/width | Laminat Z |
| --- | ---: | ---: | ---: |
| thirds_L2_reference | 40 | 6/6 | 12 |
| thirds_wave50 | 50 | 6/6 | 12 |
| thirds_port8 | 40 | 8/8 | 12 |
| thirds_substrate16 | 40 | 6/6 | 16 |
| thirds_L3_combined | 50 | 8/8 | 16 |

Wszystkie warianty używają `thirds`, PML 8, padding 0,25 długości fali,
gradingu 1,4/1,5, EndCriteria 1e-5 oraz limitu 100000 kroków. Każdy przebieg
włącza exact_endcriteria i dump_statistics. Nie zwiększa limitu max_cells.
Geometria powstaje raz. Kontrola siatki i portu poprzedza każdy natywny solve.
Raport zapisuje rzeczywiste liczby komórek portu — mogą być wyższe od minimum.

Wyniki trafiają do `outcomes/pcb_refined_sensitivity/<unikalny id>/`.
Każdy wariant zachowuje pliki natywne; główne raporty to
`refined_sensitivity.json` i `refined_sensitivity.csv`. Brak wymaganych
statystyk, osiągnięcie limitu kroków lub inny błąd zatrzymuje badanie,
zachowując wcześniejsze wyniki. Nie ma wznowienia ani automatycznych
kolejnych zagęszczeń.

## Odczyt raportu

Przyrosty R, X i zespolonego Z są liczone względem nowego L2 z tego samego
badania. W JSON liczby zespolone zapisano jako `{real, imag}` w ohmach;
w CSV kolumna delta_Z_vs_L2 zawiera ten sam obiekt JSON. Osobna kolumna
abs_delta_Z_vs_L2 podaje moduł. Względne wartości są ułamkami, nie procentami.
Mianowniki R/X mają dolną granicę 1 ohm, a Z — impedancję odniesienia.
Pojemność zastępcza i jej zmiana są dostępne tylko dla reaktancji ujemnych.

Suma trzech zespolonych przyrostów jest porównywana z przyrostem łącznym.
Reszta interakcji nie jest estymatorem błędu. Udziały modułów i względna
reszta używają mianownika `max(abs(dZ_combined), 1 ohm)`; udziały mogą
przekroczyć łącznie 100%, ponieważ wektory mogą się znosić.

`mixed` oznacza różnicę dwóch największych wkładów mniejszą niż 10%
większego wkładu, brak jakiegokolwiek wkładu lub różne dominujące czynniki
na różnych częstotliwościach. `strong_interaction` ma pierwszeństwo, gdy
moduł reszty przekracza połowę modułu przyrostu łącznego na dowolnej
częstotliwości; ten próg nie używa dolnej granicy 1 ohm.

Klasyfikacja wskazuje temat następnej analizy: port, interfejsy Z laminatu,
grading XY albo sprzężenie dyskretyzacji portu/laminatu. Nie uruchamia jej.
Status powodzenia to `diagnostic_pending_review`, nie walidacja fizyczna.
Liczba aktywnych krawędzi Ex nie dowodzi zmiany rezystancji źródła:
openEMS skaluje element RLC według liczby komórek szeregowych/równoległych.
Nie zmieniamy rezystora, sond ani wymiarów portu.
