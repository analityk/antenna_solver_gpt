# Instrukcje pracy nad antenna_solver_gpt


## Przejmowanie projektu między czatami — obowiązkowy punkt wejścia

Repozytorium jest trwałą pamięcią projektu. Historia rozmowy, pamięć modelu
ani stan lokalnego, efemerycznego środowiska nie są warunkiem kontynuacji.
`migracja.md` jest **samodzielnym punktem wejścia i bieżącą kartą przekazania**.
Użytkownik może wskazać w nowym czacie wyłącznie ten plik i polecić
kontynuowanie pracy; agent ma sam odczytać wskazane w nim źródła.

Przy rozpoczęciu nowego zadania lub przejmowaniu projektu:

1. Odczytaj **cały** `migracja.md` i wykonaj jego sekcję „Instrukcja dla nowego
   czatu”; następnie przeczytaj `AGENTS.md` (w tym lokalne instrukcje katalogów).
2. Zweryfikuj bieżącą gałąź i HEAD, historię najnowszych commitów oraz stan
   plików użytkownika. Przeczytaj `todo.md`, adekwatną końcówkę `history.md`,
   `goal.md` i odpowiednie dokumenty `docs/*.md`, zgodnie z mapą w
   `migracja.md`. W razie potrzeby obejrzyj implementację i testy.
3. Rozdziel stan udokumentowany od stanu potwierdzonego kodem i sprawdzeniami.
   Gdy dokument przekazania jest starszy niż repozytorium lub sprzeczny z nim,
   ustal aktualne fakty z kodu/commitów i zapisz rozbieżność; nie zakładaj,
   że starsze PASS oznacza nowy PASS.
4. Ustal aktualny blocker i najbliższe jednoznaczne zadanie. Jeżeli użytkownik
   polecił kontynuację, działaj według aktualnych priorytetów bez żądania
   ponownego opisu poprzednich rozmów; nowsze polecenie użytkownika ma
   pierwszeństwo.

Nie przenoś pełnych transkryptów czatu do repozytorium: zapisuj decyzje,
przesłanki, rzeczywisty stan, dowody, ograniczenia i następne działania.
Nie odczytuj bez potrzeby całej wieloletniej historii; używaj najnowszych
wpisów i sięgaj do wcześniejszych decyzji, gdy są istotne.

## Cel i stan pracy

Po odczytaniu `migracja.md` zapoznaj się z `goal.md`, adekwatną częścią
`history.md` i `docs/architecture.md` zgodnie z protokołem przejęcia.
`goal.md` jest źródłem wymagań; parametry maszynowe znajdują się w `parameters/`.
Bieżący cel: parametryczna symulacja Quadosa 8 przy 1420 MHz, z możliwością
dodania innych anten bez zmiany zasad działania rdzenia.
Dodano model `biquad` (dwa romby, osiem odcinków) i konfigurację
`parameters/biquad_1420mhz.json`. Wymiary startowe nie są dostrojoną anteną;
korzysta z tego samego eksperymentalnego portu i statusu unverified.

Platforma docelowa użytkownika: natywny Windows 11. Instrukcje uruchamiania
mają używać środowiska `.venv` i składni aktualnej powłoki użytkownika.
Instalacja i import zostały potwierdzone w CMD; PowerShell również jest dostępny.
Git, Python i VS Code są już zainstalowane. Interpreter: CPython 3.14.0, 64-bit AMD64.
Wybrany solver to openEMS. Lokalizacja paczki podana przez użytkownika:
`C:\dev\openems\openEMS`. Instrukcja instalacji: `docs/windows-setup.md`.
Nie wymagaj WSL, zmiany systemu ani uv. Użytkownik potwierdził import
openEMS 0.37.0rc3 i CSXCAD na Windowsie 2026-09-28. Walidacja obliczeniowa
pozostaje otwarta; sam import ani pierwszy solve nie kończą integracji M2.

NEC2++ / PyNEC nie jest częścią implementacji. Kontrakty przeniesiono na
openEMS: konfiguracja i manifest mają wersję 2. Wymiarów źródłowych nie zmieniono.
Potwierdzone środowisko zapisano w `docs/windows-setup.md`.

