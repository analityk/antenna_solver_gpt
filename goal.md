# Cel projektu

Wersja wymagań: 0.6. Data: 2026-09-28, Europe/Warsaw.

## Bieżący stan

Projekt `antenna_solver_gpt` używa openEMS. Kontrakty konfiguracji i manifestu
mają wersję 2; wycofany szkic NEC2++ nie jest obsługiwany.
Generator Quadosa, edytor wymiarów, eksport i kontrola geometrii są zaimplementowane.
Adapter openEMS przygotowuje model XML i zawiera odczyt impedancji oraz pola
dalekiego. Użytkownik potwierdził udane prepare oraz zapis XML na natywnym
Windowsie 2026-09-28 i ukończył pierwszy FDTD. Stwierdzony deficyt mocy PEC
12,15% wymaga wyjaśnienia przed skalowaniem anteny. Niezależne całkowanie
surowych NF2FF odtwarza wynik; walidacja fizyczna pozostaje otwarta.
Pasywny przebieg z dodatkowymi sondami ukończono na Windowsie: dwie powierzchnie
całej anteny są zgodne do 0,055%, a przekrój źródła ma niejednorodne napięcie.
Do rozstrzygnięcia hipotezy błędnego pomiaru mocy rozłożonego źródła dodano
osobny wariant z lokalnymi parami U/I; nie został jeszcze wykonany natywnie.
Nie ma jeszcze zweryfikowanego wyniku obliczeń Quadosa.
Prądy, mapy E/H, animacje oraz kontrola zbieżności pozostają do wykonania.

## Cel użytkownika

Zbudować rozwijalny program do parametrycznego badania anten. Pierwszym
przypadkiem jest Quados 8 przy **1 420 000 000 Hz**. Program ma wyjaśniać,
jak geometria — zwłaszcza C, D i H — zmienia prądy, pola E/H, dopasowanie
i charakterystykę anteny. Kolejne anteny korzystają ze wspólnego rdzenia.

Dokładnie 1420 MHz jest częstotliwością aktualnego wymagania. Nie podmieniaj
jej automatycznie na dokładną częstotliwość spoczynkową linii wodoru.

## Platforma docelowa

Program ma działać lokalnie i natywnie na Windows 11. Użytkownik posiada Git,
Python i VS Code; potwierdzony interpreter to CPython 3.14.0, 64-bit AMD64.
Ścieżka instalacji: CMD lub PowerShell, `venv` i `python -m pip`.
WSL, Linux i uv nie mogą być warunkiem korzystania z programu.
Instrukcja przygotowania: `docs/windows-setup.md`.

Warunkiem odbioru integracji solvera M2 jest działający import lub uruchomienie
solvera oraz przypadek kontrolny na natywnym Windowsie. Zbudowanie lub test
na Linuxie nie zalicza tego wymagania. Ścieżka instalacji używa gotowej paczki
openEMS dla Windows i zgodnych z nią modułów Pythona. Lokalizacja użytkownika:
`C:\dev\openems\openEMS`. Użytkownik potwierdził poprawny import openEMS
0.37.0rc3 i CSXCAD w projektowym `.venv` dnia 2026-09-28.
Przygotowanie modelu XML jest potwierdzone logiem użytkownika. Obliczeniowy
przebieg Quadosa zakończył się osiągnięciem EndCriteria; przypadek referencyjny
i walidacja fizyczna pozostają do wykonania.

## Zakres pierwszej wersji symulatora

1. Parametryczny Quados 8: osiem sekcji, cztery symetryczne gałęzie, połączenia
   dwuprzewodowe, skończony reflektor i centralny port symetryczny.
2. Niezależna zmiana A–H, średnicy drutu i wymiarów reflektora, przy zachowaniu
   ciągłości przewodów i kontroli wykonalności geometrii.
3. Zmiana częstotliwości oraz osobna operacja skalowania geometrii.
4. Rozkład zespolonych prądów, impedancja, S11/SWR, charakterystyka 3D
   i przekroje, pola E/H w wybranych płaszczyznach.
5. Animacja stanu ustalonego; wymagane klatki 0, 30, 60, 90, 120, 150, 180°.
6. Porównanie wariantów z reflektorem i bez niego oraz serie zmian C, D i H.
7. Zapis danych umożliwiający ponowny odczyt i renderowanie bez nowego solve.

