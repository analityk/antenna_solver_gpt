# TODO — PCB: aktualny stan i następne kroki

Stan na 2026-10-20. Ten plik opisuje **faktyczny stan main** po PCB-015B/B1/B2
oraz kolejność dalszej pracy. Nie oznacza, że pozycje otwarte zostały wykonane.

## Co jest już zrobione

### PCB-013A — profile i sterowanie openEMS

Dostępne są profile `preview/design/verify` w
`parameters/openems_profiles.toml`, potwierdzenie Y/N/E, `--openems-set`,
`--yes`, ustawienia timestep/EndCriteria/NrTS/MaxTime/BC/runtime, pola E/H
domyślnie w częstotliwości środkowej oraz raport fazowy co 15°.

`NrTS` jest sufitem bezpieczeństwa, nie definicją jakości.

### PCB-015A1 — walidacja geometrii bez kwadratowej pętli Python

Commit:
`017dfe1254fa173747f7d1a6535eec35979b779a`

Usunięto pełny O(N²) scan par krawędzi w `validation.py::_polygon()`.
Walidacja pozostaje fail-closed: GEOS/Shapely sprawdza poprawność polygonu,
bez `make_valid`, `buffer(0)`, snappingu ani automatycznej naprawy.

Lokalny pomiar użytkownika na tej samej serpentynie:

- przed: 3 364 506 592 wywołania, 687,776 s pod `cProfile`,
- po: 122 243 799 wywołań, 58,034 s pod `cProfile`.

To około 27,5× mniej wywołań i 11,9× krótszy profilowany przebieg. Czasy
`cProfile` nie są zwykłym wall-clock i nie służą do prognoz runtime.

### PCB-015A2/A3 — FAST / APPROX reduced quasi-TEM

Commity:

- `5b1695af2596baae301b284c8bd70886c5857b85`
- `0ac8f3b0a92dc9c9926ae3d59a14642698c215de`

Istnieje osobny solver `antenna_lab.pcb.reduced_control`, który:

- nie importuje natywnego openEMS,
- nie buduje domeny 3-D/PML/Yee-gridu,
- ekstrahuje jednoznaczne prostoliniowe/ortogonalne odcinki,
- liczy izolowany mikrostrip modelem Hammerstad–Jensen,
- rozwiązuje częstotliwościową sieć TL + idealne R/L/C,
- zapisuje Z(f), S11(f), SWR, graf i provenance,
- jawnie oznacza wynik `reduced_quasi_tem / approximate`,
- jawnie pomija promieniowanie, dyspersję, straty linii i pasożyty zakrętów/padów.

Sprzężenia równoległych odcinków są wykrywane, ale nie są jeszcze rozwiązywane.
Solver nie udaje wtedy wyniku.

Testy PCB-015A:

- celowane przed publikacją: 76/76 PASS,
- końcowe reduced: 17/17 PASS,
- pełny unittest uruchomiony raz: 414 testów, 2 failures, 27 errors, 3 skipped;
  były to istniejące/downstream odmowy audytu siatki i stara oczekiwana wielkość
  emtest3, nie błędy nowych testów reduced.

W PCB-015A nie uruchamiano natywnego FDTD.

## Faktyczny stan lokalnej serpentyny

Lokalny plik użytkownika `test_spirala.zip` istnieje poza śledzonym stanem repo.
Po PCB-015B użytkownik uruchomił FAST na rzeczywistym ZIP-ie. Kolejne jawne
blokery ujawniły dwa zbyt konserwatywne założenia oraz właściwy problem ekstrakcji.

PCB-015B jest **ukończone**: plated PTH top→udowodniony bottom ground może być
traktowany w FAST jako idealne połączenie do `ground`, z jawnym pominięciem
indukcyjności/strat via i rozłożonej impedancji topowego polygonu masowego.
Signal vias, inner-layer vias, NPTH i kontakty niejednoznaczne nadal fail closed.

PCB-015B1 dopuściło naturalny setback bottom ground od obrysu płytki. Rzeczywisty
bottom `bottom:copper_0001` ma jeden polygon, zero holes, pole
599,50695 mm² i bbox około 24,49×24,48 mm przy board 25×25 mm; różnica
25,49305 mm² wynika z około 0,25–0,26 mm cofnięcia od krawędzi. FAST nie wymaga
już `ground == board outline`; wymaga jednej ciągłej, hole-free referencji
pokrywającej całą aktywną miedź sygnałową i powierzchnie kontaktów source/RLC.

