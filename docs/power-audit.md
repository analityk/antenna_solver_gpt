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

## Interpretacja następnego wyniku

Jeżeli trzy strumienie będą bliskie 0,8785 względem pierwotnego pomiaru
portu, podejrzenie będzie koncentrować się na definicji/pomiarze mocy źródła.
Jeśli strumień zmieni się istotnie wraz z powierzchnią, trzeba zbadać
interpolację, dyskretyzację i granice domeny. Lokalny monitor jest blisko
przewodów i również ma błąd dyskretyzacji; sam nie stanowi wzorca prawdy.
Profile U/I pokażą, na ile port zachowuje się jak jeden element skupiony.
Z żadnego z tych przypadków nie wynika jeszcze automatycznie pełna walidacja.

Nie mnożymy pola przez współczynnik wymuszający bilans 1:1. Nie zmieniamy
odniesienia zysku na moc promieniowaną pod tą samą nazwą. Nie skalujemy anteny
o 5% przed wyjaśnieniem problemu i kontrolą zbieżności.

## Sprawdzenia kodu i ograniczenia

Całkowanie sprawdzono na analitycznym polu o znanej dywergencji i na danych
użytkownika. Testy obejmują niejednorodną siatkę, znaki normalnych, brak ściany,
niezgodne siatki E/H oraz sondy przesunięte w czasie. Potwierdzono identyczność
wszystkich linii siatki konfiguracji kontrolnej z plikiem `mesh.npz` starego
przebiegu. To nie jest wykonanie nowego FDTD ani sprawdzenie dodatków na Windowsie.

Czytnik obsługuje sprawdzony zespolony format HDF5 NXYZ openEMS 0.37.0rc3.
Inne formaty są odrzucane. Brak plików którejkolwiek ściany jest błędem także
przed standardowym CalcNF2FF; natywny interfejs potrafi takie pary pominąć.

Implementacja źródłowa używana do porównania:
[całkowanie NF2FF](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/nf2ff/nf2ff_calc.cpp),
[pomiar portu](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/ports.py),
[zapis pól w dziedzinie częstotliwości](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/Common/processfields_fd.cpp).
