# Migracja kontekstu — trwała pamięć i instrukcja przejęcia projektu

> **Ten plik jest punktem wejścia do repozytorium.** Jeżeli nowy czat dostał
> tylko wskazanie `migracja.md` i polecenie pracy nad projektem, poniższe
> instrukcje wystarczają do samodzielnego odtworzenia kontekstu. Nie trzeba
> wklejać historii wcześniejszych rozmów ani wymieniać pozostałych dokumentów.

**Repozytorium:** `analityk/antenna_solver_gpt`  
**Docelowa gałąź:** `main` (chyba że użytkownik jawnie wskaże inną)  
**Ostatnia inspekcja dokumentów:** 2026-10-21, Europe/Warsaw  
**Potwierdzony opublikowany checkpoint przed aktualizacją:** `02d6abbf535f2dd88abcbe28edb3d51dd9c339e4`
**Uwaga:** ten SHA jest punktem historycznym, nie obietnicą, że nadal jest HEAD. Każde wznowienie rozpoczyna się sprawdzeniem Git.

## 1. Instrukcja dla nowego czatu — wykonaj po wskazaniu tego pliku

Jesteś kolejnym wykonawcą prac nad tym samym repozytorium. **Nie polegaj na
pamięci poprzedniego czatu.** Repozytorium jest źródłem trwałego stanu, a
niniejszy plik jego indeksem operacyjnym.

1. **Połącz się z repozytorium i sprawdź rzeczywisty stan:** `main`/HEAD,
   ostatnie commity, ewentualne nieopublikowane lub cudze zmiany. Nie używaj
   zapisanego tu SHA jako docelowego commita.
2. **Przeczytaj `AGENTS.md` w całości** i zastosuj jego reguły (wraz z
   ewentualnymi lokalnymi `AGENTS.md`). Dalej przeczytaj `todo.md`, końcówkę
   `history.md`, `goal.md` i wskazane poniżej dokumenty `docs/`. Gdy kod
   dotyczy określonego modułu, odczytaj właściwą implementację i testy.
3. **Zweryfikuj checkpoint z sekcji 4–7:** porównaj go z aktualnym kodem,
   zmianami na `main`, wynikami testów i dokumentami. Jeśli od czasu tego
   zapisu powstały nowsze commity, najpierw ustal ich zakres. Nie przyjmuj
   opisu ze starszego checkpointu za dowód aktualnego działania.
4. **Odtwórz kontekst zadania:** sprecyzuj: co działa, co jest PARTIAL,
   rzeczywisty blocker, priorytet i kryterium ukończenia kolejnego kroku.
   Rozróżniaj testy historyczne od uruchomionych przez siebie.
5. **Działaj zgodnie z poleceniem użytkownika.** Jeśli prosi o kontynuowanie
   rozwoju, podejmij najwyższy aktualny, odblokowany priorytet z `todo.md`
   (obecny punkt wskazano w sekcji 5), po sprawdzeniu dostępności zapisu na
   GitHub. Nie domagaj się rekonstrukcji poprzednich rozmów. Jeśli polecenie
   dotyczy tylko diagnozy/odczytu, przedstaw stan i plan bez niezamówionych
   zmian kodu. Nowa dyspozycja użytkownika ma pierwszeństwo.
6. **Nie kończ bez przekazania pałeczki:** zastosuj końcową inspekcję
   dokumentacji z `AGENTS.md`, zaktualizuj ten plik i powiązane `*.md`
   **jeśli zmieniły się fakty**, utrwal i opublikuj dozwolone zmiany, a w
   odpowiedzi podaj commit, push, testy i ograniczenia.

Jeśli brak uprawnień do odczytu repozytorium, powiedz o blokadzie dostępu.
Jeśli brak kanału zapisu, nie rozpoczynaj kosztownej implementacji, której
nie da się opublikować; stosuj regułę z `AGENTS.md`. **Ten dokument nie
upoważnia do obchodzenia instrukcji użytkownika ani do fabrykowania wyników.**

## 2. Minimalny prompt użytkownika i „prompt do prompta”

### Prompt otwierający kolejny czat (wystarczy ten jeden)

```text
Pracujesz nad repozytorium analityk/antenna_solver_gpt, gałąź main.
Przeczytaj migracja.md i wykonaj zapisany w nim protokół przejęcia projektu.
Odtwórz stan z GitHub, zastosuj AGENTS.md i kontynuuj najbliższe zadanie
według aktualnego todo.md. Na koniec utrwal kontekst dla kolejnego czatu.
```

