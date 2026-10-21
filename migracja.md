# Migracja kontekstu — trwała pamięć i instrukcja przejęcia projektu

> **Ten plik jest punktem wejścia do repozytorium.** Jeżeli nowy czat dostał
> tylko wskazanie `migracja.md` i polecenie pracy nad projektem, poniższe
> instrukcje wystarczają do samodzielnego odtworzenia kontekstu. Nie trzeba
> wklejać historii wcześniejszych rozmów ani wymieniać pozostałych dokumentów.

**Repozytorium:** `analityk/antenna_solver_gpt`  
**Docelowa gałąź:** `main` (chyba że użytkownik jawnie wskaże inną)  
**Ostatnia inspekcja dokumentów:** 2026-10-21, Europe/Warsaw  
**Potwierdzony opublikowany checkpoint przed aktualizacją:** `3b373e9efc7cca5e5ef9e8d71bf8b02038bcd867`
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

## 4. Bieżący punkt wznowienia — PCB-015D4

**Kierunek:** pełne `.epro` → canonical PCB/source semantics → FAST.
**Baza zadania:** b7626f36bd582d678893b7f587f89f59cc745d50.
**Ostatni już opublikowany checkpoint przed tym zapisem:**
3b373e9efc7cca5e5ef9e8d71bf8b02038bcd867 (wcześniej b2086ca9ff41a848534c8945d440bd970beea5ed).
Zawsze sprawdź nowy HEAD; niniejszy końcowy checkpoint dostaje SHA po publikacji.

**DONE:** importer `.epro` bez ekstrakcji/pośredniego Gerbera, CRC/limity,
strict JSON, project.json i wybór PCB, resolver `.efoo`/embedded, PCB Footprint
przed Device, PAD ID+number+net, obrót/odbicie/SI, CSRC Value=0/source_index=0.
Materializacja padów, union miedzi per net/warstwa, kontrola zwarć i ownership,
contact metadata, port z rzeczywistej szczeliny i jawne idealne RLC są zintegrowane
z istniejącą ścieżką. Gerber i samodzielny .epcb pozostają kompatybilne.

**Obsługiwany profil:** PCB/footprint 1.8, editor 2.2.x, top/bottom/jeden dielektryk,
RECT bez round corners, circle/OVAL SMD, round through PAD z jawnym plating.
Footprinty 1.3/1.7 tylko indeksowane; ich geometria odrzucana. Przesunięcie
pad local → mirror Y na bottom → obrót instancji → PCB. Nie zmieniono
full-wave, meshera, PML ani tolerancji. Epsilon_r=1 i gruby dielektryk legalne.

**Dostępność i odbiór realny:** oba archiwa są w Git od b7626f3, nie w ulotnym
załączniku; żadnego pliku użytkownika nie zmodyfikowano.

- `gerbs/emtest4/spirala.epro`, SHA256
  d94187520eaf519afd6fa3ba8625a3aa43d2b03a9a9178a924ac98586e504132:
  canonical PASS — 2 COMPONENT, 4 PAD_NET, cztery fizyczne pady R0603,
  6 LINE, 7 ARC, 2 VIA, 4 conductors. CSRC source_index=0. Każdy pad ma
  fizyczny kontakt. PcbGeometry, normalizacja/odwrotność, pełna szczelina portu,
  PTH top/bottom i R1 sprawdzone z **jawnymi testowymi** plating=25 um,
  R1=49.9ohm (to nie domyślny parametr producenta/source).
- `gerbs/test_psu/test_psu.epro`, SHA256
  659e3eacb05b4f91645bab3f621723adf85d14f56505aa6962e7d3f60a770982:
  identity PASS — 291 komponentów/906 PAD_NET z kontrolą ID i numeru,
  288 PCB explicit + 3 Device fallback; 257 library + 34 embedded.
  **Physical canonical UNSUPPORTED:** pierwsza odmowa pusty NET (PCB record 145).
  Dalej są stare footprinty 1.3/1.7, slots i bogatszy materiał/pours.
  Nie deklarować ich fizycznego connectivity ani wyniku FAST.

