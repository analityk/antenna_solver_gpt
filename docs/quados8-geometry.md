# Geometria Quadosa 8 — specyfikacja generatora

Generator odtwarza poniższą rekonstrukcję rysunku użytkownika. Geometrię
sprawdzono testami; walidacja elektromagnetyczna pozostaje otwarta.
Rysunek wymiarowy jest źródłem długości; brak oryginalnego pliku NEC.

## Założenia geometryczne

Układ osi z `goal.md`. Wszystkie osie przewodów promiennika leżą na z = H.
Od środka anteny biegną cztery gałęzie: lewa/prawa, górna/dolna.
Gałęzie po tej samej stronie łączą się w punkcie zasilania. Górna para
łączy się we wspólnym końcowym wierzchołku; dolna para analogicznie.

Odcinki E są nachylone pod 45° do osi x/y. To idealizacja rysunku, którą
należy zachować jako opis modelu. Rzeczywiste promienie gięcia i lutowania
nie są odwzorowane. F domyka końcowy wierzchołek i nie ma narzuconych 45°.

## Jedna gałąź: prawa górna

Początek to (G/2, 0, H). Niech q = E / sqrt(2).
Kolejne ruchy w płaszczyźnie x/y:

| Odcinek | Zmiana x | Zmiana y |
| --- | ---: | ---: |
| A | 0 | A |
| E | +q | +q |
| E | −q | +q |
| B | 0 | B |
| E | +q | +q |
| E | −q | +q |
| C | 0 | C |
| E | +q | +q |
| E | −q | +q |
| D | 0 | D |
| E | +q | +q |
| F | −(G/2 + q) | sqrt(F² − (G/2 + q)²) |

Pozostałe gałęzie są odbiciami względem x = 0 i y = 0. Łączna długość
jednej gałęzi musi być równa A + B + C + D + 7E + F.

Centralny port łączy terminale (−G/2, 0, H) i (+G/2, 0, H). Jego fizyczna
definicja to idealne wymuszenie różnicowe. Adapter openEMS używa portu
skupionego o skończonej objętości i zakończeniach PEC; szczegóły zapisuje
w `openems/model.xml` i manifeście. Opis: `docs/openems-model.md`.
Portu nie dolicza się do czterech długości drutu z rysunku.

## Warunki poprawności

- Wszystkie długości i średnica dodatnie, wartości skończone.
- G większe od średnicy drutu; H większe od promienia drutu.
- F > G/2 + E/sqrt(2), aby zamknięcie miało niezerową wysokość.
- Połączenia tylko w zadanych węzłach. Brak przypadkowych przecięć, duplikatów
  segmentów, nakładających się przewodów i odizolowanych fragmentów.
- Środkowe kształty rombowe nie stają się osobnymi zamkniętymi pętlami:
  ich górne/dolne zakończenia przechodzą w dwie równoległe linie.
- Zmiana C lub D zachowuje symetrię; przesuwa odpowiednie dalsze sekcje,
  nie rozciąga po cichu odcinków E.
- Wyjście przewodu poza obrys reflektora jest raportowane, ale nie jest samo
  w sobie błędem fizycznym. Wymiary reflektora są niezależnymi parametrami.

## Reflektor

Przednia powierzchnia fizycznej płytki to z = 0, zakres x = ±szerokość/2,
y = ±długość/2; grubość rozciąga się w stronę ujemnego z.
Adapter tworzy bryłę PEC przez AddBox. Grubość jest wymiarem aktywnym;
nie zastępujemy płyty siatką drutów. Cylindry drutu mają w węzłach kule tego
samego promienia, zapewniające ciągłość połączeń. Dla konfiguracji startowej
powstaje 48 odcinków osi i 48 różnych węzłów. Długość każdej gałęzi wynosi
775,718309859 mm; objętości kul nie dolicza się do długości osi z rysunku.