Właściwa treść poleceń, lista źródeł i punkt wznowienia znajdują się **w
tym pliku**, nie w pamięci użytkownika. W innych zadaniach użytkownik może
napisać tylko „Przeczytaj migracja.md i przejmij projekt”.

### Prompt, który ten dokument przekazuje nowemu asystentowi

```text
Nie kontynuujesz poprzedniej rozmowy — kontynuujesz repozytorium.
Zweryfikuj HEAD i zmiany, przeczytaj AGENTS.md, todo.md, końcówkę history.md,
goal.md i właściwe docs. Potwierdź stan przez kod/testy lub jawnie zaznacz,
że opierasz się na historii. Ustal pierwszą blokadę i wykonaj zadanie
dozwolone przez najnowsze polecenie użytkownika. Zapisuj checkpointy
przed kosztownymi etapami. Nie zgaduj brakującej fizyki, geometrii ani PASS.
Przy zamykaniu każdej pracy skontroluj odpowiednie pliki .md, odśwież
migracja.md i dokumentację, jeśli stan faktycznie się zmienił, commituj
i publikuj do origin/main. Raportuj zakres, SHA, testy i ograniczenia.
```

### Prompt awaryjny do użycia jeszcze w trwającym czacie

```text
Zrób checkpoint przekazania projektu. Sprawdź zmiany i aktualny HEAD,
zweryfikuj AGENTS.md, todo.md, ostatnie history.md i istotne docs/*.md.
Zaktualizuj migracja.md tak, aby nowy czat mógł zacząć od samego tego pliku:
stan, decyzje, blocker, następny krok, dowody, testy i ograniczenia.
Zapisz i opublikuj dozwolone zmiany. Podaj SHA i to, co pozostaje otwarte.
```

Ten dodatkowy prompt jest opcjonalny: `AGENTS.md` nakazuje taki audyt
automatycznie po każdej pracy. Nie jest potrzebny, jeśli checkpointy
są wykonywane poprawnie na bieżąco.

## 3. Jak zachowywać stan między sesjami

**Model trwałości:** Git + jawne dokumenty; nie pamięć czatu, prywatne
notatki agenta, lokalny stan terminala, archiwum transkryptów ani
nieopublikowany patch.

| Dokument | Właściciel informacji |
| --- | --- |
| `AGENTS.md` | Trwałe zasady, procedura przejęcia, audyt na zakończenie, Git i testy. |
| `migracja.md` | **Bieżący punkt wznowienia**: kierunek, co zrobione, blocker, następny krok, poziom potwierdzenia i instrukcja dla nowego czatu. |
| `todo.md` | Aktualna kolejność pracy, kryteria i rozpisane etapy. |
| `history.md` | Chronologiczny, nieprzepisywany do migracji zapis decyzji i rezultatów większych zmian. |
| `goal.md`, `parameters/` | Wymagania i parametry źródłowe projektu. |
| `docs/*.md` | Techniczne kontrakty, formaty, ograniczenia i procedury. |
| Kod, testy, commity | Faktyczna implementacja, weryfikacja i dowód, co trafiło na `main`. |

**Początek pracy:** Git HEAD → ten plik → `AGENTS.md` → `todo.md`,
`history.md` (najnowszy istotny fragment) → `goal.md`/właściwe `docs`
→ kod i testy. Nie wystarczy pobieżna lektura niniejszego raportu.

**W trakcie:** gdy etap jest istotny lub grozi utratą postępu, zrób
checkpoint i push. Odróżniaj trwały stan kodu od jeszcze nieuruchomionych
testów. Nie czekaj na zakończenie rozmowy.

**Na końcu każdego zadania:** bez oczekiwania na prośbę użytkownika porównaj
zmiany z powiązaną dokumentacją `*.md`. Zaktualizuj `migracja.md`, `todo.md`,
`history.md` i odpowiednie `docs/*.md` **tylko tam, gdzie fakty tego
wymagają**. Nie twórz zmian samych dat lub kosmetycznych przepisań;
nie modyfikuj plików spoza zakresu dozwolonego przez użytkownika.
Sprawdź spójność i commituj/publikuj istotne zmiany zgodnie z `AGENTS.md`.

Przy aktualizacji `migracja.md` utrzymuj kolejno: (a) aktualny kierunek,
(b) dokładny punkt zatrzymania, (c) rozdzielenie DONE/PARTIAL/OPEN,
(d) jawne dowody, komendy i status testów, (e) pierwsze zadanie i warunek
zakończenia, (f) istotne decyzje/ryzyka, (g) odnośniki do dokumentów.
Aktualizuj zawartość zamiast dopisywać niekończący się dziennik.
Nie zapisuj tu sekretów, danych kont ani dużych wyników obliczeń.