M1 jest zaimplementowane: generator, walidacja, edytor i eksport geometrii.
Adapter openEMS, impedancja i pole dalekie są kodem eksperymentalnym:
Użytkownik ukończył przebieg 20260928T004231Z_902d497594 na Windowsie.
Kontrola source_work z 450 parami sond jest ukończona na Windowsie; poprawka
limitu UCRT została potwierdzona. Przy pierwotnym odniesieniu portu 1 W praca
lokalna netto wynosi 0,879386295 W, strumień zewnętrzny 0,878490162 W.
Pozorny deficyt 12,15% względem pojedynczego U·I maleje do 0,102% względem
pracy lokalnej. To nie jest jeszcze walidacja impedancji i zysku.
Znaleziono błąd adaptera: zaokrąglone kotwice siatki leżą minimalnie poza
niezaokrąglonym boxem źródła; opór obejmuje 450 krawędzi, wymuszenie tylko 270.
Pozostałe 180 krawędzi ma zmierzony wkład ujemny zgodny z samym oporem.
Nowy wariant parameters/quados8_1420mhz_aligned_feed.json ustawia
solver.port_mesh_alignment=mesh_anchors i przekazuje dokładne granice siatki
do AddLumpedPort. Użytkownik ukończył ten wariant natywnie: 450 dodatnich
wkładów pracy, zero ujemnych; ta sama geometria i siatka. Praca 0,949145539 W,
strumień zewnętrzny 0,948187885 W, różnica 0,10090% względem pracy.
Pomiar pojedynczego U·I nadal daje 1 W, czyli rozbieżność 5,085% względem
tego odniesienia. Poprawka granic jest potwierdzona, pomiar mocy portu nadal
wymaga rozwiązania. Z=67,701−j95,621 Ω i SWR200=3,6975 są robocze.
Kierunkowość na osi wynosi 17,5100 dBi w obu przebiegach; porównanie względem
lokalnej pracy daje około 17,5056 dBi, ale nie zastępuje kontroli zbieżności.
Brak opcji/legacy zachowuje stare źródło do odtwarzania; nie traktuj go jako
poprawionego modelu. Nie wymuszaj bilansu renormalizacją i nie zatwierdzaj
starego ani nowego SWR/zysku. Nie poprawiaj Z mnożnikiem bilansu mocy.
Powtarzanie aligned_feed bez zmiany hipotezy nie rozwiąże niejednorodnego
pomiaru portu; dane już to wykazały. Następny eksperyment wymaga jawnej
definicji bardziej lokalnego zasilania i jego kontroli. Potem zbieżność
i strojenie (docs/power-audit.md). Błąd otwarcia pliku zatrzymuje pracownika.
Analiza geometrii wskazuje dwie nadmiarowe kule przy (±G/2,0,H), całkowicie
wewnątrz dwóch przeciwległych walców A. Pozostałe 46 ma własne próbki E.
To wyjaśnia dwa ostrzeżenia Sphere; nie jest pełnym natywnym audytem połączeń.
Nie przedstawiaj M2 jako zakończonego. Prądy promiennika i animacja pełnego
okresu nie są zaimplementowane; ich żądanie kończy się jawnym błędem.
Przekroje E/H i diagramy fazowe są obsługiwane przez --fields dla obu anten
(docs/fields.md); testy syntetyczne nie zastępują natywnego FDTD i zbieżności.
Maskuj metal, obwiednię interpolacji i idealny port. Zachowaj surowe HDF5,
zespolone pola i wspólną skalę między fazami. Nie koryguj bilansu normalizacją.
Pasywne sondy portu i powierzchnie diagnostyczne same nie zaliczają M3.

## Zasady architektury

- `core` nie zna Quadosa, API openEMS ani interfejsu graficznego.
- Modele anten generują geometrię i porty; nie uruchamiają solvera.
- Adapter solvera przelicza jednostki i konwencje we własnej granicy.
- Parametry nie są zaszyte w kodzie. Każdy wynik zawiera ich rozwiązaną kopię.
- Wizualizacja czyta zapisane wyniki. Zmiana fazy animacji nie uruchamia solvera.
- `report` tworzy samodzielny HTML offline z istniejących wyników; opis
  w `docs/reports.md`. Ręczne raporty zapisuj poza ukończonym przebiegiem.
  Automatyczny raport powstaje przed zamknięciem manifestu nowego `run`;
  błąd prezentacji nie może unieważnić udanego FDTD. Suwak impedancji nie
  zmienia częstotliwości bilansu ani pola dalekiego. Nie zatwierdzaj modelu
  automatycznie na podstawie zgodności bilansu i nie koryguj Z/zysku.