PCB-015B2 przestało odrzucać cały conductor tylko dlatego, że Gerberowa
polygonizacja prostoliniowej trasy zawiera lokalne round/chamfered joins.
Dopuszczone są wyłącznie width-scale resztki przy udowodnionych końcach/złączach;
rzeczywiste nielokalne krzywe/skosy nadal fail closed. Użytkownik podał, że po
tych zmianach lokalne testy reduced przechodzą.

Rzeczywisty run serpentyny zatrzymuje się obecnie na:

`Reduced extraction: curved/oblique top copper top:copper_0001 has no resolvable straight sections.`

Diagnostyka tego conductora:
- pole 14,85795 mm²,
- bbox (-3,79, -17,83) … (2,64, 0,43) mm,
- 3088 wierzchołków,
- 1085 krawędzi sklasyfikowanych jako oblique i 2003 orthogonal,
- łączna długość krawędzi oblique około 52,257 mm,
- przykładowa długa krawędź (-0,56,-0,43)→(-0,57,-2,29) mm ma tylko około
  0,31° odchylenia od pionu.

To nie jest mały pad ani wyłącznie lokalny narożnik. Obecny FAST próbuje
odtworzyć centerline z końcowego `CopperPolygon`, mimo że importer Gerbera
wcześniej zna źródłowe `Line`/`Arc` i szerokość apertury. To jest aktualny
blocker. Nie należy go obchodzić globalną tolerancją kąta ani dalszym
rozluźnianiem polygon guardów.

Nie ma jeszcze wyniku FAST Z/S11 dla realnej serpentyny.

## Priorytety

### P0 — PCB-015C0: zweryfikować source-route checkpoint

Checkpoint implementuje detached Line/Arc, audyt ordered composition,
normalizację/projekcję i preferencję source axes w FAST. Przy publikacji nie
potwierdzono jeszcze realnej serpentyny. Aktualny krok to lokalna weryfikacja
route-status/Arc/połączeń osi i kontaktów; nie luzowanie polygon guardów.
Poniższy kontrakt pozostaje kryterium odbioru.

Następny krok ma usunąć potrzebę zgadywania centerline z 3-tysięcznego polygonu.

Wymagania:

- zachować z importu Gerbera źródłowe stroke/route provenance co najmniej dla
  `Line` i `Arc`: geometria osi, szerokość apertury, warstwa i provenance źródła,
- nie zastępować finalnego `CopperPolygon`; polygon pozostaje źródłem prawdy
  dla fizycznego kontaktu, clear polarity, PTH, padów i ciągłości,
- po końcowej kompozycji boolean przypisać route primitive do dokładnie jednego
  finalnego conductora albo fail closed; clear/restore nie może pozostawić
  niezweryfikowanego stroke jako aktywnej linii,
- normalizacja i geometry resolution muszą objąć route provenance spójnie z
  resztą geometrii; bez drugiego, niezależnego snappingu,
- FAST ma budować odcinki z udowodnionych centerlines/provenance, a finalny
  polygon ma potwierdzać istnienie i ciągłość przewodnika,
- dowolny kąt prostego `Line` ma być obsługiwany bez wymogu `x1==x2` /
  `y1==y2`; nie wprowadzać arbitralnej tolerancji kąta,
- prawdziwe `Arc` może pozostać jawnie unsupported w pierwszym checkpointcie,
  jeśli nie da się go poprawnie sprowadzić bez zgadywania; metadata musi jednak
  zachować fakt istnienia łuku,
- pady/flashe/regions nie mogą zostać fałszywie potraktowane jako linia TL,
- zachować deterministyczność i strict JSON provenance.

Kryterium sukcesu checkpointu: realna serpentyna ma przejść za obecny błąd
`top:copper_0001 has no resolvable straight sections` albo zatrzymać się na
nowym, bardziej fizycznym i jednoznacznym ograniczeniu źródłowego route
provenance. Nie wolno produkować Z/S11 przez zgadywanie geometrii.

### P1 — PCB-015C: pairwise coupled microstrip

Dopiero po poprawnym route extraction wrócić do głównego braku fizyki FAST.

Wymagania:

- nie ignorować równoległych overlapów,
- nie używać arbitralnego współczynnika sprzężenia,
- wyznaczać parametry sprzężonego przekroju metodą fizyczną:
  macierze C/C0 → L albo udokumentowany model even/odd,
- zbudować poprawny stamp wieloportowy do istniejącej sieci,
- splitować sekcje tam, gdzie zmienia się stan sprzężenia,
- zachować fail-closed dla 3+ przewodników/nierozwiązywalnej topologii,
- porównać kierunek zmian gap/coupling na testach syntetycznych.

Po tym kroku realna serpentyna powinna po raz pierwszy mieć FAST Z/S11, nadal
jawnie approximate i bez gwarancji błędu względem full-wave.

### P2 — skrócić preparation full-wave bez zmiany fizyki

