# Plan rozwoju — analiza fizyczna rzeczywistych projektów PCB

**Status:** plan produktu i bramki odbioru. M0 — import i audyt danych źródłowych EasyEDA — był realizowany i testowany w poprzednich etapach; nie jest ponownym zadaniem. Pierwszy nowy etap to M1. Dalsze etapy nie są jeszcze zaimplementowane. Uzgodniony kierunek na 2026-10-25; każda bramka fizyczna wymaga rzeczywistego wyniku zweryfikowanego przez użytkownika na jego Windows. Dokument jest nadrzędną mapą kierunku; `migracja.md` służy do wznowienia pracy, a `todo.md` do śledzenia aktualnego zadania. Plan nie upoważnia do zmiany fizyki, danych ani konfiguracji bez jawnego wyboru użytkownika.

## 1. Konstytucja produktu — źródło prawdy

> **Pliki `.epro`, będące archiwami ZIP projektu EasyEDA Pro, zawierają wszystkie informacje istotne z punktu widzenia topologii PCB — także MPN komponentów. Dane te są podstawą modelu i nie wolno ich odtwarzać z Gerberów ani zgadywać. Elementy spoza projektu PCB, na przykład bryłę rdzenia magnetycznego i jego właściwości, użytkownik może dostarczyć osobno. Ta zdolność importu `.epro` została już dowieziona; rozwijamy ją i sprawdzamy kompletność jej udostępnienia, zamiast pisać importer na nowo.**

Znaczenie praktyczne: z `.epro` bierzemy rzeczywiste footprinty umieszczone na PCB, pady, otwory, przelotki, miedź, wypełnienia, położenia, warstwy, sieci, instancje komponentów, parametry CAD i powiązania identyfikacyjne (łącznie z MPN, jeśli są zapisane w konkretnym projekcie). Model pośredni musi zachować identyfikatory, relacje, atrybuty oraz pochodzenie danych także wówczas, gdy nie są jeszcze wykorzystywane przez solver. Geometryczne połączenie miedzi i deklarowana sieć CAD podlegają audytowi, nie ślepemu utożsamieniu.

**Rozróżnienie konieczne:** kompletność topologiczna archiwum nie oznacza kompletności fizycznej modelu urządzenia. MPN jest identyfikatorem części, a nie automatycznie dostępnym, wiarygodnym modelem elektromagnetycznym, SPICE, termicznym lub gwarancją parametrów. Nie domyślamy się krzywej B-H ferrytu, εr/tanδ laminatu, metalizacji via, strat przełączania, impedancji przewodów ani temperatury. Taki brak zostaje pokazany użytkownikowi, który wskazuje pomiar/kartę katalogową, przybliżenie albo świadome pominięcie. Brak danych nigdy nie jest zerem.

**Najważniejszy zasób:** gotowy, source-first importer `.epro` i geometria PCB pozostają fundamentem; antenty/anteny i pełnofalowy openEMS pozostają pełnoprawną częścią produktu.

## 2. Jak rozumiem intencję użytkownika

Użytkownik **projektuje realną płytkę w EasyEDA Pro**, otwiera jej `.epro`, uzupełnia jedynie informacje niedostępne w archiwum (np. magnetyk 3D, charakterystyki materiałów, warunki pracy, modele obwodu), wybiera zjawiska, które chce zbadać, i otrzymuje weryfikowalne wyniki fizyczne dla *tej samej konstrukcji*. Nie ma odrysowywania PCB, ręcznego przepisywania netlisty ani wykonywania transformatora w osobnym edytorze EM. Dodatkową prostą geometrię można stworzyć np. w Tinkercad i wczytać jako właściwy format geometrii (STL/OBJ/STEP tylko wtedy, gdy dany eksport rzeczywiście go dostarcza i jest możliwy do poprawnego zsiatkowania).

### Zastosowania równorzędne, bez zmiany tożsamości produktu

1. **Antena PCB i antena parametryczna:** bliskie i dalekie E/H, impedancja, S-parametry, dopasowanie, promieniowanie, kierunkowość, sprawność, prądy na promienniku, pole blisko metalu. Zachować dotychczasowy tor Quados/biquad oraz analizę anteny po imporcie `.epro`.
2. **Wielowarstwowe układy PCB:** E/H/D/B, rozkład i sprzężenie pól, fringing, prądy powrotne, potencjały, pojemności, rezonanse pasożytnicze. Nie wprowadzać limitu czterech warstw: liczba warstw wynika z `.epro`, a wykonalność z modelu i zasobów.
3. **Transformator/cewka planarna powyżej 1 MHz, także dużej mocy:** rozkład powierzchniowej gęstości prądu K [A/m] i ładunku ρs [C/m²] na wszystkich arkuszach miedzi, efekty current crowding/proximity/skin, sprzężenie, L/C, straty miedzi i dielektryka, zewnętrzny rdzeń i jego wpływ; później nieliniowość ferrytu, obciążenie i prostowanie. Nie należy zakładać, że fundamentalna częstotliwość przełączania wyznacza górny koniec pasma istotnych harmonicznych.
4. **PCB jako źródło emisji:** analiza kiedy ścieżki/uzwojenia promieniują, wpływ zboczy, harmonicznych, prądów wspólnych, przewodów i otoczenia. Wynik promieniowania ma obejmować wyraźnie granicę modelowanej konstrukcji; nie udawać pełnego badania EMC bez kabli/obudowy, jeśli ich nie modelowano.
5. **Urządzenie z rzeczywistym obwodem:** wskazanie zacisków uzwojeń, sterowania, odbiorników, prostownika, obciążenia i źródeł; uzyskanie przebiegów V/I oraz zgodnych z nimi pól. Uproszczenia są elementem metody, ale są jawne i zatwierdzone.