- Nowe katalogi wyników mają prefiks nazwy pliku wariantu. `report wariant.json`
  wyszukuje ukończone obliczenia po zapisanej geometrii i częstotliwościach,
  także w starych katalogach. Nie identyfikuj geometrii samym polem `id`.
- Dodanie nowej anteny nie powinno wymagać specjalnych warunków w rdzeniu.
- Na początek jeden pakiet Pythona; solver działa w lokalnym procesie potomnym.
  Nie dodawaj
  mikroserwisów, klastra, zewnętrznej bazy ani chmury bez konkretnej potrzeby.

## Rzetelność obliczeń

- W rdzeniu stosuj SI: m, Hz, V, A, W. Milimetry i MHz służą interfejsowi.
- Ustalona konwencja fazowa: część rzeczywista F · exp(+j · faza).
- Zachowuj surowe zespolone prądy i pola. Obraz nie zastępuje danych.
- Rozróżniaj kierunkowość, zysk i zysk uwzględniający niedopasowanie.
- Rozróżniaj impedancję anteny, impedancję odniesienia i transformację baluna.
- Siatki przewodów PEC nie nazywaj ciągłą blachą. Braku dielektryków, kabla,
  strat lub skończonej grubości nie ukrywaj w opisie wyniku.
- Nie dopasowuj modelu do oczekiwanego 17,6 dBi. To wartość referencyjna,
  a nie kryterium, które wolno wymuszać.
- Nie publikuj wyniku jako zweryfikowanego bez jawnej kontroli geometrii,
  źródła, jednostek, normalizacji i zbieżności istotnych wielkości.
- Brak wyniku zapisuj jako brak danych wraz z przyczyną, nigdy jako zero.

## Historia zmian i sprawdzanie

Każda większa zmiana wymaga wpisu w `history.md`: przyczyna, zakres, wpływ
na fizykę/wyniki, wpływ na formaty i odtwarzalność, wykonane sprawdzenia oraz
ograniczenia. Nie opisuj przyszłej pracy jako zakończonej.

Sprawdzaj ryzyka wynikające z konkretnej zmiany. Nie twórz testów, które jedynie
powtarzają implementację. Dla samej dokumentacji wystarcza kontrola jej spójności.
Użytkownik wykluczył benchmarki: nie twórz ani nie uruchamiaj ich bez nowej
instrukcji użytkownika. Nie wracaj do szacowania czasu na jego komputerze.

Wyniki dużych obliczeń są poza zwykłą historią Git; wersjonowane są konfiguracje,
schematy, kod i niewielkie, świadomie wybrane dane referencyjne. Nie dodawaj
danych dostępowych, lokalnych konfiguracji kont ani całego środowiska procesu.

## Sposób pracy

Instrukcje użytkownika mają pierwszeństwo. Dokumentacja dla użytkownika jest
po polsku, nazwy w kodzie po angielsku. Zachowuj istniejące zmiany użytkownika.
Nie twórz autonomicznie nowych agentów ani rozbudowanych procesów pracy.
W katalogach z własnym `AGENTS.md` obowiązują również instrukcje lokalne.

## Trwałość pracy agenta i Git

Te zasady są obowiązkowe dla każdego zadania modyfikującego repozytorium, chyba że użytkownik jawnie nakaże inaczej.

