# Migracja kontekstu — trwała pamięć i instrukcja przejęcia projektu

> **Ten plik jest punktem wejścia do repozytorium.** Jeżeli nowy czat dostał
> tylko wskazanie `migracja.md` i polecenie pracy nad projektem, poniższe
> instrukcje wystarczają do samodzielnego odtworzenia kontekstu. Nie trzeba
> wklejać historii wcześniejszych rozmów ani wymieniać pozostałych dokumentów.

**Repozytorium:** `analityk/antenna_solver_gpt`  
**Docelowa gałąź:** `main` (chyba że użytkownik jawnie wskaże inną)  
**Ostatnia inspekcja dokumentów:** 2026-10-21, Europe/Warsaw  
**HEAD potwierdzony przed ustanowieniem tego protokołu:** `f350cb5b92dcfdb69615226e78ea9031fa3af5ab`  
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

## 4. Punkt wznowienia — stan na 2026-10-21

**Kierunek rozwoju:** `antenna_lab` jest pakietem Pythona dla modelowania
anten i PCB. Pierwotny projekt obejmuje Quados 8 i biquad przy 1420 MHz
oraz natywny openEMS na Windows 11. **Aktualny priorytet to
import fizycznej geometrii PCB z kompletnego projektu EasyEDA Pro
`.epro` (ZIP), a następnie PCB FAST/reduced quasi-TEM.**
Prace D0/D1 na pojedynczym `.epcb` są ograniczonym historycznym
checkpointem, nie docelowym workflow.

- **DONE (zakres checkpointów kodu):** M1 generowania/edycji geometrii
  anten; PCB-015D0 — parser semantyczny EasyEDA Pro PCB 1.8/editor 2.2.x;
  PCB-015D1 — ograniczona ścieżka source-only: neutralny IR, canonical
  layout, inspekcja i możliwość FAST bez Gerbera dla wspieranych projektów.
  Zachowane są jednostki, nets, Line/Arc/signed sweep, VIA i provenance.
- **PARTIAL:** PCB FAST obsługuje jednoznaczne odcinki microstrip, wybrane
  idealne R/L/C i ground-PTH, nie całe sprzężone PCB. Model EasyEDA
  obsługuje określone top/bottom, jeden dielektryk, RECT PAD,
  materializowany POURED i VIA z jawną metalizacją; nie pełny format CAD.
  Adapter openEMS dla anten i pola E/H istnieją, ale bez kompletnej
  walidacji fizycznej.
- **OPEN:** instancje zewnętrznych footprintów i kontakty komponentów;
  semantyczny Arc jako linia transmisyjna; sprzężenia pairwise microstrip;
  opcjonalne source↔Gerber/Excellon reconciliation (D2); fizyczna walidacja
  antenowego portu, impedancji, zysku i zbieżności.

Kluczowa decyzja z 2026-10-21: **.epro-first**. Cały projekt
EasyEDA Pro V2 jest podstawowym źródłem geometrii i topologii:
`project.json`, `PCB/*.epcb`, `FOOTPRINT/*.efoo`.
**O konkretnym footprintcie rozstrzyga instancja PCB, nie Device.**
Gerber/Excellon służy opcjonalnej kontroli eksportu,
nie rekonstrukcji padów, netów i łuków. Brak Gerbera
nie blokuje source-only FAST.
D2 będzie mieć tolerancję produkcyjną podawaną przez użytkownika; 10 µm
nie jest globalnym defaultem ani tolerancją siatki czy FAST.

## 5. Najbliższe zadanie i warunek przejścia dalej

**Aktualny blocker:** brak importera pełnego projektu EasyEDA Pro
`.epro` i instancjonowania padów `.efoo`, a następnie niewdrożone
Arc TL i pairwise coupling. W dostarczonym poza Git `spirala.epro`
**odnaleziono brakujący footprint** CSRC/R1
`e8bf627583724bdebefbaa0be79b0d2f` i potwierdzono 2/2
odwołania oraz 4/4 przypisania PAD_NET. Dawny status
„brak pliku geometrycznego” dotyczył jedynie samodzielnego
`test_spirala.epcb` w repo. W obecnym kodzie canonical
layout i solve pozostają ograniczone: nadal nie odtwarzają padów
zewnętrznych. Nie zgaduj geometrii z Gerbera.

