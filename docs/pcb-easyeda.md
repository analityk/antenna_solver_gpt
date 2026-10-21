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
