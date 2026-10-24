# Migracja kontekstu — trwała pamięć i instrukcja przejęcia projektu

> **Ten plik jest punktem wejścia do repozytorium.** Jeżeli nowy czat dostał
> tylko wskazanie `migracja.md` i polecenie pracy nad projektem, poniższe
> instrukcje wystarczają do samodzielnego odtworzenia kontekstu. Nie trzeba
> wklejać historii wcześniejszych rozmów ani wymieniać pozostałych dokumentów.

**Repozytorium:** `analityk/antenna_solver_gpt`  
**Docelowa gałąź:** `main` (chyba że użytkownik jawnie wskaże inną)  
**Ostatnia inspekcja dokumentów:** 2026-10-22, Europe/Warsaw
**Potwierdzony opublikowany checkpoint przed aktualizacją:** `8bef03fc42ac774e6051a5325ccb3ce7832cf83d`
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


## Aktywny checkpoint 2026-10-24 — Copper Surface Field Explorer

Nowe polecenie użytkownika ma pierwszeństwo nad wcześniejszymi zadaniami
raportowania impedancji. Cel: istniejąca aplikacja GUI oferuje dwa
tryby pól: `far` (historyczne przekroje E/H) i `copper_surfaces` —
mapy E/H i przybliżone K oddzielnie dla obu stron każdej fizycznej
warstwy miedzi, tak jak na kolorowych mapach prądu z wektorami.
Dedykowany HTML NIE pokazuje S11/SWR/impedancji ani dalekich pól.
Źródło prawdy: [docs/pcb-copper-surfaces.md](docs/pcb-copper-surfaces.md).

Implementacja na gałęzi `feature/copper-surface-field-maps` (draft PR #12; **niezmergowany main**): UI/CLI
zapisują `field_mode`; preflight i XML dodają dokładne węzły Z = Zcu
±10 µm (jawnie zmieniają CFL, cell_count); 8 sond dla 4 użytych
warstw Cu z E/H i maską tylko poza polygonem miedzi; zespolone
K_face_proxy = n × H na próbce 10 µm (NIE dokładny prąd PEC ani
skin/proximity), osobny HTML z mapami trzech amplitud i zoomem.
Nowy tryb nie maskuje automatycznie H przy metalu szerokim halo.
Stary tryb i stare raporty pozostają bez zmian.

Ważne ograniczenia: w poprzednich wynikach brakuje powierzchniowych
sond; ich danych nie da się odtworzyć przez ponowny raport.
Konieczna walidacja zbieżności pól względem odległości sond/siatki;
same mapy nie dowodzą zweryfikowanych fizycznych prądów w miedzi.
Brak natywnych testów Windows w środowisku agenta. Testy syntetyczne
nowo dodane, wyniku jeszcze nie potwierdzono. Następny krok po pull:
1) test_pcb_surface_fields.py i test_pcb_gui_commands.py;
2) PREPARE-ONLY małego `.epro` z `copper_surfaces` i audyt Z/komórek/CFL;
3) mały test natywny przed kosztownym FDTD.

## Aktualny checkpoint — stabilne nazwy raportów (2026-10-24)

Użytkownik uruchomił na Windows `antenna_lab report .../stripline3_004`
i dostał niechciany timestamp w nazwie HTML:
`outcomes/reports/stripline3_004_20261024T004959_587285Z.html`.
Przyczyną było bezwarunkowe `datetime.now(timezone.utc).strftime(...)`
w `visualization/report.py` w domyślnej ścieżce manualnego raportu.
Zmieniono **tylko nazewnictwo wyjściowego HTML**: `stripline3_004.html`,
a gdy istnieje `stripline3_004__002.html`, `__003` itd. Re-generacja
nie nadpisuje starych raportów ani danych źródłowych; `--output` oraz
automatyczny `run/report.html` zachowują swoje kontrakty. Dla wariantu
antenowego wybranego przez JSON zachowano `wariant__run.html`.
Dodano test powtarzalności, kolizji, jawnego output i niezmienności run.
Bez nowych FDTD, pól, korekt wyniku i parametrów solvera.

**Następny krok Windows:** `git pull --ff-only`;
`.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p test_report.py -v`
oraz `python -m antenna_lab report .../stripline3_004 --open`.
Sprawdzić raport HTML bez daty w `outcomes/reports/`; dotychczasowego
pliku z timestampem nie kasować. Status testów po tej zmianie:
nieuruchomione przez agenta. Dokumenty: `docs/reports.md`, `todo.md`,
`history.md`. Poprzednia diagnostyka przerwanego FDTD poniżej.

## Aktualny checkpoint — czytelność raportu PCB i recovery przerwanego FDTD (2026-10-23)

