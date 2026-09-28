# Diagnostyka rozbieżności mocy

Przebieg `20260928T004231Z_902d497594` osiągnął EndCriteria −50 dB na Windowsie.
Przy 1420 MHz i normalizacji do 1 W przyjętego przez port, openEMS zwrócił
0,878490159 W wypromieniowanego. Model zawiera PEC i próżnię; tego stosunku
nie wolno przedstawiać jako fizycznej sprawności rzeczywistej anteny.

## Ustalenia z dostarczonych danych

Sprawdzono skróty SHA-256 wszystkich 13 plików HDF5 względem manifestu.
Wszystkie sześć par E/H jest obecne, siatki są zgodne i powierzchnia zamknięta.
Niezależne całkowanie 0,5 Re(E × conj(H)) daje 0,878490162 W; względna różnica
wobec natywnego wyniku wynosi 2,8e-9. Zmiana kwadratury trapezowej na Simpsona
na tych samych próbkach daje około 0,878124395 W. Błąd samego sumowania nie
wyjaśnia 12,15%; nie wyklucza to błędu zapisanych próbek/interpolacji.

| Ściana | Strumień aktywny po normalizacji [W] |
| --- | ---: |
| −x | 0,041054646 |
| +x | 0,041054647 |
| −y | 0,003302414 |
| +y | 0,003302414 |
| −z, tył | 0,025151121 |
| +z, przód | 0,764624919 |

Moc przyjęta już uwzględnia moc odbitą. Zastosowano osobne znaczniki czasu
U/I, w tym przesunięcie I o połowę kroku FDTD. Prad jest całką po powierzchni
NF2FF; nie zależy od kroku kątów charakterystyki 5°. Usunięcie ostatnich
32 z 323 próbek portu zmienia jego moc przy 1420 MHz o około 0,199%; to
kontrola wrażliwości portu na ucięcie, nie dowód zbieżności wszystkich pól.

Pierwsza analiza wskazała model/pomiar portu, dyskretyzację i interpolację
pól; wynik lokalnej pracy poniżej rozstrzyga główną rozbieżność. Port ma
19,669 mm długości (około 0,093 długości fali), obejmuje 18 × 4 × 4
komórki, a pierwotny pomiar używa jednej linii U i jednego przekroju I.
Sam rozmiar nie dowodzi błędu. Siatka ma skok sąsiednich komórek do 1,8667
w osi z mimo ustawienia growth_ratio=1,4. Obecny generator ogranicza wzrost
w dodawanym otoczeniu, ale nie wszystkie połączenia przedziałów. Ta wada
wymaga osobnej kontroli/poprawki; w opisanym niżej porównaniu jej nie zmieniamy,
aby zachować dokładnie siatkę pierwotnego przebiegu.

## Jeden przebieg z dodatkowymi pomiarami

W CMD, po aktualizacji repozytorium i instalacji edycyjnej:

```bat
.\.venv\Scripts\python.exe -m antenna_lab run --config parameters\quados8_1420mhz_power_audit.json
```

Konfiguracja zachowuje oryginalne wymiary, siatkę, PML, port, częstotliwość
zapisu NF2FF 1420 MHz, impuls i EndCriteria 1e-5. Dodaje:

- `nf2ff`: pierwotną zewnętrzną powierzchnię całej anteny;
- `power_inner`: drugą zamkniętą powierzchnię całej anteny, bliżej konstrukcji;
- `power_feed`: małą zamkniętą powierzchnię obejmującą źródło i fragmenty
  przewodów. Jej strumień netto nie jest polem dalekim i nie służy obliczaniu zysku;
- linie pomiaru U we wszystkich 25 węzłach przekroju źródła oraz 18 sond I
  w kolejnych płaszczyznach siatki dualnej wzdłuż źródła;
- odczyt impedancji z U(t)/I(t) w zakresie 1400–1440 MHz co 0,25 MHz.

Współrzędne dodatkowych powierzchni są wybierane z istniejących linii;
żadna linia nie jest przesuwana ani dopisywana. Parametry położenia monitorów
i zakres odczytu portu są zapisane w `solver.power_diagnostics`.
Włączenie diagnostyki pomija generowanie raportu i wykresów wynikowych.
Pierwotne wyniki pozostają w swoim katalogu bez zmian.

## Wynik pasywnej kontroli na Windowsie

Użytkownik dostarczył `power_diagnostics.zip` z zakończonego przebiegu.
Wszystkie linie siatki są identyczne z pierwotnymi. Z przy 1420 MHz,
zysk i stosunek Prad/Pacc odtwarzają pierwszy wynik do zapisanej precyzji;
dodatkowe sondy nie zmieniły rozwiązania. Ponownie osiągnięto EndCriteria.