Oczekiwany tryb pracy: **projekt CAD → inspekcja/uzupełnienie → wybór rodzaju analizy i dokładności → preflight kosztu i braków → solve → wyniki z jakością, jednostkami i ograniczeniami → porównanie wariantów.** Zmiana sposobu prezentacji nie uruchamia ponownie solvera. Tryb E/H przywarstwowych nie zastępuje tradycyjnych wykresów antenowych.

## 3. Stan zastany: czego nie implementujemy od nowa

- **Dostarczone w kodzie:** import `.epro` jako ZIP, `project.json`, `PCB/*.epcb`, `FOOTPRINT/*.efoo`; resolver instancji komponentów, padów, footprintów, source bindings, fizycznego stackupu i multi-layer; import bez pośredniego Gerbera; PTH/źródła/materiały w istniejącym, zadeklarowanym podzbiorze. Istnieją PCB GUI dla Windows, PREPARE-ONLY, adapter openEMS, tryb przestrzennych E/H, raporty offline i manifesty. MPN może istnieć w źródle — **do sprawdzenia, czy jest już zachowany i wystawiany przez wszystkie warstwy pipeline'u**.
- **Zaimplementowane nie oznacza przyjęte fizycznie:** natywna walidacja wyników nadal ma luki (port, temporalna zbieżność, odzyskanie pola z niedokończonego przebiegu). Dokumentowane przypadki importu są ograniczone do określonych dialektów/rekordów. Nie deklarować bezwarunkowej obsługi wszystkich dowolnych `.epro` i pełnych schematów.
- **Nie ma jeszcze:** wiarygodnych map E/H/D po obu stronach każdej warstwy, K/ρs, pełnego katalogu materiałów i brył rdzenia, wieloportowego sprzęgnięcia SPICE, kompleksowej ekstrakcji C/L ani uzasadnionych strat dynamicznych transformatora; nie nazywać ich gotowymi.
- **Błąd projektu prezentacji:** istniejąca maska lokalnego halo metalowego w `solvers/pcb_fields.py` zamienia w przetworzonych E/H próbki blisko miedzi na NaN. Surowe HDF5 pozostaje nienaruszone, ale maski nie wolno przenosić na tryb current crowding. Rozdzielić surowe próbki, maskę geometrii, wiarygodność składowych i warstwę wizualizacji. To odpowiedzialność postprocessingu i semantyki pól, a nie samego rysowania.
- **Brak arbitralnej granicy czterech warstw:** limit Fairbeam `max_planes=4` dotyczy tamtego kodu demonstracyjnego. W naszym importerze nie ma założenia dokładnie czterech warstw; ograniczenie budżetem komórek, pamięcią i jakością wyników jest jawne.

Punkty odniesienia w repozytorium: [AGENTS.md](AGENTS.md), [migracja.md](migracja.md), [docs/pcb-easyeda.md](docs/pcb-easyeda.md), [docs/pcb-copper-surfaces.md](docs/pcb-copper-surfaces.md), [docs/pcb-current-charge-goal.md](docs/pcb-current-charge-goal.md), [docs/architecture.md](docs/architecture.md), [goal.md](goal.md).

## 4. Architektura integracji — wspólne odpowiedzialności, osobne silniki

### 4.1. Jeden kanoniczny model konstrukcji

- **Źródło i pochodzenie:** niezmienialna migawka oryginalnego `.epro`, suma kontrolna, wersja importera, mapa rekordów źródłowych i nieobsługiwanych elementów. Możliwość ponownej inspekcji bez solve. Oryginalny plik i identyfikatory nie tracą informacji.
- **Geometria/topologia:** fizyczne warstwy, sieci, przewodniki, izolacje, pad/via, połączenia, komponenty i ich MPN/atrybuty; opcjonalne bryły zewnętrzne z jawnie podanym układem współrzędnych, jednostkami, orientacją, szczelinami i relacjami mechanicznymi. Wymagać zgodności obwodu CAD z modelem przewodnictwa EM lub komunikować różnice.
- **Materiały i modele:** parametry zależne od częstotliwości, temperatury i pól tam, gdzie to konieczne; rozdzielenie danych katalogowych, pomiaru, domysłu użytkownika oraz modelu idealizowanego. Referencja do MPN nie jest automatycznym modelem solvera.
- **Porty i stany pracy:** nazwane terminale z parą pad/net/położenie/biegunowość, pobudzenie, terminacja, referencja masy i fazy; układy wieloportowe, pełne różnicowe zasilanie. Porty nie są wybierane heurystycznie od nazwy footprintu.
- **Wariant modelu:** wersjonowany kontrakt opisujący świadome uproszczenia (PEC/sheet/objętościowa miedź, idealny vs stratny dielektryk, liniowy vs nieliniowy rdzeń, element skupiony vs bryła, środowisko otwarte/ekranowane). To część danych wejściowych, a nie niejawna konfiguracja wizualizacji.

