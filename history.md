# Historia większych zmian

Historia opisuje skutki decyzji, nie zastępuje historii commitów Git.

## 2026-09-28 — M0: wydzielenie projektu Antenna Lab

**Powód:** użytkownik wymaga osobnego, rozwijalnego projektu GitHub,
instrukcji `AGENTS.md`, wymagań `goal.md` i oceny większych zmian w tym pliku.

**Zmiana:** przygotowano strukturę rdzenia, modeli anten, adapterów solvera,
parametrów, wizualizacji, aplikacji i wyników. Dodano konfigurację Quadosa 8
przy dokładnie 1420 MHz, źródłowe wymiary, szkic konstrukcji geometrii oraz
kontrakt outcomes i schematy JSON. Zakres tej zmiany to fundament projektu.

**Wpływ na fizykę i wyniki:** nie wykonano nowej symulacji. Konfiguracja
startowa używa skali 2450/1420, z jawnym niepotwierdzonym założeniem
częstotliwości bazowej. Nie przeniesiono wyniku zysku double biquada na Quadosa.
Siatka reflektora, port idealny i brak baluna są jawnymi uproszczeniami.

**Wpływ na architekturę:** zależności NEC2++ mają pozostać w adapterze;
nowa antena ma dostarczać geometrię, a wizualizacja czytać wspólny format danych.
Nie powstał jeszcze wykonywalny symulator ani interfejs.

**Wpływ na zgodność i odtwarzalność:** pierwsza wersja schematów to 1.
Wymagany manifest zapisuje wersję kodu, solvera, konfigurację i listę artefaktów.
Brak wcześniejszych publicznych formatów do migracji.

**Sprawdzenie:** dane z rysunku zestawiono z A–H i wymiarami reflektora;
obliczono skalowanie i sumę długości gałęzi. Sprawdzono składnię JSON,
wymagane pola konfiguracji, zgodność wymiarów oraz lokalne odsyłacze i ścieżki.

**Ograniczenia i dalsza praca:** topologia opisana w dokumentacji wymaga
implementacji i kontroli numerycznej. Wygenerowane charakterystyki jeszcze
nie istnieją. Użytkownik utworzył puste repozytorium `analityk/quados_nec2-`
i udostępnił je do zapisu. Ten komplet plików tworzy jego fundament.

## 2026-09-28 — zawężenie zakresu: bez benchmarków

**Powód:** bezpośrednia instrukcja użytkownika podczas przygotowywania projektu.

**Zmiana:** usunięto benchmarki z planu i z zakresu aktualnej implementacji.
Nie dodano ich kodu ani nie uruchomiono obciążeń pomiarowych.

**Wpływ:** praca skupia się na wymaganiach i strukturze projektu. Parametry
komputera użytkownika pozostają informacją projektową, bez prognoz czasów
i bez obietnicy użycia wszystkich rdzeni lub GPU przez pojedyncze obliczenie.
Kontrola poprawności fizycznej przyszłych wyników nadal jest wymagana.

## 2026-09-28 — platforma docelowa: natywny Windows 11

**Powód:** użytkownik potwierdził Windows 11 oraz istniejące instalacje Git,
Pythona i VS Code. Zmiana systemu nie jest rozwiązaniem dla tego projektu.

**Zmiana:** wymaganie zapisano w AGENTS.md, goal.md 0.2 i architekturze.
Dodano instrukcję podstawowego środowiska w PowerShellu z venv i pip.
Dokładna wersja i architektura Pythona pozostają do odczytania u użytkownika.

**Wpływ na fizykę i dane:** brak zmiany modelu, wymiarów i formatów outcomes.
Zmienia się wymaganie instalacyjne i kryterium odbioru adaptera solvera.

**Wpływ na integrację:** potwierdzono brak wheel Windows w wydaniu PyNEC
2.3.4 na PyPI. Upstream setup.py ma ustawienia GCC; wymagane jest opracowanie
i sprawdzenie natywnego pakietu lub innego adaptera NEC2++ dla Windowsa.
Nie deklarujemy, że samo pip install albo doinstalowanie MSVC zamyka temat.

**Sprawdzenie:** przejrzano metadane wydania, setup.py, pyproject.toml i build.sh
upstream oraz dokumentację venv. Nie wykonano kompilacji lub testu na Windowsie.
Przygotowanie zwykłych bibliotek Python nie oznacza gotowego środowiska solvera.

## 2026-09-28 — antenna_solver_gpt, wybór openEMS i konkretne środowisko Windows

**Powód:** użytkownik wybrał ogólną nazwę `antenna_solver_gpt`, wykluczył
NEC2++ z przyszłej implementacji, potwierdził Python 3.14.0 x64 i podał
ścieżkę paczki openEMS: `C:\dev\openems\openEMS`.

**Zmiana:** zaktualizowano nazwę projektu w README i instrukcjach, wybór
solvera w wymaganiach oraz architekturze, plan integracji i instrukcję Windows.
Wyjaśniono rolę `.venv`; polecenia używają konkretnego interpretera i ścieżki
użytkownika oraz lokalnych modułów z paczki openEMS 0.37.0-rc3 MSVC.
Użytkownik zmienił nazwę repozytorium GitHub; potwierdzono odczyt gałęzi main
pod adresem `analityk/antenna_solver_gpt`. Zaktualizowano odnośniki i polecenia Git.

**Wpływ na fizykę i wyniki:** nie zmieniono wymiarów ani nie wykonano symulacji.
Zmiana solvera wymaga osobnego projektu dyskretyzacji, źródła, reflektora
i odczytu danych. Samo przemianowanie nie daje równoważności modeli.

**Wpływ na architekturę i formaty:** openEMS jest wybranym solverem; NEC2++
nie będzie implementowany. Szczegółowe kontrakty M0 związane z NEC zostały
oznaczone w `goal.md` jako nieaktywne i wymagające migracji przed implementacją.
Nie deklarujemy, że obecne schematy lub `model.nec` opisują wejście openEMS.
Nazwa wewnętrznego pakietu `antenna_lab` pozostaje niezależna od nazwy repozytorium.

**Sprawdzenie:** sprawdzono instrukcję Python z oficjalnej paczki openEMS,
dokumentację venv i zgodność zapisanych ścieżek oraz odsyłaczy. Nie wykonywano
benchmarków ani testów na komputerze użytkownika. Import openEMS nie został
jeszcze potwierdzony. Repozytorium pozostaje na etapie specyfikacji.

## 2026-09-28 — potwierdzony import openEMS na Windowsie użytkownika

**Powód:** użytkownik przesłał log udanej instalacji pakietów i wynik importu
z lokalnego CMD w projektowym `.venv`.

**Zmiana:** zapisano działający import openEMS 0.37.0rc3 i CSXCAD oraz wersje
pakietów z logu instalacji. Uzupełniono instrukcję Windows o składnię CMD,
aktualny katalog repozytorium i wyjaśnienie podfolderu tworzonego przez klonowanie.
Zaktualizowano stan instalacji w instrukcjach, wymaganiach i architekturze.

**Sprawdzenie:** użytkownik wykonał `import openEMS, CSXCAD` i otrzymał
`openEMS: 0.37.0rc3` oraz `CSXCAD: OK`. Polecenie działało z interpretera
`.venv` w `C:\dev\antenna_solver_gpt\antenna_solver_gpt`.
Źródłem potwierdzenia jest log użytkownika, nie wykonanie na innym komputerze.
Sprawdzono spójność aktualizacji dokumentacji.

**Wpływ na fizykę i wyniki:** brak zmian modelu oraz danych symulacyjnych.
Potwierdzono instalację i ładowanie modułów; nie uruchomiono przypadku
obliczeniowego, symulacji Quadosa ani benchmarków. Etap M2 pozostaje otwarty.

**Wpływ na odtwarzalność:** udokumentowano konkretne wersje środowiska;
formaty wyników i konfiguracje anten nie zmieniły się. Pełny plik zależności
aplikacji powstanie przy jej implementacji.

## 2026-09-28 — M1 i pierwszy adapter openEMS

**Powód:** środowisko użytkownika importuje openEMS; kolejnym krokiem jest
wykonywalny model anteny i podgląd, z zachowaniem rozdziału geometrii i fizyki.

**Zmiana:** dodano instalowalny edycyjnie pakiet, parametryczny generator
Quados8, kontrolę połączeń i kolizji, edytor Matplotlib oraz polecenia check,
geometry, prepare i run. Edytor rozdziela zmianę częstotliwości i skalowanie.
Adapter przygotowuje siatkę i pełny FDTD XML; zawiera odczyt portu, impedancji,
S11/SWR oraz NF2FF i raport. Proces solvera jest oddzielony od procesu CLI.

**Wpływ na fizykę:** porzucony szkic NEC zastąpiono cylindrami PEC ze złączami
kulistymi oraz pełną płytą PEC o aktywnej grubości. Port jest skończonym
obszarem AddLumpedPort ze standardowymi zakończeniami. Wymiary źródłowe i
założenie skalowania 2450/1420 nie zmieniły się. Nie obliczono jeszcze
charakterystyki anteny, prądów ani pól. Występujące w testach liczby portu
są analitycznymi danymi jednostkowymi, nie wynikami symulacji Quadosa.

**Wpływ na formaty:** konfiguracja i manifest mają wersję 2; v1 jest jawnie
odrzucane. Przebiegi przechowują konfigurację, schematy, geometrię, archiwum
wybranych źródeł i skróty plików. Etap i stan wykonania są niezależne od
walidacji fizycznej. Wycofane kontrakty NEC usunięto z aktywnej dokumentacji.
Zachowano docelowe wymagania M2/M3 dotyczące prądów, E/H i animacji.

**Sprawdzenie:** przeszło 12 testów geometrii, normalizacji analitycznej,
siatki i zapisu. Sprawdzono instalację edycyjną pakietu i uruchomienie spoza katalogu repozytorium,
eksport CLI, wizualnie oba rzuty i edytor oraz
zmiany C, częstotliwości i odrzucenie kolidującego portu. Brak biblioteki
openEMS w środowisku wykonawczym poprawnie zakończył prepare stanem failed
i zapisanym logiem. API porównano z przypiętymi źródłami wydania 0.37.0-rc3.
To kontrola kodu na Linuxie; nie zalicza wymaganego odbioru M2 na Windowsie.

**Ograniczenia:** przygotowanie XML i obliczenia natywnym solverem pozostają
do sprawdzenia na Windowsie. Nie wykonano dipola kontrolnego ani trzech siatek
Quadosa. Wyniki adaptera są zawsze unverified; program nie potwierdza jeszcze
automatycznie osiągnięcia EndCriteria. Prądy, mapy E/H i animacje są odrzucane
jako nieobsługiwane, zamiast zapisywania pustych danych. Nie było benchmarków.

## 2026-09-28 — płynna edycja parametrów i rozdzielenie zapisów

**Powód:** użytkownik zgłosił opóźnienia przy wpisywaniu oraz niejasną różnicę
między zapisem wariantu i eksportem. Jednocześnie potwierdził udane prepare
na Windowsie, run_id 20260928T002146Z_f265477ca6, komunikat zapisu model.xml.

**Przyczyna:** TextBox Matplotlib odrysowywał całą figurę podczas edycji
kursora. Dodatkowe on_submit przy utracie fokusu uruchamiało walidację,
przebudowę i odświeżanie wszystkich pól. Był to problem obsługi GUI,
nie obliczeń openEMS.

**Zmiana:** formularz używa natywnych kontrolek Tk/ttk. Wpisywanie i Tab
oznaczają tylko niezastosowane zmiany; Enter/Zastosuj zatwierdza cały
formularz. EditorState zachowuje pełną precyzję nietkniętych wartości
i odrzuca błędy bez częściowego zmieniania modelu. Sama zmiana częstotliwości
nie przebudowuje geometrii. Podgląd jest rysowany po zmianie geometrii.
Komunikaty mają stałe miejsce, aby ich zmiana nie zmieniała rozmiaru wykresu.

Przyciski mają nazwy Zapisz parametry (.json) i Eksportuj geometrię oraz
widoczne opisy zawartości. Obie akcje najpierw zatwierdzają wpisane dane.
Ścieżkę zapisu można skopiować. Eksport PNG używa FigureCanvasAgg,
bez otwierania dodatkowej figury GUI. Uporządkowano pozycję legendy.

**Wpływ na fizykę i odtwarzalność:** brak zmiany generatora, solvera, jednostek
i formatów danych v2. JSON parametrów pozostaje wejściem przez --config,
a eksport tworzy odrębny przebieg geometryczny z pełną dokumentacją.
Tkinter jest już częścią standardowej instalacji Pythona Windows;
nie dodano zależności pip. Potwierdzenie prepare pochodzi z logu użytkownika,
nie z lokalnego odczytu jego XML. FDTD i walidacja fizyczna nadal są otwarte.

**Sprawdzenie:** przeszło 14 testów bez GUI, w tym nowe przypadki niepełnego
wpisu, odrzucenia kolizji, zachowania precyzji oraz braku przebudowy przy
zmianie samej częstotliwości. Dodano dwa testy integracyjne Tk: brak rysowania
i generowania podczas wpisywania/Tab, jedno zatwierdzenie Enter oraz oddzielne
artefakty obu zapisów. W środowisku wykonawczym nie można uruchomić ekranu Tk;
testy te są jawnie pomijane, a działanie nowego okna wymaga potwierdzenia
na Windowsie użytkownika. Nie wykonywano benchmarków ani pomiarów czasu.

## 2026-09-28 — audyt deficytu mocy i pasywna diagnostyka

**Powód:** użytkownik wymaga wyjaśnienia deficytu mocy przed generowaniem
kolejnych raportów i skalowaniem anteny. Dostarczył dane zakończonego przebiegu
20260928T004231Z_902d497594, port U/I oraz wszystkie 13 plików NF2FF HDF5.

**Ustalenia:** natywny wynik 0,878490159 W na 1 W przyjęty przez port został
odtworzony niezależnie jako 0,878490162 W. Sprawdzono skróty plików, komplet
ścian, zgodność E/H, orientacje i symetrię strumieni. Nie stwierdzono błędu
samego całkowania/normalizacji; przyczyna deficytu pozostaje niepotwierdzona.
Port zajmuje 18 × 4 × 4 komórki. W siatce wykryto skok wielkości komórek do
1,8667 mimo growth_ratio=1,4; generator nie ogranicza wszystkich przejść.
Osiągnięcie EndCriteria potwierdza solver.log, nie stanowi kontroli zbieżności.

**Zmiana:** dodano opcjonalne pasywne monitory dwóch dodatkowych powierzchni
mocy, 25 linii U i 18 przekrojów I portu oraz ich odczyt. Oddzielny wariant
konfiguracji zachowuje pierwotną geometrię, siatkę, impuls, port i zakończenie.
Diagnostyczny postprocessing zapisuje JSON, widma NPZ, impedancję 1400–1440 MHz
co 0,25 MHz i małą paczkę ZIP; pomija raport HTML i wykresy wynikowe.
Standardowe CalcNF2FF poprzedza teraz kontrola obecności sześciu par plików,
aby nie przyjąć niekompletnej powierzchni. Dodano jawną zależność h5py.

**Wpływ na fizykę:** brak zmiany wymiarów, źródła lub siatki. Nie wymuszono
bilansu mnożnikiem i nie przypisano deficytu rzeczywistym stratom PEC.
Celowo zachowano także znaną nierównomierność siatki w eksperymencie porównawczym.
Naprawa siatki i walidacja modelu pozostają osobnymi kolejnymi krokami.
Monitor wokół źródła służy strumieniowi lokalnemu; nie jest transformowany
na charakterystykę pola dalekiego. Mapy i prądy promiennika M3 pozostają otwarte.

