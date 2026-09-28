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

## Wzór kolejnego wpisu

- Data i krótka nazwa zmiany.
- Powód oraz powiązany cel lub problem.
- Co rzeczywiście zmieniono.
- Wpływ na fizykę i dotychczasowe wyniki.
- Wpływ na architekturę, formaty i odtwarzalność.
- Wykonane sprawdzenia i ich rezultat.
- Ograniczenia, migracje lub konieczność ponownego przeliczenia wyników.
