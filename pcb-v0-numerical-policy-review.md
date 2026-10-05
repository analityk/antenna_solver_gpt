Reviewed commit: fbb2cde
Status: architecture / numerical policy review
Scope: PCB v0
Native FDTD executed: no

1. Executive decision
Architektura jest właściwa. Obecna siatka jest poprawnym etapem infrastrukturalnym, ale nie powinna jeszcze trafić do FDTD.
Przegląd dotyczy fbb2cde. Nie zmieniałem plików ani nie tworzyłem commitu. Sprawdziłem dokumentację oznaczoną openEMS 0.37.0-rc3 oraz pomocniczo aktualny kod źródłowy portów. Zgodność z konkretnym zainstalowanym buildem wymaga później testu natywnego.
Decyzje:
- zachować rozdzielenie geometrii, kotwic, podziału osi i polityki fizycznej;
- zastosować płaski port lumped w XY, na z=0;
- ustawienia symulacji umieścić w osobnym kontrakcie;
- regułę 1/3–2/3 odroczyć do badania zbieżności;
- przed fizycznym mesherem naprawić ochronę interfejsów Z — znalazłem dwa odtwarzalne przypadki ich utraty.
2. Current assumptions: KEEP / CHANGE / DEFER
Element	Decyzja	Powód i konsekwencja
Geometria w SI, oddzielna konfiguracja	KEEP	Parametry materiałowe i ścieżki nie powinny trafiać do meshera jako geometria.
Normalizacja całej PCB do +X	KEEP	Upraszcza port, zachowuje geometrię i transformację odwrotną.
Dokładne granice portu i ich pierwszeństwo	KEEP	Źródło, rezystancja i siatka muszą używać tych samych współrzędnych.
z=0 miedzi	KEEP — wymaganie twarde	Zerowej grubości metal musi leżeć na linii siatki.
Ekstrema i środki bounding boxów miedzi	KEEP dla placeholdera	Nie opisują przewężeń, szczelin ani wewnętrznych krawędzi dowolnego Gerbera.
Wszystkie ekstrema miedzi jako wiecznie obowiązkowe linie XY	CHANGE w docelowej polityce	Uniemożliwiałyby odsunięcie siatki od krawędzi według reguły 1/3–2/3.
Scalanie kotwic Z tak samo jak pomocniczych XY	CHANGE	Może usunąć płaszczyznę miedzi lub grubość laminatu.
Rozpoznawanie połączeń między polygonami	DEFER do importera	Obecna walidacja świadomie traktuje rekordy jako oddzielne przewodniki.


Płaszczyzna i krawędź to różne wymagania. Dokumentacja wymaga dokładnego wyrównania zerowej grubości powierzchni do siatki, natomiast dla krawędzi metalu zaleca celowe przesunięcie linii. Nie należy przesuwać płaszczyzny Z w ramach reguły 1/3–2/3. openEMS 0.37.0-rc3 documentation
3. Final PCB-v0 port contract
Decyzja: prostokątne, zerowej grubości wymuszenie między padami. Bez sztucznej wysokości w powietrzu lub laminacie. Port zastępuje miejsce podłączenia elementu; nie jest modelem kondensatora.
Dla znormalizowanej geometrii:
ym = (negative.y + positive.y) / 2

start = [negative.x, ym - width/2, 0.0]
stop  = [positive.x, ym + width/2, 0.0]

exc_dir = "x"