**Formaty i odtwarzalność:** opcjonalne pole solver.power_diagnostics rozszerza
v2 bez zmiany starych konfiguracji. Dodano jawne artefakty w outcomes/README.md.
Pierwotnych danych nie nadpisano. Wariant i położenia monitorów są zapisywane.

**Sprawdzenie:** 18 testów bez natywnego solvera przeszło; klasa testów GUI
została pominięta z powodu niedostępnego Tk. Nowe kontrole sprawdzają twierdzenie
o dywergencji dla znanego pola, niejednorodne komórki, znaki normalnych,
niekompletne/niezgodne E/H, osobne znaczniki U/I i izolację eksperymentu.
Czytnik sprawdzono również na rzeczywistych plikach użytkownika. Potwierdzono
identyczność wszystkich linii siatki nowej konfiguracji z jego mesh.npz.
Nie wykonano nowego FDTD ani benchmarków. Natywne dodatkowe monitory wymagają
uruchomienia na Windowsie użytkownika; wyniki pozostają unverified.

## 2026-09-28 — wyniki kontroli pasywnej i lokalna praca źródła

**Powód:** użytkownik dostarczył `power_diagnostics.zip`; należy wyjaśnić
rozbieżność mocy przed strojeniem geometrii i dalszymi raportami.

**Ustalenia:** pasywna kontrola na Windowsie odtwarza pierwszą impedancję,
zysk i stosunek Prad/Pacc do zapisanej precyzji. Wszystkie linie siatki są
identyczne. Strumienie całej anteny wynoszą 0,878490162 i 0,878968878 względem
1 W portu (różnica 0,0545%). Lokalny monitor przy źródle daje 0,840440439;
przecina przewody i nie jest wzorcem mocy. Amplitudy 25 całek U różnią się
do 16,8%, fazy do 10,8°. Port nie ma jednorodnego przekroju napięcia.
Hipoteza błędu pojedynczego U·I jako miary mocy rozłożonego źródła jest
uzasadniona, ale jej ilościowe potwierdzenie wymaga lokalnych iloczynów.

**Zmiana:** osobna konfiguracja source_work i moduł solvers/source_work.py
dodają 450 par pasywnych U/I, po jednej dla każdej krawędzi elektrycznej
obszaru elementu zasilającego. Odczyt kontroluje rzeczywiste indeksy sond
z nagłówków oraz odtworzenie dotychczasowych całek U/I przez sumy lokalne.
Zapisuje podpisane wkłady pracy, ich sumę i różnice wobec strumieni powierzchni.

**Wpływ na fizykę:** geometria, dyskretyzacja, źródło, impuls, PML i kryterium
końca pozostają identyczne. Nie zmieniono normalizacji, impedancji ani zysku.
Praca lokalna oznacza wkład netto do pola, po lokalnym pochłanianiu, nie moc
generatora przed oporem zasilania. Skończony zapis jest nadal ograniczeniem.
Znana wada przejść siatki i walidacja zbieżności pozostają otwarte.

**Formaty i odtwarzalność:** kompatybilne rozszerzenie konfiguracji v2
o source_edge_work, nowy source_work_spectra.npz i pola diagnostycznych JSON.
Paczka ZIP obejmuje nowe surowe sondy i widma. Stare przebiegi i konfiguracje
pozostają bez zmian. Cel projektu 0.6 zapisuje stan tej kontroli.

**Sprawdzenie:** 23 testy przeszły; klasa GUI pominięta z powodu braku Tk.
Nowe przypadki obejmują znaki i czynny wkład dla analitycznego pola, ujemną
pracę, błędne składanie sond, przesunięty kontur oraz dokładnie 450 unikalnych
krawędzi na niezmienionej siatce. Sprawdzono przypięte źródła openEMS dotyczące
obiegów H, indeksów, przyciągania do siatki i rozkładu elementu skupionego.

**Ograniczenia:** pierwszy zestaw monitorów jest potwierdzony natywnym wynikiem
użytkownika; nowy zestaw lokalny nie był jeszcze wykonany w openEMS na Windowsie.
Nie ogłaszamy naprawy ani zamknięcia bilansu. Nie wykonano benchmarków.

## 2026-09-28 — limit plików sond Windows i przerywanie błędnego zapisu

**Powód:** log użytkownika z `20260928T101020Z_78b86cdbac` zawiera 436 błędów
otwierania sond, począwszy od power_edge_i_0253. Wariant wymaga 945 plików,
a pierwszy błąd wypada dokładnie po 507 lokalnych sondach, 2 sondach portu
i 3 standardowych strumieniach, zgodnie z domyślnymi 512 strumieniami UCRT.
Poprzednia implementacja nie uwzględniała tego ograniczenia Windows.

**Zmiana:** dodano przygotowanie limitu w procesie pracownika przed Run.
Adapter liczy sondy w XML, rezerwuje zapas 128 strumieni, podnosi limit
_setmaxstdio do 2048 dla obecnego modelu i sprawdza równoczesne otwarcie
945 strumieni przez natywne fopen. Nie obniża już wyższego limitu, kontroluje
odmowę zwiększenia i zamyka wszystkie otwarte strumienie także przy błędzie.
Nadrzędny proces przerywa pracownika przy pierwszym `Can't open file:`;
nie dopuszcza dalszego FDTD i raportu z niekompletnym zapisem.

**Wpływ na fizykę:** brak zmian geometrii, siatki, źródła, sond, normalizacji
i kryterium końca. To poprawka obsługi plików, nie wyjaśnienie deficytu mocy.
Poprzednie pliki są zachowane, a nowa próba tworzy osobny katalog.

**Formaty i odtwarzalność:** manifest.solver.native_io zapisuje stan limitu
i kontrolę strumieni. Rozszerzenie mieści się w istniejącym schemacie v2.
Wymagania 0.7 obejmują wykrywanie błędów zapisu przed obliczeniem i w jego trakcie.
Nie dodano zależności pip ani zmiany ustawień systemowych; limit jest lokalny
dla procesu ze wspieraną dynamiczną biblioteką UCRT paczki MSVC.

**Sprawdzenie:** zestaw unittest zakończył się sukcesem (31 testów w liczniku,
pominięty test rzeczywistego UCRT oraz klasa Tk). Nowe kontrole obejmują
945 strumieni przy limicie 512, odmowę zwiększenia, sprzątanie po częściowej
odmowie otwarcia, zachowanie wyższego limitu, odczyt XML i zatrzymanie procesu
na rzeczywistym komunikacie z logu. Zwykłe ostrzeżenie o nieużytej kuli
nie przerywa obliczeń. Sprawdzono dokumentację Microsoft i źródła paczki MSVC.

**Ograniczenia:** tutaj nie uruchomiono Windows ani natywnego openEMS.
Preflight UCRT i poprawne zapisanie kompletu sond wymagają potwierdzenia
na komputerze użytkownika. Nie wykonano benchmarków. Bilans PEC pozostaje otwarty.

## 2026-09-28 — lokalna praca zamyka bilans; korekta granic wymuszenia

**Powód:** użytkownik dostarczył kompletny wynik source_work po poprawce UCRT.
Należy rozstrzygnąć deficyt przed strojeniem, bez narzucania sprawności 100%.

**Ustalenia:** zapisano wszystkie 900 lokalnych sond; preflight UCRT 945
strumieni i limit 512 → 2048 działa na Windowsie. Zakończono do EndCriteria
−50 dB. Praca netto 0,879386295 W jest zgodna ze strumieniem zewnętrznym
0,878490162 W do 0,102%, z wewnętrznym 0,878968878 W do 0,0475%. Pojedyncze
U·I portu przyjęte jako 1 W nie mierzy poprawnie tej pracy. Surowe nagłówki,
widma i odtworzenie całek U/I są zgodne; siatka i stare wyniki się nie zmieniły.

**Przyczyna w adapterze:** kotwice siatki zaokrąglano do 1e-12 m, granice
AddLumpedPort pozostawały niezaokrąglone. Skrajne linie y wychodzą poza box
o 0,324 pm. Opór używa SnapBox2Mesh i obejmuje 450 krawędzi; geometryczny
test wymuszenia obejmuje tylko 270. Dokładnie te krawędzie dostarczają
dodatnią pracę +1,434333232 W; pozostałe 180 pochłania −0,554946937 W.
Ich −Re(I/U) odtwarza konduktancję gałęzi RC z operator.cpp do 3,19e-5.
Przypięte źródła openEMS i CSXCAD potwierdzają różne reguły doboru krawędzi.

**Zmiana:** solvers/feed.py uzgadnia port z dokładnymi kotwicami w nowym
trybie mesh_anchors, tylko w tolerancji 1e-12 m. Większa odchyłka jest błędem.
Audyt przed Run zapisuje nominalne/użyte granice, indeksy i pokrycie boxem.
Nowa konfiguracja quados8_1420mhz_aligned_feed.json wymaga 450/450 krawędzi.
Stare konfiguracje bez opcji lub z legacy zachowują dawny model i ostrzegają.

**Wpływ na fizykę:** wymiary anteny, siatka, opór i jego zakończenia, R, impuls,
PML i EndCriteria pozostają takie same. Dyskretne wymuszenie zmienia się
270 → 450 krawędzi i wymaga nowego FDTD. Nie przeskalowano geometrii ani
normalizacji pola. Stary zysk i SWR nie są zatwierdzone; bilans pracy nie
zastępuje zbieżności ani przypadku referencyjnego. M2 nadal otwarte.

**Formaty i odtwarzalność:** opcjonalne solver.port_mesh_alignment rozszerza
konfigurację v2, bez zmiany zachowania dawnych plików. Nowy feed_grid_coverage.json
i manifest.solver.feed dokumentują granice; audyt wchodzi do ZIP. Pakowanie
starych danych bez audytu pozostaje możliwe. Wymagania 0.8 opisują następny
przebieg. Dokładną analizę i identyfikację paczki zapisano w docs/power-audit.md.

**Sprawdzenie:** zestaw unittest zakończył się sukcesem (35 testów w liczniku;
pominięty lokalny test UCRT i klasa Tk). Nowa regresja odtwarza 270/450,
sprawdza 450/450 po wyrównaniu, identyczność modelu/siatki/lokalnych sond,
odrzucenie większego przesunięcia i przekazanie granic do natywnego API
przez adapter z atrapą. Siatkę porównano także z dostarczonym mesh.npz.

**Ograniczenia:** nowego wariantu nie wykonano tutaj ani na komputerze
użytkownika. Audyt przed Run dotyczy geometrii boxa, nie wyniku FDTD.
Skończony rozmiar portu może nadal wymagać kontroli. Wada przejść siatki
i zbieżność pozostają otwarte. Nie wykonano benchmarków.

## 2026-09-28 — potwierdzony aligned_feed i pozostały błąd odniesienia portu

**Powód:** użytkownik dostarczył ukończony power_diagnostics(2).zip po zmianie
granic wymuszenia. Trzeba ocenić poprawkę i uniknąć strojenia na podstawie
niezweryfikowanej impedancji lub samej zmiany liczby zysku.

**Ustalenia:** 900 surowych sond jest kompletnych, indeksy zgodne z planem,
kod odpowiada d0b925d6, siatka identyczna. Osiągnięto EndCriteria −50,04 dB.
Wszystkie 450 krawędzi daje dodatnią pracę; 180 pasywnych krawędzi starego
wariantu zostało usuniętych przez poprawkę. Praca 0,949145539 W i zewnętrzny
strumień 0,948187885 W różnią się o 0,10090% względem pracy. Wewnętrzna
powierzchnia daje 0,948698445 W (różnica 0,04710%).

**Pozostały problem:** pojedynczy pomiar U·I daje nadal 1 W. Różnica wobec
lokalnej pracy to 5,085% tego odniesienia; w przekroju portu amplitudy U
różnią się do 9,897%, fazy do 4,281°. Robocze Z=67,701−j95,621 Ω,
SWR200=3,6975. Zysk +z odniesiony do portu wzrósł 16,94737 → 17,27896 dBi,
ale względem pracy lokalnej oba przebiegi dają około 17,5056 dBi, różniąc się
o 0,000060 dB. Kierunkowość +z także pozostaje około 17,5100 dBi.
To porównanie na jednej siatce i jednej osi, nie walidacja zbieżności.

**Geometria:** dwie kule przy zaciskach zasilania całkowicie mieszczą się
w walcach przeciwległych odcinków A. Każda obejmuje 72 próbki E, wszystkie
już objęte sąsiednim metalem; pozostałe 46 kul ma co najmniej trzy własne
próbki. Wyjaśnia to dwa ostrzeżenia Sphere. Natywnych ID nie ma w paczce;
wniosek opiera się na geometrii i niezależnej analizie próbek, nie pełnym
teście ciągłości operatora. Modelu nie zmieniono w celu wyciszenia komunikatu.

**Zmiana i wpływ na fizykę:** zapisano wynik kontroli w docs/power-audit.md
i małym docs/validation/aligned-feed-20260928.json z identyfikacją paczki.
Zaktualizowano wymagania 0.9, stan projektu i instrukcje. Kod solvera,
parametry, normalizacja i wcześniejsze wyniki pozostały bez zmian.
Nie dodano zależności ani nowego formatu outcomes. Następny eksperyment
ma badać definicję i pomiar bardziej lokalnego portu, przed skalowaniem anteny.
Powtarzanie tego samego wariantu nie wnosi danych potrzebnych do tej diagnozy.

**Sprawdzenie:** niezależna DFT surowych sond odtwarza zapisane widma do
5e-16 względnej normy. Odtworzono całki U/I (4,52e-13 i 1,55e-8) oraz
161 punktów gęstego widma impedancji. Sprawdzono skróty i zgodność 22 plików
Python z kodem użytym przez użytkownika. Nie uruchamiano ponownie FDTD
ani benchmarków; zmiana dokumentacyjna nie wymagała nowych testów solvera.

**Ograniczenia:** nowe pełne pola HDF5 nie są częścią paczki; odczyty
powierzchni pochodzą z jej power_balance.json, nie z ponownego całkowania
HDF5 tutaj. Pomiar portu, referencja i zbieżność pozostają otwarte. Dane
mają nadal status unverified; nie korygowano impedancji mnożnikiem mocy.

## 2026-09-28 — lokalny interaktywny raport HTML

**Powód:** użytkownik chce samodzielnie oglądać i interpretować wyniki,
bez przesyłania kolejnych paczek i zużywania tokenów. Wzorcem jest wcześniej
przygotowany HTML z suwakiem częstotliwości i wyborem odniesienia impedancji.

**Zmiana:** dodano `report <katalog>` i `report --latest --open`, samodzielny
HTML bez sieci, interaktywne R/X, SWR, S11, stratę niedopasowania, minimum,
przejścia X przez zero i eksport CSV. Raport pokazuje zapisane przekroje
kierunkowe, moc portu, lokalną pracę, strumienie, podpisane wkłady krawędzi,
stan wykonania i ostrzeżenia. Pole dalekie i bilans zachowują własne etykiety
częstotliwości. Brak pliku daje informację o braku danych. Dodano opcjonalną
DFT istniejących sond portu oraz instrukcje CMD, wymagania 0.10 i kontrakt
raportów. Nowe `run` tworzą raport również przy włączonej diagnostyce mocy.

**Wpływ na fizykę:** żaden. Nie zmieniono anteny, źródła, siatki, solvera ani
normalizacji, nie uruchamiano FDTD i benchmarków. Raport nie zatwierdza M2,
nie stroi geometrii i nie poprawia impedancji mnożnikiem. Porównanie zysku
względem lokalnej pracy jest jawnie diagnostyczne. Gęsta DFT nie zwiększa
fizycznej rozdzielczości przebiegu. Zref przelicza dopasowanie, nie balun.

