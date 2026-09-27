# Źródła i pochodzenie danych

## Geometria

- Dragoslav Dobričić, YU1AW: rysunek „Quados 8 Antenna”, dostarczony przez
  użytkownika. Dane odczytane bezpośrednio: A–H, średnica 2 mm, reflektor
  720 × 73 × 1,5 mm, cztery odcinki drutu po 449,6 mm, zasilanie przez balun 4:1.
- Artykuł autora: [Quados Sector Antenna for 2.4 GHz WiFi](https://www.qsl.net/yu1aw/ANT_VHF/quados.pdf),
  antenneX, marzec 2008. Wyjaśnia ideę połączeń, reflektora i zasilania.
  Nie wszystkie wymiary w artykule dotyczą wersji ośmioelementowej;
  nie wolno mieszać ich z tabelą Quadosa 8.
- 2450 MHz w konfiguracji jest założeniem skalowania, nie zweryfikowaną
  częstotliwością optimum konkretnego rysunku Quadosa 8.

## Solver

- [NEC2++](https://github.com/tmolteno/necpp) — projekt autora, implementacja
  metody momentów zgodna z NEC-2.
- [NE/NH — pola bliskie](https://www.nec2.org/part_3/cards/ne.html).
- [Dokumentacja NEC2++](https://tmolteno.github.io/necpp/).
- [openEMS](https://docs.openems.de/en/latest/) — możliwy przyszły adapter FDTD.

Przy integracji należy zapisać dokładną wersję solvera i jego zależności,
zachować wymagane informacje licencyjne i nie dołączać cudzych plików
binarnych bez określenia sposobu dystrybucji. M0 nie zawiera kodu solvera
ani kopii artykułu lub rysunków autora.

## Poprzedni eksperyment

Wcześniejsza symulacja double biquada przy 800 MHz w tej rozmowie korzystała
z PyNEC 2.3.4. Stanowi wskazówkę integracyjną, nie wynik dla Quadosa 8.
Nie przenosimy jej czasów wykonania ani zysku do wymagań tej anteny.

