# Lokalne raporty HTML

Raport działa z zapisanymi wynikami. Nie potrzebuje openEMS/CSXCAD, serwera,
internetu, konta ani klucza API. Nie uruchamia FDTD i nie zużywa tokenów.
Wystarcza środowisko projektu z NumPy, Matplotlib, jsonschema i h5py.

## Raport wybranego wariantu — także z dawnych obliczeń

```bat
.\.venv\Scripts\python.exe -m antenna_lab report quados8_variant_sz4.json --start-mhz 1200 --stop-mhz 1650 --step-mhz 0.25 --open
```

Podaj plik wariantu. Sama nazwa jest szukana najpierw w bieżącym katalogu,
a następnie w `parameters/`; można też podać pełną ścieżkę. Program odczytuje
`parameters.resolved.json` ukończonych symulacji i dopasowuje faktyczną
geometrię, model fizyczny oraz częstotliwości. Nie polega na polu `id`, które
we wcześniejszych wariantach mogło mieć tę samą wartość.

Gdy jest kilka pasujących wyników, wybiera najnowszy z takimi samymi
ustawieniami symulacji i solvera. Jeśli takich nie ma, wybiera najnowszą
zgodną geometrię i częstotliwości, wypisując ostrzeżenie o innych ustawieniach.
Wybrany katalog zawsze pojawia się w terminalu. Brak zgodnej geometrii
oznacza błąd; program nie podstawi innej anteny ani nie uruchomi solve.
Po zmianie wymiarów w JSON należy użyć kopii pasującej do starych obliczeń.

To działa również z dotychczasowymi katalogami nazwanymi samą datą i ID.
Ich pliki i manifesty pozostają niezmienione. Nowy HTML otrzymuje nazwę
wybranego wariantu. Nazwy nowych katalogów obliczeń mają postać
`quados8_variant_sz4__20260928T221500Z_0123456789`; czas i ID zachowują
niezależność kolejnych obliczeń tej samej geometrii.

## Najnowsza ukończona symulacja — Windows CMD

```bat
cd /d C:\dev\antenna_solver_gpt\antenna_solver_gpt
git pull --ff-only
.\.venv\Scripts\python.exe -m antenna_lab report --latest --open
```

W istniejącej instalacji edycyjnej (`pip install -e .`) nie trzeba instalować
projektu ponownie. `--latest` wybiera najnowszy czas utworzenia zapisany w
manifeście o etapie `simulation` i stanie `completed`; pomija `prepare`,
eksporty geometrii, przerwane i trwające obliczenia. Wymaga też `summary.json`.
Nie wybiera katalogu tylko dlatego, że był ostatnio modyfikowany.

Nowy samodzielny HTML trafia do `outcomes/reports/`. Nazwa jest stabilna:
`stripline3_004` → `stripline3_004.html`; przy ponownym generowaniu bez
`--output` powstają `stripline3_004__002.html`, `stripline3_004__003.html`
itd. **Bez timestampu.** Istniejących raportów nie nadpisujemy. Przy
raportowaniu wariantu anteny wybranego przez `report <wariant.json>` nazwa
uwzględnia jawny wariant i katalog przebiegu (`wariant__run.html`).
`--output` zachowuje dokładną nazwę podaną przez użytkownika i kończy się
błędem, jeśli plik istnieje. Automatyczny `report.html` w nowym katalogu
`run` pozostaje bez zmian. Ścieżka pojawia się w terminalu.
`--open` otwiera go w domyślnej przeglądarce; można też otworzyć
plik dwuklikiem. Po skopiowaniu samego HTML na inny komputer nadal działa.
JavaScript steruje suwakami i wykresami; bez niego dostępne są statyczne
wykresy i tabele. Wydruk używa statycznego wykresu z pierwotnym Zref.

## Konkretny przebieg i miejsce zapisu

```bat
.\.venv\Scripts\python.exe -m antenna_lab report "outcomes\runs\20260928T004231Z_902d497594" --open
```

Można podać inny folder, również rozpakowaną diagnostykę:

```bat
.\.venv\Scripts\python.exe -m antenna_lab report "C:\wyniki\moj_przebieg" --output "C:\wyniki\raport-01.html" --open
```

Istniejącego pliku nie nadpisujemy. Nowy raport powstaje poza folderem
źródłowego przebiegu, aby zachować jego manifest i skróty. Brak manifestu
w małej paczce daje informację o niepotwierdzonym stanie wykonania; nie
blokuje odczytu dostępnych danych. Pusty lub uszkodzony zestaw danych
kończy się komunikatem, a nie wykresem zastępczym.