Wywołanie: AddLumpedPort(..., R=reference_impedance_ohm, excite=1, ...). Nazwa kierunku określa oś; znaki napięcia, prądu i wektora wymuszenia należy zachować zgodnie z konwencją biblioteki.
Dokumentacja dopuszcza powierzchniowy port lumped. Jego rozmiar musi pozostawać elektrycznie mały; podział dużego portu na więcej komórek nie naprawia ograniczeń modelu skupionego. openEMS 0.37.0-rc3 documentation
Pytanie	Kontrakt PCB v0
Liczba komórek X	Startowo co najmniej 2 przez szczelinę, potem kontrola zagęszczenia. To zalecenie projektu, nie wymóg API.
Liczba komórek Y	Startowo co najmniej 2 przez szerokość. Więcej, jeśli wymaga tego rozdzielczość lokalna.
Liczba komórek Z portu	Zero przedziałów, jedna płaszczyzna siatki. Domena ma komórki nad i pod nią.
Granice poprzeczne	Dokładnie na liniach siatki — przyjmujemy to jako twardy kontrakt projektu.
Środek Y	Zachować. Pomaga jednoznacznie umieścić centralną ścieżkę pomiaru napięcia.
Środek X	Zachować dla symetrii i diagnostyki. Nie jest uniwersalnym wymogiem AddLumpedPort ani gwarancją poprawnego pomiaru prądu.
Kontakt z padami	Wewnętrzne krawędzie padów pokrywają granice X portu i obejmują całą jego szerokość.
Wnętrze szczeliny	Bez metalu przecinającego obszar wymuszenia.


Kod LumpedPort umieszcza pomiar napięcia centralnie poprzecznie, a pomiar prądu w środku długości. Ponieważ siatki E i H są przesunięte, sama obecność środkowej kotwicy nie dowodzi poprawności pomiaru. openEMS 0.37.0-rc3 documentation
Asercje przed utworzeniem portu:
- dokładna obecność granic X/Y i z=0 w ostatecznej siatce;
- identyczne granice przekazywane rezystancji i wymuszeniu;
- pełne pokrycie kontaktów przez pady;
- brak PEC wewnątrz szczeliny;
- zgodność zbioru aktywnych krawędzi Eₓ rezystora i źródła;
- miejsce na sondy również po obu stronach płaszczyzny Z.
Dla płaskiego portu oczekiwana liczba krawędzi Eₓ wynosi Nx × (Ny+1), nie Nx × Ny × Nz.
Test: natywny audyt źródła oraz porównanie Z/S11 dla zagęszczenia X/Y. Nie kopiować feed.nominal_bounds(): obecnie tworzy port objętościowy i odrzuca zerowy wymiar Z.
4. Final PCB-v0 mesh policy
Poniższe liczby są proponowanymi ustawieniami startowymi, a nie dowodem dokładności.
Oznaczenia: f_mesh — częstotliwość projektowania siatki, t — grubość laminatu.
Obszar	Ustawienie startowe
Powietrze poza detalami	krok ≤ c0 / f_mesh / 20
Laminat, XY	krok ≤ c0 / (f_mesh × sqrt(epsilon_r)) / 20
Laminat, Z	krok ≤ minimum z powyższej długości i t/4
Przez laminat	minimum 4 komórki
Szczelina portu	minimum 2 komórki X
Szerokość portu	minimum 2 komórki Y
Istotne ścieżki i szczeliny poza portem	startowo minimum 3 komórki przez wymiar, lokalnie
Wzrost sąsiednich komórek	cel 1,4, sprawdzany limit 1,5 w obie strony