**Najbliższe zadanie — PCB-015D4 (nowa decyzja użytkownika):**
zaimplementować import pełnego projektu EasyEDA Pro V2 `.epro`
(bezpieczny ZIP, `project.json`, `PCB/`, `FOOTPRINT/`),
resolver biblioteki i `.efoo`/złożonego `.epcb`,
instancjonowanie **footprintu wybranego na PCB**,
geometrię padów, transformacje SI, `PAD_NET` i audyt
fizycznych kontaktów. `Device` nie może zastępować
jawnego footprintu PCB; fallback wyłącznie, gdy
footprint PCB nie został wskazany, a rozwiązanie
jest jednoznaczne. Na przykładzie `test_psu.epro`
potwierdzono 291/291 instancji i 906/906 przypisań pad→net w danych
źródłowych, lecz **nie jest to jeszcze zdolność obecnego kodu**.
Przesłane `test_psu.epro` nie jest częścią repozytorium;
dla odtwarzalności testów będzie potrzebna osobna zgoda na dodanie
artefaktu lub ponowne dostarczenie. Plik `spirala.epro` **został dostarczony w bieżącym czacie**:
9410 B, SHA256 `d94187520eaf519afd6fa3ba8625a3aa43d2b03a9a9178a924ac98586e504132`, ZIP z
`project.json`, jednym `.epcb`, dwoma `.efoo` i
dwoma `.esym`. **Nie jest w repozytorium**; ponowne wznowienie
pracy programistycznej wymaga jego ponownego przekazania
lub zgody użytkownika na dodanie jako fixture.
CSRC i R1 mają PCB `Footprint=R0603` (2×RECT SMD),
nety 1=A, 2=B i zgodne ID e8/e7. **Nie ma konfliktu:**
użytkownik ręcznie wybiera footprinty rodziny rezystorów
(np. R0603) również dla niepolaryzowanych kondensatorów.
3D bierze się z komponentu. Biblioteczny `Device C0603/100 nF`
nie zmienia elektrycznej geometrii PCB.
**`CSRC` z `Value=0` jest źródłem sygnału o numerze 0,
nie kondensatorem 0 F; następne jawne źródła mają
indeksy 1, 2, ...; `C1` i inne kondensatory są zwykłe.**
Wymiary i dalszy kontrakt: `docs/pcb-easyeda.md`.
Jeśli wymagany plik `.efoo` nie jest dostępny, zachowaj jawny
`missing-source-dependency` i wskaż dokładną brakującą zależność zamiast
udawać udany solve.

**Kryterium D4:** `.epro` daje canonical obraz rzeczywistej geometrii
padów i sieci bez Gerberów, udokumentowaną transformację
`COMPONENT → footprint PCB → PAD → PAD_NET`,
poprawną rolę źródła `CSRC/Value=0` i brak sztucznego
alarmu o C0603/R0603. Dopiero potem model Arc TL
i sprzężeń; nie zgłaszaj pełnego solve wcześniej.

**Potem:** (1) PCB-015D3 — fizyczna długość łuku z promienia i signed sweep,
bez chordy lub tessellacji Gerbera; (2) PCB-015C — pairwise/curved coupling
z fizycznym modelem C/C0 lub even/odd i fail-closed; (3) opcjonalnie D2 —
feature-aware reconciliation z jawną tolerancją użytkownika; (4) optymalizacja
pełnej fali. Numer P2 w starszej liście nie oznacza aktualnego priorytetu D2.
Przed podjęciem działań zawsze ponownie przeczytaj końcówkę `todo.md`.

**Niezmienny kontrakt po przejęciu:** pełne `.epro` jest wejściem
geometrii. Priorytet jawnego footprintu PCB jest bezwzględny;
niepolaryzowane pasywne 0603 i pokrewne mogą celowo używać
rodziny R. `CSRC/Value=0` to źródło nr 0, a dodatkowe
jawne źródła mają kolejne wartości całkowite. Nie traktuj
innych kondensatorów jako źródeł z samej nazwy `C`
czy footprintu `R`. `Device` i model 3D nie mogą
przedefiniować fizycznego footprintu.

**Punkty do inspekcji w kodzie:** `src/antenna_lab/pcb/easyeda.py`,
`src/antenna_lab/pcb/easyeda_model.py`,
`src/antenna_lab/pcb/source_ir.py`,
`src/antenna_lab/pcb/reduced_control.py`,
`src/antenna_lab/solvers/reduced_source.py`,
`tests/test_pcb_easyeda.py`. Kieruj się stanem kodu, nie samą listą plików.