### 4.2. Warstwa analityczna i wyjście

Każdy adapter otrzymuje model kanoniczny i konfigurację żądanej analizy, po czym zwraca **surowe dane natywne i typowane wyniki**: E, H, D, B, J objętościowe, K powierzchniowe, ρs, prądy/napięcia terminali, macierze C/L/Z/S, straty, pola dalekie. Nie wymagamy, by każdy solver umiał policzyć wszystko. Każdy wynik niesie geometrię warstwy/strony, pozycję próbkowania, pasmo, fazę, konwencję, skalowanie, jednostki, normalizację, metodę, parametry materiałów, siatkę, status wiarygodności, zakres zaniedbań, provenance i możliwość powrotu do próbek natywnych.

Oddzielić odpowiedzialności: **importer/semantyka CAD → model fizyczny i definicja portów → profil/adapter solvera → walidacja numeryczna i interpretacja fizyczna → zapis danych → raport offline/GUI**. Aplikacja Windows pozostaje jedną aplikacją, nie uruchamia samowolnie kilku silników ani nie kopiuje odpowiedzialności solvera do raportu.

### 4.3. Integracja wielosolverowa, dopiero gdy daje przewagę

1. **openEMS zostaje podstawowym solverem pełnofalowym, zwłaszcza dla anten:** istniejący adapter, FDTD, NF2FF, porty, HDF5, dumpy E/H/D/B i rot(H). Analiza przywarstwowa wymaga osobnej walidacji sposobu próbkowania Yee: żadnej iluzji „E nad metalem” z automatycznej interpolacji przez nieciągłość.
2. **Palace — kandydat do niezależnego adaptera elektrostatyki/magnetostatyki i MES 3D:** eksport modelu do siatki objętościowej + jego konfiguracji, odczyt macierzy pojemności/indukcyjności oraz pól. Nie zakładać zgodności portów/materialnych warunków brzegowych bez przeprowadzenia kontroli. Uwaga wdrożeniowa: **brak oficjalnie wspieranego natywnego Windows**; żaden krok fundamentu nie może wymagać WSL lub przeniesienia całego GUI. Adapter opcjonalny i warunkowy; najpierw studium wykonalności natywnej instalacji lub oddzielnego, dobrowolnego środowiska.
3. **Fairbeam — wzorzec postprocessingu, nie drugi obowiązkowy runtime:** kod rejestracji częstotliwościowej rot(H) na metalowych sheetach, odwzorowania geometrii i fazorów. Nie przejmujemy jego normalizacji 0–1000 jako wartości bezwzględnej ani limitu czterech płaszczyzn; poprawność w A/m wymaga osobnego sprawdzenia szerokości dualnej komórki.
4. **PyPEEC — ewentualny adapter magnetoquasistatyczny do prądów/strat w wielowarstwowym uzwojeniu:** użyteczne AC, prądy i magnetyka, lecz **bez efektów pojemnościowych i dielektryków**, geometrię sprowadza do voxel grid. Nie może być jedynym silnikiem transformatora z fringing/ładunkiem.
5. **GetDP + Gmsh / Elmer — kandydaci do nieliniowego rdzenia i strat AC:** użyć istniejących sformułowań MES i obsługi sprzęgnięcia obwodowego, nie pisać własnego solvera. Wymagają weryfikacji formatów, źródeł, modeli ferrytu, zgodności warunków i środowiska Windows. **Nie oznacza** to obietnicy kompletnego nieliniowego solvera jako etapu pierwszego.
6. **ngspice albo Xyce + scikit-rf — obwód i sprzężenie:** EM liczy liniowy wieloport dla określonego zakresu częstotliwości i stanu materiałów, scikit-rf aproksymuje Z/Y/S i generuje pasywny/stabilny model zastępczy do SPICE; SPICE liczy PWM, tranzystory, prostowniki, obciążenia. Wyniki prądów/napięć harmonicznych mogą następnie posłużyć do liniowej superpozycji pól EM dla zgodnych terminali. **Nieliniowy magnetyk wymaga osobnego modelu sprzężenia**; nie przepuszczać go niejawnie przez stałą macierz S.
7. **Gmsh / narzędzia CAD / ParaView:** siatkowanie i diagnostyka 3D jako opcjonalne elementy infrastruktury; raport HTML i GUI nie mogą zależeć od ręcznej obsługi ParaView. Rozdzielić tolerancję geometrii, siatki i dokładność materiałów.

### 4.4. Reguły współdziałania modeli

