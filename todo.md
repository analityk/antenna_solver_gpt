# TODO — PCB: aktualny stan i następne kroki

Stan na 2026-10-08. Ten plik opisuje **faktyczny stan main** po PCB-015A oraz
kolejność dalszej pracy. Nie oznacza, że pozycje otwarte zostały wykonane.

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

## Faktyczny blocker lokalnej serpentyny

Lokalny plik użytkownika `test_spirala.zip` istnieje poza śledzonym stanem repo
i został uruchomiony po PCB-015A. FAST zatrzymuje się obecnie na:

`Reduced v1: drills/via paths unsupported (not silently omitted).`

To jest blanket guard wykonywany przed właściwą ekstrakcją reduced.

Z zapisanego lokalnie `geometry.json` ustalono dwa PTH:

1. `Drill_PTH_Through.DRL:1`
   - kontakt top: `top:copper_0002`
   - kontakt bottom: `bottom:copper_0001`
   - `connected_layer_roles = ['top', 'bottom']`

2. `Drill_PTH_Through.DRL:2`
   - kontakt top: `top:copper_0003`
   - kontakt bottom: `bottom:copper_0001`
   - `connected_layer_roles = ['top', 'bottom']`

Oba dotykają tej samej ciągłej płaszczyzny bottom ground. To uzasadnia następny
wąski krok: w modelu FAST traktować taki **udowodniony PTH top→continuous-ground**
jako idealne połączenie do węzła `ground`, z jawnym pominięciem indukcyjności
via i strat barrel. Nie wolno rozszerzyć tego automatycznie na signal vias,
inner-layer vias, NPTH albo kontakty niejednoznaczne.

Nie ma jeszcze wyniku FAST Z/S11 dla serpentyny.

## Priorytety

### P0 — PCB-015B: ideal ground-connected PTH w reduced solverze

Do zrobienia:

- najpierw udowodnić ciągły bottom ground,
- fizycznie sklasyfikować plated PTH,
- wspierać tylko PTH dotykający dokładnie jednego top conductor i udowodnionego
  bottom ground,
- cały taki top conductor mapować do sieciowego `ground`,
- nie ekstrahować go jako zwykłej linii mikrostripowej,
- terminal źródła/RLC na takim conductorze mapować do `ground`,
- zapisać `ground_vias`, `ground_connected_top_conductors`,
  `via_inductance` i `via_barrel_loss` jako jawne uproszczenia,
- signal/inner/ambiguous vias nadal fail closed.

Kryterium sukcesu na serpentynie: przejść **za** blanket-via rejection. Jeżeli
kolejną barierą będzie `coupling_required`, PCB-015B jest sukcesem.

### P1 — PCB-015C: pairwise coupled microstrip

To jest główny brak fizyki FAST dla serpentyny.

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

Pozostaje do wykonania:

- field dump ograniczony do PCB bbox + jawny margines,
- opcjonalny full-domain dump,
- `xy_dielectric_mid`,
- Ez / |E| dla laminatu,
- pionowy przekrój trace→ground,
- domyślny viewport Fit PCB,
- Full field extent jako opcja,
- wspólny crop E/H,
- playback fazy co 15° bez dodatkowego FDTD.

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
8. PASS/PARTIAL/FAIL nie blokuje trwałego commita/pusha znaczącej pracy.

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

Najbliższy pojedynczy krok to **PCB-015B**, nie dalsze strojenie PML ani viewer.