| Pomiar | Wartość przy pierwotnej normalizacji do 1 W portu |
| --- | ---: |
| Port, jedna linia U i jeden przekrój I | 1,000000 W |
| `nf2ff`, zewnętrzna powierzchnia całej anteny | 0,878490162 W |
| `power_inner`, bliższa powierzchnia całej anteny | 0,878968878 W |
| `power_feed`, mała powierzchnia przy źródle | 0,840440439 W |

Powierzchnie całej anteny różnią się o 0,0545% względem zewnętrznego strumienia.
Nie wskazuje to na narastającą utratę 12% pomiędzy tymi powierzchniami.
Nie wyklucza wspólnego błędu próbek, błędu przy źródle ani wpływu PML na samo
rozwiązanie. Lokalna powierzchnia przecina przewody i obejmuje silne pole
reaktywne; jej odczyt nie jest niezależnym wzorcem mocy źródła.

Wśród 25 linii U amplituda sięga 1,16801 amplitudy linii środkowej,
a względne przesunięcie fazy sięga −10,8259°. To ilościowa wskazówka,
że przekrój źródła nie ma jednego napięcia. Uśrednienie napięć i pomnożenie
przez środkowy prąd dałoby 0,941817 wartości pierwotnej — nie 0,87849.
Nie wolno stosować takiego uśrednienia jako arbitralnej poprawki.

Prądy w 16 wewnętrznych przekrojach dają iloczyn z pierwotnym U od 0,97766
do 1,00000 wartości portu. Dwa skrajne przekroje przy metalowych zakończeniach
dają około 2,07759 i różnią się fazą o około −32,77°. Są to diagnostyczne
iloczyny różnych sond, nie 18 alternatywnych pomiarów mocy anteny. Samo
przesunięcie płaszczyzny I wewnątrz portu nie wyjaśnia deficytu.

## Kontrola lokalnej pracy źródła

Pierwszy zestaw sond przechowuje całki U przez całą długość i I przez cały
przekrój. Nie da się z nich odtworzyć iloczynów lokalnych: suma U razy suma I
nie zastępuje sumy odpowiednio sparowanych U·I. Brakuje danych potrzebnych
do bezpośredniego obliczenia pracy rozłożonego źródła.

Konfiguracja `parameters/quados8_1420mhz_source_work.json` dodaje opcję
`solver.power_diagnostics.source_edge_work=true`. Zapisuje 450 par sond:
18 krawędzi wzdłuż x × 5 × 5 w przekroju. Każda para mierzy napięcie na jednej
krawędzi elektrycznej i obieg H wokół przyporządkowanej jej ściany siatki dualnej.
To nadal tylko pasywne pomiary na tej samej siatce, bez zmiany źródła.

