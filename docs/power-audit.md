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

Podejrzenia pozostają w modelu/pomiarze portu, dyskretyzacji i interpolacji
pól. Port ma 19,669 mm długości (około 0,093 długości fali), obejmuje 18 × 4 × 4
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

## Następna kontrola: lokalna praca źródła

Pierwszy zestaw sond przechowuje całki U przez całą długość i I przez cały
przekrój. Nie da się z nich odtworzyć iloczynów lokalnych: suma U razy suma I
nie zastępuje sumy odpowiednio sparowanych U·I. Brakuje danych potrzebnych
do bezpośredniego obliczenia pracy rozłożonego źródła.

Konfiguracja `parameters/quados8_1420mhz_source_work.json` dodaje opcję
`solver.power_diagnostics.source_edge_work=true`. Zapisuje 450 par sond:
18 krawędzi wzdłuż x × 5 × 5 w przekroju. Każda para mierzy napięcie na jednej
krawędzi elektrycznej i obieg H wokół przyporządkowanej jej ściany siatki dualnej.
To nadal tylko pasywne pomiary na tej samej siatce, bez zmiany źródła.

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

Jeżeli suma pracy da około 0,8785 wartości pierwotnego portu, będzie to
bezpośredni argument za błędem utożsamienia jego pojedynczego U·I z mocą
całego źródła. Jeżeli da około 1, trzeba dalej badać dyskretyzację/pola i bilans
między obszarem źródła a otoczeniem. Wynik pośredni wymaga analizy udziałów
lokalnych oraz pozostałego błędu. Żadnego z tych wyników nie przewidziano
ani nie wpisano do programu. Korekta modelu portu i sprawdzenie zbieżności
będą oddzielnym krokiem po tej kontroli.

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
pomiarów i indeksów; wymagają jeszcze wykonania natywnego przebiegu.

Czytnik obsługuje sprawdzony zespolony format HDF5 NXYZ openEMS 0.37.0rc3.
Inne formaty są odrzucane. Brak plików którejkolwiek ściany jest błędem także
przed standardowym CalcNF2FF; natywny interfejs potrafi takie pary pominąć.

Implementacja źródłowa używana do porównania:
[całkowanie NF2FF](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/nf2ff/nf2ff_calc.cpp),
[pomiar portu](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/ports.py),
[zapis pól w dziedzinie częstotliwości](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/Common/processfields_fd.cpp).

Dla pracy lokalnej: [całka prądu i obieg H](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/Common/processcurrent.cpp),
[przyciąganie sond do siatki](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/FDTD/operator.cpp),
[rozkład elementu skupionego na krawędzie](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/FDTD/extensions/operator_ext_lumpedRLC.cpp).