**Architektura i odtwarzalność:** odczyt i prezentacja są w `visualization/`;
CSS/JS w module Python trafiają do snapshotu kodu. Bez nowych zależności.
Ręczne raporty zapisują się poza niezmiennymi wynikami, w `outcomes/reports/`
albo nowym pliku wskazanym przez użytkownika. Raport automatyczny jest częścią
końcowego spisu artefaktów. Błąd samego raportu zapisuje ostrzeżenie, bez
unieważnienia ukończonego solve. Nie zmieniono wersji surowych formatów v2.

**Sprawdzenie:** 49 testów unittest, 2 pominięcia dla niedostępnego natywnego
Tk i Windows UCRT. Nowe testy obejmują niezmienność wyników, wybór ukończonej
symulacji, wejścia częściowe i błędne, dwa mianowniki bilansu, znaki pracy,
osobne znaczniki czasu U/I, granice widma, polecenie CLI i błąd raportowania.
Wygenerowano HTML z trzech rzeczywistych zestawów użytkownika: pierwotnego
przebiegu (1001 punktów 1300–1550 MHz), starej kontroli source_work oraz
aligned_feed (161 punktów 1400–1440 MHz). Dla ostatniego raport wyznacza
5,085446% różnicy port/praca i 0,100896% różnicy praca/strumień oraz
450 dodatnich wkładów, zero ujemnych. Obejrzano wygenerowane obrazy widma
i charakterystyki. Logikę JS sprawdzono w lokalnym środowisku Node z atrapą
DOM: suwak, Zref, kliknięcie wykresu, przycisk celu, CSV, jeden punkt,
idealne dopasowanie oraz ujemna rezystancja.

**Ograniczenia:** nie uruchomiono natywnej przeglądarki Windows ani openEMS.
Kontrola JS nie jest testem renderowania w przeglądarce. Raport czyta gotowy
bilans powierzchni, nie powtarza całkowania HDF5. Nie ma map E/H ani animacji.
Progi zbieżności i definicja pomiaru portu nadal wymagają osobnej pracy.
Wcześniejsze symulacje nie wymagają ponownego przeliczenia do użycia raportu.

## 2026-09-28 — wczytywanie parametrów w edytorze

**Powód i zakres:** użytkownik poprosił wyłącznie o otwieranie zapisanych
parametrów z widoku anteny. Dodano przycisk „Wczytaj parametry…” obok zapisu.
Poprawny JSON aktualizuje pola, podgląd i ścieżkę; staje się też bazą przycisku
„Przywróć początkowe”. Anulowanie lub błąd pliku zachowuje bieżącą edycję.
Wczytywana jest cała konfiguracja, wraz z ustawieniami solvera.

**Wpływ:** bez zmian solvera, siatki, formatów i danych wynikowych. Samo
otwarcie pliku nie uruchamia obliczeń. Zaktualizowano opis przycisków.

**Sprawdzenie:** kontrola odczytu poprawnego JSON, synchronizacji pól,
zachowania ustawień solvera i bazy przywracania oraz anulowania i błędnego
JSON przy niezastosowanych wpisach. Dwa dotychczasowe testy stanu edytora
przechodzą; klasa testów natywnego Tk pominięta z powodu braku biblioteki.
Kontrolę obsługi przycisku wykonano bez natywnego okna; Windows GUI nie
uruchamiano w tym środowisku.

## 2026-09-29 — wyniki i raporty wybierane po geometrii

**Powód:** katalogi nazwane wyłącznie datą i losowym ID utrudniały wybór
wcześniejszych iteracji. Użytkownik wymaga obsługi nazw swoich wariantów.

**Zmiana:** nowe przebiegi mają nazwę `wariant__czasUTC_id`, wyprowadzoną
z nazwy pliku `--config` lub pliku wczytanego/zapisanego w edytorze.
`report quados8_variant_sz4.json` szuka pliku także w `parameters/` i dobiera
ukończony przebieg według rzeczywistej geometrii, modelu fizycznego
i częstotliwości. Działa na starych zapisanych konfiguracjach; nie wymaga
zmiany nazw historycznych folderów. Nazwa wariantu trafia też do nowego HTML.
Przy wielu wynikach preferuje najnowszy o identycznych ustawieniach symulacji
i solvera. Fallback na zgodną geometrię z innymi ustawieniami jest jawny.
Brak zgodnej geometrii nie uruchamia obliczeń i nie wybiera innej anteny.

**Wpływ na fizykę:** bez zmian geometrii, siatki, portu i solvera, bez FDTD
i benchmarków. Wyszukiwanie ignoruje odziedziczone `id`, opisy i ścieżki
schematów; parametry liczbowe porównuje po kanonizacji do 12 miejsc po
przecinku (długości SI: 1 pm). Stan fizycznej walidacji nie zmienia się.

**Format i odtwarzalność:** manifest v2 rozszerzono o opcjonalne
`variant_name` oraz `geometry_sha256`. Odczyt starszych manifestów pozostaje
zgodny. Czas i losowy sufiks zapobiegają nadpisaniu kolejnej iteracji;
dotychczasowych plików wynikowych i manifestów nie modyfikujemy.
Wymagania podniesiono do 0.11, zaktualizowano instrukcje i kontrakt outcomes.

**Sprawdzenie:** 55 testów unittest; dwa pominięcia środowiskowe dla Tk
i Windows UCRT. Nowe przypadki sprawdzają stare katalogi, wspólne `id`
różnych geometrii, brak zmian w plikach podczas wyszukiwania, rozróżnienie
częstotliwości i reflektora, preferencję ustawień solvera, unikalne nazwy
i manifesty oraz CLI z nazwą JSON bez prefiksu `parameters/` i etykietę HTML.
Natywnego FDTD ani interfejsu Windows nie uruchamiano.

## 2026-09-29 — drugi model: klasyczny biquad

**Powód:** użytkownik chce symulować biquad w istniejącym środowisku.

**Zmiana:** osobny generator, schemat i konfiguracja `biquad_1420mhz.json`.
Parametry obejmują bok S, szczelinę G, wysokość H, średnicę drutu i reflektor.
Edytor przełącza formularz po wczytaniu modelu; nazwy okna, eksportu i wariantu
odpowiadają antenie. Wspólne polecenia check/run/report obsługują nowy model.

**Wpływ na fizykę:** dwie gałęzie po cztery równe odcinki, wspólny port
różnicowy, opcjonalna płyta PEC. Skończona szczelina nieznacznie odkształca
kąty rombów. Startowe S = ćwierć fali, H = ósma część fali, Zref = 50 Ω
nie oznaczają dostrojenia. Wykorzystano istniejące mesh_anchors i diagnostykę
pracy źródła. Nie zmieniono solvera ani modelu Quadosa. Brak kabla, baluna
i strat; walidacja portu, impedancji i zysku pozostaje otwarta.

**Format i odtwarzalność:** dodatkowy model i schemat parametrów;
konfiguracje/manifesty pozostają v2. Bez migracji i zmian wcześniejszych
wyników. Rdzeń pozostaje niezależny od anteny. Wymagania mają wersję 0.12.

**Sprawdzenie:** 60 testów unittest, wynik OK; dwa pominięcia środowiskowe
(Tk i Windows UCRT). Kontrole nowego modelu obejmują topologię, długości,
symetrię, szczelinę, odrzucanie błędnych wymiarów, skalowanie, reflektor,
siatkę, pokrycie portu sondami i parametry edytora. Konfiguracja startowa
przechodzi check bez ostrzeżeń: 266 × 268 × 83 = 5 916 904 komórki.
Obejrzano eksport geometrii. Natywnego GUI Windows i FDTD nie uruchamiano;
nie wykonano benchmarków. Wyniki EM biquada muszą powstać w nowym przebiegu.

## 2026-09-29 — przekroje E/H i diagramy fazowe obu anten

**Powód:** użytkownik chce diagram podobny do pokazanego wzoru: dwie kolumny
E/H, kolejne fazy co 30° lub 15°, z geometrią anteny w tle.

**Zmiana:** --fields dodaje przekroje xy_front, xz i yz dla biquada oraz
Quadosa. Adapter zapisuje zespolone FD dumpy 10/11 i NPZ ze wszystkimi
składowymi. Raport tworzy arkusze fazowe, pliki PNG i odnośniki pobrania.
--phase-step oraz --field-components odtwarzają diagram z zapisanych pól,
bez FDTD. --front-offset-mm ustala położenie przed promiennikiem; zapisane
są współrzędne żądane i przyciągnięte do istniejącej siatki.

**Wpływ fizyczny:** pasywne zapisy 2D nie zmieniają geometrii, źródła ani
siatki. Dodatkowy koszt stanowi gromadzenie DFT i zapis danych. Wspólna
normalizacja E/H pochodzi z port_spectra, bez korekty bilansu. Konwencja
Re(F·exp(+j·faza)) zachowuje referencję napięcia; native dual time H jest
uwzględnione przez openEMS. Skala danej kolumny jest stała między fazami.
Metal, halo jednej lokalnej przekątnej komórki i źródło są maskowane NaN.
Maska jest geometryczna, nie jest mapą natywnych voxeli. Nie pokazujemy
wyinterpolowanej mapy jako dokładnego pola na powierzchni przewodnika.

**Format i odtwarzalność:** opcjonalne field_front_offset_m w konfiguracji
v2, field_layout.json, fields/metadata.json (kontrakt pól v1), NPZ i surowe
HDF5. Stare przebiegi pozostają niezmienne; bez zapisanych pól raport
pokazuje brak danych i potrzebę nowego run. Wymagania: 0.13; szczegóły:
docs/fields.md. Nie dodano zależności ani animacji pełnego okresu.

**Sprawdzenie:** 66 testów unittest, OK; dwa pominięcia Tk/Windows UCRT.
Nowe kontrole: obie anteny i istniejące węzły siatki, parametry natywnego
API, faza i normalizacja fali płaskiej, maska, błędne położenie, format
HDF5 i wspólna siatka E/H, zapis NPZ, CLI, wspólna skala kolorów oraz
niezmienność danych podczas raportowania offline. Obejrzano diagramy
testowe oznaczone jako syntetyczne; nie są wynikiem symulacji anteny.
API sprawdzono w przypiętych źródłach wydania 0.37.0rc3.

**Ograniczenia:** nie wykonano natywnego FDTD ani benchmarków. Kontrola
na Windowsie, źródła i zbieżności E/H pozostaje otwarta, status unverified.
Nierozwiązana rozbieżność U/I i pracy lokalnej nadal dotyczy amplitud.
Prądy promiennika i pełna animacja pozostają nieobsługiwane.

## 2026-09-29 — czytelny błąd wymiarów w edytorze biquada

**Powód:** na zrzucie użytkownika model nie aktualizował się po edycji.
G=2 mm i drut 2 mm oznaczały zerowy prześwit portu. Walidacja prawidłowo
odrzucała cały formularz, ale komunikat pod wykresem był łatwy do przeoczenia.

**Zmiana:** opisano G jako rozstaw osi zacisków, H jako wysokość osi drutu.
Błąd podaje G, średnicę, prześwit i wymaganą nierówność. Wyświetla się także
przy Zastosuj z informacją, że podgląd nadal pokazuje poprzedni model.
Po udanym zatwierdzeniu komunikat wraca do instrukcji edycji.

**Wpływ:** bez zmian geometrii, definicji G, walidacji styku, solvera,
formatów i dawnych wyników. Nie dopuszczamy zwartego portu i nie poprawiamy
wpisów automatycznie. Poprawny zestaw nadal zatwierdza się przez Enter/Zastosuj.

**Sprawdzenie:** odtworzono wszystkie wymiary i częstotliwość ze zrzutu:
odrzucenie zachowuje poprzedni model; po G=4 mm zmieniają się geometria
i współrzędne wykresu (bok 300 mm, wysokość 15 mm, 2450 MHz).
Przeszło 6 testów biquada i 2 testy stanu edytora. Testy natywnego Tk są
pominięte w tym środowisku; dodano przypadek błędu i powrotu po poprawce.
Bez FDTD i benchmarków.


## 2026-10-06 — PCB-009A: syntetyczny kontrolny FDTD

Dodano osobną komendę `python -m antenna_lab.pcb.control` z opcją `--output`.
Wspólny przypadek kontrolny i test natywnego XML używają tej samej geometrii
20 × 20 mm, dwóch padów i jednorazowej normalizacji. Kontrakty siatki,
portu, materiału, pobudzenia i PML pozostają bez zmian.

Przygotowany model przechodzi audyt zamrożonej siatki, Run z zachowaniem
plików natywnych i przywróceniem cwd, a potem CalcPort dla trzech zadanych
częstotliwości. Z, S11 i SWR są ilorazami widm, bez normalizacji mocy.
Niepoprawne widma i |S11| ≥ 1 przerywają obliczenia. Wynik jest unverified.
Zapis: impedance.csv i ścisły summary.json z metadanymi przygotowania oraz
ustawieniami; zerowe odbicie ma s11_db=null (puste pole CSV). Nowe katalogi
UTC są unikalne, jawny katalog musi być pusty. Bez pól, NF2FF i Gerbera.

Sprawdzenie: 10 nowych testów kontrolnych, 132 testy PCB (1 pominięty),
pełny zestaw 199 testów (3 pominięte), bez błędów. Natywny smoke XML
pominięty z powodu braku openEMS; użytkownik wcześniej potwierdził XML
na Windowsie. Rzeczywisty kontrolny FDTD i zbieżność pozostają do wykonania
lokalnie; testy tej zmiany używały atrap, bez natywnego Run.


## 2026-10-06 — PCB-009A1: parametry częstotliwości kontrolnej PCB

Dodano jawne parametry Hz w API przypadku kontrolnego i runnera oraz opcje
CLI --center-mhz, --cutoff-mhz, --frequencies-mhz i --loss-reference-mhz.
Domyślny eksperyment pozostaje identyczny. Brak jawnego odniesienia strat
oznacza wybrany środek pobudzenia. Geometria nie jest skalowana ani zmieniana.

Konstruowane ustawienia przechodzą istniejący schemat i walidator JSON
przez mały adapter w simulation.py: jedna polityka dodatniości, skończoności,
kolejności i okna ±0,8 cutoff. Błąd zatrzymuje ścieżkę przed natywnym API.
Pobudzenie, CalcPort, siatka, odstęp do PML i kappa korzystają z ustawień
istniejącą ścieżką. CSV i summary.json zachowują wybraną listę oraz ustawienia.
Bez zmian wzorów Z/S11/SWR, schematu, portu, meshera i statusu unverified.

Przykłady CMD (po aktualizacji repozytorium):
```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.control
.\.venv\Scripts\python.exe -m antenna_lab.pcb.control --center-mhz 2450 --cutoff-mhz 400 --frequencies-mhz 2200 2400 2450 2500 2700
.\.venv\Scripts\python.exe -m antenna_lab.pcb.control --center-mhz 900 --cutoff-mhz 150 --frequencies-mhz 800 900 1000
.\.venv\Scripts\python.exe -m antenna_lab.pcb.control --center-mhz 2450 --cutoff-mhz 400 --loss-reference-mhz 2400 --frequencies-mhz 2200 2450 2700
```

Sprawdzenie: control 15, simulation 12, adapter 15, mesh 34 — OK;
138 testów PCB (1 pominięty), pełny zestaw 205 (3 pominięte), bez błędów.
Testy obejmują domyślne i zmienione pasma, niezmienność geometrii, błędne
wartości, jedno- i pięciopunktowe widma, rzeczywisty pipeline z atrapami
natywnego API oraz zapis ustawień i strat materiału. W ścieżkach solvera,
meshera i portu brak wymogu 1,42 GHz. Natywny XML pominięto z braku openEMS.
Użytkownik potwierdził wcześniejszy pierwszy FDTD na Windowsie; tej zmiany
nie uruchamiano natywnie. Badanie zbieżności pozostaje odrębnym etapem.


