# Cel projektu

Wersja wymagań: 0.1. Data: 2026-09-28, Europe/Warsaw.

## Cel użytkownika

Zbudować rozwijalny program do parametrycznego badania anten. Pierwszym
przypadkiem jest Quados 8 przy **1 420 000 000 Hz**. Program ma wyjaśniać,
jak geometria — zwłaszcza C, D i H — zmienia prądy, pola E/H, dopasowanie
i charakterystykę anteny. Kolejne anteny korzystają ze wspólnego rdzenia.

Dokładnie 1420 MHz jest częstotliwością aktualnego wymagania. Nie podmieniaj
jej automatycznie na dokładną częstotliwość spoczynkową linii wodoru.

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
- Model M2: wolna przestrzeń, PEC, standardowy model cienkoprzewodowy NEC2++.
  Skończony reflektor jest połączoną siatką przewodów, nie ciągłą blachą.
  Wymiary blachy są parametrami konstrukcyjnymi; jej grubość nie jest
  odwzorowana przez tę siatkę i musi być oznaczona jako nieaktywna w solverze.
- Model siatki ma osobne parametry: podział x/y i promień przewodów siatki.
  Nie wolno utożsamiać tego promienia z grubością blachy ani średnicą promiennika.
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
Dokładny kontrakt opisuje `outcomes/README.md`. Pierwszy pełny przebieg ma zawierać:

- `manifest.json`, `parameters.resolved.json`, `geometry.json`, `model.nec`;
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

| Etap | Warunek zakończenia | Stan |
| --- | --- | --- |
| M0 | Instrukcje, wymagania, historia, moduły, parametry i kontrakt outcomes | Zakończone w tym commicie |
| M1 | Generator geometrii odtwarza topologię, długości, symetrię i port; pokazuje model do kontroli | Planowane |
| M2 | NEC2++ liczy prądy, impedancję i pole dalekie; referencja kontrolna i sprawdzenie zbieżności | Planowane |
| M3 | Zespolone E/H, maski, przekroje i animacje fazy oraz komplet outcomes | Planowane |
| M4 | Lokalny interfejs, porównywanie wariantów i przegląd zapisanych wyników | Planowane |

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