## Wymiary i pochodzenie

Źródło wymiarów: rysunek Quados 8 autorstwa YU1AW dostarczony w rozmowie.
Oryginał opisuje pasmo WLAN 2,4 GHz; dokładna częstotliwość optymalizacji tej
wersji nie została potwierdzona. Do wymiarów początkowych przyjęto jawnie
2450 MHz. Współczynnik skali: 2450 / 1420 = 1,7253521126760563.

| Parametr | Rysunek źródłowy [mm] | Początkowo przy 1420 MHz [mm] |
| --- | ---: | ---: |
| A | 19,7 | 33,989437 |
| B | 40,2 | 69,359155 |
| C | 41,3 | 71,257042 |
| D | 44,3 | 76,433099 |
| E | 37,5 | 64,700704 |
| F | 41,6 | 71,774648 |
| G | 11,4 | 19,669014 |
| H | 13,7 | 23,637324 |
| Średnica drutu | 2,0 | 3,450704 |
| Długość reflektora | 720,0 | 1242,253521 |
| Szerokość reflektora | 73,0 | 125,950704 |
| Grubość reflektora | 1,5 | 2,588028 |

G oznacza odstęp **osi przewodów**, H — odległość **osi promiennika od
przedniej powierzchni reflektora**. Długości odcinków odnoszą się do osi
przewodu w idealizacji prostych segmentów. Źródłowa długość każdej z czterech
gałęzi wynosi A + B + C + D + F + 7E = 449,6 mm.

Tabela jest punktem startowym, nie dokumentacją wykonawczą dostrojonej anteny.
Parametry numeryczne, z większą precyzją, zapisano w `parameters/`.
Zaokrąglenie tabeli nie może być źródłem danych dla solvera.

## Geometria i fizyka

- Układ prawoskrętny: x poziomo, y wzdłuż długiej osi anteny, z przed antenę.
  Środek reflektora jest początkiem układu; jego przednia płaszczyzna to z = 0,
  promiennik leży na z = H. Kierunek główny: +z. Polaryzacja oczekiwana: E w x.
- Szczegółowa konstrukcja gałęzi i zamknięć końcowych: `docs/quados8-geometry.md`.
  Środkowych sekcji nie wolno zastępować niezależnymi zamkniętymi pętlami.
- Model M2: wolna przestrzeń i PEC. Odcinki drutu są cylindrami o skończonym
  promieniu, połączonymi kulami w węzłach. Reflektor jest pełną, skończoną płytą
  PEC; jego grubość jest aktywnym wymiarem geometrii. Brak rzeczywistych gięć.
- Siatka kartezjańska FDTD jest niezależna od wymiarów konstrukcyjnych.
  Zachowuje węzły portu, rozdzielczość w otoczeniu przewodów i komórki PML.
  Rozdzielczość początkowa nie stanowi potwierdzenia zbieżności.
- Reprezentacja portu: AddLumpedPort wzdłuż +x, ze skończonym przekrojem
  kwadratowym równym średnicy drutu i metalowymi zakończeniami.
  Ta idealizacja źródła wymaga kontroli numerycznej.
  Szczegóły siatki, portu i normalizacji: `docs/openems-model.md`.
- Idealny port różnicowy w środku anteny. Początkowe Z odniesienia: 200 Ω.
  Nie jest to założenie, że obliczona impedancja wejściowa wynosi 200 Ω.
- Rzeczywisty koncentryk, balun 4:1, wsporniki, straty przewodnika, grunt i LNA
  są poza pierwszym modelem. Wynik nie jest charakterystyką toru z balunem.
- Mapa nadawcza: normalizacja do 1 W mocy przyjętej przez port. Faza 0° oznacza
  dodatnie maksimum napięcia portu. Pola odtwarzane jako Re(F · exp(+j · faza)).
  Nie jest to amplituda odbieranego sygnału kosmicznego ani start impulsu.
- Próbki wewnątrz przewodów i obszary niewiarygodne dla przybliżenia są
  maskowane, z zapisem maski i przyczyny; nie otrzymują sztucznego pola zero.
- Kąty pola dalekiego: theta od +z (0–180°), phi od +x ku +y (0–360°).
  Definicję polaryzacji poprzecznej zapisuje wynik; nie zgaduj jej przy odczycie.

