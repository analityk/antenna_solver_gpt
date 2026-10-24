# PCB — mapy pól i prądów przy powierzchniach miedzi

## Cel etapu, ustalony przez użytkownika

Na każdej fizycznej warstwie miedzi osobno (TOP / INNER / BOTTOM)
pokazać widok XY od góry i od dołu, z mapami amplitud E, H oraz
przybliżonej gęstości prądu powierzchniowego i wektorami jego kierunku.
Wzorcem wizualnym są kolorowe mapy prądów na samym przewodniku
(wskazane przykłady z programów EM). Nie interesują nas rozległe pola
w odległości 1 mm nad i pod całym PCB.

Raport tego trybu NIE pokazuje S11, SWR, impedancji, NF2FF ani
dalekich przekrojów powietrza. Port wciąż istnieje wewnętrznie,
żeby wzbudzić pole i ustalić fazę oraz normalizację 1 V.
Nie tworzymy oddzielnego solvera ani nie zmieniamy geometrii EasyEDA.

## Dwa tryby w jednej aplikacji

- far: dotychczasowy zestaw xy_air, xz_feed, yz_feed oraz stary raport.
- copper_surfaces: pary XY tuż przy każdej fizycznie zmaterializowanej
  warstwie Cu, nowy osobny raport powierzchniowy.

GUI przechowuje pole field_mode per folder projektu. CLI przyjmuje
--field-mode far albo --field-mode copper_surfaces. W obu trybach
--fields-mhz określa 1–3 częstotliwości, a PREPARE-ONLY jest zalecany.
Nie uzupełniać brakujących warstw, konturów ani otworów miedzi.

## Próbkowanie i jawny koszt FDTD

Dla każdego z poziomów Z miedzi powstają węzły siatki
Z = z_copper + 10 µm oraz Z = z_copper - 10 µm.
Wybór węzłów jest dokładny i dokumentowany w rozwiązywanej siatce.
Za cienkie dielektryki lub brak miejsca blokują przygotowanie.
Dodatkowe węzły Z ZMIENIAJĄ siatkę FDTD, mogą zwiększać cell_count,
obniżać timestep CFL i przedłużać symulację. Nie wolno twierdzić,
że nowy tryb to bezkosztowy pomiar. Po PREPARE-ONLY należy sprawdzić
pełny budżet oraz native model.xml przed długim FDTD.

Każda para E/H jest zespolonym dumpem częstotliwościowym openEMS.
Dane są przycinane do obszaru XY płytki z marginesem 1 mm,
a Z jest ograniczone do ośmiu powierzchni dla czterech warstw.
Surowe pliki natywne HDF5 pozostają zachowane. Po normalizacji 1 V
powstają oddzielne pliki NPZ dla każdej fizycznej warstwy i strony.

## Maska, E, H i prąd powierzchniowy

Nowy tryb maskuje wyłącznie obszary poza rzeczywistym polygonem Cu,
z zachowaniem szczelin, dziur i niezależnych wysp. NIE używa dawnego
halo jednej lokalnej komórki, które zasłaniało okolice miedzi.

E oznacza V/m, H oznacza A/m, natomiast mapę prądu opisujemy wyraźnie
jako K_face_proxy = n_face × H_t(z_copper +/- 10 µm) [A/m].
Zapisujemy składowe zespolone, nie wyłącznie obraz PNG.
Kolor mapy K pokazuje moduł amplitudy, strzałki chwilowy kierunek
przy fazie 0 stopni. Każda strona posiada osobne dane.

To przybliżenie na podstawie próbkowanego H, NIE graniczny prąd na
miedzi. OpenEMS interpoluje do węzłów; idealna warstwa PEC ma w
modelu zerową grubość. Nie mamy tu rozwiązania skin effect,
proximity effect ani strat miedzi o skończonej grubości.
Dla fizycznych wniosków trzeba sprawdzić zbieżność odległości sond,
siatki i model przewodności. Nie wolno oznaczać proxy jako
zweryfikowanego J albo wnioskować z niego gotowych strat.

## Raport i jakość wizualizacji

Nowy raport HTML zawiera osobne sekcje dla każdej warstwy i strony,
obrazy XY |E|, |H| i |K_face_proxy|, strzałki oraz dokładne Z sondy.
Obraz jest wysokiej rozdzielczości i można go powiększać oraz przewijać.
Zoom na PNG nie dodaje próbek pola i nie zastępuje przyszłej
interaktywnej eksploracji NPZ czy 3D. Istniejący raport dalekich
przekrojów pozostaje nienaruszony.

## Plan etapowy / akceptacja

A. Kod, GUI, CLI, siatka, HDF5/NPZ, osobny HTML, testy syntetyczne.
B. Windows PREPARE-ONLY na małej płytce: osiem sond, poprawna
   geometria i pola Z, koszt CFL/cells, bez FDTD do czasu audytu.
C. Jeden krótki natywny FDTD: poprawność H/E, fazy, maski
   prawdziwej miedzi, zgodność prądów z portem i konwencją n × H.
D. Test zbieżności dla modelu PEC i porównanie z fizycznym odniesieniem.
   Dopiero później rozbudowa viewerów i ilościowe modele skin/proximity.

Stan funkcji eksperymentalny do czasu testów Windows. Sama obecność
kolorowej mapy, Topology audit PASS czy HDF5 processed nie stanowi
walidacji gęstości prądu.
