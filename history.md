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