- Port i terminal ma identyfikator niezależny od solvera, związany z **konkretnymi padami/sieciami**, biegunowością, jednostką i układem współrzędnych. Każdy adapter dowodzi, jak go odwzorował. Różnica liczby portów i konfiguracja referencyjnych końcówek muszą być jawne.
- Wspólna migawka konstrukcji i modelu materiałów, ale **oddzielne** siatki; FDTD i MES nie muszą używać identycznych elementów. Mapowanie wyników między siatkami musi zachować wielkość fizyczną i informację o błędzie, a porównanie nie może mylić interpolacji do obrazu z obliczeniem.
- Moc zasilająca, bilans energetyczny, prądy i fazy muszą być zgodne w całym łańcuchu. Nie normalizować „do zgodności”. C/L/S z modelu o zmienionej geometrii nie są porównywalne bez jawnego śladu.
- Wyniki natywne archiwizować jako źródłowe. Przerwane obliczenie z pustymi danymi pól pozostaje niekompletne, nie „zero E”. Raport i porównania działać offline z manifestu, również po zmianie UI.
- Raporty jako **widoki danych**: (a) antenowy, (b) bliskie pola przestrzenne, (c) `copper-faces` dla wszystkich warstw z E/H/D, K i ρs bez narzuconych wykresów S11/SWR, (d) C/L/straty/obwody, (e) emisja; te same wyniki mogą być użyte w różnych widokach. Nie usuwać S11 i NF2FF z produktu dlatego, że nie są pokazywane w widoku miedzi.

## 5. Polityka modeli, przybliżeń i interakcji z użytkownikiem

Wybór modelu nie jest błędem — **to część inżynierii**. Dla każdej analizy program powinien pokazać: (1) co rzeczywiście modeluje, (2) co pominął, (3) na jakiej podstawie określił materiał, (4) jakiego typu błędu należy oczekiwać lub czy wielkość błędu jest nieznana, (5) jakie dane mogą zmienić wniosek. Statusy: `measured/input`, `derived`, `assumed`, `omitted-by-user`, `unsupported`, `not-validated`; **nie używać tych samych etykiet jako stwierdzenia dokładności**.

Proponowane pytania programu tylko wtedy, kiedy wpływają na wynik: „Czy do tej analizy pojemności wolno pominąć soldermaskę?”, „Czy wystarczy liniowy model rdzenia i zakres, w którym brak nasycenia?”, „Czy potrzebne są straty AC, czy na tym etapie wystarczy prąd wypadkowy idealnego sheetu?”, „Czy zewnętrzne kable mają znaleźć się w modelu emisji?”, „Czy model dielektryka stały w paśmie harmonicznych wystarczy, czy potrzebna jest zależność od częstotliwości?”. Każda decyzja jest zachowana w manifeście i odtwarzalna.

W GUI przed solve: orientacyjny rozmiar siatki, przestrzeń dyskowa, wymagane pasmo, potencjalny wzrost kosztu, brak materiałów i możliwe świadome uproszczenia; bez niezweryfikowanych szacunków czasu użytkownika. Dwa możliwe tryby: szybka **analiza orientacyjna** z wyraźnym zakresem uproszczeń albo **analiza projektowa** ze sprawdzeniem zbieżności. Bez automatycznego redukowania dokładności dla uzyskania wykonalności.

## 6. Etapy implementacji i rzeczywiste bramki odbioru (kolejność)

**Zasada bramkowania:** kolejny etap uruchamiamy dopiero, gdy dostarczony wynik z poprzedniego etapu jest użyteczny w jego zamierzonym zakresie; jeśli nie, poprawiamy ogólną warstwę odpowiedzialną za błąd lub wybieramy jawny inny model. Nie kodujemy pod nazwę testowego projektu. Sprawdzenia poniżej są **oceną wyników przez użytkownika**, nie tylko zestawem testów jednostkowych. Tolerancje liczbowe ustalamy z nim dla każdego pomiaru/zakresu zastosowania; nie dopasowujemy progu po zobaczeniu wyników.

### M0. Import i audyt .epro — istniejący fundament, bez ponownego audytu

**Wykonano już wcześniej:** audyt dużego archiwum `gerbs/test_psu/test_psu.epro`, kontrolę ZIP/CRC i powiązań bibliotek, 291/291 instancji komponentów oraz 906/906 powiązań PAD_NET, 288 jawnych footprintów PCB i 3 przypisanych przez Device, 257 bibliotek zewnętrznych i 34 osadzonych. Kod importu D4 i testy na rzeczywistych projektach już istnieją. PSU jest większy od planowanych przykładów. Nie pisać importera na nowo ani nie nakazywać powtórzenia tych samych testów. Źródła: `docs/pcb-easyeda.md`, `todo.md`, wcześniejsze wpisy `history.md`.

**Granica potwierdzenia historycznego:** audyt PSU zakończył się **identity PASS**, natomiast **physical canonical UNSUPPORTED** dla pełnego PSU w ówczesnym zakresie: pusty rekord NET, biblioteki footprintów 1.3/1.7, slots i złożone wypełnienia. Jest to odrębne od 291/906: liczby potwierdzają integralność referencji, nie fizyczną łączność wszystkich sieci PSU ani jego gotowość do FDTD. Projekt `spirala.epro` przeszedł canonical/contact audit w obsługiwanym profilu. Nie przekuwać historycznego ograniczenia pełnego PSU w ogólną blokadę dalszego rozwoju ani nie rozbudowywać parsera dla nieużywanych przypadków.