Oficjalny przykład patcha stosuje λ/20 i cztery komórki przez laminat. Długość fali w niemagnetycznym podłożu skraca się przez sqrt(epsilon_r); nie należy używać w całym laminacie długości fali w powietrzu. openEMS 0.37.0-rc3 documentation
Implementacja: lokalne ograniczenia kroku, następnie grading. Globalna siatka kartezjańska przenosi zagęszczenie osi również poza sam detal — trzeba raportować koszt przed alokacją.
Test: końcowa kontrola stosunków sąsiednich kroków. Sam parametr ratio funkcji wygładzającej nie gwarantuje spełnienia limitu. openEMS 0.37.0-rc3 documentation
Krawędzie metalu: DEFER UNTIL CONVERGENCE STUDY
Na pierwszym kontrolnym modelu prostokątnym pozostawić dokładne krawędzie XY. Zapisać ograniczenie: nie zastosowano korekcji osobliwości krawędziowych.
Powód: obecnie priorytetem jest weryfikacja źródła. Jednoczesna zmiana kontaktu pad–port i reprezentacji krawędzi utrudniłaby interpretację błędów.
Przed uznaniem impedancji za zweryfikowaną porównać siatkę wyrównaną z 1/3–2/3 na prostym wzorcu. Oficjalny przykład linii mikropaskowej pokazuje, że zagęszczenie siatki wyrównanej nie musi zastąpić korekcji krawędzi. openEMS 0.37.0-rc3 documentation
Docelowo granice portu pozostają twarde; pozostałe cechy miedzi stają się wskazówkami do siatkowania, nie bezwarunkowymi liniami.
Powietrze i PML
- Startowo PML_8 na sześciu ścianach.
- Odległość od całej struktury do początku PML: domyślnie c0 / f_min_result / 4.
- Grubość PML dodać osobno; nie wliczać jej w wolną przestrzeń.
- W PML przyjąć stały krok w kierunku normalnym; wcześniej łagodne przejście.
- Domena obejmuje rzeczywiste wymiary płytki plus odstępy. f_max steruje krokiem, a dolna analizowana częstotliwość — domyślnym odstępem.
To punkt startowy dla otwartej struktury, nie konieczność identycznego odstępu w każdym zastosowaniu. Dopuszczalny jawny odstęp w metrach, ale wymaga porównania z większą domeną. Dokumentacja zaleca λ/4 dla struktur promieniujących i sprawdzenie wpływu oddalenia PML. openEMS 0.37.0-rc3 documentation
Zbieżność: najpierw 4→8 komórek Z oraz 2→4 przez port, potem osobno większa domena i PML 8→12. Porównywać zespolone Z i S11, nie tylko minimum wykresu dB.
5. Simulation-settings contract
Decyzja: wariant B — osobne pcb-simulation.json i PcbSimulationSettings.
Powód: ta sama płytka powinna mieć wiele eksperymentów bez zmiany danych fizycznych.
Minimalny zakres:
- częstotliwości wyników;
- excitation_center_hz, excitation_cutoff_hz;
- dodatnia impedancja odniesienia, domyślnie 50 Ω, konfigurowalna;
- kontrolki rozdzielczości, grading, limit komórek;
- odstępy domeny i liczba komórek PML;
- kryterium zaniku, limit kroków i liczba wątków;
- częstotliwość odniesienia strat materiału.
Bez reflektora, NF2FF i wymuszania mocy przyjętej 1 W. Z i S11 nie wymagają takiej normalizacji.
Częstotliwość siatki
Przyjąć jawnie:
f_mesh = excitation_center_hz + excitation_cutoff_hz

cutoff oznacza parametr fc funkcji SetGaussExcite, czyli nominalne odsunięcie od środka do granicy około −20 dB. Nie jest całkowitą szerokością pasma ani twardym odcięciem widma. Taki wybór f0+fc stosują oficjalne przykłady. openEMS 0.37.0-rc3 documentation
Dla v0 proponuję wymagać dodatniego zakresu wyników wewnątrz f0 ± 0,8fc; współczynnik 0,8 jest naszym marginesem jakości pobudzenia. Zmiana liczby punktów wynikowych nie zmienia siatki. Zmiana impulsu może ją zmienić.
Docelowe API
make_pcb_mesh(geometry, simulation_settings) -> PcbDomainMesh
Wynik: osie, rozmiar i koszt, granice PML, rozwiązane parametry polityki oraz audyt portu.
Obiekty PcbPlaceholderMesh* pozostają publiczne dla testów infrastruktury, lecz nie jako wejście solvera. PcbMeshAnchorPlan zachowuje obecne API; przyszły mesher nie powinien traktować wszystkich jego kotwic jako niezmiennych przy korekcji krawędzi.
6. Material-loss contract
Decyzja: dla wąskopasmowego v0 użyć epsilon oraz przewodności elektrycznej kappa obliczonej w jawnej częstotliwości odniesienia:
kappa = 2 × pi × f_loss_ref × epsilon0 × epsilon_r × loss_tangent

CSXCAD nazywa przewodność elektryczną kappa; sigma oznacza przewodność magnetyczną. Oficjalny przykład laminatu stosuje właśnie powyższe przeliczenie. openEMS 0.37.0-rc3 documentation
Konsekwencja: stałe są epsilon_r i kappa, a efektywny tangens strat wynosi:
tan_delta(f) = tan_delta_ref × f_loss_ref / f