**Późniejsza weryfikacja pełnego archiwum (2026-10-21):**
przesłany przez użytkownika poza Git `test_psu.epro` jest poprawnym
ZIP EasyEDA Pro V2 (SHA256 `659e3eacb05b4f91645bab3f621723adf85d14f56505aa6962e7d3f60a770982`);
wewnątrz: 1 PCB, 46 plików `.efoo`, 77 plików `.esym` i
`project.json` z 46 footprintami oraz 77 device. Wszystkie
291 instancji komponentów mają definicję footprintu (254 bezpośrednio
w `.efoo`, 34 w `.epcb`, 3 przez Device), a wszystkie 906 rekordów
`PAD_NET` wskazuje istniejący numer pada. Wcześniejsze 169 brakujących
odnosi się **tylko do pojedynczego pliku** `test_psu.epcb`.
Nie udowodniono fizycznego connectivity ani obliczeń FAST;
plik `.epro` nie jest wersjonowany. Szczegóły `docs/pcb-easyeda.md`.

**Nowe rozpoznanie zależności (statyczna inspekcja 2026-10-21):**
`test_spirala.epcb` zawiera 2 `COMPONENT`, 4 `PAD_NET` i 0 `PAD`/`FOOTPRINT`;
nie dostarcza więc sam geometrii CSRC/R1. `test_psu.epcb` jest nietypowym
złożeniem 34 dokumentów `FOOTPRINT` i jednego `PCB`; dokument PCB zawiera
291 komponentów, a po dopasowaniu `HEAD.uuid`/`HEAD.source` do atrybutu
`Footprint` 119 instancji ma odpowiadającą definicję, 169 jej nie ma,
zaś 3 nie mają rozpoznanego atrybutu. Obecne definicje obejmują
`R0603`, `G0603`, testpointy i przewlekane złącze; nie jest to reguła
SMD/THT ani dowód definicji 0805. Samo dopasowanie identyfikatora
nie jest jeszcze udanym importem modelu. Szczegóły: `docs/pcb-easyeda.md`.

## 6. Dowody, dostępne komendy i niewykonane sprawdzenia

**Dotychczas potwierdzone historycznie:**

- `test_spirala.epcb`: 198 rekordów, 6 LINE, 7 ARC, 2 VIA,
  4 dostępne regiony miedzi; obrys około 25 mm, dielektryk około
  0,2 mm, epsilon_r = 4,5. Parser i ograniczony canonical PASS,
  nie pełny solve. SHA256 danych:
  `e528f2a4ac1a1957a45e48806bc93da8b42e4af4a0f1da27cd84ce26714d0c4b`.
- 11 testów `test_pcb_easyeda.py` PASS dla checkpointu D0/D1, w tym
  syntetyczny source-only FAST bez Gerbera. Następne 3 wąskie regresje
  PASS, zapisane na końcu `history.md`. Są to wyniki **historyczne**,
  nie testy uruchomione podczas odczytu tego dokumentu.
- Brak potwierdzonego full solve rzeczywistej serpentyny; nie uruchamiano
  w tych checkpointach pełnego zestawu testów ani natywnego FDTD.
- 2026-10-21 do repo dodano także `gerbs/test_psu/test_psu.epcb` i
  `gerbs/test_psu/psu.zip`. Ich obecność nie dowodzi jeszcze działania FAST.
- Zakończone natywne przebiegi antenowe na Windowsie potwierdziły poprawkę
  granic zasilania `aligned_feed` (450 dodatnich wkładów). Lokalna praca
  0,949145539 W i strumień 0,948187885 W różnią się o około 0,10090%,
  ale pojedyncze odniesienie U·I=1 W różni się od lokalnej pracy o
  5,085%. **Nie zatwierdza to impedancji ani zysku**; M2/M3 otwarte.

**Inspekcja source bez portu/Gerbera (CMD Windows):**

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-source gerbs\realpcb_microstrip\test_spirala.epcb --inspect-source
```

**Obsługiwany solve z kompletnymi kontaktami:**

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control --easyeda-source projekt.epcb --source-config source-contacts.json
```

**Pełne testy na docelowym Windows, tylko gdy zasadne:**

```cmd
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

Projekt używa `unittest`, nie wymaga `pytest`. Benchmarki są wykluczone
bez osobnej instrukcji użytkownika. Dla zmiany samej dokumentacji wystarczy
kontrola spójności treści i commitów; nie przedstawiaj jej jako testu EM.

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