**Wniosek operacyjny:** M0 nie wymaga nowych prac ani odbioru od użytkownika. Jeśli kiedyś konkretna analiza wykaże brak odczytanego atrybutu (np. MPN) lub nierozpoznany prymityw, naprawić wskazaną odpowiedzialność ogólnego importera tylko wtedy, gdy jest to konieczne. Nie przeprowadzać ponownego całościowego audytu PSU.
### M1. Materiały, komponenty, zaciski, bryły zewnętrzne i preflight

**Kod:** wykorzystać już istniejący import i profile materiałów PCB; dołożyć tylko brakujące fizyczne parametry, zewnętrzną bryłę rdzenia z kontrolą jednostek/położenia, named terminal pairs, odpowiednie źródła i obciążenia. MPN może służyć odsyłaczowi do konkretnego modelu, ale nie należy ponownie audytować wszystkich identyfikatorów ani zgadywać parametrów. Raport „co uwzględniono/co pominięto”, z oceną kosztu siatki.

**Użytkownik sprawdza:** w podglądzie geometrii potrafi wskazać oba uzwojenia i ich końce, rdzeń, szczelinę, materiał, εr/tanδ, grubość miedzi oraz ewentualne idealizacje komponentów; PREPARE-ONLY nie gubi połączeń i nie wybiera portu na podstawie MPN.

**Bramka:** można jednoznacznie zatwierdzić *kompletny do danej analizy* model bez ukrytego domyślania; rdzeń nie musi jeszcze wpływać na pole, ale geometria i model muszą być poprawnie przypisane.

### M2. Ochrona i fizyczne domknięcie toru antenowego

**Kod:** zachować pełnofalowe openEMS i istniejącą obsługę Quados/biquad oraz anten PCB; poprawić ogólne kryteria zbieżności, diagnostykę źródła, normalizację i raport NF2FF bez ingerencji w historyczne wyniki. Wprowadzić wersję spójnego kontraktu portów i weryfikacji mocy. Część pracy może wykorzystać już istniejące narzędzia.

**Użytkownik sprawdza:** uruchamia znaną antenę parametryczną i realną antenę PCB z `.epro`; ocenia geometrię, pobudzenie, stabilność widma, pola, S11/impedancję i charakterystykę daleką. W miarę możliwości odnosi się do znanych wyników/pomiarów, a także do siatki o różnej gęstości.

**Bramka:** brak regresji dotychczasowej anteny, czytelna rozbieżność port/bilans rozwiązana lub jawnie oznaczona jako ograniczenie blokujące tylko zależne od niej wielkości. NF2FF zachowuje prawidłową powierzchnię otaczającą całą konstrukcję.

### M3. Wiarygodne próbki pól przy sheetach bez zakrywania zjawiska

**Kod:** odseparować HDF5 i zespolone pola natywne od maski prezentacyjnej; zbadać `dump_mode=0/1/2` i położenia Yee dla E/H/D/rot(H), PEC i conducting sheet. Dla N warstw rejestrować i identyfikować obie strony każdej warstwy (2N widoków), różne ośrodki ε, granice siatki, pozycje rzeczywistych próbek i ich jakość. Próbki w pobliżu portu, metalu i krawędzi nie znikają bez śladu.

**Użytkownik sprawdza:** na prostym kondensatorze dwóch okładek, jednej warstwie i kilku sprzężonych warstwach porównuje E/H/D nad i pod metalem, symetrie, znaki i wpływ zagęszczenia siatki; ogląda realny wynik oraz warstwy maskujące **oddzielnie**.

**Bramka:** wyniki z obu stron nie są skutkiem mieszania pól przez interpolację; poprawne zachowanie granic, fazy i jednostek. Jeśli openEMS nie umożliwia wiarygodnego odzyskania wymaganych granic, zmienić metodę/solver do tej wielkości, nie udawać pomiaru odległymi przekrojami.

### M4. Mapa prądu i ładunku — kluczowy rezultat PCB

**Kod:** obliczać `K_net = n × (H_plus − H_minus)` w A/m i `rho_s_net = n · (D_plus − D_minus)` w C/m², z właściwą stroną, epsilon i fazą; niezależnie sprawdzić rot(H) z dump type 13 jako metodę porównawczą, z przeliczeniem na powierzchnię zgodnie z Yee. Dla idealnego PEC można diagnostycznie pokazywać wielkości przypisane każdej stronie matematycznego sheetu, **nie** nazywając ich niezależnymi prądami realnej folii. Wprowadzić kontrolę ciągłości ładunku i bilansu prądów poza portami, metryki całkowe, zbieżność i prezentację granic rozdzielczości.

**Użytkownik sprawdza:** rzeczywisty wielowarstwowy transformator bez skomplikowanej elektroniki — mapy K/ρs na wszystkich warstwach, zmiana koncentracji prądu i fringing przy zmianie odstępu, geometrii i częstotliwości; różnice pól po obu stronach wynikają ze sprzężenia. Prosty wzorzec prądu/kondensatora stanowi dodatkowe odniesienie. Ogląda wyniki ilościowe, nie tylko mapy znormalizowane do 100%.