- Status testów PASS/PARTIAL/FAIL, brak zależności natywnych, błędy integracyjne i dług techniczny nie są bramką dla commitowania ani publikacji.
- Przed rozpoczęciem istotnej pracy sprawdź, czy istnieje działający kanał zapisu do docelowego repozytorium GitHub. Preferuj zwykły `git push`. Jeśli powłoka nie ma poświadczeń, ale dostępna integracja GitHub potrafi zapisywać, użyj jej.
- Jeżeli nie ma żadnego działającego kanału zapisu do GitHuba, zatrzymaj zadanie przed kosztowną/istotną implementacją i poproś o dostęp. Nie wykonuj długiej pracy, która pozostanie wyłącznie w efemerycznym środowisku agenta.
- Każdą znaczącą zmianę kodu, testów lub dokumentacji commituj także wtedy, gdy zadanie kończy się PARTIAL albo FAIL.
- Każdy commit z pracą agenta publikuj do `origin/main`, chyba że bieżące polecenie użytkownika jawnie wskazuje inną gałąź.
- Gdy istnieje już znacząca praca, zrób commit i push checkpointu przed drogim pełnym zestawem testów. Kolejne poprawki commituj i pushuj osobno. Trwałość pracy ma pierwszeństwo przed idealnie czystą historią.
- Nie wstrzymuj pushu z powodu nieudanego końcowego testu. Raportuj osobno stan testów i stan publikacji.
- Plik patch nie jest normalnym sposobem przekazania pracy. Używaj go wyłącznie awaryjnie po wyczerpaniu uwierzytelnionych sposobów publikacji i tylko gdy użytkownik zaakceptuje taki fallback.
- Nie używaj `git add -A`, `git add .` ani `git commit -am`. Stage'uj wyłącznie jawne pliki należące do zadania.
- Nie dodawaj przypadkowo `outcomes/`, lokalnych backupów parametrów, archiwów ZIP, plików `*.patch` ani innych niepowiązanych plików użytkownika.
- Nie wykonuj `reset --hard`, `clean`, usuwania ani nadpisywania niepowiązanej pracy użytkownika.
- W raporcie końcowym zawsze podaj opublikowany SHA, gałąź, wynik pushu, faktycznie uruchomione testy i znane ograniczenia.

Pełny zestaw testów na docelowym Windows uruchamiaj poleceniem:
`.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v`.
Projekt używa `unittest`; nie instaluj pytest tylko po to, aby uruchomić testy.

## Obowiązkowe zamknięcie zadania: inspekcja dokumentacji i przekazanie stanu

**Ten krok wykonuj samodzielnie na końcu każdej pracy dotyczącej repozytorium,
również wtedy, gdy użytkownik nie wspomni o dokumentacji ani migracji.**
Nie odkładaj go do końca czatu, bo czat może zakończyć się bez ostrzeżenia.
Dla dłuższych prac powtarzaj checkpoint po samodzielnych, istotnych etapach.

1. Przejrzyj zmiany i aktualność powiązanych plików `*.md`: co najmniej
   `migracja.md`, `todo.md`, właściwy fragment `history.md` oraz te pliki
   `docs/*.md`, `README.md`, `goal.md` i lokalne `AGENTS.md`, które dotyczą
   zmienianego zachowania. Nie czytaj i nie przepisuj wszystkich dokumentów
   bez związku z zadaniem.
2. Jeżeli stan, blocker, następny krok, wynik testów, decyzja, CLI, format,
   ograniczenie lub kontrakt uległy zmianie, **zaktualizuj `migracja.md`**
   i odpowiednie dokumenty źródłowe w tym samym etapie pracy. Dla większych
   zmian uzupełnij `history.md` według istniejących zasad; `todo.md` ma
   odzwierciedlać realny priorytet. `migracja.md` ma pozostać czytelnym,
   aktualnym punktem startowym, nie dziennikiem wszystkich zdarzeń.
3. Jeśli nie ma merytorycznej zmiany dokumentacji, pozostaw pliki bez zmian;
   nie twórz sztucznych commitów ani aktualizacji samych dat. Jeżeli użytkownik
   wprost ograniczył zakres modyfikowanych plików lub zlecił tylko odczyt,
   respektuj to i opisz zauważone rozbieżności bez zapisu zabronionych plików.
4. Utrwal istotne zmiany checkpointem `git commit` i opublikuj zgodnie z
   zasadami powyżej. Nie wstrzymuj publikacji ze względu na PARTIAL/FAIL;
   odróżniaj testy wykonane teraz od testów historycznych. Nie wpisuj do
   `migracja.md` SHA commita, który dopiero powstanie: podaj SHA ostatniej
   **już opublikowanej** wersji przed checkpointem, a SHA nowego commita
   potwierdź po pushu w odpowiedzi.
5. W odpowiedzi końcowej podaj, co wykonano, co pozostało otwarte, faktyczne
   testy i ich status, zakres aktualizacji dokumentacji oraz SHA, gałąź i
   wynik publikacji. Gdy publikacja jest niedostępna, jasno zgłoś ten fakt;
   nie zapewniaj o zachowaniu stanu bez trwałego zapisu.

**Ostatnie obowiązkowe pytanie kontrolne agenta przed zamknięciem pracy:**
„Czy nowy czat, znając tylko `migracja.md`, potrafi ustalić aktualny stan,
przyczynę bieżącej przeszkody, najbliższe zadanie oraz źródła weryfikacji?”.
Jeśli nie — popraw przekazanie stanu przed zakończeniem.
