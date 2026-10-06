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

Ustawienia pierwszego przebiegu są zwykłymi ustawieniami control: siatka
aligned, 20 komórek/długość fali, minima portu 2/2, laminat Z 4, PML 8,
padding 0,25, EndCriteria 1e-5, limit 100000 kroków. Nie włączamy
exact_endcriteria ani macierzy zbieżności. Zasilanie i odczyt impedancji
pozostają w istniejącym adapterze; nie zmieniamy fizyki FDTD.

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