## 2026-10-06 — PCB-009B: macierz zbieżności syntetycznej PCB

Dodano sekwencyjną komendę `python -m antenna_lab.pcb.convergence`: osiem
jawnie nazwanych wariantów, od baseline przez pojedyncze zmiany do
reference_fine. Wspólna funkcja run_control_model obsługuje również stary
control; opcje pasma i walidacja są współdzielone. Każdy wariant zachowuje
tę samą geometrię i osobne native/model.xml, dane natywne, CSV i summary.
Domyślne wartości i kontrakty fizyczne pozostają bez zmian.

convergence.json i convergence.csv porównują R, X i zespolone Z względem
baseline oraz refined numerical reference. Względne różnice to ułamki,
z progami mianowników 1 ohm dla R/X i Zref dla modułu Z. Pojemność zastępcza
jest tylko diagnostyką dla X<0. Raport obejmuje ustawienia i rozmiary siatki,
jej min/max krok oraz najgorszy stosunek sąsiednich kroków. Identyfikator
geometrii SHA256 i jej pełna znormalizowana kopia umożliwiają kontrolę
niezmienności. Status powodzenia: diagnostic_pending_review, nigdy validated.

Nowe/niepuste katalogi są chronione przed nadpisaniem; domyślne katalogi UTC
są unikalne. Błąd lub KeyboardInterrupt zapisuje failed, zachowuje wcześniejsze
wyniki i nie uruchamia kolejnych wariantów. Brak wznowienia w v0.
Zakończenie Run nie dowodzi osiągnięcia EndCriteria przed limitem kroków.

Sprawdzenie: convergence 5, control 15, simulation 12, adapter 15, mesh 34
— OK; 143 testy PCB (1 pominięty), pełny zestaw 210 (3 pominięte), bez błędów.
Testy używają atrap i znanych widm; rzeczywisty mesher sprawdzono dla ośmiu
wariantów w pasmach 0,9/1,42/2,45 GHz. Natywnego FDTD nie uruchamiano.
Smoke XML pominięty z braku openEMS. Użytkownik wcześniej potwierdził
pojedyncze natywne przebiegi w tych trzech pasmach; macierz pozostaje
do ręcznego uruchomienia i oceny. Bez Gerbera, pól, NF2FF i diagnostyki mocy.

Pierwsza lokalna próba: `python -m antenna_lab.pcb.convergence`
z projektowej .venv i ustawionym CSXCAD_INSTALL_PATH. Opcjonalnie te same
--center-mhz/--cutoff-mhz/--frequencies-mhz/--loss-reference-mhz co control.
Nie uruchamiać automatycznie kilku macierzy ani wariantów równolegle.


## 2026-10-06 — PCB-009C: zrównoważona drabina przestrzenna PCB

Wyniki PCB-009B przekazane przez użytkownika wskazały dominującą wrażliwość
na port (~8,03% zespolonego Z) i podział Z laminatu (~4,71%) przy 1,42 GHz.
Wpływ domeny/PML/czasu był dużo mniejszy. Nie uznano rozwiązania za zbieżne.

Dodano osobną komendę `python -m antenna_lab.pcb.spatial_convergence`.
L0/L1/L2/L3 równocześnie zmieniają cells_per_wavelength 20/30/40/50,
podział szczeliny i szerokości portu 2/4/6/8 oraz laminatu Z 4/8/12/16.
Powietrze 0,25 długości fali, PML 8, EndCriteria 1e-5, limit 100000 kroków
i grading 1,4/1,5 pozostają stałe. Geometria i model materiału nie zmieniają się.
Pasmo i walidacja są współdzielone z control. PCB-009B pozostaje bez zmian.

Przed każdym solverem powstaje siatka preflight z istniejącym max_cells;
jej rozmiary, kroki i grading są drukowane i zapisywane. Istniejący runner
odtwarza ją deterministycznie; metadane muszą się zgadzać. Błąd limitu
zatrzymuje poziom przed natywnym API i zachowuje wcześniejsze wyniki.
Katalogi poziomów są niezależne; brak wznowienia i dodatkowych poziomów.

spatial_convergence.json/CSV zawierają Z, S11, SWR, pojemność diagnostyczną,
porównania kolejnych poziomów i względem L3, metadane siatki oraz trend |delta Z|.
Progi inżynierskie dla L3–L2: względne Z/X ≤1% i R ≤5% na każdej częstotliwości.
Status diagnostic_candidate_converged lub diagnostic_not_converged nie oznacza
walidacji fizycznej. R/X używają progu mianownika 1 ohm, Z — Zref. Porównanie
pojemności wymaga obu X<0; jawny próg mianownika 1e-18 F dotyczy wyłącznie
tej diagnostyki i nie wpływa na bramkę inżynierską. Trend nie jest wymuszany.

Sprawdzenie: 8 nowych testów z atrapami, dotychczasowe control/convergence
i adapter bez błędów; 151 testów PCB (1 pominięty), pełny zestaw 218
(3 pominięte), OK. Sprawdzono granice progów, matematykę porównań, trzy pasma,
kolejność preflight/solve, brak mutacji i zachowanie wyników po błędzie
L2/L3 lub przerwaniu. Natywnego FDTD nie uruchamiano; XML smoke pominięty
z braku openEMS. Drabina wymaga lokalnego wykonania na Windowsie.
Bez Gerbera, korekcji 1/3–2/3, pól, NF2FF i diagnostyki mocy.

## 2026-10-06 — PCB-009D: eksperyment krawędzi portu

Dodano jawny tryb thirds dla dwóch prostokątnych padów syntetycznych; aligned
pozostaje domyślny. Geometria miedzi, fizyczny port i Z=0 są zachowane.
Audyt odrzuca konflikty kotwic oraz podział komórki krawędziowej przez grading.
Runner porównuje aligned/thirds na istniejących L2/L3; wymaga statystyk natywnych
i zakończenia przed limitem kroków. Zapisuje ścisły JSON/CSV także po błędzie.
Dokumentacja: docs/pcb-port-edge-experiment.md.

Sprawdzenie: 11 nowych testów, cały zestaw 229 testów OK (3 pominięte).
Siatki aligned L2/L3 porównano dokładnie z kodem sprzed zmiany: identyczne.
Brak rzeczywistego FDTD w środowisku agenta; A/B wymaga lokalnego Windows.
Wynik jest diagnostyczny, nie stanowi walidacji fizycznej ani zmiany domyślnej.

## 2026-10-06 — PCB-009E: dekompozycja wrażliwości wokół thirds L2

Użytkownik przekazał wyniki natywnego PCB-009D: zmiany Z dla thirds L2–L3
wyniosły 1,89965/1,91197/1,90776% przy 1,30/1,42/1,50 GHz; aligned około
2,33–2,36%. Wszystkie cztery przebiegi zakończyły się przed limitem 100000
kroków z exact_endcriteria i dump_statistics. Poprawa nie zalicza progu 1%.

Dodano osobną komendę pcb.refined_sensitivity: pięć sekwencyjnych wariantów
thirds_L2_reference, thirds_wave50, thirds_port8, thirds_substrate16 oraz
thirds_L3_combined. Jedna geometria, wspólne pasmo i model portu 50 ohm;
zmieniają się tylko zadane minima dyskretyzacji. Solver, domyślny aligned
i istniejące komendy pozostają bez zmian. Kontrola preflight zapisuje
siatkę, port oraz wskazówki thirds; przed porównaniem wymaga prawidłowych
statystyk natywnych i zakończenia poniżej limitu. Błąd zachowuje pliki
oraz wcześniejsze poprawne wyniki.

Ścisły JSON/CSV zapisuje przyrosty zespolone względem własnego L2,
sumę wkładów, resztę interakcji, udziały modułów i diagnostyczną klasyfikację.
Udziałów nie normalizuje się do 100%. Pojemność pozostaje pomocnicza dla X<0.
Liczba krawędzi Ex nie jest interpretowana jako zmiana rezystancji źródła;
uwzględniono wskazane przez użytkownika skalowanie natywnego elementu RLC.
Dokumentacja: docs/pcb-refined-sensitivity.md.

Sprawdzenie: 10 nowych testów na atrapach natywnych z rzeczywistym kodem
siatki/portu i zapisu wyników; pasmo domyślne i 2,45 GHz. Sprawdzono
arytmetykę wektorową, granice klasyfikacji, bezpieczne mianowniki, brak
mutacji, limity, niepoprawne statystyki, formaty i zachowanie wyników po błędzie.
172 testy PCB OK (1 pominięty), cały zestaw 239 OK (3 pominięte).
Nowych natywnych symulacji nie uruchamiano. Wynik badania wymaga lokalnego
Windows; status diagnostic_pending_review nie jest walidacją fizyczną.
Bez Gerbera, pól, NF2FF, diagnostyki mocy i przeprojektowania portu.


## 2026-10-06 — PCB-010A: rzeczywiste Gerbery EasyEDA

Dodano gerbonara==1.6.3 i shapely>=2.1,<2.2 oraz importer dodatnich regionów,
flashy i kołowych linii/łuków. Gerbonara parsuje RS-274X, Shapely łączy miedź;
wynik zawiera po jednym poligonie na rozłączny przewodnik. GKO określa
środek linii obrysu, więc pisak nie powiększa płytki. Konwersja do SI jest
na granicy importu, normalizacja portu wykonywana raz. Otwory, polaryzacja
clear, kontakt wyłącznie punktowy i niejednoznaczne obrysy są odrzucane.

Komenda pcb.gerber_control używa zwykłej polityki control i istniejącego
adaptera FDTD/CalcPort; --prepare-only kończy się na XML. Wydzielono wspólny
konstruktor ustawień bez zmiany wartości ani zachowania dotychczasowych
komend. Źródłowa/znormalizowana geometria, transformacja, skróty Gerberów,
wersje bibliotek i założenia trafiają do wyników. Miedź PEC zerowej grubości,
bez maski/pasty/sitodruku, B.Cu i vias; laminat z konfiguracji. Status unverified.
Nie dodano sweepów, pól, NF2FF ani nowej fizyki.

Zbadano GTL/GKO dodane wcześniej przez użytkownika w commicie b9bc0c6
(potomek wskazanego 21feddd). PCB-010A nie dodaje ani nie zmienia tych plików.
Rzeczywisty GTL oprócz regionów zawiera obrysy pisakiem 0,2032 mm. Prawa
krawędź szczeliny leży na X=12,86700 mm, a podany koniec X=12,92312 mm
jest wewnątrz miedzi. Audyt portu poprawnie odrzuca pierwotny port.
parameters/pcb_easyeda_requested.json zachowuje pierwotne dane; osobny
pcb_easyeda_stroked_feed.json jawnie zmienia tylko dodatni koniec na
12,86700 mm. Szczelina ma wtedy 0,64412 mm, szerokość nadal 0,86401 mm.
Nie usunięto linii miedzi ani nie zmieniono sformułowania portu. Parametry
laminatu 1,6 mm / 4,3 / 0,018 są jawnymi wartościami startowymi do potwierdzenia.

Sprawdzenie: rzeczywiste pliki dają płytkę 25x25 mm i dwie wyspy; import,
normalizacja i audyt ekonomicznej siatki/portu przechodzą dla jawnego wariantu.
11 testów na autorskich minimalnych Gerberach i atrapach natywnych obejmuje
łączenie regionów/padów, linie/łuki, jednostki, szczelinę 0,70024 mm reprezentatywnego
wzorca bez obrysowego pisaka, odrzucenie konfliktu pisaka i przygotowanie XML
bez Run. Wszystkie 183 testy PCB OK (1 pominięty), cały zestaw 250 OK
(3 pominięte). Wersje testowane: Gerbonara 1.6.3, Shapely 2.1.2.
Natywne FDTD wymaga Windows. Instrukcje i ograniczenia: docs/pcb-gerber.md.


## 2026-10-06 — PCB-010B: ekonomiczne profile jakości Gerber

Dodano --quality preview/design/verify (domyślnie design) wyłącznie do
gerber_control. Jawne profile ustawiają minima siatki, padding/PML i budżet
czasowy według PCB-010B; wszystkie używają dump_statistics, tylko verify
włącza exact_endcriteria. Nie zmieniono syntetycznych komend diagnostycznych
ani fizycznych poligonów, portu, laminatu lub częstotliwości wyników.

Polityka gerber_economical_v1 zachowuje dokładnie krytyczne kotwice płytki,
granic materiałów, portu i Z=0. Pomija środki bounding box miedzi w preview/design.
Pozostałe niekrytyczne kotwice są deterministycznie odrzucane poniżej połowy
mniejszej lokalnej rozdzielczości dwóch kotwic; verify używa tej samej ochrony.
Metadane raportują każdą pominiętą kotwicę i przyczynę. Wspólne API siatki,
portu i adaptera otrzymują opcjonalną politykę; brak opcji zachowuje stare
zachowanie. Rzadsza siatka ujawniła ryzyko przeoczenia fragmentu PEC w błędnym
porcie: dodatkowy Gerber-only audyt fizycznych poligonów z istniejącą tolerancją
geometrii nadal odrzuca pierwotną kolidującą konfigurację, bez zmiany źródła.

Preflight liczy min_dx/dy/dz, CFL, czas impulsu 9/(pi*cutoff), dolną granicę
liczby kroków i aktualizacji komórek. Nie jest prognozą czasu działania.
Jeśli samo wymuszenie osiągnęłoby limit, natywne API nie jest ładowane.
Statystyki natywne muszą potwierdzić iterations < max_timesteps; dojście
do limitu zapisuje failed / max_timesteps_reached i blokuje CalcPort.
summary zawiera profil, politykę/kotwice, koszty, actual_iterations i termination_status.
Przy prepare-only actual_iterations=null i termination_status=not_run.

Sprawdzenie: 7 nowych testów plus zaktualizowane oczekiwania domyślnego
Gerber control; 190 testów PCB OK (1 pominięty), całość 257 OK (3 pominięte).
Pokryto profile, koszt CFL/impulsu, krytyczne współrzędne, stagger 25 um,
niezmienność miedzi CSXCAD/materiału/portu między profilami, blokadę przed
natywnym API oraz limit kroków bez odczytu impedancji. Wszystkie Run to atrapy.
Na rzeczywistej geometrii sprawdzono wyłącznie siatkę: preview 76440,
design 131760, verify 620490 komórek. Nie uruchamiano natywnego FDTD.
Dokumentacja zasad i ograniczeń: docs/pcb-gerber.md. Wyniki nadal unverified.

## Wzór kolejnego wpisu

- Data i krótka nazwa zmiany.
- Powód oraz powiązany cel lub problem.
- Co rzeczywiście zmieniono.
- Wpływ na fizykę i dotychczasowe wyniki.
- Wpływ na architekturę, formaty i odtwarzalność.
- Wykonane sprawdzenia i ich rezultat.
- Ograniczenia, migracje lub konieczność ponownego przeliczenia wyników.

## 2026-10-06 — PCB-010C: gęsty sweep Gerberów

