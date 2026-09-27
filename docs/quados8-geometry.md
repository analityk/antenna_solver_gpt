# Geometria Quadosa 8 — specyfikacja generatora

To jawna rekonstrukcja rysunku użytkownika, jeszcze bez walidacji solverem.
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
definicja to idealne wymuszenie różnicowe; reprezentacja segmentem źródła
w NEC jest zadaniem adaptera i musi zostać opisana w `model.nec` i raporcie.
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
Pierwszy adapter zastępuje ją połączoną siatką w z = 0. Każde skrzyżowanie
siatki musi być węzłem elektrycznym. Podział siatki i promień jej drutów
są parametrami numerycznymi, odrębnymi od wymiarów konstrukcyjnych anteny.