**Uwaga o SHA:** commit nie może zawierać wiarygodnego własnego SHA przed
utworzeniem. W nagłówku zapisuj SHA ostatniego *już potwierdzonego*
commita bazowego, a opublikowany SHA nowego commita podawaj po publikacji
w raporcie końcowym. Nowy czat zawsze sam sprawdza HEAD.

## 4. Bieżący punkt wznowienia — spirala po PCB-015D3

**Zakres użytkownika: wyłącznie `gerbs/emtest4/spirala.epro`. Bez PSU.**
Nie powtarzać szerokiego D4, nie uruchamiać pełnej suite/native/FDTD/benchmarków.

**DONE — nazewnictwo:** wspólny lekki allocator Gerber/FAST daje
`outcomes/pcb_reduced/spirala_001`, następnie max zajętych numerów +1.
Atomowy mkdir obsługuje równoległe starty; działa także `--inspect-source`.
Jawny `--output` ma pierwszeństwo. Stare katalogi i archiwa nietknięte.
Opublikowany checkpoint `b9c99872ceb6eb936bbcc666eb10bb2ee78a7de9`.

**DONE — D3 metryka i graf semantic ARC:** `SourceSection` rozróżnia ARC/LINE,
zachowuje source endpoints/center/signed sweep i rzeczywistą długość r*abs(theta).
Projektowane węzły nie wyznaczają nowego promienia. Kierunek, net/owner, source
junctions, physical contact i receipt projekcji są kontrolowane. Nie zmieniono
full-wave, mesh, PTH ani tolerancji. Implementacja opublikowana w
`02d6abbf535f2dd88abcbe28edb3d51dd9c339e4`; późniejszy checkpoint uzupełnia
wyniki, diagnostykę konsoli i dokumentację (sprawdź HEAD).

**Potwierdzona spirala Git:** SHA256
`d94187520eaf519afd6fa3ba8625a3aa43d2b03a9a9178a924ac98586e504132`.
Canonical D4 nadal: 2 COMPONENT, 4/4 PAD_NET, pady R0603, 6 LINE, 7 ARC,
2 VIA, 4 conductors. CSRC = source_index 0, nie kondensator zero.
Aktywny net A: **5 LINE + 7 ARC, 36.373621555 mm**, przed/po projekcji 10 µm.
2 PTH uziemiają dwa top conductors. Jeden jawny testowy R1 = 49.9 Ω,
plating = 25 µm; to nie odczytane/domyślne parametry produkcyjne.
Testowana ścieżka CLI zapisuje graf/summary, bez impedance.csv.
Wariant lokalny użytkownika SHA `af91f8611267418ca6039f0af45b78475c8998694abf324632a14de69e743df0`
nie był tutaj dostępny/testowany; nie nadpisano pliku Git ani danych użytkownika.

**PARTIAL — fizyka FAST:** analityczna długość łuku jest w istniejącym modelu
TL, ale parametry przekroju są nadal uniform quasi-TEM; korekty krzywizny i
sprzężenia nie są obliczane. **OPEN / pierwszy blocker:**
`Reduced PARTIAL: semantic ARC lengths/topology extracted; curved coupling analysis unsupported (PCB-015C)`.
`curved_coupling_audit` wymienia 7 ARC oraz 5 skośnych LINE. Brak osiowych
parallel overlaps nie znaczy braku sprzężeń. Solve jest blokowany przed Z/S11.

## 5. Następne zadanie i źródła kodu

**PCB-015C: pairwise/curved coupling dla spirali.** Najpierw jawny fizyczny
kontrakt modelu, potem implementacja; żadnych zgadywanych współczynników,
obcięcia łuków do cięciw ani milczącego pomijania bliskich sekcji. D3 nie jest
walidacją EM całej serpentyny. Arc curvature corrections pozostają jawnie
niezamodelowane. Nie rozszerzać zadania o PSU.

Kod: `solvers/reduced_source.py` (source axis/audit), `solvers/reduced_pcb.py`
(SourceSection, graph, guard), `pcb/reduced_control.py` (CLI i zapis przed odmową),
`pcb/output.py` (nazwy). Źródła D4: `pcb/easyeda_project.py`,
`pcb/easyeda_footprints.py`, `pcb/easyeda_model.py`, `pcb/source_ir.py`.
Pełny kontrakt: docs/pcb-easyeda.md, docs/pcb-reduced.md, todo.md.

## 6. Wykonane testy i następna tania komenda (CMD Windows)