Na rzeczywistym przebiegu użytkownika `outcomes/pcb_easyeda/stripline2_006`
przerwanym po >3 h (brak temporalnej zbieżności) offline
`antenna_lab.pcb.postprocess --run-dir ...` odzyskał sondy portu i raport,
ale E/H failed. Obserwacja Windows: HDF5 ma `FieldData/FD` z atrybutem
częstotliwości `[1.2e9,1.5e9,1.8e9]` i **zero zbiorów `f0...`**; to brak
zapisanych próbek, nie udowodniona niezgodność `NXYZ`. `openEMS_stats.txt`
brakuje; `termination_status=unconfirmed`. Próbek `port_ut_1` jest 71 w
oknie ~3.016 ns (co 43.087 ps, **nie** krok FDTD). Z odzyskanych Z/S11 nie
wolno wnioskować o rzeczywistym rezonansie bez dalszej walidacji.

Użytkownik zgłosił zrzut nieczytelnej ściany JSON `Rozwiązany profil openEMS`
i mylące fioletowe pionowe kreski na schemacie stackupu. Dostosowano
renderer: rozwijany pełny profil z krótką etykietą `design/max_cells`,
rysunek warstw bez umownych rozmieszczeń PTH/NPTH, diagnostyka pustego
HDF5 bez fałszywego błędu formatu. Nie zmieniono danych, geometrii,
mesh, portu, materiałów, silnika ani FDTD. Testy regresyjne dodane. Użytkownik potwierdził na Windows:
`postprocess_002` wygenerował nowy raport, port `processed`, pola
`failed` z prawidłowym komunikatem pustego FD, temporalne zakończenie
`unconfirmed`; 7/7 testów `test_fields.py` PASS. Wszystkie 5 testów
`test_pcb_report.py` zatrzymały się w identycznym `setUp` — fixture
`vertical=True,loop=True` powodował `PCB copper fidelity` (inner=(2,0),
modeled=(1,0)), przed wykonaniem testów HTML. W osobnym checkpointcie
zmieniono **tylko fixture raportów** na bazowy bez mostka; nie rozluźniono
fizycznego audytu, a wariant loop pozostaje w osobnych testach topologii.
Zmiana fixture nie została jeszcze wykonana na Windows. Natywnego FDTD
nie uruchamiano przez agenta.

**Pierwszy krok po `git pull --ff-only`:** bez solve ponowić
`.\\.venv\\Scripts\\python.exe -u -m antenna_lab.pcb.postprocess --run-dir "outcomes\\pcb_easyeda\\stripline2_006"`;
nowy HTML w `postprocessed/postprocess_NNN/report.html` powinien mieć
zwinięty profil i stackup bez pseudo-via; fields pozostaje failed,
ponieważ brak próbek. Dokumenty `docs/reports.md`, `docs/fields.md`,
`todo.md`, `history.md`. Najbliższy cel: osobny eksperyment ograniczonego
czasu/modelu, który zapisze użyteczne widma E/H i wyjaśni plateau energii;
nie utożsamiać wyniku częściowego z walidacją SI.

## Checkpoint — multilayer EasyEDA EM stackup (2026-10-23)

Po potwierdzeniu `LAYER_PHYS 15 inner stackup unsupported` rozszerzono
adapter EasyEDA na źródłowe stosy wielowarstwowe. Nie zmieniano
silnika openEMS ani FAST. `source_physical_stackup` filtruje wyłącznie
fizyczne TOP/INNER(SIGNAL/PLANE)/BOTTOM oraz SUBSTRATE w kolejności
LAYER_PHYS. Pozostałe znane warstwy (silk/mask/paste/stencil) wykluczono
z modelu EM i zachowano w metadanych. Soldermask — osobny przyszły
model εr_eff, dziś bez ukrytych korekt. Realny stripline1 ma cztery
warstwy miedzi i trzy SUBSTRATE; wartości εr są 0 i **nie są** domyślnie
zastępowane FR4. SOURCE INSPECT może pokazać brak materiału, ale
PREPARE/FDTD wymaga jawnych εr poprzez tabelę Warstwy EM w Windows GUI
lub `--dielectric-material LAYER_ID:ER:TAN`. Ręczny JSON nie jest
obowiązkowy. Użyta grubość PTH również wymaga jawnego wyboru.

Testy `tests/test_pcb_easyeda_stackup.py` i
`tests/test_pcb_gui_commands.py`: dodane, bez pełnej suite.
Nie stwierdzono natywnej zgodności siatki/XML i wyników EM na Windows;
następne działanie użytkownika: `git pull --ff-only`, uruchomić GUI,
wybrać stripline1, wykonać INSPECT, sprawdzić mapowanie i źródłowe
braki εr; następnie wprowadzić fizyczne materiały i PREPARE-ONLY,
nie uruchamiać FDTD bez oceny wyniku przygotowania.