Kolejne `run` automatycznie tworzą `report.html` i obrazy w swoim nowym
folderze, przed końcowym spisem SHA-256. Obejmuje to diagnostykę mocy.
Błąd samego raportu pozostawia ukończone wyniki i ostrzeżenie; można później
ponowić `report`. Nie trzeba z tego powodu powtarzać symulacji.

## Co można oglądać

| Część | Funkcje i granice |
| --- | --- |
| Widmo portu | Suwak i wpisana częstotliwość wybierają najbliższą zapisaną próbkę; można też kliknąć wykres |
| Dopasowanie | Zref: 50/75/100/200 Ω i wartość użyta w przebiegu; R, X, SWR, S11, moc odbita i strata niedopasowania |
| Minimum SWR | Minimum w dostępnych próbkach, z ostrzeżeniem o brzegu zakresu; nie automatyczne strojenie anteny |
| X = 0 | Przybliżone przejścia reaktancji przez zero, interpolowane liniowo między punktami |
| CSV | Widmo i przeliczone dopasowanie dla wybranego Zref; bez zmiany źródłowego CSV |
| Bilans mocy | Moc odniesienia portu, lokalna praca i zapisane strumienie; obie różnice mają jawne mianowniki |
| Praca krawędzi | Liczba wkładów dodatnich, ujemnych i bliskich zeru z NPZ; kontrola zgodności sumy z JSON |
| Pole dalekie | Przekroje xz/yz z zapisanego NPZ przy częstotliwości najbliższej celowi; brak pliku oznacza brak wykresu |
| Zysk i kierunkowość | Osobne wielkości na +z; porównanie zysku względem pracy lokalnej pozostaje diagnostyką |
| Wiarygodność | Parametry i commit obliczeń, status, ostatni poziom energii, ostrzeżenia logu, skróty plików wejściowych |

Zmiana Zref to przeliczenie współczynnika odbicia. Nie modeluje baluna,
transformatora ani zmiany źródła. Dla R ≤ 0 raport nie podaje pasywnego SWR
ani straty niedopasowania. Taki wynik wymaga wyjaśnienia w modelu/pomiarze.

Suwak widma **nie zmienia częstotliwości tabel bilansu i pola dalekiego**.
Te części mają własne etykiety częstotliwości. Nie interpolujemy mocy
i charakterystyki między brakującymi pomiarami. Mała paczka diagnostyczna
zwykle nie zawiera `far_field.npz`; pełny lokalny przebieg może go zawierać.

## Gęstszy odczyt istniejącego przebiegu

Domyślny odczyt używa `impedance_dense.csv`, a przy jego braku
`impedance.csv` lub impedancji w `summary.json`. Jeżeli dostępny jest tylko
jeden punkt oraz istnieją surowe `openems/port_ut_1`, `openems/port_it_1`
i pasmo wymuszenia w `mesh.json`, raport sam wyznacza 1001 punktów DFT
wokół centrum: ±10% częstotliwości środkowej, zawężone do pasma wymuszenia.

Własny zakres, np. podobny do pierwszego raportu:

```bat
.\.venv\Scripts\python.exe -m antenna_lab report --latest --start-mhz 1300 --stop-mhz 1550 --step-mhz 0.25 --open
```

Wszystkie trzy opcje muszą wystąpić razem. Wymagają surowych sond portu
i `mesh.json`; zakres musi mieścić się w zapisanym paśmie wymuszenia.
Limit wynosi 10001 próbek. Koniec trafia do widma tylko wtedy, gdy wypada
na siatce określonej przez początek i krok. Używane są osobne znaczniki czasu
U oraz I, z uwzględnieniem przesunięcia próbek H o połowę kroku czasowego.

To ponowna transformata **istniejących próbek czasowych**, bez solve.
Mniejszy krok daje więcej odczytów tej samej transformaty; nie zwiększa
czasu symulacji, fizycznej rozdzielczości ani zaufania do wyniku. Poza
użytecznym pasmem źródła i przy słabym widmie prądu impedancja jest podatna
na błędy. Raport nie ocenia automatycznie stosunku sygnału do szumu widma.

## Interpretacja bilansu

Raport oblicza osobno:

- `(moc portu − praca lokalna) / moc portu`;
- `(praca lokalna − strumień zewnętrzny) / praca lokalna`.

Różnica względem pojedynczego U·I nie jest automatycznie stratą anteny.
Zgodność strumienia z pracą lokalną nie zatwierdza impedancji ani siatki.
`power_feed` przecina przewody i nie jest mocą promieniowania całej anteny.
Zysk względem pracy lokalnej pokazujemy wyłącznie jako porównanie; nie
modyfikujemy zysku ani impedancji w wynikach. Wszystkie obecne modele
pozostają `unverified`.