W tej sesji faktycznie wykonano:
- `test_pcb_output`: 3 PASS (nazwy, równoległość, explicit output/inspect).
- `test_reduced_source_arcs`: pierwsza próba 2 PASS / 1 ERROR (skośna e40 w
  starym x/y guardzie), po poprawce 3 PASS. Następnie rozszerzony plik: 4 PASS.
- Wraz z rozszerzonym plikiem 3 pojedyncze regresje: `test_pcb_easyeda.EasyEdaTests.test_source_arc_survives_projection_but_physics_remains_guarded`,
  `test_pcb_easyeda.EasyEdaTests.test_source_only_fast_without_manufacturing_files`,
  `test_pcb_easyeda_project.ProjectTests.test_real_spiral_canonical_port_vias_and_explicit_passive`:
  cały ten mały zestaw 7 PASS.
- `test_pcb_reduced.ReducedTests.test_parallel_runs_detected_not_silently_ignored`
  i `test_import_does_not_load_native_or_fullwave_adapter`: 2 PASS.
- `git diff --check`: bez błędów whitespace.

Nie uruchomiono pełnej suite, PSU, native/FDTD, benchmarków, convergence ani
szerokich sweepów. Testy realnej spirali użyły tymczasowych katalogów; stare
`outcomes/` pozostały nietknięte. Historia D4 jest w history.md, nie jest nowym
testem tej sesji.

Następny tani test lokalny (bez parametrów/solverów natywnych):

```cmd
git pull --ff-only && .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_reduced_source_arcs.py -v
```

Inspekcja użytkowa:
`.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-project gerbs\emtest4\spirala.epro --inspect-source`

## 7. Dokumenty, decyzje i ograniczenia wymagające zachowania

- [`AGENTS.md`](AGENTS.md): obowiązkowe zasady, Windows, Git, checkpointy,
  testy i końcowa inspekcja dokumentacji.
- [`todo.md`](todo.md): **nadrzędna operacyjna kolejność** aktualnych prac.
- [`history.md`](history.md): chronologia zmian, ostatnie wpisy PCB-015D0/D1
  i wyniki ich testów; sprawdzaj końcówkę po każdej sesji.
- [`docs/pcb-easyeda.md`](docs/pcb-easyeda.md): dialekt, jednostki,
  source IR, ograniczenia footprintów, source-only CLI.
- [`docs/pcb-reduced.md`](docs/pcb-reduced.md): zakres fizyczny FAST,
  metoda quasi-TEM i warunki fail-closed.
- [`docs/architecture.md`](docs/architecture.md): separacja rdzenia,
  solverów, geometrii i GUI.
- [`goal.md`](goal.md), [`docs/power-audit.md`](docs/power-audit.md),
  [`docs/fields.md`](docs/fields.md): wymagania antenowe i obszary
  jeszcze niezweryfikowane fizycznie.

Nienaruszalne założenia: source EasyEDA > Gerber w semantyce CAD;
brak danych oznacza brak, nie zero; nie zgaduj jednostek, metalizacji via,
geometrii footprintów ani sprzężeń; tolerancja produkcyjna ≠
geometry-resolution ≠ siatka EM; `POUR` bez materializowanego `POURED` nie
daje automatycznie miedzi. Symulacja ukończona ≠ fizycznie zweryfikowana.
Pracuj natywnie na Windows 11 w `.venv`, bez obowiązku WSL/uv.

## 8. Protokół aktualizacji tego pliku — kontrola jakości przekazania

Po ukończonym zadaniu agent ma odpowiedzieć sobie:

1. Czy nowy czat rozpozna aktualny HEAD i nie pomyli historycznego SHA
   z najnowszym? Czy opisuje zmianę dokonującą się **naprawdę**, a nie plan?
2. Czy najbliższy krok jest konkretny, ma blocker oraz mierzalne kryterium
   ukończenia, a priorytet jest zgodny z `todo.md`?
3. Czy status DONE/PARTIAL/OPEN i wynik testów są udokumentowane bez
   przypisywania sobie cudzych lub nieuruchomionych sprawdzeń?
4. Czy zmiany istotne dla użytkownika znalazły się także w właściwych
   `docs/*.md`, `history.md` i `todo.md` (o ile zakres zadania pozwala)?
5. Czy checkpoint został opublikowany na właściwej gałęzi i czy
   odpowiedź zawiera SHA, wynik pushu, testy i ograniczenia?

Jeśli odpowiedź brzmi „nie”, uzupełnij przekazanie przed końcem pracy
zamiast liczyć, że następnym razem użytkownik pamięta brakujące fakty.
Unikaj rutynowych aktualizacji bez zmian merytorycznych. Ten mechanizm
powinien działać niezależnie od czasu życia, liczby i modelu kolejnych czatów.