## Kolejny checkpoint — realne łuki POURED stripline1 (2026-10-23)

Po scaleniu poprzedniej obsługi wielu konturów użytkownik nadal
otrzymał `POURED e102 ... unsupported polygon subtype (only R or straight
L contour)`. Projekt `gerbs/stripline1/stripline1.epro` dodany na `main`
został odczytany wprost: PCB record 230 (`e102`) to pięć otworów
okrągłych z dwóch `ARC 180`, record 234 (`e103`) to pięć otworów
z `ARC 90` i `L`. Nowy `curved_polygon_ring` obsługuje signed
ARC/CARC i L oraz R w fizycznej geometrii konturów POUR/POURED,
korzystając z budżetu 1e-7 m jak istniejący gerber parser. Testy
używają repozytoryjnego archiwum + offline synthetic fixtures.
Nie pomijano otworów ani warstw.

Osobny przyszły blocker: **13 rekordów LAYER_PHYS, POURED na layer16**,
podczas gdy `build_source_layout` wymaga stosu top / jeden substrate /
bottom i odrzuca wewnętrzne fizyczne warstwy. Nie deklarować
`stripline1` jako FDTD-ready po samym odblokowaniu ARC. Jeżeli
pojawi się błąd stackupu, nie usuwać warstw z CAD i nie
aproksymować wielowarstwowego PCB jako dwuwarstwowego. Nie
uruchamiano FDTD/PSU/FAST.

## Checkpoint importera: complex EasyEDA POURED (2026-10-23)

Użytkownik testował `gerbs/stripline1/stripline1.epro` w Windows GUI.
`--inspect-source` zwrócił `POURED e102 (record 230): complex POURED
fill rule unsupported`. Wspólny parser EasyEDA przed zmianą odrzucał
każdy `POURED` z więcej niż jednym konturem. Dodano w `easyeda.py`
wiele poprawnych L/R rings dla SOLID POUR / filled unstroked POURED,
a `easyeda_model.py` materializuje nonzero winding z otworami i
osobnymi wyspami bez dopowiadania miedzi. Nieznane kontury zakrzywione
i thermal strokes są nadal blokowane. Dodano 5 małych testów
regresyjnych, izolowany algorytm Shapely sprawdzony na dziurach/wyspach.
Nie przetestowano prawdziwego `stripline1.epro`, którego brak po
stronie asystenta; nie uruchamiano FDTD/PSU/FAST.
Najbliższy krok: `git pull --ff-only` i ponowna inspekcja w GUI,
w razie kolejnego UNSUPPORTED zachować dokładny log. Dokumenty:
`docs/pcb-easyeda.md`, `todo.md`, `history.md`.

## Checkpoint GUI: parametry automatycznie przypisane do folderu CAD (2026-10-23)

GUI wcześniej przechowywało formularz w globalnym pliku użytkownika,
nie przełączając ustawień solvera przy nowym `.epro`. Aktualnie dodano
`pcb/gui_project_settings.py`: katalog `parameters/<folder_projektu>/`
(identyfikacja folderem pod `gerbs`, nie pojedynczym plikiem .epro).
Wybór pliku tworzy katalog jeśli potrzeba, pokazuje go pod ścieżką
projektu, a lokalny `gui-settings.json` zapisuje atomowo wartości
eksperymentu, jakości, pól, override i fabrykacyjnych założeń PTH.
Wszystkie `.epro` z jednego folderu używają tych samych ustawień;
nie przenosi się specyficznego manualnego source-config, source PCB ID
ani poprzedniego katalogu wyników. `CSXCAD_INSTALL_PATH` i globalny
TOML pozostają ustawieniami instalacji. Lokalne pliki gui-settings
wykluczono z Git. Testy offline dodane; odbiór Windows GUI/FDTD nie
został wykonany w środowisku asystenta. Bez zmian geometrii/EM/FAST/PSU.

## Poprawka GUI: excitation guard (2026-10-23)

Nowe GUI początkowo stosowało center ± cutoff, a backend wymaga
center ± 0.8×cutoff. Dla center=600/cutoff=500/sweep=100–900
zatrzymywał się dopiero solver. Dodano wcześniejszą walidację w
`gui_commands.py`, komunikat z właściwymi granicami i przycisk
`Dopasuj pobudzenie do sweep`. Przycisk wylicza center=(lo+hi)/2,
cutoff=(hi−lo)/1.6 tylko po akcji użytkownika. Dla podanego przypadku
500/500 MHz. Dodano celowany test regresyjny. Nie zmieniono fizyki,
solverów, mesha ani PTH. Bez FDTD.

## Nowy checkpoint — Windows PCB GUI (2026-10-23)