Nie wolno opisywać tego jako stałego tangensa strat w całym paśmie. Obecny zapis kontraktu wymaga doprecyzowania.
Test: sprawdzić odtworzenie zadanych strat przy f_loss_ref oraz raportować ich odchylenie na krańcach pasma. Nie pomijać niezerowych strat bez komunikatu. Model bezstratny jest poprawny dla jawnego loss_tangent=0.
Miedź pozostaje AddMetal z płaskim polygonem; grubość i przewodność miedzi pozostają metadanymi. CSXCAD rozróżnia PEC i stratny conducting sheet. openEMS 0.37.0-rc3 documentation
7. Recommended ticket sequence
Zalecam następującą kolejność:
1. PCB-006B-A — ochrona interfejsów Z i niezerowego rozmiaru siatki.
2. PCB-006C — osobne ustawienia symulacji i obliczanie ograniczeń kroku, bez CSXCAD.
3. PCB-006D — pełna domena, grading, powietrze i PML, z końcowym audytem.
4. PCB-007A — laminat i płaski PEC w CSXCAD, najpierw geometria syntetyczna.
5. PCB-007B — port powierzchniowy i audyt kontaktów/krawędzi źródła.
6. PCB-008 — prepare i XML.
7. Kontrolny FDTD syntetycznej PCB oraz zbieżność portu/siatki.
8. PCB-009 — eksperyment z biblioteką Gerbera.
9. PCB-010 — importer i walidacja cech rzeczywistej płytki.
Przesuwam pierwszy FDTD przed importer. W przeciwnym razie błędy importu, siatki i źródła pojawią się jednocześnie.
8. Blockers before coding
Klasyfikacja	Ustalenie	Konsekwencja i test
BLOCKER przed fizyczną siatką	_merge(z) może usunąć dokładne 0.0. Odtworzyłem: miedź z=-5e-11 przechodzi walidację, plan zwraca (-0.0016, -5e-11).	Chronić interfejsy; solver musi mieć jednoznaczną wspólną płaszczyznę metalu i portu. Bez cichego przesuwania geometrii.
BLOCKER przed fizyczną siatką	Laminat 5e-11 m przechodzi walidację, po scaleniu ma jedną kotwicę Z. Placeholder zwraca (22,22,0) i cell_count=0.	Odrzucać nierozdzielalne interfejsy i każdą oś bez dodatniej liczby komórek.
FIX BEFORE PCB-007	Walidacja sprawdza końce portu, nie pełne styki ani wnętrze prostokąta źródła.	Dodać sprawdzenie pełnej szerokości kontaktów i braku zwarcia/obcego metalu.
FIX BEFORE PCB-007	Tolerancja geometrii dopuszcza różne, bliskie zera płaszczyzny Z.	Wprowadzić jawny kontrakt eksportu: dokładne wspólne Z albo błąd; nie zakładać, że tolerancja siatki rozwiązuje problem.
SAFE TO DEFER	Bounding boxy nie zabezpieczają przewężeń i szczelin polygonów.	Przed obsługą rzeczywistych Gerberów wymagana kontrola istotnych cech, bez kotwiczenia każdego wierzchołka.
SAFE TO DEFER	Korekcja 1/3–2/3.	Odroczyć do kontrolowanego porównania; wyniki pozostają unverified.
NOT A PROBLEM	Środki portu, normalizacja +X, oddzielna konfiguracja, fixture o pełnej szerokości.	Zachować; nie traktować ich jako dowodu poprawności fizycznej.
NOT A PROBLEM	Odrzucanie zbyt bliskich krytycznych kotwic portu.	Zachować 1e-10 m; rozszerzyć ochronę na interfejsy Z.


Dwa pierwsze przypadki sprawdziłem bez zapisu plików. Pozostałe ustalenia wynikają z przeglądu kodu; nie wykonywałem natywnego FDTD.
Ready for Light implementation: YES
Dokładny następny ticket: PCB-006B-A: preserve PCB Z interfaces and reject collapsed mesh axes.
Zakres: ochrona interfejsów Z, jawne odrzucenie ich kolizji, kontrola dodatnich wymiarów siatki i testy dwóch opisanych regresji. Bez zmiany tolerancji portu, polityki częstotliwościowej ani CSXCAD.