**PARTIAL:** ogólna zgodność EasyEDA, elektryczny FAST i source component subset.
CSRC/Value to indeks, nie nominalna pojemność Device. Zwykły C1 nie jest źródłem.
Kolejne jawne źródła mogą mieć Solver Role=source i ciągłe indeksy od 0;
obecny solver odrzuca wiele źródeł. `component_values` ustala jawne R/L/C;
niezamodelowany element nie jest cicho pomijany. 3D nie rozstrzyga footprintu.

**OPEN:** D3 Arc TL, PCB-015C coupling, rozszerzenie PSU i opcjonalne D2.
Realna spirala po udanym canonical dociera do **EasyEDA source ARC unsupported**.
Nie wygenerowano dla niej Z/S11 i nie należy deklarować całego FAST jako PASS.

## 5. Następne zadanie i źródła kodu

**Najbliżej PCB-015D3:** korzystać z zachowanych source ARC/signed sweep/radius,
nie tessellacji ani cięciwy. Po nim coupled microstrip; nie omijać guardów.
Warunek: poprawny model i testy łuku, zachowana semantyczna ciągłość i długość.
PSU jest odrębnym zakresem kompatybilności, nie wymogiem do rozpoczęcia D3.

Kod D4: `pcb/easyeda_project.py` (bezpieczny ZIP/resolver),
`pcb/easyeda_footprints.py` (pady i transformacje), `pcb/easyeda_model.py`
(canonical/net/contact), `pcb/reduced_control.py` (CLI),
`pcb/source_ir.py`, `solvers/reduced_source.py` (guard/terminal).
`tests/test_pcb_easyeda_project.py` i legacy `test_pcb_easyeda.py`.
Pełny kontrakt i ograniczenia: docs/pcb-easyeda.md, docs/pcb-reduced.md, todo.md.

## 6. Dowody i następne tanie komendy (CMD Windows)

Faktycznie uruchomione w D4:
- `python -X utf8 -m unittest test_pcb_easyeda_project -v`: 11 PASS (pierwszy checkpoint).
- `python -X utf8 -m unittest test_pcb_easyeda_project test_pcb_easyeda -v`: 25 PASS.
- Trzy testy po wzmocnieniu asercji: round THT z jawnym plating,
  real spiral canonical/Arc guard, explicit source indices: 3 PASS.
- Read-only diagnostic obu archiwów: wyniki powyżej; pierwsza próba PSU
  wykazała wersję biblioteki 1.7, po rozdzieleniu indeksu od materializacji
  potwierdzono 291/906 i aktualny physical guard pustego NET.
Nie uruchomiono pełnej suite, native/FDTD, benchmarków ani convergence sweeps.
Nie wykonywano pełnego solve serpentyny. Wyniki historyczne anten i D0/D1
pozostają w history.md; nie są dowodem nowej walidacji EM.

```cmd
git pull --ff-only && .\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-project gerbs\emtest4\spirala.epro --inspect-source
```

```cmd
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_pcb_easyeda_project.py -v
```

Inspekcja nie wymaga config portu/plating. Solve wymaga jawnego source-config
(port mode=source/source_index albo explicit; plating oraz component_values),
przy czym obecne guardy Arc/coupling nadal uniemożliwiają pełny wynik serpentyny.
Nie zgaduj brakującej elektryki z Device. Polecenia/dane przykładów są w docs.

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

### Checkpoint 2026-10-21 — zakres wyłącznie spirala

Najnowsze polecenie użytkownika ogranicza pracę do `spirala.epro`, bez PSU.
FAST przechodzi na wspólną z Gerber numerację `spirala_NNN`, także dla
`--inspect-source`; testy w `test_pcb_output.py`. Następny krok to D3
semantyczne ARC, potem jawna blokada niewymodelowanych sprzężeń. Ostatni
opublikowany HEAD przed tym checkpointem: `4af79ef1dc3ddfca82cbf13228e84e22db7ff822`.