**Bramka:** K i ρs są odtwarzalne, poprawne wymiarowo i dostatecznie stabilne siatkowo dla wskazanej decyzji konstrukcyjnej; singularności krawędziowe nie są interpretowane przez maksimum pojedynczej komórki. Bez tej bramki nie deklarować rozwiązania current crowding ani charge density.

### M5. Pojemności, dielektryki i wpływ rdzenia — wybór silnika na podstawie dowodu

**Kod:** w pierwszej kolejności pojemności i rozkłady D/E między conductor nets, uwzględniając jawne εr, straty i zależność od częstotliwości tam, gdzie solver je obsługuje. Ocenić adapter MES (Palace lub inne narzędzie działające w zaakceptowanym środowisku) dla macierzy C i L oraz bryły rdzenia; nie blokować reszty brakiem natywnego Palace. Zapisać identyczne źródłowe geometrie, terminale i różnice założeń.

**Użytkownik sprawdza:** kondensator płaski lub prosta geometria z wynikiem analitycznym, potem transformator z rdzeniem i bez, różne przekładki: pojemności między uzwojeniami, pole fringing i zależność od εr; odniesienie do pomiaru L/C, jeśli ma przyrząd lub wiarygodne dane.

**Bramka:** wartość C/L, zależność od geometrii i przyjęta dokładność są wiarygodne; powstaje wymienny tor wynikowy albo udokumentowane ograniczenie i decyzja o narzędziu alternatywnym.

### M6. Rzeczywista miedź: AC, skin/proximity, straty

**Kod:** dodać *odrębny* model miedzi o skończonej przewodności/grubości lub solver magnetoquasistatyczny/MES dla J [A/m²], strat przewodzenia i temperatury odniesienia. Porównać zgodność wypadkowej K z całkowaniem J po grubości. Rozstrzygnąć zakres przydatności `ConductingSheet`, a nie obliczać strat z niezweryfikowanego K przy dowolnej grubości.

**Użytkownik sprawdza:** proste przewodniki o znanej rezystancji DC/AC, różne grubości i odstępy uzwojeń, transformator planarny przy >1 MHz; sprawdza trendy i, jeśli możliwe, opór AC lub straty zmierzone dla wybranej częstotliwości.

**Bramka:** czytelne i zbieżne oszacowanie strat w zadanym modelu; odróżnienie pól i prądu netto idealnego sheetu od rzeczywistego przekroju miedzi. Przy braku wiarygodnego modelu etap pozostaje ograniczony, lecz M4 jest nadal przydatny.

### M7. Obwód: wieloport i realne warunki pracy

**Kod:** wieloportowy model EM/terminali, ekstrakcja liniowego pasywnego odpowiednika w szerokim zakresie harmonicznych, kontrola stabilności/pasywności i dopasowania; adapter scikit-rf + wybrany ngspice/Xyce. Łączenie uzwojeń ze źródłem PWM, tranzystorami, prostownikiem, kondensatorami i obciążeniem bez ręcznego przepisywania PCB; stosować kompatybilne modele SPICE podane przez użytkownika. Rekonstrukcja harmonicznych E/H/D/K/ρs przez superpozycję **tylko w liniowym zakresie materiałów**.

**Użytkownik sprawdza:** znany obwód zasilanie–transformator–prostownik–obciążenie: napięcia i prądy po obu stronach, przekładnia, fazy, rezonanse, bilans mocy, wpływ obciążenia; różnica między czystym idealnym modelem obwodu i modelem z pasożytami PCB. Przy nieliniowym rdzeniu ten etap wymaga jawnego uproszczenia lub M8.

**Bramka:** model odtwarza zachowanie terminali w zadanym paśmie i pasywności, nie generuje energii, a przeniesienie pobudzeń do pól ma spójne oznaczenie portów i faz.

### M8. Nieliniowy magnetyk i sprzężenie wielofizyczne (warunkowo)

**Kod:** adapter modelu B-H, strat ferrytu, temperatury i iteracji ze źródłem/obwodem; w pierwszym zakresie wybrana metoda GetDP/Elmer lub równoważna, **po** weryfikacji, czy może korzystać z naszej geometrii i potrzebnych terminali. Model liniowy pozostaje świadomą, szybszą opcją.

**Użytkownik sprawdza:** pomiar/charakterystyka materiału, wyraźna różnica między nienasyconym i nasyconym rdzeniem, prąd magnesujący, straty i wpływ szczeliny; porównuje wynik z rzeczywistymi danymi lub znanym modelem producenta.

**Bramka:** można uzasadnić nieliniowość i bilans; jeśli nie, raport zatrzymuje się na liniowej analizie i podaje warunki, w których wynik nie może opisywać urządzenia.

### M9. Emisja i zachowanie antenowe fizycznego układu

**Kod:** zachować i rozszerzyć NF2FF openEMS, uwzględniać właściwe otwarte granice, zewnętrzne przewody/obudowy jako *opcjonalne lecz jawne* bryły i drogi prądu. Wykorzystać harmoniczne pobudzeń z M7 dla analizy liniowej; porównywać pola i widma wraz z częstotliwościami.

