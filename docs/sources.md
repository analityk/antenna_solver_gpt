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

## Solver i API

- [openEMS — dokumentacja](https://docs.openems.de/en/latest/).
- [Wydanie Windows 0.37.0-rc3](https://github.com/thliebig/openEMS-Project/releases/tag/v0.37.0-rc3).
- [API openEMS](https://docs.openems.de/en/latest/python/openEMS/openEMS.html).
- [Porty](https://docs.openems.de/en/latest/python/openEMS/ports.html).
- [NF2FF](https://docs.openems.de/en/latest/python/openEMS/nf2ff.html).
- [Geometria CSXCAD](https://docs.openems.de/en/latest/python/CSXCAD/CSProperties.html).

Adapter sprawdzano względem źródeł podmodułów przypiętych przez wydanie,
ponieważ dokumentacja latest może się zmieniać:

- openEMS commit `67d378488ee40de815eed00f8aaa808f0a9e3c6d`:
  [openEMS.pyx](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/openEMS.pyx),
  [ports.py](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/ports.py),
  [nf2ff.py](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/nf2ff.py),
  [utilities.py — DFT](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/utilities.py),
  [przykład anteny](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/Tutorials/Simple_Patch_Antenna.py).
- Diagnostyka mocy tego samego wydania:
  [kwadratura strumienia na ścianach](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/nf2ff/nf2ff_calc.cpp),
  [odczyt par plików E/H](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/python/openEMS/nf2ff.py),
  [DFT pól i znaczniki czasu](https://github.com/thliebig/openEMS/blob/67d378488ee40de815eed00f8aaa808f0a9e3c6d/Common/processfields_fd.cpp).
- CSXCAD commit `dcdb62bcfd1111ee3594ba22d06089b41b380990`:
  [źródła](https://github.com/thliebig/CSXCAD/tree/dcdb62bcfd1111ee3594ba22d06089b41b380990).

Przegląd źródeł nie zastępuje wykonania na Windowsie. Repozytorium projektu
nie dołącza cudzych bibliotek binarnych, artykułu ani rysunków autora anteny.
Wersje faktycznie importowane przez adapter zapisuje manifest przebiegu.

## Poprzedni eksperyment

Wcześniejsza symulacja double biquada przy 800 MHz w tej rozmowie korzystała
z PyNEC 2.3.4. Stanowi wskazówkę integracyjną, nie wynik dla Quadosa 8.
Nie przenosimy jej czasów wykonania ani zysku do wymagań tej anteny.


## Interfejs

- [Matplotlib — osadzenie wykresu w Tk](https://matplotlib.org/stable/gallery/user_interfaces/embedding_in_tk_sgskip.html).
- [Python 3.14 — kontrolki ttk](https://docs.python.org/3.14/library/tkinter.ttk.html).

Rysowanie i pola tekstowe są rozdzielone. Wcześniejszy TextBox Matplotlib
wykonywał pełne canvas.draw w _rendercursor przy edycji, a on_submit również
przy opuszczeniu pola; nowy formularz nie używa tych kontrolek.