Raport odczytuje zapisaną diagnostykę powierzchni, bez ponownego całkowania
HDF5. Wkłady bliskie zeru mają próg `max(1e-10 × największy moduł wkładu,
1e-15 W)`. Sumy SHA-256 identyfikują dostępne pliki, lecz nie stanowią
pełnego porównania z manifestem. Automatyczny raport pomija skrót manifestu,
który jest zamykany dopiero po zapisaniu raportu.

Zapisane przekroje E/H są pokazywane jako diagramy fazowe, z pobieraniem PNG.
`report ... --phase-step 15` lub `30` zmienia liczbę klatek bez FDTD;
`--field-components x z` wybiera E_x i H_z. Nowy zapis wymaga `run --fields`.
Stare wyniki bez pól pokazują jawny brak danych. Opis: [fields.md](fields.md).
Powyższe diagramy antenowe nie mają animacji; nie ma automatycznej zmiany geometrii ani zaliczania
kontroli fizycznej na podstawie progu procentowego. Opisy powstają z jawnych
reguł i liczb, nie z usługi AI. Stan implementacji pól pozostaje w `goal.md`.


W raportach PCB **rozwiązany profil openEMS** jest domyślnie zwinięty:
wiersz pokazuje nazwę profilu i `max_cells`, a kliknięcie rozwija pełny,
oryginalny JSON (również ścieżkę konfiguracji i jej SHA). Widok pozostaje
samodzielnym HTML i nie zmienia zapisanych ustawień. Schemat **Stackup**
pokazuje wyłącznie warstwy dielektryczne i symboliczne powierzchnie miedzi;
nie rysuje przelotek jako fioletowych pionowych linii o wymyślonym X.
Wiercenia PTH/NPTH pozostają w sekcji `Drills / vias` i w zapisanej
geometrii. Schemat stosu nie jest rzeczywistym przekrojem XZ/YZ płytki.

Raporty PCB mają odtwarzacz fazowy oraz wspólny ROI dla E/H i wszystkich
faz danej planszy/częstotliwości. Domyślnie `--field-view active+geometry`,
`--field-crop-threshold-db -40`, `--field-crop-margin-mm 1`.
`--field-view domain` przywraca cały zapisany przekrój diagnostyczny.
Kontrakt progów, fallbacków i pozostałych trybów: [fields.md](fields.md#roi-raportów-pcb--bez-nowych-obliczeń).
Opcje zmieniają wyłącznie raport; zapisane NPZ/HDF5 pozostają nietknięte.

## PCB: animowane GIF-y prądu na miedzi w samodzielnym HTML (2026-10-26)

**Obecna implementacja zgodna z akceptacją użytkownika:** wyłącznie **GIF** z kontrastowym rozkładem `|K(t)|=|Re(K exp(jφ))|`, po jednym na warstwę miedzi i częstotliwość. Każdy GIF ma 24 klatki z odstępem 15°, 180 ms na klatkę, nieskończoną pętlę oraz obrys i kierunki wektora z zapisanej geometrii PCB. Nie ma sterowania suwakami, Play/Pause, indywidualnych PNG ani widoku liniowego. Każdy GIF znajduje się we własnym `<details><summary>...` — standardowy „dziubek” służy do rozwijania i zwijania. Pierwsza sekcja jest domyślnie otwarta.

Animacje są osadzane w samodzielnym offline HTML jako `data:image/gif;base64`; przy automatycznym raporcie plik jest również zapisywany do `plots/current_phase_*.gif`. Do kodowania i spójnej palety barw używany jest Pillow. Jedna stała logarytmiczna skala kontrastu dla całego cyklu danej pary warstwa/częstotliwość, z p99,5 obwiedni zespolonej; skal nie porównujemy między różnymi warstwami. Żadnej kolejnej symulacji FDTD ani zmian `currents/*.npz` / natywnych HDF5. Raport standardowego `antenna_lab report` można wyrenderować ponownie z ukończonego przebiegu.

**Ograniczenia:** GIF ma najwyżej 256 kolorów i sam zapętla się bez kontroli pojedynczej fazy. To prezentacja diagnostycznego `K_est` z `rot(H)`, nadal niewalidowanego fizycznie. Dla `stripline4_004` wejściowe `tanδ=1.001` wymaga sprawdzenia przed ewentualnym kolejnym przebiegiem. Antenowy raport oraz osobny odtwarzacz E/H pozostają bez zmian.

Szczegóły: [pcb-current-maps.md](pcb-current-maps.md).