## Wymagane outcomes

Każdy przebieg otrzymuje osobny, niezmienny katalog `outcomes/runs/<run_id>/`.
Dokładny kontrakt opisuje `outcomes/README.md`. Poniższa lista opisuje docelowy pełny przebieg M3, nie aktualnie dostępne dane.
Aktualny podzbiór plików i etapy geometry/prepare/run opisuje ten kontrakt.
Docelowy pełny przebieg ma zawierać:

- `manifest.json`, `parameters.resolved.json`, `geometry.json`, `openems/model.xml`;
- `currents.npz`, `impedance.csv`, `far_field.npz`;
- `fields/xz.npz`, `fields/yz.npz`, `fields/xy_front.npz`;
- `summary.json`, `validation.json`, `solver.log`, `report.html`;
- `plots/geometry.png`, `plots/pattern_cuts.png`, `plots/impedance.png`,
  `plots/fields_xz_phases.png`, `plots/fields_yz_phases.png`;
- `animations/fields_xz.gif` — pełny okres do płynnej pętli.

Przekroje xz i yz przechodzą przez oś anteny; xy_front leży przed promiennikiem.
Położenie, zakres i rozdzielczość każdej siatki zapisuje konfiguracja uruchomienia.
Pierwsza rekonstrukcja faz używa tych samych skal kolorów pomiędzy klatkami
i porównywanymi modelami, przy tej samej normalizacji mocy.

## Kryteria odbioru

Priorytet przed strojeniem: wyjaśnić rozbieżność mocy portu i NF2FF. Wariant
diagnostyczny dodaje wyłącznie pasywne pomiary do pierwotnego modelu i siatki,
zapisuje strumienie trzech zamkniętych powierzchni oraz rozkład odczytów portu.
Druga kontrola sumuje lokalną pracę 450 krawędzi źródła i sprawdza odtworzenie
całek U/I z pomiarów lokalnych; zachowuje tę samą geometrię i siatkę.
Nie dopuszcza się wymuszenia bilansu przez przeskalowanie pola. Zgodność
bilansu sama nie zastępuje zbieżności impedancji i zysku. Tryb diagnostyczny
zapisuje dane bez raportu; opis: `docs/power-audit.md`.

| Etap | Warunek zakończenia | Stan |
| --- | --- | --- |
| M0 | Instrukcje, wymagania, historia, moduły, parametry i kontrakt outcomes | Zakończone; kontrakty przeniesione na openEMS |
| M1 | Generator geometrii odtwarza topologię, długości, symetrię i port; pokazuje model do kontroli | Zaimplementowane i sprawdzone testami geometrii |
| M2 | openEMS liczy prądy, impedancję i pole dalekie; referencja kontrolna i sprawdzenie zbieżności | Adapter impedancji/pola dalekiego napisany; prądy i walidacja otwarte |
| M3 | Zespolone E/H, maski, przekroje i animacje fazy oraz komplet outcomes | Planowane |
| M4 | Lokalny interfejs, porównywanie wariantów i przegląd zapisanych wyników | Edytor gotowy; porównania i sterowanie obliczeniami otwarte |

Kontrola M2 obejmuje dipol jako niezależny przypadek fizyczny oraz przynajmniej
trzy poziomy dyskretyzacji Quadosa. Wstępne progi stabilności pomiędzy dwoma
najgęstszymi poziomami: zmiana zysku na osi ≤ 0,1 dB i względna zmiana
impedancji ≤ 2%. Dla pola M3: ≤ 5% różnicy norm zespolonych wektorów
w jawnie ustalonym zbiorze punktów poza maską; w pobliżu zer pola stosować
kryterium bezwzględne zapisane w raporcie. Progi są kryteriami projektu,
nie deklaracją dokładności względem anteny fizycznej. Niespełnienie oznacza
wynik niezweryfikowany; nie wolno luzować progów tylko dla uzyskania zaliczenia.

## Poza bieżącym zakresem

Benchmarki, prace nad GPU, optymalizacja szybkości przed działającym modelem,
hosting obliczeniowy, automatyczny dobór najlepszej anteny, macierze wielu
anten, układ odbiorczy i model nieba. Można rozwijać je później po nowej decyzji.