Dodano opcjonalną regularną siatkę częstotliwości do gerber_control; jeden Run
oraz jeden CalcPort obsługują wszystkie próbki. Niepodzielny przez krok koniec
zakresu nie jest dopisywany. summary.json zawiera metadane sweepu, minima
próbkowane i sąsiednie przedziały przejścia X przez zero, bez interpolacji.
Usunięto mylące określenie wyniku Gerber jako syntetycznego. impedance.csv
pozostaje jedyną tabelą widma. Bez zmian geometrii, siatki, portu i profili.
Liczba próbek nie zmienia siatki przy niezmienionym zakresie częstotliwości;
padding nadal zależy od minimum częstotliwości. Wyniki nie uzyskują nowej
kwalifikacji walidacyjnej. Testy fake: Gerber 23, pełny zestaw 262 OK
(3 pominięte); bez natywnego FDTD i bez modyfikacji historycznych wyników.

## 2026-10-07 — PCB-010D: katalog Gerberów i lokalny raport PCB

Wejściem gerber_control jest teraz katalog. Gerbonara/metadane i konwencje
nazw identyfikują warstwy; role, SHA256 i pominięcia trafiają do import/summary.
Nieobsługiwana dolna/wewnętrzna miedź, wiercenia i nieustalone Gerbery blokują
przebieg. Nowy opcjonalny pcb-physical.schema.json i przykład FR4 opisują
wyłącznie fizykę; bez konfiguracji używane są jawne założenia unverified.
Starszy JSON z plikami pozostaje obsługiwany.

Auto feed wymaga dwóch zgodnych prostokątnych flashów. Szczelinę wyznacza
przecięcie pełnej sumy miedzi z osią między padami, nie same apertury.
Pełne powierzchnie styku i prostokątna szczelina mają kontrolę geometryczną
przed normalizacją, a następnie niezmieniony audyt siatki. Usunięto wyłącznie
uniwersalny zakaz portu na jednym CopperPolygon; pętla może łączyć oba końce
poza szczeliną. Nie zmieniono geometrii importera, solvera ani profili.

Istniejące report.py/report_data.py i wspólne CSS/JS obsługują zapisane PCB:
geometria, R/X, S11, SWR, minima i przedziały X=0, metadane i ograniczenia.
Automatyczny report.html/plots powstaje po sukcesie; awaria prezentacji
nie odbiera statusu completed. Ręczne report --open działa bez Gerberów
i natywnych bibliotek, zapisując nowy HTML poza ukończonym przebiegiem.
Nie dodano pól, NF2FF ani nowego frameworka HTML. Wyniki nadal unverified.

Sprawdzenia: import obu rzeczywistych katalogów bez FDTD — emstest gap
0,64412 mm, emstest2 gap 0,70024 mm i szerokość 0,86401 mm; drugi ma jeden
przewodnik. Kontrola normalizacji i portu/siatki zaliczona. Testy PCB: 206 OK
(1 skip), raporty: 17 OK; pełny zestaw: 273 OK (3 skip). Native Run w testach
wyłącznie atrapą; istniejące testy raportu antenowego bez zmian. Sprawdzono
wizualnie rysunek pętli z realnej geometrii; widmo kontrolne pochodziło z atrapy.
Ograniczenia: auto tylko poziome/pionowe zgodne prostokątne pady; pozostałe
układy wymagają jawnego portu. Natywne wykonanie pozostaje lokalnie na Windows.

## 2026-10-07 — PCB-010E: pola PCB i odtwarzanie okresu RF

Dodano --fields-mhz (1–3 unikalne częstotliwości w paśmie wymuszenia).
Pasywne FD E/H korzystają z istniejącego wspólnego instalatora dumpów
i czytnika HDF5. PCB adapter wybiera xy_air (pierwsze dodatnie Z), xz_feed
i yz_feed (środek portu), wyłącznie na istniejących liniach poza PML.
Wspólny limit 4 mln punktów × częstotliwości i koszt DFT są jawne przed Run.
Siatka, geometria, port, wymuszenie, PML i profile nie zostały zmienione.

