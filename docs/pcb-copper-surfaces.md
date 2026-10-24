# PCB — dwa tryby pomiaru i raportu (specyfikacja, 2026-10-24)

Status: **cel zatwierdzony przez użytkownika; niezaimplementowany**. Stan bazowy: main ba323c3. Nie zmieniono kodu ani nie uruchomiono FDTD.

## Cel i zakres
W istniejącej aplikacji Windows użytkownik wybiera **spatial-eh** (dotychczasowe przekroje xy_air, xz_feed, yz_feed) albo **copper-faces** (XY, każda fizyczna warstwa miedzi oddzielnie, obserwacja z +Z i -Z). Zachować poprzedni tryb bez regresji. Nie tworzyć drugiego solvera ani gałęzi produktu. W trybie copper-faces raport zawiera mapy E i H dla obu stron każdej warstwy, na częstotliwościach wskazanych przez użytkownika; nie pokazuje S11, SWR, impedancji, przekrojów w oddali ani wykresów portu. Pozostawić dyskretną metrykę jakości, pochodzenie danych, maski i ostrzeżenia. Dane surowe mogą nadal zawierać diagnostykę portu potrzebną do normalizacji — niewidoczną w tym typie raportu.

## Istniejący stan
`solvers/pcb_fields.py` definiuje wyłącznie trzy przekroje przestrzenne; `install_frequency_planes` rejestruje E/H z dump_mode=1 i interpolacją node. `pcb_sample_mask` maskuje miedź i halo jednej lokalnej komórki; nie wolno użyć tej maski bez zmian do nowego celu. `visualization/fields.py` rozpoznaje nazwy trzech przekrojów PCB; `pcb_fields.py` wizualizuje E i wybraną składową H. `report_data.py` wymaga widma impedancji, a `report.py` zawsze tworzy panel impedancji. `gui_commands.py` i `gui.py` nie mają wyboru trybu pomiaru. `model.py` ma copper_layers z rolą i pozycją z; `easyeda_stackup.py` mapuje fizyczny stos. Folia jest zerogrubościowym PEC albo conducting sheet, a jej grubość fizyczna jest metadanymi, nie dwiema odległymi powierzchniami geometrii.

## Kontrakt danych
Każdy rekord pomiaru powinien zawierać niezależny identyfikator warstwy (rola, źródłowe ID, z), stronę `+z`/`-z`, żądane i rzeczywiste z próbki, odległość od miedzi, oś normalną, wspólną siatkę XY, częstotliwości, zespolone Ex/Ey/Ez i Hx/Hy/Hz, jednostki, konwencję fazy i normalizację, maski/validity oraz status odczytu. N warstw oznacza 2N widoków; np. 4 warstwy = 8 widoków. Płaszczyzny muszą leżeć w fizycznie odpowiednich ośrodkach, poza PML, na istniejącej siatce lub na udokumentowanych fizycznie poprawnych pozycjach Yee. Nie traktować samego najbliższego węzła jako gwarancji pola na powierzchni. Jeśli brak rozdzielczości, przerwać lub oznaczyć stronę jako unavailable, nie interpolować z arbitralnego 1 mm. Nie zmieniać siatki ani geometrii tylko po to, by ukryć błąd próbkowania. Audyt kosztu i geometrii przed FDTD.

## Fizyka i ograniczenia
Warunek skoku pola: dla normalnej +z od strony -z do +z, `K_net = z_hat × (H_plus − H_minus)` w A/m (zależnie od konsekwentnie przyjętej orientacji). To **prąd wypadkowy cienkiej powierzchni**, nie osobno `K_top` i `K_bottom`. Dla idealnego PEC i prawidłowych jednostronnych granic można rozważać prądy przypisane stronom, lecz model zerowej grubości, interpolacja Yee, krawędzie, szczeliny, PTH i model sheet wymagają niezależnej walidacji. Nie przedstawiać ich jako pomiaru dwóch rzeczywistych powierzchni folii 35 µm. Pole E tangencjalne przy PEC powinno spełniać warunek brzegowy; wartość interpolowana przez metal nie jest poprawnym pomiarem.

Poprawny przybliżony opór powierzchniowy dobrego, grubego przewodnika przy silnym skin effect: `Rs = sqrt(pi*f*mu/sigma)` [ohm/square], `delta = sqrt(1/(pi*f*mu*sigma))` [m], `J ~ K/delta` [A/m²], a średnia gęstość strat powierzchniowych `p = 0.5*Rs*|K|²` [W/m²] dla fazorów szczytowych. Nie stosować bez weryfikacji dla cienkiej folii, PEC, sprzężonych obu stron lub blisko krawędzi. Wcześniejsze wzory `Rs=pi*f*mu*sigma` i `J~K*delta` są błędne wymiarowo. E/H przy powierzchniach umożliwiają ocenę sprzężenia i porównanie rozkładu prądu między wariantami, ale sama jedna mapa nie dowodzi przyczynowości zmiany.

## Raport
Tryb `spatial-eh`: istniejący HTML i stare pliki pozostają odczytywalne. Tryb `copper-faces`: lista warstw w kolejności stackupu; dla każdej dwa jawnie opisane widoki (+z/-z) w tej samej orientacji XY (opcjonalne odbicie widoku od spodu musi być opisane), mapy E i H, wybór składowej/modułu/fazy, wspólna skala porównawcza i granice geometrii właściwej warstwy, maski i status. Nie pokazywać danych niezmierzonych jako zero. K i straty AC — wyłącznie opcjonalnie, po walidacji. Raport offline bez ponownego FDTD, bez przepisywania źródłowych NPZ/HDF5. Typ raportu wynika z zapisanego manifestu pomiaru, a nie z nazwy katalogu czy pliku. Dla brakujących danych wyświetlać przyczynę i nie udawać sukcesu.

## Warunki odbioru
- Dwa tryby w jednym GUI/CLI i w trwałym manifeście, przygotowanie i uruchomienie używają identycznego kontraktu.
- N warstw daje 2N identyfikowalnych, rzeczywiście odczytanych widoków E/H; weryfikacja z i siatki oraz poprawnej strony ośrodka.
- Testy sztuczne nie zastępują natywnego openEMS: test granic PEC/sheet, bliskości, orientacji, skali, fazy, wpływu siatki i symetrii/asymetrii.
- Raport copper-faces nie ma paneli S11, impedancji, SWR, oddalonych przekrojów; stary raport nie ma regresji.
- Ponowne generowanie HTML offline nie zmienia danych; przerwany HDF5 z pustym FieldData/FD jest niekompletny.
- Wynik pozostaje `unverified` do czasu potwierdzenia fizyki i zbieżności; nie obiecywać dwóch oddzielnych prądów obu stron folii bez zmiany/zweryfikowania modelu.