Na bazie narzędzi PCB dodano `src/antenna_lab/pcb/gui.py` (Tkinter),
czysty moduł `gui_commands.py`, Windows `PCB_GUI.bat`, celowane testy
bez natywnego solvera i `docs/pcb-gui.md`. GUI prowadzi przez wybór
lokalnego `.epro`, inspect-source (bez rozwiązywania FAST), przygotowanie,
pełny FDTD i późniejszy raport. W formularzu są wszystkie częstotliwości,
profil, geometry-resolution, PTH, opcjonalna source-config, override
solverów, faza 15/30°, kadrowanie pola. Stan zadań wyświetla się w
logu na żywo. Każdy etap działa jako osobny subprocess, nie wymaga
drugiego solvera. `--yes` uruchamia FDTD dopiero po pytaniu w GUI.
Wyniki `<stem>_NNN`, brak nadpisywania i brak fałszywego completed.

Nowe GUI uruchom: `PCB_GUI.bat` z głównego katalogu repozytorium lub
`\.venv\Scripts\python.exe -m antenna_lab.pcb.gui`. Nie wykonano
natywnego uruchomienia GUI pod Windows w środowisku asystenta ani FDTD;
testy komend: `python -m unittest discover -s tests -p test_pcb_gui_commands.py -v`.
Pierwszy test odbiorczy użytkownika to otwarcie GUI i inspekcja lokalnego
`gerbs/dif4001/dif4001.epro`, potem PREPARE-ONLY.

## Nowy checkpoint — automatyczna konfiguracja źródła EasyEDA

Dla pełnego `.epro` kontroler PCB potrafi bez `--source-config` zbudować
źródłowy kontrakt portu i R/L/C z atrybutów instancji / referencjonowanego
Device. Zapisuje `source-config.resolved.json` w katalogu nowego przebiegu.
Samodzielny generator `python -m antenna_lab.pcb.easyeda_auto_config
--easyeda-project PATH --output FILE` nie uruchamia FDTD ani nie wymaga
przejścia parsera fizycznej geometrii. PTH-plating nadal wymaga jawnej
wartości; `--pth-plating-um` nie jest zgadywane. Zakres: tylko .epro,
bez zmian mesha/openEMS/FAST/PSU.

Dla lokalnego `gerbs/dif400/dif400.epro` wcześniejsza inspekcja zatrzymała
się na `DIMENSION e4`: to osobny problem parsera, którego sam generator nie
naprawia. Nie ma lokalnej kopii tego nowego archiwum w środowisku asystenta;
nie deklarować jego importu ani FDTD jako PASS.

## 4. Bieżący punkt wznowienia — ROI wizualizacji pól PCB

Baza 8bef03fc42ac774e6051a5325ccb3ce7832cf83d. Implementacja w
visualization/field_roi.py i pcb_fields.py. Ta sama warstwa raportów dla
EasyEDA/Gerber, bez zmian solvera. Domyślnie active+geometry / −40 dB / 1 mm.
Pełna specyfikacja: docs/fields.md. Dane NPZ/HDF5 nie są modyfikowane.

## 5. DONE / PARTIAL / OPEN

DONE implementacja ROI: maksimum po całym okresie z fazorów, oddzielne
względne progi E/H, suma fizycznej geometrii i aktywności, fallback, stałe
limity PNG/HTML dla wszystkich faz. Domain pokazuje pełny zapisany przekrój.
Nie rozszerzać ROI samą szarą maską halo lub obrysem PCB.
9 testów test_pcb_field_roi PASS (w tym oba CLI);
ReportTests.test_report_is_offline_escaped_and_does_not_touch_sources PASS.
PcbFieldTests.test_fixed_scales_display_only_subsampling_and_strict_loader
zatrzymuje się w setUp przed wizualizacją: copper fidelity inner=(2,0),
modeled=(1,0). Potwierdzono ten sam błąd uruchamiając wersję testu
z f1c7a5a na niezmienionym mesherze. Nie rozluźniano audytu geometrii.
Realne dane pól spirali niedostępne; dwa zrzuty obejrzano, nie są testem NPZ.
Poprzedni postprocessing: 17 testów historycznych PASS, native Windows nadal
wymaga lokalnego odbioru; brakujące legacy artefakty nie są zgadywane.

## 6. Następne sprawdzenie

```cmd
.\.venv\Scripts\python.exe -m antenna_lab report "<katalog_wynikow>" --field-view active+geometry --field-crop-threshold-db -40 --field-crop-margin-mm 1 --open
```

Testy ukierunkowane: test_pcb_field_roi. Nie wykonywać FDTD, pełnej suite,
PSU ani FAST. Następny krok: lokalny odbiór raportu z rzeczywistych pól;
nie ponawiać kosztownej symulacji. Problem fixture meshera jest odrębny.
Opcje ROI działają także w pcb.postprocess; tylko prezentacja, bez wpływu na
CalcPort, normalizację pól, maskowanie i częstotliwości.

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