Jedno Run oraz jedno CalcPort dla sumy częstotliwości impedancji/pól.
Impedance.csv zachowuje tylko sweep. Pamiętane uf_tot normalizuje E/H
do 1∠0 V portu, nie do mocy przyjętej. Zero/nieskończone odniesienia
i niezgodne natywne siatki są błędem. Pełne zespolone komponenty XYZ
trafiają do fields/*.npz, a fazory/czynniki, jednostki i konwencja do
metadata.json. Maski miedzi z=0, źródła i halo jednej lokalnej przekątnej
komórki są konserwatywne, nie opisują natywnej zajętości Yee. Laminat nie
jest maskowany; surowe HDF5 pozostają nietknięte, NPZ używa NaN dla maski.

Raport współdzieli loader, konwencję fazy i generator HTML/PNG z antenami.
PCB adapter rysuje chwilowe wektory E oraz podpisane Hz/Hy/Hx, interfejsy
laminatu, miedź i port. Suwak/Play/Pause pokazuje 0–330° i czas w ns;
stałe symetryczne skale zależą od pełnej obwiedni fazora, nie klatki.
Rozrzedzenie dotyczy tylko wyświetlania (mapy do 80×80 i rzadsze strzałki).
PNG zawiera 0/90/180/270°. Ręczna regeneracja z NPZ działa offline bez
openEMS/Gerberów. Dotychczasowe raporty bez pól i raporty antenowe zachowane.

Testy: 13 field tests, 213 PCB OK (1 skip), pełny zestaw 280 OK (3 skip).
Atrapy potwierdzają jeden Run/CalcPort, niezależne częstotliwości, dokładną
siatkę, format HDF5/NPZ, maski i normowanie, raw SHA256, fazy i raport.
JS wykonano z atrapą canvas/DOM: suwak, Play/Pause, 330→0 i czas przy 2 GHz.
Obejrzano kontaktowy PNG na rzeczywistej geometrii emstest2 z syntetycznymi
polami testowymi. Nie uruchomiono natywnego FDTD; zapis realnych dumpów
openEMS 0.37.0rc3 pozostaje do sprawdzenia lokalnie na Windows. Wyniki
nadal unverified. Nie dodano NF2FF, prądów, bilansu ani nowej fizyki.

## 2026-10-07 — PCB-011A: conducting-sheet PCB copper

Dodano opcjonalny model `conducting_sheet` do fizycznej konfiguracji folderu
Gerberów. PEC pozostaje domyślny i zgodny ze starszymi przebiegami. Parametry
35 µm / 58 MS/m przykładu pcb_fr4_1p6_realistic.json są założeniami, podobnie
jak FR4 1,6 mm / epsilon_r 4,3 / tan(delta) 0,018; brak danych producenta.

CSXCAD otrzymuje AddConductingSheet z przewodnością i grubością w SI zamiast
AddMetal. Poligony nadal mają zerową grubość geometryczną przy z=0. Parametry
materiału przechodzą wyłącznie do instalatora, nie do meshera. Test porównuje
dokładnie domeny, osie i poligony PEC/sheet w preview/design/verify: identyczne,
bez dodatkowych linii Z. Fizyczne straty miedzi mogą zmienić impedancję, pola
i zanik energii; sama identyczność siatki nie zatwierdza wyników ani czasu run.

Summary i metadane przygotowania zapisują model, grubość, przewodność,
przewodność powierzchniową (2030 S dla przykładu), użycie parametrów przez
solver oraz brak grubości geometrycznej. Raport odróżnia PEC od sheet.
Maska i opisy PCB E/H dotyczą płaskiej miedzi, nie zakładają już PEC;
normalizacja, fazy i położenia przekrojów są niezmienione. Stare raporty PEC
pozostają odtwarzalne. Bez nowych zależności, przebiegów porównawczych,
soldermask, przelotek, dolnej miedzi lub szorstkości.

Testy: 217 PCB OK (1 skip), pełny zestaw 284 OK (3 skip). Nowe testy z atrapami
sprawdzają wywołania materiałów, identyczne siatki, walidację, metadane XML,
prepare-only, pojedynczy Run/CalcPort z E/H i regenerację raportu offline.
Nie uruchomiono natywnego FDTD; weryfikacja rzeczywistego conducting sheet
na lokalnym openEMS 0.37.0rc3 / CSXCAD 0.7.0rc3 pozostaje do wykonania.

## 2026-10-07 — PCB-011B: physical multilayer PCB stackup

Dodano physical schema v2 z jawnymi rolami top/innerN/bottom i oddzielnymi
materiałami dielektryków. Konfiguracja nadal nie zawiera nazw Gerberów.
Przykład pcb_fr4_4layer.json jest zbiorem założeń FR4, nie specyfikacją
producenta. Wersja v1, domyślne wejście folderowe i legacy JSON pozostają.

Import rozpoznaje role z Gerbonara/X2 i nazw KiCad/EasyEDA, sprawdza
kolejność, brak/nadmiar/duplikaty i zapisuje SHA256 każdej warstwy. Drill/
Excellon blokuje przebieg; nie dodano via-connectivity. Boolean union
wykonuje się osobno na warstwę. Stabilne ID zawierają rolę, każdy poligon
zachowuje własne Z. Port auto/explicit działa wyłącznie na top; dolna miedź
pod szczeliną jest legalna, rzeczywista miedź w górnej szczelinie nadal
blokuje solve. Jedna normalizacja obraca wszystkie warstwy i obrysy.

Zaczynamy od top=0, głębokość wyznaczają wyłącznie dielektryki. Każdy
materiał ma osobny zakres Z i constant-kappa, bez uśredniania epsilon_r.
Miedź każdej warstwy jest AddMetal lub AddConductingSheet z własnymi
parametrami; grubość sheet nie daje objętości ani nowych komórek Z.
Dokładne interfejsy są kotwicami: za bliskie są odrzucane, nie scalane.
XY respektuje najkrótszą falę w stosie; Z lokalną falę materiału oraz
istniejące minimum komórek względem łącznej grubości, bez mnożenia minimum
przez liczbę warstw. Jakości preview/design/verify nie zmieniono. Cienkie
rzeczywiste dielektryki pozostają widoczne w kosztach/CFL i mogą zablokować
przebieg przed ładowaniem natywnych modułów, jeżeli limit czasu obcina impuls.

Zapisane geometry/summary zawierają warstwy, dokładne Z, całkowitą grubość,
parametry/kappa/przewodność powierzchniową i SHA256. Stare pole substrate
jest widokiem pierwszego materiału dla kompatybilności; pełen model używa
listy rzeczywistych dielektryków. Raport offline dodaje tabelę Stackup i
plots/stackup.png (symboliczne kreski miedzi). Top-view pokazuje górną
miedź, pionowe cięcia wszystkie warstwy. Maski E/H mierzą odległość do
poligonów na ich własnym Z; napięcie odniesienia, fazy i jeden Run/CalcPort
pozostają bez zmian. Nie dodano nowych dumpów ani zmiany portu.

Sprawdzenia: deterministyczne fixture'y 2-/4-warstwowe, sąsiednie dielektryki,
rozdzielny union, poprawne role/Z, blokady konfiguracji/plików/wierceń,
port nad zakopaną miedzią, materiały i maski wszystkich Z, dokładne siatki
niezależne od grubości miedzi, preflight drogiego stosu, pojedynczy Run na
atrapach i regeneracja raportu bez Gerberów/native. Obejrzano stackup.png.
Nie uruchomiono natywnego FDTD; multilayer wymaga lokalnego sprawdzenia na
Windows. Brak wierceń nie dowodzi kompletności fizycznej. Istniejące
ograniczenia importera (m.in. otwory poligonów/clear polarity) nie zmienione.

Końcowe testy: 228 PCB OK (1 skip), pełny zestaw 295 OK (3 skip).
Testy v1, legacy, emstest/emstest2, preview/design/verify, sweep, E/H i
raportów pozostają zielone. Pominięcia dotyczą opcjonalnych środowisk;
nie są potwierdzeniem natywnego multilayer FDTD.

## 2026-10-07 — PCB-011C: Gerber copper clearances

Usunięto ogólne odrzucanie clear polarity i otworów miedzi. Gerbonara nadal
parsuje RS-274X. Shapely składa prymitywy w kolejności obiektów: dark union,
clear difference, dzięki czemu późniejsze dark przywraca miedź. Nie ma
sumowania wszystkich dark przed clear. Budżet aproksymacji krzywych i cleanup
nie zmieniony; błędny/pusty/niepoligonowy wynik jest odrzucany bez napraw.
Board outline nadal musi być pojedynczym zewnętrznym konturem, bez NPTH.

CopperPolygon zachowuje vertices_xy_m jako obrys zewnętrzny i opcjonalne
holes_xy_m jako pierścienie wewnętrzne. Jeden połączony przewodnik z otworami
pozostaje jednym rekordem. Role/Z/ID są zachowane; transformacja obejmuje
również otwory. Walidacja, ciągły i dyskretny audyt feedu wykluczają wnętrza
otworów, zachowując tolerancję styku na granicach. Kontrole portu pozostają
ograniczone do top. Metadane per warstwa zapisują liczby prymitywów dark/clear,
końcowych przewodników i otworów; JSON nie zawiera obiektów Gerbonara.

CSXCAD nadal otrzymuje zewnętrzne poligony PEC/conducting_sheet, bez
triangulacji. Wewnętrzne pierścienie są poligonami wspólnego materiału
pcb_copper_clearance_air (epsilon=1, kappa=0) na identycznym Z. Priorytety
10/11 dla miedzi/clearance rosną o 2 na poziom zagnieżdżenia. Jest to konieczne,
aby clearance macierzystego przewodnika nie skasował później przywróconej
izolowanej wyspy (priorytet 12). Plan zależy tylko od geometrii danej warstwy,
nie innych Z. Priorytety i brak grubości/linii Z są zapisane w metadanych.
Po instalacji wykonywany jest dokładny audyt zamrożonej siatki. Materiał
conducting sheet nie jest zamieniany na PEC. Same otwory nie dodają kotwic;
zmiana zewnętrznych bounds/liczby przewodników może wpłynąć na istniejącą
politykę kotwic tak jak każda zmiana fizycznej geometrii.

Maski E/H używają wspólnej reprezentacji poligonu z otworami na każdym Z,
z zachowaniem halo rzeczywistej miedzi i źródła. Pozycje, fazy i odniesienie
1 V nie zmienione. Rysunki korzystają ze ścieżek złożonych z przeciwną
orientacją pierścieni i prawdziwych przecięć pionowych, bez zamalowywania
otworów/wysp. Regeneracja offline czyta tylko zapisane wyniki i geometrię.

Testy: 235 PCB OK (1 skip), pełny zestaw 302 OK (3 skip), bez natywnego FDTD.
Fixture'y obejmują pełną płaszczyznę, okrągły antipad, wiele otworów,
późniejsze przywrócenie miedzi, wcięcie na brzegu, rozłączne przewodniki,
clearances na osobnych Z, pierścień z łuku i clear prymityw apertury.
Sprawdzono priorytety na przywróconej wyspie, identyczne poligony PEC/sheet,
niezmienione osie, mutację natywnej siatki jako błąd, port obok antipadu/na
krawędzi otworu, maski, piksele transparentnego wycięcia, przekroje warstwowe,
jeden Run/CalcPort na atrapach i raport offline. Obejrzano wygenerowany
rysunek otworu z przywróconą wyspą. Test historycznie odrzucający clear/otwory
zastąpiono nowymi dodatnimi przypadkami; błędne wejścia/punktowe styki nadal
są odrzucane. V1/v2 i emstest/emstest2 pozostają zielone.

Wyniki nadal unverified: natywna ocena priorytetów CSXCAD/openEMS na Windows
pozostaje do wykonania. Nie dodano Excellon, vias, NPTH, soldermask,
komponentów, chropowatości ani dodatkowych przebiegów/zbieżności.

## PCB-011D — Excellon through-hole vias / NPTH (2026-10-07)

Powód: v2 odrzucało wszystkie drill files, więc fizyczne wielowarstwowe
zestawy nie mogły mieć połączeń międzywarstwowych. Dodano import okrągłych
przelotowych wierceń Gerbonara 1.6.3. Gerbonara interpretuje wszystkie
instrukcje NC; kod projektu sprawdza wyłącznie metadane nazw/komentarzy.
Jawne PTH/NPTH z nazw i plating/X2 muszą być zgodne. Brak klasy, konflikt,
pusty plik, slot/route, nieobsługiwane narzędzie, blind/buried/microvia lub
nieprzelotowy zakres oznacza błąd. Pozostawiono odrzucanie ostrzeżeń parsera,
w tym niepewnego formatu liczbowego. Oryginalne Txx są pobierane z mapy
ExcellonParser przypiętej wersji, nie odtwarzane własnym parserem.

Fizyczna schema v2 przyjmuje opcjonalne drills.pth_plating_um i
pth_model=solid_pec_equivalent. PTH wymaga jawnego obiektu, NPTH nie.
V1 nadal odrzuca wiercenia; nie dodano nazw źródeł do konfiguracji.
PcbDrill jest odłączonym rekordem SI: środek, średnica, plated, źródłowa
rola/narzędzie/SHA256, grubość PTH, promień równoważny i role kontaktów.
PcbGeometry.drills domyślnie jest pustym tuple. Normalizacja/inverse mapują
środek tą samą transformacją XY co resztę płytki, bez drugiej normalizacji.
Kontakty wynikają z odległości środka do końcowej miedzi z otworami;
co najmniej dwie warstwy są wymagane. Antipad nie tworzy kontaktu. Drille
na porcie, poza obrysem lub wzajemnie zachodzące odrzucono w tej wersji.

PTH instalowany jest jako pojedynczy AddCylinder na AddMetal, od z=0 do
bottom, promień drill/2+plating. To jawny solid PEC equivalent: bez strat
metalizacji i bez pustego wnętrza beczki. NPTH to cylinder epsilon=1,
kappa=0 przez cały stack, usuwający także miedź. Priorytety są wyższe niż
wszystkie poligony i clearances PCB-011C; zmieniają materiał tylko wewnątrz
walca. Po instalacji obowiązuje dokładny audyt zamrożonych osi CSXCAD.
Native property API porównano z dokumentacją CSPrimCylinder.

Jedynymi nowymi kotwicami siatki są dokładne X/Y środków (także NPTH).
Zapisane osobno jako drill_centres_xy_m w planie, domenie i ekonomicznej
polityce. Brak kotwic promienia, metalizacji lub teselacji i nowych Z.
Zmiana metalizacji zmienia fizyczny promień, nie siatkę. Nie odrzucamy
wierceń dla oszczędności: bliskie krytyczne kotwice są zachowane albo
jawnie nierozdzielalne; ograniczenia komórek/kosztu działają przed Run.
Zachowany środek nie jest dowodem zbieżności EM promienia na grubej siatce.

Maski pól obejmują walce PTH i lokalne halo. NPTH odejmuje maskę miedzi;
substrat nadal nie jest maskowany. Wizualizacje mają oznaczenia otworów
z góry, prawdziwe przekroje walców i tabelę Drills / vias. Stackup pokazuje
przelot symbolicznie, bez pozorowania skali ścianek. Raport używa wyłącznie
zapisanej geometrii/metadanych; źródła i liczby/narzędzia/SHA256 oraz kontakty
są zachowane w import/summary JSON. Fazy, odniesienie 1 V, mesh policy
rozdzielczości, port i liczba przebiegów nie zmienione.

Testy: nowe 8 OK; PCB 242 OK (1 skip; przed dodaniem ostatniego regresyjnego
przypadku bliskich środków); końcowy pełny zestaw 310 OK (3 skip), w tym
wszystkie 8 nowych. Wykorzystano tylko atrapy natywne. Pokryto PTH/NPTH,
jednostki mm/inch, narzędzia, X2/nazwy/konflikty, slots/routes/spans,
kontakty top/inner/bottom i antipad, orphan, transformację, grubość bez
zmian osi, dokładne środki i budżet, priorytety/NPTH, mutację siatki jako
błąd, maski, jeden fake Run oraz regenerację offline po usunięciu źródeł.
Stare testy blanket-rejection zamieniono na odrzucenie pustego/nie-Excellon
źródła. V1/v2 bez drill oraz emstest/emstest2 pozostają zielone.

Ograniczenia: wyniki unverified; rzeczywiste CSXCAD/openEMS na Windows
wymaga lokalnego sprawdzenia. Nie wykonano natywnego FDTD. Nie dodano
blind/buried/microvias, plated slots, strat/chropowatości barrel, soldermask,
komponentów, konektorów, NF2FF ani sweepów zbieżności.

## PCB-011D1 — zgodność Excellon G90 po nagłówku (2026-10-07)

Przyczyna: EasyEDA umieszcza G90 po %, co Gerbonara 1.6.3 prawidłowo
interpretuje jako tryb absolutny, lecz zgłasza SyntaxWarning. Import
odrzucał z tego powodu Drill_PTH_Through.DRL z gerbs/emtest3.

read_drill_source przechwytuje ostrzeżenia obu przejść parsera. Jedyny
wyjątek to kategoria SyntaxWarning i pełny komunikat Gerbonara wskazujący
bieżący plik, numer linii oraz instrukcję "G90", zakończony dokładnie:
G90 header statement found after end of header. Każda inna instrukcja,
wiadomość lub kategoria pozostaje błędem ConfigurationError. Nie zmieniono
parsera NC, klasyfikacji, geometrii, połączeń ani fizyki. Źródłowe pliki
Excellon pozostają bez zmian.

Metadane źródła mają compatibility_warnings: source_filename, statement,
warning_text i disposition=accepted_gerbonara_compatibility_warning.
Powtórzenie tej samej diagnostyki przez open() i przejście identyfikujące
Txx jest zapisane raz. Metadane przechodzą istniejącą ścieżką drill_sources
do import/summary. Czysty import zapisuje pustą listę.

Testy: 3 nowe OK; pełny zestaw 313 OK (3 skip), bez natywnego FDTD.
Fixture'y G90 przed/po końcu nagłówka dają identyczne współrzędne,
narzędzia i średnice; test zachowuje bajty źródeł. Pokryto inne rzeczywiste
ostrzeżenia, błędny/niejednoznaczny Excellon oraz warianty komunikatu,
instrukcji i kategorii w obu przejściach parsera. Osobno odczytano wskazany
produkcyjny plik: T01, średnica 0.305 mm, XY 4.826 / 10.24543 mm,
zaakceptowane G90 w linii 11, bez zmiany pliku. Nie wykonywano pełnego
solve/importu całego emtest3 ani napraw innych elementów zestawu.

## PCB-011D2 — odróżnienie Gerber drill drawing od Excellon (2026-10-07)

Przyczyna: samo słowo drill w nazwie kierowało Gerber_DrillDrawingLayer.GDD
z emtest3 do parsera Excellon. _role() kieruje teraz do NC tylko rozszerzenia
.drl/.xln lub format identify_file()==excellon. Rozpoznany Gerber pozostaje
na ścieżce Gerber. Dla rozpoznanego Gerbera .GDD/DrillDrawingLayer oznacza
rolę drill_drawing, automatycznie omitted w istniejących metadanych bundle.
Nazwa, ścieżka i SHA256 zostają zapisane. Nieznane dane ze słowem drill nie
są uznawane za Excellon. Gerberowe FileFunction opisujące fizyczne wiercenia
pozostaje nieobsługiwane i kończy się jawnym błędem bez wywołania Excellon.

Nie zmieniono read_drill_source ani whitelist ostrzeżenia G90 z PCB-011D1.
Fizyka, siatka, klasyfikacja PTH/NPTH i źródłowe pliki pozostają niezmienione.
Dodano minimalny fixture GDD zaczynający się G04 Layer: DrillDrawingLayer*.
Test katalogu F.Cu/B.Cu/outline/DRL/GDD śledzi wywołania read_drill_source
oraz ExcellonFile.open: tylko DRL dociera do obu. GDD jest omitted, a PTH
łączy top/bottom. Usunięcie GDD nie zmienia geometrii. Wcześniejszy test
nieobsługiwanych wierceń Gerber sprawdza teraz właściwy błąd formatu,
zamiast błędu powstałego przy próbie parsowania Gerbera jako NC.

Testy: 2 nowe OK, pełny zestaw 315 OK (3 skip), bez natywnego FDTD.
Sprawdzono też pliki produkcyjne: GDD -> drill_drawing; DRL -> drill -> PTH.
Nie uruchamiano pełnego solve ani napraw innych elementów zestawu emtest3.

## PCB-011D3 — deduplikacja pomocniczego eksportu via (2026-10-07)

Przyczyna: EasyEDA eksportuje ten sam przelotowy PTH w Through.DRL oraz
Through_Via.DRL, co tworzyło dwa walce i uruchamiało walidację nakładania.
load_drills parsuje teraz wszystkie źródła przed składaniem końcowych
rekordów. Między różnymi źródłami identyczne przelotowe PTH są porównywane
z zachowanym właścicielem przez istniejące TOLERANCE_M: odległość XY oraz
różnica średnicy <= 1e-10 m. Nie ma zaokrąglania, uśredniania ani łańcuchowego
rozszerzania tolerancji. Deterministyczna kolejność nazw (casefold, nazwa,
ścieżka) stawia Drill_PTH_Through.DRL przed Drill_PTH_Through_Via.DRL.

Każde źródło zachowuje SHA256 i surowe hole_count. Nowe modeled_hole_count
oraz suppressed_duplicate_holes opisują narzędzie, XY, średnicę, nazwę,
disposition=duplicate_pth_suppressed, canonical_source i canonical_drill_id.
Tylko zachowane rekordy trafiają do geometrii, siatki, walców i masek pól.
Via-only działa samodzielnie. Nie zmieniono validate_drills ani whitelist
G90; różne średnice poza tolerancją, PTH/NPTH w tym samym miejscu oraz
odrębne nakładające się otwory nadal są błędami. Nie zmieniono fizyki ani
źródłowych Excellonów.

Testy: 4 nowe OK; pełny zestaw 319 OK (3 skip), bez natywnego FDTD.
Sprawdzono parsowanie obu źródeł, odwróconą kolejność wejściową, preferowane
źródło, lexical fallback, provenance, tolerancję, via-only i konflikty.
Fixture EasyEDA 4.826 / 10.24543 mm, T01=0.305 mm daje jeden PcbDrill,
jeden rekord środka siatki i jeden AddCylinder na atrapach natywnych.

Rzeczywisty gerbs/emtest3 przeszedł import z jawną tymczasową konfiguracją
2 warstw FR4 1.6 mm i metalizacją 25 µm (założenia). Surowe PTH: Through=1,
Through_Via=1. Finalnie 1 PTH, właściciel Through.DRL. Przy próbie kolejnego
etapu wykryto osobną przeszkodę: obrócony środek ma Y=-1.347460503399846e-19 m,
a krytyczna kotwica portu leży niemal w zerze. Obecny planner odrzuca te
różne kotwice jako zbyt bliskie. Pełna domena/XML dla emtest3 nie powstała;
nie uruchamiano FDTD. Nie zmieniono normalizacji ani tolerancji w tym ticket.

## PCB-011D4 — dokładna ortogonalna normalizacja portu (2026-10-07)

Przyczyna: cos(pi/2) pozostawiał Y via około -1.35e-19 m przy obrocie
pionowego portu emtest3, co poprawnie uruchamiało ochronę zbyt bliskich
krytycznych kotwic siatki. Dla dokładnie osiowego źródłowego portu transform
używa współczynników -1/0/+1, po dotychczasowym przesunięciu środka. Te same
współczynniki obowiązują w inverse oraz dla całej geometrii: obrys, miedź,
otwory, dielektryki, port i drille. Nie zmieniono tolerancji, _merge ani
reguł deduplikacji; nie dodano snapowania/zaokrąglania współrzędnych.

PcbTransform ma opcjonalne exact_orthogonal=False; nowa normalizacja ustawia
True tylko dla dokładnie osiowego wejścia. To informacja potrzebna inverse:
sam kąt może się zaokrąglić do ćwierćobrotu również dla rzeczywiście ukośnego
portu. Ogólne źródła zachowują atan2/cos/sin w obie strony. Stare konstruktory
i metadane bez flagi pozostają zgodne z wcześniejszym zachowaniem.

Dodano brakujący w baseline plik parameters/pcb_fr4_2layer_pth.json z jawnymi
niezweryfikowanymi założeniami FR4 1.6 mm, epsilon_r 4.3, loss tangent .018,
dwiema warstwami conducting sheet 35 µm/58 MS/m i PTH plating 25 µm.
Testy: 2 nowe OK (cztery osie, exact Y/midpoint, planner, inverse, wszystkie
rodzaje obiektów, oblique 37 i 89.999999999 stopni); pełny zestaw 321 OK,
3 skip. Nie wykonano natywnego FDTD.

Rzeczywisty CLI emtest3 + nowy plik fizyczny, preview, center 2000 MHz,
cutoff 625 MHz, sweep 1500..2500 co 10 MHz, --prepare-only: import PASS,
deduplikacja PASS (1 PTH), siatka PASS: (56,46,31), 79856 komórek.
Port w metrach: (-0.00035012000000000064,-0.0) ->
(0.0003501199999999989,0.0). PTH: (-0.0022005700000000007,-0.0).
Nie zerowano reszt zaokrąglenia translacji wzdłuż osi; Y jest dokładnie 0.

XML preparation zatrzymało się na ładowaniu native_modules: No module named
openEMS. To środowisko nie ma natywnych openEMS/CSXCAD; pełna weryfikacja
XML pozostaje na Windowsie. Nie przedstawiamy atrap testowych jako natywnego
PASS. Nie zmieniano ani nie naprawiano innych elementów produkcyjnego zestawu.

## PCB-011E — idealne elementy z ENET i port CSRC

Powód: emtest4 zawiera wiele padów elementów; stare wykrywanie dokładnie
pary prostokątnych błysków nie określa właściwego źródła. W fizycznym v2
import ENET + FlyingProbe wiąże jawne sieci/piny z końcowym obrazem miedzi.
CSRC Value=0 wybiera jedyny port, R/C/L biorą wyłącznie props.Value.
Bez ENET zachowany jest dotychczasowy import. Nie dodano bibliotek.

Nowe niemutowalne rekordy elementów i pochodzenia źródła są serializowane,
transformowane razem z PCB i odtwarzalne offline. Kotwice obejmują tylko
podłużne styki. Boxy używają istniejącej komórki poprzecznej i pierwszej
powietrznej Z; brak legalnego kontaktu kończy przygotowanie błędem.
AddLumpedElement: pojedyncze R/C/L, LEtype=1, caps=True; priorytet 5,
audyt siatki przed/po. Brak nowego Run, geometrii obudowy, ESR/ESL/DCR.
Wartości elementów nie wpływają na osie. Raport i pola pokazują elementy,
bit maski 8 używa istniejącej polityki lokalnego halo.

Sprawdzenia: parser/wartości/jednostki, sieci i odrzucenia, finalna przerwa,
normalizacja/inverse, kotwice/stała oś Z, instalacja R/C/L na atrapach,
jeden port/Run/CalcPort, pola i raport po usunięciu źródeł. Pełny zestaw unittest:
329 testów, OK, 3 pominięte testy zależne od natywnego środowiska.
Rzeczywisty emtest4: CSRC A–B; C1=100pF, L1=18nH, R1=49.9Ω.
Preview 2 GHz/cutoff 625 MHz poprawnie blokuje impuls 55 210 kroków wobec
limitu 50 000. Jawny cutoff 1000 MHz daje 288 120 komórek i minimum
34 507 kroków; bez elementów 181 790 komórek, oś Z bez zmian.
Prepare-only dochodzi do braku natywnych bibliotek w środowisku agenta;
XML/kontakt natywny pozostają do wykonania na Windowsie. Nie uruchamiano
natywnego FDTD. Wszystkie wyniki pozostają unverified.

## PCB-012A — globalna całkowitoliczbowa kratownica i odłączony audyt

Baza: aff797a. Wprowadzono PcbGrid dla 100/10/1/0,1 µm, dokładne
zaokrąglenia dziesiętne (połowy od zera), floor/ceil oraz zamrożone rekordy
geometrii tickowej. Oddzielne quantize_pcb_geometry nie ma połączenia
z aktywnym importerem/CLI/siatką/adapterem. Nie zmieniono XML ani parametrów
FDTD, tolerancji geometrii czy łączenia kotwic. RLC, epsilon, straty,
przewodność i materiałowa grubość conducting sheet nie są kwantyzowane.

Warstwy akumulują wspólne interfejsy w tickach. Promienie kół są całkowite,
średnice modelowane wynoszą 2*promień; oryginalne średnice i galwanizacja
pozostają provenance. Zapis source_json zachowuje pełny odłączony obraz
wejścia wraz z SHA256. Metadata audytu liczą zmiany i maksymalne przesunięcia,
przykładów jest najwyżej 20. Zanik lub zmiana topologii zwraca błąd z audytem,
a nie naprawiony model. Nie stosuje się make_valid ani naprawy buforem.
Sprawdzana jest własność i sieć połączeń terminali, regiony/otwory, PTH/NPTH.

Sprawdzenia: nowe testy arytmetyki dla wszystkich kwantów, pierścieni, zaników,
wspólnych interfejsów, otworów, błędnych kontaktów i zwarć, zachowania
provenance oraz niezmienności aktywnej siatki; pełny zestaw unittest:
341 testów, OK, 3 pominięte (zależności natywne).
Odłączony audyt 10 µm: emtest3 PASS, 550/577 zmienionych wartości,
max XY 6,820704 µm; emtest4 PASS, 4540/4566, max XY 7,019105 µm.
Max Z=0 w obu. Kontakty PTH i liczby regionów zachowane. Bez FDTD.
PASS dotyczy audytu geometrii, nie dokładności EM. Integracja solvera dopiero
w kolejnych ticketach; żadnego publicznego przełącznika nie dodano.

## PCB-012B — odłączona budowa domeny w całkowitych tickach

Baza: 15c159d. Dodano pcb_lattice_mesh z jawnym planem wymaganych kotwic
tickowych i istniejącą polityką fizyczną. To osobna wewnętrzna ścieżka:
aktywny importer, wybór kotwic, make_pcb_domain_mesh, CLI i native XML
pozostają bez zmian. Nie uruchamiano FDTD ani benchmarków.

Podziały używają dzielenia całkowitego z resztą, grading — dokładnych
porównań wymiernych i całkowitych punktów podziału. Maksima fizyczne są
zaokrąglane w dół do ticków, wymagane powietrze w górę. PML kopiuje
szerokość komórki powietrza bez ułamkowych współrzędnych. Brak legalnego
kroku albo budżetu kończy się błędem. Istniejące tolerancje nie zmieniły się.

Wynik przechowuje osie i granice jako tuple[int,...]; SI jest pojedynczym
eksportem to_domain_mesh. Audyt obejmuje kotwice, minimalny tick, maksima
lokalne, grading, PML i max_cells. Metadata zawierają kwant, min/max ticków,
kroki w metrach i off_grid_line_count. Zmiana dotyczy wyłącznie infrastruktury;
nowy typ nie jest automatycznie podłączony do solvera ani do raportów run.

Sprawdzenia: 15 nowych testów (wszystkie cztery kwanty, 1000 małych podziałów,
trudne przejścia gradingu, dokładne limity budżetu, PML, polityki jakości,
eksport SI, odrzucenie floatowych kotwic i niezmienność ścieżki legacy).
PCB: 273 testy OK. Pełny zestaw: 356 testów OK, 3 pominięte natywne.
Syntetyczna płytka 20×20 mm: q=100 µm daje 82×83×72=490032 komórki;
q=10/1/0,1 µm daje 76×70×65=345800. Wszystkie audyty off_grid_line_count=0.
Grubszy kwant może wymagać większego zagęszczenia dla zachowania gradingu.
Migracja wyboru kotwic z geometrii i publicznego workflow pozostaje PCB-012C.

## PCB-012B (zastępujący eksperyment tickowy) — geometria przed istniejącym mesherem

Baza merytoryczna: 15c159d/PCB-012A. Zgodnie z nową decyzją wycofano
integer-tick mesher z 9b72de4 i jego testy. Historia tego commitu pozostaje,
ale aktywna infrastruktura nie zawiera alternatywnego algorytmu siatki.
Rozdzielczość geometrii jest niezależna od rozdzielczości EM; nie narzuca
wielokrotności ticków ani minimalnej wielkości komórki.

Nowy odłączony kandydat: importowana geometria → dotychczasowa normalizacja
raz → kwantyzacja/audyt PCB-012A → materializacja do zwykłego PcbGeometry
w SI → istniejący make_gerber_mesh_anchor_plan/make_pcb_domain_mesh oraz
audyt kontaktów portu i boxów elementów. Surowe dane i transformacja są
oddzielnym provenance. Bez zmiany CLI, produkcyjnych przebiegów, polityki
ekonomicznych kotwic, gradingu, PML, profili i bez XML/FDTD.

Materializacja zachowuje wartości R/L/C i materiałów, conducting-sheet
thickness oraz identyfikatory i hashe. QuantizedPcbDrill przechowuje
rozdzielczość i źródłową średnicę jako dowód projekcji. Walidator sprawdza
dokładną regułę PCB-012A, zamiast wymuszać sumę już skwantyzowanej średnicy
i surowej galwanizacji. Nie zmienia to surowych PcbDrill ani ich serializacji,
nie przywraca usuniętych cyfr i nie rozluźnia kontroli połączeń/kolizji.

Diagnostyka rozdziela odstęp współrzędnych geometrii (z kategorią/właścicielem
najbliższej pary) od minimalnej końcowej komórki FDTD. Nie czyni każdego
wierzchołka krytyczną kotwicą. Formaty geometrii źródłowej nie zmieniły się;
metadane dodatkowe istnieją tylko w odłączonym kandydacie.

Eksperyment emtest4, preview 2 GHz, cutoff 1 GHz, sweep 1500–2500/10 MHz:
raw 288120; geometry resolution 100 µm poprawnie FAIL (obie pełne powierzchnie
kontaktu CSRC utracone); 10 µm 195615; 1 µm 288120; 0,1 µm 282240 komórek.
Przy 10 µm zachowane CSRC, C1=100 pF, L1=18 nH, R1=49,9 Ω i PTH top–bottom;
modelowana szerokość CSRC 0,86 mm, końce ±0,35 mm. Oś Z niezmieniona.
emtest3: 99750 → 102900 (+3,16%), jeden PTH, te same kontakty i dokładna
normalizacja ortogonalna. Brak przypadku PASS z regresją komórek >5%.
Szczegółowe odstępy, koszty i powody FAIL: docs/pcb-grid.md.

Sprawdzenia: 9 nowych testów jednostkowych i 1 integracyjny na emtest3/emtest4;
26 testów powiązanych grid/drill/model. Pełny zestaw: 351 testów OK,
3 pominięte natywne. Potwierdzono legalność niecałkowitych względem
rozdzielczości geometrii linii FDTD oraz kroku EM mniejszego od tej skali.
PASS dotyczy eksperymentu geometrii i kontaktów; brak publicznej aktywacji
i brak nowego sprawdzenia fizycznej zbieżności.

## 2026-10-07 — PCB-012C: produkcyjna rozdzielczość geometrii

**Powód:** odłączony wariant PCB-012B został sprawdzony przez użytkownika
natywnie na Windows: emtest4 10 µm dał identyczne 195615 komórek w preflight
oraz XML. Ten etap włącza projekcję do zwykłego workflow, bez zmiany meshera.

**Zmiana:** `--geometry-resolution-um {100,10,1,0.1}`, domyślnie 10,
również dla legacy JSON i API Python. Wspólne `apply_geometry_resolution`
przyjmuje już znormalizowaną geometrię; normalizacja i materializacja odbywają
się raz. Wszystkie kotwice, mesh, port, elementy, pola i native otrzymują
modelowaną geometrię. Kontrola dokładnej równości preflight/native blokuje
Run przy rozbieżności. Audyt odrzuca niepoprawną topologię przed mesherem.
Nie zmieniono fizyki, profili, siatki float, częstotliwości ani wartości RLC.

**Zapis i raport:** osobno geometry.source.json, geometry.normalized_source.json
oraz geometry.json; import/summary zawierają blok geometry_resolution.
Nieudana projekcja zapisuje źródła i audyt, bez udawania poprawnego geometry.json.
Raport offline wyświetla modelowane CSRC/wiercenia, liczniki zmian i krótkie
przykłady. Liczba wierceń pochodzi z pth_count/npth_count, nie liczby kluczy.
Brak współdzielonego cache przebiegów, więc nie dodano mechanizmu cache.

**Akceptacja bez natywnego FDTD:** produkcyjne prepare-only z atrapami native
odtwarza emtest4 (69,81,35)=195615, 30446 kroków impulsu, 5955694290 aktualizacji;
raw miał 288120 komórek. Jedno CSRC, C1=100 pF, L1=18 nH, R1=49,9 Ω i jeden
PTH top–bottom zachowane. emtest3: raw 99750 → (60,49,35)=102900 (+3,16%).
emtest4 100 µm poprawnie odrzucony przed mesherem: port 0,9 mm nie mieści się
na miedzi kontaktowej 0,8 mm. Nie wykonuje się automatycznego retry.

**Testy:** testy produkcyjnej tożsamości geometrii, CLI/API, provenance,
rozbieżności native/preflight, jednego Run/CalcPort z polami, offline report
oraz rzeczywistych emtest3/emtest4. Oczekiwania testu pól dostosowano do
modelowanej geometrii. Test kosztu dielektryka 1 µm jawnie używa 0,1 µm,
aby nadal badać koszt, a nie wcześniejsze odrzucenie zanikającej warstwy.
Pełny zestaw: 357 testów, OK, 3 pominięte (natywne openEMS/CSXCAD,
Windows UCRT i GUI Tk). Testy kierunkowe PCB/pól/stackupu: 24, OK.

**Ograniczenia:** kontener nie ma openEMS/CSXCAD; testy produkcyjne używają
atrap native. Nowy publiczny prepare-only pozostaje do potwierdzenia na
Windows. To akceptacja architektury, nie badanie zbieżności ani walidacja EM.

## 2026-10-08 — PCB-012D: hierarchiczne wejścia ZIP (akceptacja real preview zablokowana)

**Powód:** warianty PCB mają współdzielić stackup/ENET bez kopiowania ich do
rozpakowanych katalogów. ZIP jest źródłem, nie etapem ekstrakcji.

**Zmiany robocze:** bezpośredni ZipMember + Path, niezależne dziedziczenie
local → jeden parent, jawny config nadrzędny wobec stackupu automatycznego,
strict adapter EasyEDA fizycznego stackupu. Oryginalne bajty i ścieżki ENET,
katalog modeli przyszłych komponentów, hashe ZIP/wpisów i pochodzenie
materiałów są oddzielną deterministyczną informacją. Parsery używają
Gerbonara from_string dla ZIP; nie napisano parsera Gerber/NC. ENET wewnątrz
archiwum jest błędem. Folder/legacy JSON zachowują zachowanie i nie dziedziczą.

**Fizyka:** bez zmian. Epsilon nie jest zgadywane; real stackup to 35 µm Cu /
0,2 mm epsilon=4,5 tanδ=0 / 35 µm Cu. Maska pominięta, model miedzi/przelotek
pozostaje dotychczasowy. Rozdzielczość geometrii 10 µm i siatka float nietknięte.

**Sprawdzenie danych:** dokładne bajty 13 wpisów ZIP zgodne z dawną kopią
katalogową. Geometria/normalizacja/model/siatka/koszt zgodne dla ZIP lokalnego,
dziedziczonego i importu katalogowego. Po tej kontroli usunięto tylko
`gerbs/realpcb_microstrip/test1/`, zachowując oryginalny ZIP/ENET/stackup.

**Blokada akceptacji:** test1 topology PASS, dwa PTH top–bottom, jedno CSRC,
R1=49,9 Ω; preview daje 356040 komórek (92,86,45), minimum impulsu 90937
kroków / 32377209480 aktualizacji. Dotychczasowy resolver R1 odrzuca brak
legalnej komórki poprzecznej; dodatkowo 90937 > 50000. Zjawiska są identyczne
dla dawnego importu katalogowego. Nie naprawiano ich niedozwoloną zmianą
meshera/profilu ani ukrytym refinement. Nie wykonano natywnego FDTD.

**Testy:** testy hierarchii, formatów, jednostek, ochrony ZIP, źródeł/provenance,
bezpośredniego parsowania, fake-native przygotowania poprawnego syntetycznego
ZIP oraz rzeczywistej równoważności i jawnego odrzucenia kosztu/styków.
Pełny zestaw: 368 testów, OK, 3 pominięte (openEMS/CSXCAD, Windows UCRT, Tk).
Końcowy zestaw wejść ZIP i konfiguracji: 22 testy, OK. Warunek pełnej
akceptacji rzeczywistego prepare-only nie jest spełniony, więc nie utworzono
commitu; przygotowano łatkę do przeglądu bez zmian polityki solvera.

## 2026-10-08 — PCB-012E: deterministyczne kontakty komponentów w siatce

**Powód:** R1 w test1 ZIP nie miał pełnej komórki poprzecznej wewnątrz okna
kontaktu. Sama poprawna geometria nie gwarantowała jej w oszczędnej siatce.

**Zmiana:** wspólna polityka kotwic komponentów zachowuje krytycznie końce
przerwy i poprzeczne min/max modelowanego okna kontaktu, przed podziałem oraz
gradingiem. Filtr Gerber ich nie usuwa. To wymaganie siatki EM, nie zmiana
rozdzielczości CAD ani nowa krata FDTD. Nie dodano kotwic Z. Wartości RLC,
geometria, źródło, import ZIP i profile pozostają bez zmian. Resolver zachowuje
wszystkie audyty i wskazuje teraz styki/politykę EM zamiast drobniejszego CAD.
Metadane component_terminal_anchors_m obejmują także poprzeczne granice.

**Akceptacja test1 bez FDTD:** lokalne stackup/ENET, geometria 10 µm;
R1=49,9 Ω przechodzi końcowy audyt w preview i design. Preview:
(92,112,45)=463680, minimum 90937 kroków / 42165668160 aktualizacji;
design: (98,126,58)=716184, 91442 kroków / 65489297328 aktualizacji.
Oba produkcyjne prepare-only dochodzą do preflight kosztu i zatrzymują się
przed native na istniejącym limicie impulsu (50000 / 75000). Zgodnie z zakresem
nie jest to wada PCB-012E ani powód do zmiany budżetu. XML/FDTD nie wykonano.

**Wpływ na odtwarzalność:** dodatkowe wymagania XY mogą zmienić grading i koszt;
preview test1 wcześniej 356040 komórek nie pozwalało zainstalować R1.
Regresja emtest4: raw 288120 → 270480; model 10 µm 195615 → 214935
(69,89,35), Z bez zmian. Uaktualniono tylko odpowiednie oczekiwania testów.
emtest3 bez komponentów pozostaje (60,49,35)=102900.

**Sprawdzenia:** kotwice X/Y we wszystkich profilach, pełne styki i okno,
niezmienność od wartości RLC i brak nowego Z, uszkodzona siatka, niejednoznaczna
miedź, przerwa oraz kolizje źródła/komponentów/wierceń. Zachowano testy ZIP,
syntetyczne atrapy native oraz rzeczywiste preview/design. Wyniki testów nie
potwierdzają zbieżności ani dokładności fizycznej modelu.

**Wynik testów:** komponenty/ZIP 21 testów OK; pełny unittest 370 testów OK,
3 pominięte (natywne openEMS/CSXCAD, Windows UCRT, GUI Tk). Bez FDTD.

## 2026-10-08 — PCB-012F: zachowanie modelowanej miedzi w siatce EM

**Powód:** filtr ekonomiczny usuwał fizyczne krawędzie miedzi na podstawie
odstępu zależnego od długości fali. Samo zachowanie polygonu CSXCAD nie
zapewniało reprezentacji jego szerokości w siatce.

**Zmiana:** modeled_copper_features_v2 wyznacza współrzędne normalne odcinków
poziomych/pionowych wszystkich obrysów i otworów. Chroni także wewnętrzną
szerokość przewężenia w polygonie połączonym z dużymi padami. Usunięto filtr
below_half_local_resolution. Pominąć można tylko numeryczny środek bbox;
nie zmieniono polygonów, projekcji, materiałów, źródła ani wartości RLC.
Nie przywrócono siatki tickowej; grading/podział nadal używa float.
Kotwice portu/komponentów/wierceń i polityka Z pozostają niezmienione.

**Audyt:** nowy czysto pythonowy pcb_features.py sprawdza końcowe granice
oraz przekroje prostokątne (szerokości źródłowe/modelowane/reprezentowane).
Krzywe mają chronione extrema i ograniczone wsparcie przedziałów bbox,
nie każdy wierzchołek aproksymacji. Obwiednie pełnych/przeciętych komórek
muszą zachować obszary, otwory, ich własność i brak zwarć między przewodnikami.
Niepowodzenie lub budżet miliona komórek audytu kończy przygotowanie przed
native. To konserwatywny test topologii, nie natywne zajęcie Yee ani zbieżność.
Reszty po translacji raw można utożsamić wyłącznie w granicy 8 ULP skali płytki,
nie większej od istniejącej tolerancji geometrii; każda równoważność jest
raportowana. Nie zmieniono _merge ani tolerancji portu. Projektowane granice
regresji szerokości są zachowane dokładnie, bez równoważności float.

**Metadane:** summary.copper_mesh_fidelity, modelowane i zachowane granice,
przekroje, źródłowe granice przy dostępnej geometrii raw, audyt krzywych,
liczniki fizycznych współrzędnych oraz przyczyny pominięcia środków bbox.
Audyt w make_pcb_domain_mesh obowiązuje również ścieżkę adaptera natywnego.
Błąd max_cells nie powoduje upraszczania miedzi.

**Regresje bez FDTD:** ten sam środek/stackup, q=10 µm: 0,376/0,384 mm →
0,38 mm; 0,25/0,38 mm → różne 0,25/0,38 mm. Potwierdzono granice i zmierzone
szerokości w siatce dla przewężenia połączonego z padami oraz otworu/szczeliny,
we wszystkich profilach. Wartości RLC nie wpływają na siatkę, Z się nie
zagęszcza. Zachowano audyty PCB-012E. Testy raw kosztu nie wymagają już
starego zaniżonego rozmiaru siatki ani limitu 105% tego rozmiaru.

**Rzeczywisty test1 ZIP, 10 µm:** import, normalizacja, projekcja, siatka,
audyt miedzi i R1 PASS. Zachowane 16 X + 12 Y fizycznych współrzędnych,
zero stłumionych. Preview: (333,265,45)=3971025 (poprzednio 463680),
min XYZ 4,0722/4,1667/100 µm, impuls minimum 295026 kroków,
1171555621650 aktualizacji. Design: (345,221,58)=4422210 (poprzednio 716184),
min XYZ 4,0722/8,3333/66,6667 µm, minimum 235091 kroków,
1039621771110 aktualizacji. max_cells nieprzekroczone. Budżety impulsu
50000/75000 pozostają przekroczone, bez zmiany profili/EndCriteria/wymuszenia.
Dane nie stanowią porównania A/B wyników elektromagnetycznych.

**Koszt audytu:** obwiednie są składane z dokładnych poziomych pasów komórek,
nie z osobnego wielokąta każdej komórki; zbiór punktów pozostaje identyczny.
Dotychczasowy limit miliona komórek audytu i kryteria topologii nie są osłabione.
**Testy celowane:** 61 testów cech/siatki/komponentów/ZIP PASS; po końcowej
optymalizacji audytu dodatkowe 7 testów (6 cech + rzeczywiste emtest3/emtest4)
PASS. emstest/emstest2 import/projekcja/kontakt PASS. Brak natywnego FDTD.

**Pełny unittest (końcowy stan):** 376 testów, 2 failures, 17 errors, 3 skipped.
Wszystkie 19 niepowodzeń dotyczy wcześniejszego zatrzymania przez niezmieniony
preflight impulsu: 17 testów fake-run/report/fields/prepare oczekuje przejścia
zbyt małego budżetu; dwa oczekują późniejszego błędu termination lub grid mismatch.
Dotyczy modułów test_pcb_bundle, clearances, copper, drills, fields, gerber,
gerber_quality, gerber_sweep, production_resolution i report. Nie zwiększono
budżetów ani nie wyłączono preflight, aby uzyskać zielony wynik. Skip: native
openEMS/CSXCAD, Windows UCRT i GUI Tk. Regresje cech, PCB-012E, emstest/emstest2,
emtest3/emtest4 i test1 przechodzą w pełnym przebiegu. Zakres geometrii PASS;
integracja całego zestawu PARTIAL, polityka budżetu pozostaje osobnym zadaniem.


## PCB-012G — feature-aware economical copper meshing

Zastąpiono promowanie wszystkich prostoliniowych granic kompaktowymi parami
szerokości/szczelin i udokumentowaną regułą 1/3 metal–2/3 otoczenie. Konflikty
z krytycznymi kotwicami używają audytowanej rozdzielonej reprezentacji, nigdy
zmiany polygonu. Zachowano PCB-012F: q10 0,376/0,384→0,38, ale 0,25 i 0,38
są rozróżnialne. Geometria, RLC, źródło, tolerancje, Z i profile bez zmian.
Dokładne kryteria i źródła openEMS: docs/pcb-gerber.md.

Serpentyna 12/144 wierzchołków: identyczne 93×95×30=265050 komórek (ratio1).
Łuki 44/140 wierzchołków: identyczne 186×122×30=680760; 16 cech, 21/27
wymaganych ograniczeń XY. Żaden wierzchołek nie jest bezpośrednio promowany.
Test1 preview: 3971025→833850, design:4422210→1372280. Audyty cech,
komponentów i portu PASS. Krytyczne wiercenia/źródło wymuszają minima10/30µm;
cutoff1GHz nadal przekracza niezmienione budżety impulsu. Design cutoff1,9GHz:
1463168 komórek, minimum48128 kroków; fake-native prepare PASS, rzeczywiste
prepare blokuje brak openEMS. Nie wykonano FDTD ani porównania impedancji.

**Weryfikacja:** 54 testy cech/siatki/komponentów PASS, 12 testów ZIP/wybranych
kotwic PASS, dodatkowy fake-native prepare PASS; końcowe 10 testów cech PASS.
Pełny unittest uruchomiono raz: 381 testów, 3 failures, 33 errors, 3 skipped.
Wynik integracji PARTIAL: 28 niepowodzeń dotyczy wcześniejszego fail-closed audytu
obwiedni (w tym test oczekujący późniejszego preflight), 7 niezmienionego
budżetu impulsu; jeden test oczekuje starego rozmiaru siatki emtest3
60×49×35 zamiast obecnego271×278×35. Nowy audyt bywa zbyt konserwatywny przy
połączeniach padów/regionów: wewnętrzna obwiednia rozdziela połączony polygon.
Nie wyłączono kontroli topologii, nie podniesiono budżetów ani nie zmieniono
niepowiązanych oczekiwań testów. Test1, nowe serpentyny/łuki i komponenty PASS;
cały adapter wymaga dalszej pracy przed uznaniem wydania za w pełni zgodne.


## PCB-013A — zewnętrzne profile openEMS (checkpoint)

Przeniesiono profile Gerber do komentowanego TOML; NrTS=1e9 jako wspólny sufit.
Dodano walidowany runtime, MaxTime, kontrolę jawnego CFL, BC, natywne opcje Run,
Y/N/E i nadpisania tylko bieżącego przebiegu, bez input w API. Pola domyślnie
center, fazy raportu15°, jawne opt-out. Zapis profilu/SHA256/nadpisań w summary
oraz raport offline. Nie zmieniono geometrii, meshera PCB-012G, parametrów
fizycznych ani diagnostyk syntetycznych. Przy wyłączeniu statystyk zakończenie
pozostaje niepotwierdzone. Checkpoint publikowany przed pełnym unittest.
Testy profilów używają wyłącznie atrap native; nie wykonano FDTD.

PCB-013A: pierwszy checkpoint opublikowano jako 6e0195b9 na origin/main.
Celowane testy po dopięciu integracji: 82/82 PASS (profiles, openems_pcb,
pcb_control, pcb_simulation, gerber_quality, gerber_sweep, pcb_zip).
Testy obejmują jeden fake Run z domyślnymi E/H, zapis profilu i faz15°,
wyłączone statystyki bez twierdzenia completed oraz odmowę CalcPort po MaxTime.
Zaktualizowano wyłącznie oczekiwania związane z nowymi profilami: duży NrTS,
jawne opt-out pól w testach bez dumpów, opcjonalne runtime=None w starej konfiguracji.
Real ZIP nadal sprawdza zbyt mały, teraz jawnie nadpisany NrTS. Drugi checkpoint
publikowany przed jedynym pełnym unittest. Brak natywnego FDTD.

PCB-013A — weryfikacja końcowa: drugi checkpoint 449bdb73 opublikowano przed
pełnym unittest. Pełny zestaw uruchomiono dokładnie raz: 397 testów,
14 failures, 33 errors, 3 skipped. Wykrył regresję rozszerzenia run_options
w syntetycznych diagnostykach oraz stare atrapy bez dumpów przy nowych polach ON.
Przywrócono dokładnie dawny zapis run_options dla runtime=None; testy bez pól
używają teraz jawnego opt-out, zaś osobne testy sprawdzają domyślne E/H.
Po poprawkach: 41/41 testów celowanych PASS (16 profili, edge_convergence,
refined_sensitivity i cztery dotknięte integracje Gerber/report).
Nie powtarzano całego zestawu. Historyczne odmowy audytu obwiedni PCB-012G
oraz stara oczekiwana wielkość siatki emtest3 pozostają poza zakresem.
Zakres PCB-013A PASS na atrapach; całe repozytorium PARTIAL, native Windows
nie sprawdzono. Żaden natywny Run ani solve/convergence nie został uruchomiony.
Końcowy commit publikuje także te wyniki. Żadne outcomes ani niepowiązane
pliki użytkownika nie są dodawane do commita.


## PCB-015A1 — koszt walidacji polygonów

Usunięto pełną kwadratową pętlę par krawędzi Pythona. GEOS sprawdza
poprawność bez naprawiania geometrii; STRtree ogranicza stare testy tolerancji
bliskich krawędzi do przestrzennych sąsiadów. Zachowano liniowe kontrole
liczb, krawędzi, pola i sąsiednich cofnięć. Bez zmiany tolerancji, formatu,
źródłowych współrzędnych lub fizyki. Test strukturalny kontroluje brak
przeglądu odległych par, nie czas wykonania. Brak benchmarków i FDTD.
Testy: validation+transform 29/29 PASS; szerszy zestaw 36 testów ma dwa
wcześniejsze błędy audytu obwiedni meshera w test_pcb_clearances, pozostałe
34 PASS. Kontrole otworów w tym zestawie przechodzą; błędów meshera nie zmieniano.

## PCB-015A2 — oddzielny FAST / APPROX (checkpoint izolowanej linii)

Dodano jawny solver reduced_quasi_tem z importem ZIP/katalogu, istniejącą
normalizacją/projekcją oraz compact_features. Odtworzenie grafu musi dowieść
pokrycia całej miedzi; niejednoznaczna geometria jest odrzucana. Linia
Hammerstad–Jensen (zero thickness/quasi-static), sieć nodalna z dokładnymi
równaniami TL i idealnymi R/L/C. CSV Z/S11/SWR, graf i provenance JSON.
Wspólne argumenty częstotliwości wydzielono bez zależności od adaptera;
walidacja pasma jest współdzielona. Nie zmieniono profili/full-wave/siatki.

Zakres PARTIAL: sprzężenia par są wykrywane i blokują solve (nie są po cichu
pomijane); łuki, niejednoznaczne pady, ground slots i vias również fail closed.
Linie bezstratne; promieniowanie, dyspersja i pasożyty nie są modelowane.
Dokładny kontrakt, metoda, ograniczenia i komenda: docs/pcb-reduced.md.
Testy to tożsamości linii open/short/load/match, faza, kierunek zmian w/h/er,
stampy RLC/różnicowe, graf straight/L/U, brak native/meshera/promptu i zapis
strict JSON/CSV. Brak natywnego FDTD, benchmarków, nowych zależności.
Checkpoint jest publikowany przed jedynym pełnym unittest.
Celowany zestaw przed publikacją: 76/76 PASS (reduced, simulation, validation,
transform, control, gerber_sweep). Fizyczna trafność pozostaje approximate.

PCB-015A — końcowa weryfikacja i trwałość:
- A1 opublikowano jako 017dfe1254fa173747f7d1a6535eec35979b779a.
- A2 opublikowano jako 5b1695af2596baae301b284c8bd70886c5857b85 przed pełną suite.
- Pełny unittest uruchomiono RAZ: 414 testów, 2 failures, 27 errors, 3 skipped.
  Wszystkie 27 errors to istniejące odmowy PCB copper fidelity. Jeden failure
  oczekuje późniejszego błędu preflight zamiast tej odmowy, drugi oczekuje
  starego emtest3 60×49×35 zamiast 271×278×35. Brak niepowodzeń nowych testów.
  Nie zmieniano niepowiązanych testów ani nie osłabiano audytu full-wave.
- Końcowo źródło i RLC korzystają z istniejącego audit_physical_feed; wykrywane
  są też nakładające się obszary komponentów/źródła. Nie ma słabszego testu
  samej powierzchni w reduced. Nieobsługiwane łuki odrzucamy przed przekrojami.
- 17 testów reduced po tej poprawce PASS, w tym rzeczywiste minimalne pliki
  GTL/GBL/GKO -> Gerbonara -> normalizacja/projekcja -> graf -> CSV, bez native.
- Dostępny realpcb_microstrip/test1.zip: import/projekcja PASS, FAST odmowa
  z powodu wierceń/vias (zgodna z jawnym ograniczeniem). test_spirala.zip
  nie istnieje w śledzonym stanie repozytorium. Nie ma wyniku Z dla serpentyny.
- Całość PARTIAL: brak macierzy/modalnego modelu sprzężeń par, nieobsługiwane
  pady/łuki/vias wymagają osobnego rozszerzenia. Izolowane linie PASS wyłącznie
  w zakresie opisanej aproksymacji, bez kalibracji full-wave/promieniowania/strat.
Nie uruchomiono FDTD, benchmarków ani sweeps zbieżności. Zmiany publikowane
wyłącznie w jawnych plikach zadania; outcomes/źródła użytkownika nietknięte.