Pierwsza próba `20260928T101020Z_78b86cdbac` wykazała błąd otwierania plików
po osiągnięciu domyślnego limitu 512 strumieni UCRT. Komplet 945 sond nie został
zapisany. Adapter przygotowuje teraz limit i sprawdza zasoby przed Run,
a błąd otwarcia natychmiast zatrzymuje pracownika. Kolejna próba na Windowsie
zakończyła się kompletnym zapisem: 945 strumieni, limit UCRT 512 → 2048;
opis: [obsługa strumieni Windows](windows-setup.md#wiele-sond-i-limit-otwartych-plików).

```bat
.\.venv\Scripts\python.exe -m antenna_lab run --config parameters\quados8_1420mhz_source_work.json
```

Przy przyjętym znaku U = −całka E·dl sumujemy 0,5 Re(U_edge · conj(I_edge)).
Jest to praca netto wprowadzana do pola w obszarze źródła, obejmująca ujemny
wkład pochłaniania w oporze zasilania. Nie jest samą mocą generatora przed
odjęciem strat w tym oporze. I zawiera także prąd przesunięcia; w ustalonym
stanie harmonicznym w bezstratnej komórce jego wkład czynny znika. Skończony
zapis impulsu pozostaje źródłem błędu. Wkładów ujemnych nie zerujemy.

Program kontroluje indeksy siatki faktycznie zapisane w nagłówkach sond.
Suma 18 lokalnych U musi odtworzyć każdą dawną linię U, a suma 25 lokalnych I
każdy dawny przekrój I. Odchyłka maksymalna powyżej 1e-4 względem największej
amplitudy odniesienia dla danej częstotliwości przerywa odczyt. Ten próg
sprawdza składanie pomiarów; nie jest progiem akceptacji bilansu fizycznego.

## Wynik pracy lokalnej i zidentyfikowany błąd

Użytkownik dostarczył kompletną paczkę `power_diagnostics(1).zip` dnia
2026-09-28, SHA-256
`be912077dbaa06e4809988a6523f12feb18665782d65c2cb51d9ba6e1aff0be3`.
Jest 900 surowych plików lokalnych sond, a ich indeksy zgadzają się z planem.
Ponowna DFT odtwarza zapisane widma do około 3e-16 względnej normy.
Sumy lokalnych U odtwarzają 25 długich linii do 3,96e-13, a sumy I odtwarzają
18 przekrojów do 2,34e-8. Siatka oraz pierwotne Z, SWR i zysk pozostały identyczne.

| Pomiar przy 1420 MHz | Wartość w pierwotnej normalizacji | Różnica względem pracy lokalnej |
| --- | ---: | ---: |
| Pojedyncze U·I portu | 1,000000000 W | — |
| Suma lokalnej pracy netto źródła | 0,879386295 W | — |
| Zewnętrzna powierzchnia całej anteny | 0,878490162 W | −0,10190% |
| Wewnętrzna powierzchnia całej anteny | 0,878968878 W | −0,04747% |
| Mała powierzchnia przy zasilaniu | 0,840440439 W | −4,42875% |

Niemal cały deficyt 12,15% jest więc skutkiem użycia pojedynczego U·I jako
miary pracy niejednorodnego źródła. Nie wykazano utraty 12% podczas propagacji.
Pozostałe około 0,1% nie zostało wyzerowane ani uznane za zbieżność.

Rozkład pracy ujawnił konkretny błąd adaptera. Kotwice w `mesh._axis` są
zaokrąglane do 12 miejsc po przecinku w metrach, a granice AddLumpedPort
były przekazywane bez tego zaokrąglenia. Granice w y:

- źródło: ±0,0017253521126760563 m;
- siatka: ±0,001725352113 m;
- skrajne linie leżą poza źródłem o około 3,2394e-13 m, czyli 0,324 pm.

Opór portu jest odwzorowany przez `Operator::Calc_LumpedElements()` z użyciem
`SnapBox2Mesh`, więc obejmuje 18 × 5 × 5 = 450 krawędzi. Wymuszenie sprawdza
przynależność współrzędnych E do boxa. `CSPrimBox::IsInside` nie używa
przekazanego argumentu tolerancji, a `CoordInRange` porównuje granice wprost.
Obie skrajne warstwy y są wykluczone: wymuszenie obejmuje 18 × 3 × 5 = 270
krawędzi. O rozstrzygnięciu decyduje strona granicy, nie wielkość odchyłki.

W danych dokładnie te 270 krawędzi daje dodatnią pracę +1,434333232 W,
a pozostałe 180 — ujemną −0,554946937 W. Na ujemnych krawędziach zmierzone
−Re(I/U) zgadza się z konduktancją rozłożonego oporu do 3,19e-5 względnie.
Konduktancję wyznaczono z rzeczywistych długości krawędzi i pól dualnych
według gałęzi równoległej RC w `operator.cpp`; nie według rozszerzenia RLC.
To niezależne potwierdzenie, że skrajne warstwy działają jako sam opór.
Podane dodatnie/ujemne sumy są lokalną pracą netto, nie osobnymi mocami
idealnego generatora i całego oporu zasilającego.

Dokładne granice odtworzono z pełnych parametrów, kodu i `mesh.npz`.
XML biblioteki zapisuje część współrzędnych ze zmniejszoną precyzją;
nie użyto go do wnioskowania o odchyłce 0,324 pm. Run korzysta z obiektu
zbudowanego w pamięci, nie wczytuje ponownie zapisanego XML.

## Następny przebieg: spójne granice źródła

`parameters/quados8_1420mhz_aligned_feed.json` włącza
`solver.port_mesh_alignment=mesh_anchors`. Moduł `solvers/feed.py` wybiera
dokładne istniejące kotwice dla granic całego AddLumpedPort i odrzuca odchyłkę
większą niż 1e-12 m. W tym modelu największa korekta to 3,381e-13 m.
Audyt przed Run wykazuje 450/450 krawędzi w obszarze wymuszenia. Zapisuje go
`feed_grid_coverage.json` oraz manifest.solver.feed; plik trafia do paczki ZIP.
Ten audyt jest geometryczny, nie jest wynikiem operatora natywnego.

Nie zmieniają się fizyczne wymiary anteny, linie siatki, dyskretny opór i jego
metalowe zakończenia, R=200 Ω, impuls, PML ani EndCriteria. Te same lokalne
sondy mierzą pracę. Zmienia się rozkład wymuszenia 270 → 450 krawędzi, dlatego
potrzebny jest nowy FDTD. Stare dane nie pozwalają obliczyć skutku tej zmiany.
Konfiguracje bez nowej opcji lub z `legacy` zachowują dawny model i zgłaszają
ostrzeżenie o niepełnym pokryciu — służą odtworzeniu, nie naprawie.

W CMD, po zakończeniu poprzedniego przebiegu:

```bat
git pull --ff-only
.\.venv\Scripts\python.exe -m antenna_lab run --config parameters\quados8_1420mhz_aligned_feed.json
```

Przygotowanie powinno wypisać:

```text
Granice źródła (mesh_anchors): 450/450 krawędzi portu w obszarze wymuszenia.
```

Sprawdzimy, jak zmieniają się niejednorodność napięcia i lokalna praca,
czy oba strumienie nadal odtwarzają tę pracę i czy pojedyncze U·I staje się
wiarygodnym odniesieniem. Sama pełna obecność wymuszenia nie gwarantuje
jednorodnego pola w porcie o skończonym rozmiarze.

Nie zatwierdzamy starego Z=73,114−j84,015 Ω, SWR=3,2787 ani zysku 16,947 dBi.
Przeliczenie tego samego starego pola względem zmierzonej pracy zwiększyłoby
liczbę zysku o 0,558 dB, lecz nie naprawiłoby źródła ani impedancji. Nie zostało
zastosowane. Po sprawdzeniu nowego źródła nadal potrzebna jest kontrola
siatki, zbieżności i przypadku referencyjnego; M2 pozostaje otwarte.

Nie mnożymy pola przez współczynnik wymuszający bilans 1:1. Nie zmieniamy
odniesienia zysku na moc promieniowaną pod tą samą nazwą. Nie skalujemy anteny
o 5% przed wyjaśnieniem problemu i kontrolą zbieżności.

## Sprawdzenia kodu i ograniczenia

Całkowanie sprawdzono na analitycznym polu o znanej dywergencji i na danych
użytkownika. Testy obejmują niejednorodną siatkę, znaki normalnych, brak ściany,
niezgodne siatki E/H oraz sondy przesunięte w czasie. Potwierdzono identyczność
wszystkich linii siatki konfiguracji kontrolnej z plikiem `mesh.npz` starego
przebiegu. Użytkownik potwierdził działanie pierwszego zestawu dodatkowych
monitorów na Windowsie, dostarczając powyższe wyniki. Nowe 450 par lokalnych
sond sprawdzono testami znaków pracy, analitycznego strumienia, składania
pomiarów i indeksów oraz kompletnym natywnym przebiegiem użytkownika.
Regresja granic odtwarza 270/450 starego źródła, wymaga 450/450 po poprawce,
kontroluje identyczność geometrii/siatki/sond i odrzucenie zbyt dużego
przesunięcia. Test granicy adaptera sprawdza argumenty AddLumpedPort.
Nowego wariantu z poprawionym źródłem nie wykonano jeszcze natywnie.

Czytnik obsługuje sprawdzony zespolony format HDF5 NXYZ openEMS 0.37.0rc3.
Inne formaty są odrzucane. Brak plików którejkolwiek ściany jest błędem także
przed standardowym CalcNF2FF; natywny interfejs potrafi takie pary pominąć.

Implementacja źródłowa używana do porównania:
[całkowanie NF2FF](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/nf2ff/nf2ff_calc.cpp),
[pomiar portu](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/ports.py),
[zapis pól w dziedzinie częstotliwości](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/Common/processfields_fd.cpp).

Dla pracy lokalnej: [całka prądu i obieg H](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/Common/processcurrent.cpp),
[przyciąganie sond do siatki](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/FDTD/operator.cpp),
[rozkład oporu równoległego RC na krawędzie](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/FDTD/operator.cpp).

Dla pokrycia źródła: [wybór krawędzi wymuszenia](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/FDTD/extensions/operator_ext_excitation.cpp),
[IsInside dla boxa](https://github.com/thliebig/CSXCAD/blob/dcdb62bcfd1111ee3594ba22d06089b41b380990/src/CSPrimBox.cpp),
[CoordInRange i dokładne porównania granic](https://github.com/thliebig/CSXCAD/blob/dcdb62bcfd1111ee3594ba22d06089b41b380990/src/CSPrimitives.cpp).
