# PCB: Prepare / Run / Postprocess / Report

Wspólna granica dla EasyEDA, Gerber i kontroli syntetycznej:

- Prepare zapisuje `pcb-run.json` przed Run: wersję kontraktu, geometrię SI,
  pełne osie siatki, rozwiązaną konfigurację, specyfikację portu, plan pól,
  provenance i SHA256 XML. Zapis nie wymaga późniejszego importu CAD.
- Run (`execute_pcb_fdtd`) wykonuje silnik i zapisuje `execution.json`.
  `returned` oznacza wyłącznie powrót z API, nie osiągnięcie EndCriteria.
- Postprocess (`process_results`) współdzielony przez zwykły przebieg i CLI:
  natywny CalcPort, istniejące równania Z/S11/SWR, istniejący odczyt E/H,
  normalizacja do 1 V portu i maski. Brak statystyk nie blokuje portu.
- Report czyta tylko zapisane CSV/NPZ/geometrię i używa dotychczasowego HTML.

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.postprocess --run-dir outcomes\pcb_easyeda\NAZWA_PRZEBIEGU
```

Działa także dla katalogów Gerber. `native/` oraz `openems/` są rozpoznawane;
obecność dwóch modeli XML wymaga rozstrzygnięcia, nie wybieramy arbitralnie.
Odzyskiwanie tworzy nową rewizję `postprocessed/postprocess_NNN` wewnątrz
katalogu wejściowego. Nie nadpisuje pierwotnego summary, sond, XML ani HDF5.
Wynik polecenia podaje ścieżkę raportu oraz oddzielne statusy etapów.
Kolejne wywołanie na kompletnym katalogu przetworzonym waliduje i wykorzystuje
CSV/NPZ bez CalcPort. Rewizje są osobne, ale wartości odtwarzają się deterministycznie. `--recompute` wymusza odczyt surowych danych, nadal bez Run.
Natywne biblioteki są potrzebne tylko do odtworzenia czytnika CalcPort;
ponowny raport z kompletnych danych przetworzonych ich nie potrzebuje.

Status `unconfirmed` oznacza brak wiarygodnych statystyk czasowych. Osiągnięcie
limitu kroków/czasu nie daje `completed`, nawet gdy sondy pozwalają wyliczyć Z.
Obliczone parametry pozostają `unverified`. Błąd pojedynczego przekroju nie usuwa innych poprawnych płaszczyzn ani
CSV; błąd raportu nie unieważnia obliczeń. Nie fabrykujemy stats ani zbieżności.

Starsze wyniki: loader wymaga jawnych geometry.json, pełnego mesh.json,
simulation_settings i preparation/port w summary. Brakujące pola wymienia
w diagnostyce. Nie odtwarza ustawień z bieżącego profilu ani ponownego CAD.
Starszy niekompletny przebieg może wymagać dodatkowego eksportu oryginalnej
specyfikacji; nie jest automatycznie uznawany za odtwarzalny.

Sprawdzenie bez native: 12 testów postprocessingu oraz 3 granic kontrolerów
EasyEDA/synthetic i 1 Gerber PASS. Pierwsza próba granic wykazała stare atrapy
bez specyfikacji portu; atrapy uaktualniono, bez poluzowania kontraktu.
Danych rzeczywistego nieudanego przebiegu Windows nie ma w tym środowisku.
Nie wykonano FDTD i nie zmieniono fizyki, geometrii ani siatki.

Przykład ponownego raportowania zapisanej rewizji:

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.postprocess --run-dir outcomes\pcb_easyeda\NAZWA_PRZEBIEGU\postprocessed\postprocess_001
```

W `stages` są osobne engine/temporal_completion/port/fields/report. Przy błędzie
pola zapisują się tylko kompletne NPZ poprawnych przekrojów; metadata wskazuje
failed_planes. Brakujące przekroje nie są zastępowane zerami. Błędy zwracają
niezerowy kod CLI; odczyt poprawnych sond przy braku stats pozostaje możliwy.