Po usunięciu starego O(N²) profil pokazuje nowe bottlenecki:

- `compact_features()`: 17 wywołań, około 31,3 s cumulative pod cProfile,
- `make_gerber_mesh_anchor_plan()`: 7 wywołań, około 27,3 s cumulative,
- `make_pcb_domain_mesh()`: 2 wywołania, około 25,0 s cumulative,
- całe `prepare-only`: około 58,0 s pod cProfile.

Czasy cumulative nakładają się i nie wolno ich sumować.

Kierunek:

- policzyć immutable physical feature model raz dla niezmienionej geometrii
  i przekazywać go dalej,
- nie wywoływać `compact_features()` wielokrotnie w plannerach/audytach,
- utworzony i zaudytowany finalny mesh przekazać do native preparation zamiast
  budować ten sam mesh po raz drugi.

Bez osłabiania feature/copper/port audits.

### P3 — ekonomiczna domena full-wave

Dopiero po użytecznym FAST wrócić do:

- diagnostyki bilansu komórek domeny,
- PCB-specific absolute padding XY/Z zamiast samego wavelength padding,
- taniego prepare-only sweepu domen,
- minimalnej liczby FDTD do convergence check,
- DESIGN jako ekonomicznego full-wave,
- VERIFY jako konserwatywnego odniesienia.

Nie zmieniać kilku osi jakości naraz.

### P4 — pola i viewer PCB

Częściowo wykonane w PCB-016A:

- domyślny widok XY raportu używa teraz Fit PCB: bbox całej geometrii PCB
  + 6% marginesu zamiast pełnego extentu dumpu,
- E i H w tym samym widoku używają identycznego cropu,
- browser sampling 80×80 jest wybierany wewnątrz pokazywanego zakresu,
  więc nie marnuje rozdzielczości ekranu na puste powietrze,
- statyczne diagramy fazowe XY używają tego samego viewportu,
- zmiana jest wyłącznie prezentacyjna: NPZ, field dump, mesh i FDTD pozostają
  bez zmian; stare przebiegi można przerysować bez ponownego solve.

Pozostaje do wykonania:

- field dump ograniczony do PCB bbox + jawny margines,
- opcjonalny Full field extent / full-domain dump,
- `xy_dielectric_mid`,
- Ez / |E| dla laminatu,
- pionowy przekrój trace→ground,
- sensowny viewport pionowych XZ/YZ,
- playback fazy co 15° bez dodatkowego FDTD pozostaje zachowany.

## Zasady dalszej pracy

1. FAST ma redukować fizykę do istotnych modów/napięć/prądów; nie implementować
   "sparse FDTD" przez pomijanie komórek o chwilowo małym polu.
2. Promieniowanie rzędu około 1% nie jest celem dokładności FAST, ale nie wolno
   deklarować 1% błędu bez kalibracji.
3. Geometry resolution pozostaje niezależna od siatki EM.
4. Nie upraszczać źródłowej miedzi po cichu.
5. Unsupported topology -> fail closed, nie zgadywać.
6. Full-wave DESIGN/VERIFY pozostaje arbitrem dla finalistów i kalibracji FAST.
7. Drogie FDTD tylko wtedy, gdy decyzji nie da się podjąć z modelu reduced,
   prepare-only albo istniejących wyników.
8. Testy na lokalnym komputerze użytkownika są tanie; testy wykonywane przez
   zdalnego agenta są kosztowne. Agent ma preferować analizę statyczną i mały,
   bezpośrednio związany zestaw testów, a pełny unittest uruchamiać najwyżej raz
   i tylko wtedy, gdy jest naprawdę potrzebny do decyzji.
9. Znaczącą pracę commitować i publikować na origin/main przed drogim testem.
   PASS/PARTIAL/FAIL, brak fixture użytkownika lub błąd integracyjny nie blokuje
   checkpointu/pusha. Po nieudanym teście opublikować stan wraz z diagnozą,
   zamiast pozostawiać pracę wyłącznie w środowisku agenta.

## Docelowy układ

```text
FAST / APPROX
  reduced quasi-TEM / transmission-line network
  -> codzienne iteracje i sweepy
  -> ground PTH jako jawna aproksymacja po klasyfikacji
  -> coupled-line physics wymagane dla serpentyny

DESIGN
  ekonomiczny full-wave openEMS
  -> kontrola efektów 3-D pominiętych przez FAST

VERIFY
  konserwatywny openEMS
  -> finaliści i kalibracja modelu FAST
```

Najbliższy pojedynczy krok to **lokalna weryfikacja PCB-015C0 na source routes**,
nie dalsze strojenie PML, viewer ani coupled-line solver przed poprawną ekstrakcją osi.
