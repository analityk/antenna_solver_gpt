# EasyEDA source-first — PCB-015D0/D1

Source PCB jest nadrzędny. Gerber/Excellon nie jest wymagany; brak eksportu
produkcyjnego oznacza `manufacturing_validation=not_requested`.

## Format i jednostki

Obsługiwany profil: JSON arrays per line, DOCTYPE PCB 1.8, editorVersion 2.2.x.
Nieznany dialect/version jest odrzucany zamiast zgadywania skali. Parser
zachowuje pełne raw records, indeksy linii, ID i SHA256 niezmienionych bajtów.

Centralna konwersja w `pcb/easyeda.py`: PCB Line/Arc/Via/Poly/Pour i grubości
LAYER_PHYS używają mil (25.4 µm). Współrzędne materializowanego POURED używają
10 mil (254 µm). CANVAS określa tylko display unit. Nie stosujemy rounding
KiCada ani jego inwersji osi do ekranowego układu PCB; canonical XY zachowuje
źródłowy +Y w górę, signed sweep dodatni CCW. R zaczyna się w lewym górnym rogu,
a wysokość biegnie w stronę -Y. Semicircle ±180° ma środek w połowie cięciwy.

Podstawa, nie dopasowanie skali do wymiarów użytkownika:

- [Oficjalny format EasyEDA Pro V2](https://github.com/easyeda/easyeda-file-format-v2/tree/63f38c2758cbe2456e8b5c7e76469369430d94af/docs/en/pcb): pola LINE/ARC/VIA, CANVAS, polygon-system, LAYER_PHYS.
- [Importer KiCad EasyEDA Pro](https://gitlab.com/kicad/code/kicad/-/tree/master/pcbnew/pcb_io/easyedapro), sprawdzony 2026-10-21: `ScaleSize` 25400 nm/unit, `ScalePos` z inwersją do układu KiCad, ARC center z signed angle, R height ze znakiem minus, POURED `ptScale=10`.
- [Dokumentacja importera KiCad](https://dev-docs.kicad.org/en/import-formats/easyeda/index.html#_easyeda_pro_format).

Ogólna dokumentacja V2 mówi 0.01 inch bez rozróżnienia PCB/schematic. Nie
przenosimy tego domyślnie na wszystkie rekordy PCB: implementacja importera
potwierdza rozdzielone skale. Nie jest to EasyEDA Standard ani format Pro V3.

## Zakres checkpointu parsera

DOCTYPE, HEAD, CANVAS, LAYER, LAYER_PHYS, NET, LINE, ARC, VIA, PAD_NET,
COMPONENT i ATTR. POLY/POUR: niezaokrąglone R (dowolny obrót) i proste kontury
L; POURED: pojedynczy wypełniony, niestrokowany kontur. Raw pola pozostają
niezmienione. Unknown records są zachowane i blokują canonical solve, chyba że
są rozpoznanym metadata edytora lub mają prefiks META_. Unsupported footprint,
complex fill rule czy thermal-spoke nie stają się domyślnie pełną miedzią.

Materiał nie jest oceniany jako „typowa PCB”: epsilon_r=1 i gruby dielektryk
są legalne. Zakres przybliżenia microstrip nadal należy do solvera, nie parsera.
Arc zachowuje signed sweep i mathematically derived center; nie ma jeszcze
modelu TL łuku ani pairwise/curved coupling. Gerber-only fallback bez zmian.

## Source-only CLI i canonical checkpoint D1

Inspekcja semantyki i dostępnego modelu, bez wymogu portu:

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-source gerbs\realpcb_microstrip\test_spirala.epcb --inspect-source
```

Zapisuje `source_ir.json` (w tym raw records), `source_model.json` (obrys,
stackup, miedź per net/layer, routes, vias, zależności footprintów), `import.json`
i `summary.json`. `source_inspected` nie oznacza ukończonego solve ani pełnego
modelu kontaktów. Zależności są wypisane w konsoli i zapisane w metadata.

Solve dla obsługiwanego source z kompletnymi padami i kontaktami:

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-source projekt.epcb --source-config source-contacts.json
```

Jawny override opisuje kontakty w źródłowym układzie XY, w mm:

```json
{"port":{"mode":"explicit","negative_mm":[-2.032,0],"positive_mm":[2.032,0],"width_mm":0.508}}
```

Opcjonalne `drills` ma istniejące pola `pth_plating_um` i
`pth_model="solid_pec_equivalent"`. VIA podaje średnicę otworu i pada, **nie**
grubość metalizacji. Nie zgadujemy jej z annular ring. Model PTH pozostaje
istniejącą aproksymacją. Inner/blind/buried spans nie są obsługiwane tym adapterem.

D1 obsługuje jeden dielektryk między top/bottom, source LINE/ARC, materializowany
POURED, absolutne niezaokrąglone SMD PAD RECT i through VIA z jawną metalizacją.
COMPONENT/PAD_NET/ATTR zachowują intencję; zewnętrzny footprint jest szukany pod
jawnym hashem w `FOOTPRINT/<hash>.efoo` obok source lub katalogu projektu.
Brak footprintu blokuje solve precyzyjnym missing-source-dependency; znaleziony
zewnętrzny footprint również wymaga przyszłego adaptera instancji. Nie udajemy
obsługi elementów przez pominięcie ich padów lub wartości.

Pad z jednym semantic route junction może być idealnym equipotential terminalem:
pełny fizyczny contact/gap nadal przechodzi audyt, pad musi należeć do tego samego
conductora. Pad electrical length i parasitics są jawnie pominięte, nie zgadywane
jako dodatkowa TL. Wiele junctions w padzie -> błąd. Źródłowe nets kontrolują
zwarcia; final physical polygons kontrolują ownership. Source routes i pady
przechodzą istniejącą normalizację i geometry resolution; ID/net/signed sweep
nie są odzyskiwane z polygonów. Fizyczny audyt projekcji pozostaje obowiązkowy.

Nie wdrożono D2 ani publicznego parametru manufacturing tolerance. Nie ma
ukrytego domyślnego limitu; source-only zapisuje `not_requested`. Gerber ZIP/
katalog nadal działa przez dotychczasowy argument pozycyjny. Full-wave bez zmian.


## Sprawdzenie checkpointu 2026-10-21

11 testów w `test_pcb_easyeda.py` PASS: parser, jednostki, signed sweeps,
VIA, nietypowy dielektryk, błędy, brak footprintu, source-only FAST z idealnymi
padami, projekcja/normalizacja i guard Arc. Realny `test_spirala.epcb` dodany
przez użytkownika do repo: odczyt + canonical layout PASS (198 records,
6 Line / 7 Arc / 2 Via). Brakuje geometrii footprintu CSRC/R1
`e8bf627583724bdebefbaa0be79b0d2f`; canonical output zachowuje ten brak,
nie jest pełnym modelem fizycznym do solve. Pełny source nie był zmieniany.
Nie sprawdzano `test_spirala.zip`, nie uruchamiano FDTD ani pełnej suite.