**Użytkownik sprawdza:** znana antena PCB (regresja z M2) oraz transformator/układ z oznaczonymi przewodami; charakterystyka kierunkowa, promieniowana moc, wrażliwość na geometrię przewodów i ekrany. Tam, gdzie można, porównanie pola bliskiego z sondą lub pomiarem EMC.

**Bramka:** wynik antenowy nadal poprawny, dla układu PCB zakres geometryczny emisji jest jawny; nie przedstawiać idealizacji gołej płytki jako emisji kompletnego urządzenia.

### M10. Spójne GUI, raporty i porównywanie projektów

**Kod:** jeden Windows GUI, profile analiz z widocznymi zależnościami i modelami; wspólny viewer z warstwami, stronami, częstotliwością, fazą, widokiem 3D, normalizacją; osobne raporty antenowe, powierzchniowe, C/L, obwodowe i emisji. Porównanie wariantów fizycznych o zgodnych pobudzeniach, skalach i parametrach; replay offline bez zmiany danych.

**Użytkownik sprawdza:** przechodzi od tego samego `.epro` do kilku analiz, widzi dokładne źródła danych i pominięte zjawiska, zapisuje/porównuje raporty i otwiera je bez instalowania narzędzi numerycznych. Wybór wizualizacji nie usuwa ani nie przelicza niepotrzebnie natywnych próbek.

**Bramka:** rozwiązanie jest użyteczne inżyniersko i zachowuje stare anteny/raporty oraz pełną historię wyników. GUI nie dopowiada fizyki, której solver nie policzył.

**Kolejność praktyczna:** na bazie zrealizowanego wcześniej M0 zaczynać od M1, następnie M2–M4 jako rdzeń produktu, potem M5 i M6; M7 dopiero po wiarygodnych portach i wieloporcie; M8 warunkowe; M9 może mieć wczesne regresje antenowe wraz z M2, lecz pełna emisja urządzenia po M7. M10 rozwija się inkrementalnie, nie trzeba odkładać całej ergonomii do końca.

## 7. Ryzyka i alternatywy bez udawania wyniku

| Co może się nie udać | Dlaczego | Działanie i decyzja użytkownika |
| --- | --- | --- |
| Import nieznanego rekordu `.epro`, brak MPN w udostępnionym modelu | Braki dialektu, parser nie zachowuje wszystkich pól, CAD może nie zawierać danego atrybutu | Audyt oryginału i coverage; zachować surowe rekordy, poprawić parser tej klasy semantyki, nie zgadywać z Gerbera; brak MPN jawny |
| FDTD przy cienkiej miedzi myli wartości jednostronne | Siatka Yee i interpolacja na skoku E/D, przewodnik PEC vs sheet | Porównać tryby dumpu i warunki Maxwella; ewentualnie solver MES/BEM dla tej wielkości; nie interpolować z arbitralnego 1 mm |
| Current crowding przy ostrych krawędziach pozornie rośnie bez granic | Osobliwości idealnych krawędzi i za mała siatka | Pokazywać zbieżność i całki po ustalonym obszarze zamiast tylko piku |
| Nie ma wiarygodnych strat miedzi | Idealna powierzchnia PEC nie modeluje J przez grubość ani skin effect | Dodać objętościowy model / model powierzchniowo-impedancyjny po walidacji; wyniki K netto pozostają jawnie inną wielkością |
| Niezidentyfikowany dielektryk lub ferryt | Brak εr/tanδ vs f, μ(f), strat, B-H, temperatury i szczeliny | Prosić o kartę/pomiar albo jawnie przyjąć model stały/liniowy w ograniczonym paśmie; oznaczyć zasięg ważności |
| Rdzeń z STL/STEP ma błędne wymiary, styk lub nieszczelną siatkę | CAD i mesher stosują inne jednostki/topologie | Preflight geometrii i materiału; jawny wybór sposobu naprawy; bez automatycznego domknięcia szczeliny |
| Brak portów lub zbyt silna idealizacja źródła | Nie można określić dróg prądów i zasilania bez poprawnej referencji | Wybór padów i terminali; analiza budżetu mocy i konsekwentnej referencji fazy |
| S-parametry poza badanym pasmem i niepasywna aproksymacja | Harmoniczne PWM wychodzą poza sweep, fit może naruszać fizykę | Wyliczyć wymagane pasmo z przebiegu; kontrola stabilności i pasywności; ograniczyć zakres lub poszerzyć obliczenia |
| Brak natywnego Palace na Windows | Upstream nie wspiera oficjalnie kompilacji natywnej Windows | Palace opcjonalny, nie bramka M0–M4; sprawdzić wykonalność lub alternatywę, bez obowiązkowego WSL |
| Rozbieżne modele FDTD/MES/PEEC | Różne założenia, geometrie, materiały i warunki | Nie scalać nieporównywalnych liczb; wersjonować modele i ustalać obszar wspólnej weryfikacji |
| Liczba warstw i komórek przerasta zasoby | Objętość domeny, PML, wybrane pola, liczba monitorów i pasmo | Preflight budżetu; wybór mniejszego *udokumentowanego* zakresu, adaptacja siatki albo inny solver; bez limitu 4 zakodowanego w produkcie |
| Antena urządzenia zależy głównie od kabli i obudowy | PCB jest tylko częścią źródła promieniowania | Zaproponować jawny model kabli/obudowy lub ograniczyć wniosek do gołego PCB |
| Dane nie są dostępne z przerwanego solve | Sam HDF5 z atrybutami częstotliwości nie zawiera żadnych prób | Utrwalić `incomplete` i recovery wyłącznie dla realnie zapisanych danych; nie podawać pól zerowych |

