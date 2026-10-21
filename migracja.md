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
oraz natywny openEMS na Windows 11. **Aktualny priorytet to PCB FAST,
reduced quasi-TEM, oparty na oryginalnym EasyEDA source PCB.**

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

Kluczowa decyzja z 2026-10-21: **source-first**. Oryginalny plik EasyEDA jest
nadrzędnym źródłem topologii i intencji projektowej. Gerber/Excellon służy
opcjonalnie do sprawdzania eksportu, nie do rekonstrukcji znanych netów,
łuków i komponentów. Brak Gerbera sam w sobie nie blokuje source-only FAST.
D2 będzie mieć tolerancję produkcyjną podawaną przez użytkownika; 10 µm
nie jest globalnym defaultem ani tolerancją siatki czy FAST.

## 5. Najbliższe zadanie i warunek przejścia dalej

**Pierwszy aktualnie udokumentowany blocker:** na
`gerbs/realpcb_microstrip/test_spirala.epcb` parser i częściowy canonical
layout działają, ale komponenty `CSRC/R1` odwołują się do zewnętrznego
footprintu o hashu `e8bf627583724bdebefbaa0be79b0d2f`, którego
geometrii nie ma w zbudowanym modelu. Nie zgaduj padów/połączeń i nie
odtwarzaj ich z Gerbera.

**Najbliższe zadanie:** zweryfikować aktualne pliki źródłowe i zależności,
następnie zaprojektować/zaimplementować obsługę instancji zewnętrznego
footprintu EasyEDA i adapter kontaktów komponentów; uwzględnić jawne
przypisania pin↔pad↔net, transformacje oraz fizyczny audyt zwarć i kontaktów.
Jeśli wymagany plik `.efoo` nie jest dostępny, zachowaj jawny
`missing-source-dependency` i wskaż dokładną brakującą zależność zamiast
udawać udany solve.

**Kryterium gotowości do następnego etapu:** źródłowy model z kompletną
dostępną geometrią/pinami dla CSRC/R1 przechodzi jawne kontrole geometryczne
i semantyczne bez wymyślania elementów. Nie oznacza to jeszcze, że obliczono
serpentynę: aktywne `ARC` i coupling nadal mogą kończyć FAST błędem.

**Potem:** (1) PCB-015D3 — fizyczna długość łuku z promienia i signed sweep,
bez chordy lub tessellacji Gerbera; (2) PCB-015C — pairwise/curved coupling
z fizycznym modelem C/C0 lub even/odd i fail-closed; (3) opcjonalnie D2 —
feature-aware reconciliation z jawną tolerancją użytkownika; (4) optymalizacja
pełnej fali. Numer P2 w starszej liście nie oznacza aktualnego priorytetu D2.
Przed podjęciem działań zawsze ponownie przeczytaj końcówkę `todo.md`.

**Punkty do inspekcji w kodzie:** `src/antenna_lab/pcb/easyeda.py`,
`src/antenna_lab/pcb/easyeda_model.py`,
`src/antenna_lab/pcb/source_ir.py`,
`src/antenna_lab/pcb/reduced_control.py`,
`src/antenna_lab/solvers/reduced_source.py`,
`tests/test_pcb_easyeda.py`. Kieruj się stanem kodu, nie samą listą plików.

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