**Licencje:** przed użyciem kodu Fairbeam / innego solvera sprawdzić licencję i warunki łączenia oraz dystrybucji; inspiracja algorytmem lub adapter IPC nie jest automatycznie zgodą na kopiowanie implementacji do projektu. Równie ważne jest odróżnienie narzędzia wbudowanego od oddzielnego procesu.

## 8. Co jest potrzebne od użytkownika, a co nie

Nie jest potrzebny kolejny `.epro` do audytu importu ani ponawianie testów PSU. W repozytorium są już sprawdzone przykłady. Do M1: dla wybranego fizycznego przypadku potrzebna jest wiedza o konkretnym rdzeniu, jego pozycjonowaniu, brakujących parametrach laminatu oraz terminalach uzwojeń. Do etapów późniejszych: karta materiału magnetycznego/εr w interesującym paśmie, schemat sterowania i obciążenia, opcjonalnie pomiary C/L/Rac, V/I, pola lub emisji. Nie potrzebujemy od razu wszystkich danych do wszystkich modeli.

Po każdym kamieniu milowym użytkownik otrzymuje: **konkretne wyniki, instrukcję ich obejrzenia, listę różnic i uproszczeń, status `accepted / needs-model-change / unavailable` oraz pytanie, czy zakres dokładności wystarcza do następnego kroku.** Nie oczekujemy, że „zielone” testy kodu zastąpią jego ocenę konstrukcyjną.

## 9. Pierwsza następna praca — M1, bez ponownego audytu importu

**M1: modele fizyczne uzupełniające istniejący projekt PCB.** Wykorzystać dotychczasowy `.epro`, istniejące odwzorowanie komponentów, miedzi i stackupu. Dołożyć tylko to, czego konkretna analiza rzeczywiście wymaga: materiały dielektryków i magnetyków, opcjonalną zewnętrzną bryłę rdzenia z pozycjonowaniem, wskazanie elektrycznych terminali uzwojeń oraz pobudzenia i obciążenia. Pierwszy rzeczywisty odbiór użytkownika: PREPARE-ONLY i podgląd zgodności fizycznej konstrukcji, przypisanych materiałów i terminali, wraz z jawnymi uproszczeniami. Nie wykonywać na nowo audytu liczby instancji i PAD_NET dużego PSU.

**Równoległe zobowiązanie:** zachować istniejący solver antenowy openEMS, przygotować referencję M2 i po fizycznym preflight rozwijać przywarstwowe próbki E/H/D oraz K/ρs w M3/M4. Żadnego nowego solvera wyłącznie dlatego, że istnieje; każdy adapter musi wnosić określoną brakującą wielkość i mieć ocenę wyniku.
## 10. Źródła zewnętrzne — punkty startowe, nie obietnice zgodności

- openEMS: [field dumps i problem interpolacji Yee](https://docs.openems.de/en/latest/octave/autogenerated/CSXCAD/AddDump.html), [NF2FF](https://docs.openems.de/en/latest/concepts/nf2ff.html), [openEMS](https://openems.de/).
- Fairbeam: [repozytorium](https://github.com/ismailakdag/fairbeam), [konkretny kod map prądu](https://github.com/ismailakdag/fairbeam/blob/main/python/fairbeam/fields.py).
- Palace: [dokumentacja i rodzaje analiz](https://awslabs.github.io/palace/stable/quick/), [status Windows](https://awslabs.github.io/palace/stable/faq/).
- PyPEEC: [możliwości i jawne ograniczenia](https://pypeec.otvam.ch/).
- GetDP/Gmsh: [tutorial sprzężenia obwodowego i MES](https://getdp.info/dev/doc/texinfo/getdp.html), [Gmsh](https://gmsh.info/).
- scikit-rf: [Vector Fitting i model SPICE](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.vectorFitting.VectorFitting.html), [pasywność/eksport](https://scikit-rf.readthedocs.io/en/latest/_modules/skrf/vectorFitting.html).
- Narzędzia docelowe obwodu: [ngspice](https://ngspice.sourceforge.io/), [Xyce](https://xyce.sandia.gov/).

**Definicja sukcesu całego programu:** na importowanym `.epro` użytkownik rozpoznaje dokładnie swoją topologię, świadomie opisuje brakującą fizykę, otrzymuje użyteczne, ilościowe i jawnie ograniczone wyniki elektromagnetyczne/obwodowe, potrafi je skonfrontować z konstrukcją i powtórzyć analizę; funkcje antenowe nadal działają i pozostają rozwijane. Nie obiecujemy „cyfrowego bliźniaka 1:1”, lecz wiarygodne i kontrolowalne modele fizyczne.
