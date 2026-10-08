# TODO — PCB solver: wydajność domeny i użyteczne pola

Stan planu: do wykonania po zakończeniu bieżącej pracy nad wydajnością.
Dokument ma być planem kolejnych zmian, nie deklaracją że zostały wykonane.

## Zmiana kierunku: najpierw model zredukowany, nie tańszy pełny FDTD

Po profilowaniu `prepare-only` i analizie celu projektowego priorytet zmienia się.

Użytkownika interesuje przede wszystkim impedancja, rezonanse i sprzężenia linii
mikropaskowej. Strata około 1% mocy przez promieniowanie nie jest istotna dla
szybkiego modelu projektowego. Pełny 3D FDTD pozostaje narzędziem weryfikacyjnym,
a nie domyślnym silnikiem każdej iteracji.

Nie implementować "sparse FDTD" przez pomijanie komórek o małym chwilowym polu.
W FDTD nie jest to bezpieczne kryterium lokalne: pole propaguje się między komórkami.
Zamiast tego zredukować liczbę niewiadomych fizycznie: napięcia/prądy i dominujące
mody quasi-TEM wzdłuż ścieżek oraz ich lokalne sprzężenia.

### Priorytet 0A — naprawić koszt przygotowania modelu

Profil `cProfile` dla serpentyny pokazał patologiczny koszt walidacji:

- około 3,36 mld wywołań funkcji Python,
- `validate_pcb_geometry`: około 630 s cumulative, 21 wywołań,
- `_intersect`: około 130 mln wywołań,
- `_on_segment`: około 523 mln wywołań,
- `_cross`: około 783 mln wywołań,
- `make_pcb_domain_mesh`: wykonywany dwa razy w jednej ścieżce prepare/run.

Liczby 3,36 mld dotyczą wywołań funkcji walidatora, NIE komórek FDTD.

Naprawa ma zachować fail-closed semantics, ale usunąć ręczny O(N²) test
samoprzecięć polygonu. Użyć GEOS/Shapely do sprawdzenia poprawności polygonu,
bez `make_valid`, `buffer(0)` ani automatycznej naprawy. Tanie kontrole liniowe
(finite, liczba punktów, zdegenerowane krawędzie, pole) zachować.

Pełną walidację wykonywać na granicach, gdzie geometria rzeczywiście się zmienia
(import -> normalize -> quantize/materialize), a nie wielokrotnie w czystych
helperach meshera/portu. Po utworzeniu finalnego mesha przekazać ten sam obiekt
do native preparation zamiast budować go drugi raz.

Ta część jest obowiązkowym checkpointem przed modelem zredukowanym, bo "fast"
solver nie może czekać minutami na walidację wejścia.

### Priorytet 0B — fast PCB reduced-order solver

Dodać osobny, jawnie przybliżony solver dla obsługiwanego podzbioru PCB:

- mikrostrip na top copper nad ciągłą ground plane,
- jednorodny laminat,
- ścieżki głównie ortogonalne / rectilinear,
- lumped R/L/C z istniejącego modelu,
- pojedyncza niebranżowana ścieżka lub układ, którego topologia może być
  jednoznacznie wyprowadzona; przypadki niejednoznaczne fail closed.

Solver ma operować na grafie/napięciach/prądach, nie na objętościowym Yee-gridzie.
Wykorzystać istniejące `compact_features()`: ma już fizyczne szerokości pasków,
clearance/gap pairs i zakresy równoległych odcinków. Nie tworzyć drugiego,
sprzecznego ekstraktora wymiarów.

Minimalny model v1:

- straight microstrip sections -> quasi-TEM per-unit-length L/C (or Z0/epsilon_eff),
- długości elektryczne wzdłuż wyprowadzonej osi ścieżki,
- istniejące lumped R/L/C w grafie,
- równoległe odcinki rozpoznane z istniejących clearance features,
- coupling tylko wtedy, gdy można go policzyć z jawnie udokumentowanego modelu;
  nie wymyślać arbitralnego współczynnika,
- brak modelowania promieniowania jako cecha kontraktu fast solvera,
- brak udawania, że v1 zastępuje full-wave przy via, slotach, złożonych groundach,
  silnej radiacji, oblique/ambiguous geometry.

Preferowany wynik:

- Z(f), S11(f), SWR,
- podstawowe napięcia/prądy wzdłuż segmentów,
- metadane: długości, szerokości, h, epsilon_r, użyty model, coupling sections,
  jawne ograniczenia i powody fail-closed.

Nie uruchamiać nowego FDTD w ticketcie implementacyjnym. Jeśli istnieją już zapisane
wyniki full-wave, można je tylko odczytać do porównania; brak takich danych nie
może prowadzić do wymyślania referencji.

### Architektura jakości po tej zmianie

```text
FAST / APPROX
  reduced quasi-TEM / transmission-line graph
  -> codzienne iteracje, sweepy, kierunek zmian
  -> promieniowanie celowo pomijane

DESIGN
  ograniczony full-wave openEMS
  -> weryfikacja efektów 3D i sprzężeń, które fast model pomija

VERIFY
  konserwatywny openEMS
  -> finaliści i kalibracja modelu fast
```

Docelowo full-wave ma służyć do kalibracji modelu zredukowanego. Jeśli różnica
FAST vs VERIFY pozostaje akceptowalna dla danego typu PCB, kolejne iteracje tego
typu nie wymagają pełnego FDTD.

---

## Dlaczego ten plan istnieje

Obecny solver PCB odziedziczył część polityki domeny i wizualizacji typowej dla anten.
To jest zbyt kosztowne i mało użyteczne dla mikrostripu nad płaszczyzną masy.

Przykład referencyjny z serpentyną:

- PCB: około 25 × 25 mm = 6,25 cm²,
- widoczny przekrój domeny: około 80 × 80 mm = 64 cm²,
- solver: 5 970 456 komórek,
- 70 080 timestepów,
- 4707,84 s = około 78 min 28 s,
- ustalona wydajność około 94 MC/s,
- zakończenie po osiągnięciu kryterium energii.

Koszt FDTD skaluje się w pierwszym przybliżeniu jak:

`liczba komórek × liczba timestepów`.

Nie wolno więc traktować rozmiaru domeny jako kosmetyki. Jednocześnie procent pustego
obszaru na obrazku 2D nie jest równy procentowi czasu CPU: siatka jest
niejednorodna, solver jest 3D, a PML ma inny koszt. Najpierw trzeba zmierzyć udział
komórek, potem zmniejszać domenę i sprawdzać zbieżność.

Drugi problem jest niezależny: aktualny widok pola PCB pokazuje głównie duży
przekrój domeny nad płytką. Dla mikrostripu h≈0,2 mm interesujące pole elektryczne
jest przede wszystkim przy ścieżce, w laminacie i pomiędzy ścieżką a ground plane.
Dlatego obecny viewer może być poprawny formalnie, ale jest mało użyteczny
inżyniersko.

---

## Zasady, których nie łamiemy

1. Geometria CAD / geometry resolution pozostaje niezależna od domeny FDTD.
2. Nie upraszczamy miedzi tylko po to, żeby wynik był tańszy.
3. Zmiana viewportu albo obszaru dumpu pól nie może zmieniać geometrii ani siatki.
4. Pole ma pozostać dostępne domyślnie dla przebiegów PCB.
5. Krok fazy raportu pozostaje 15°; fazy są odtwarzane z zespolonego fazora bez
   dodatkowego FDTD.
6. Nie przewidujemy wall-clock runtime z heurystyk. Raportujemy komórki,
   timestep/CFL i cell-updates.
7. Drogie FDTD uruchamiamy dopiero po tanich prepare-only i tylko dla finalistów.
8. Każda zmiana wpływająca na fizykę domeny wymaga porównania z większą domeną.
9. PASS/PARTIAL/FAIL nie blokuje commita ani pushu; praca ma być trwała.

---

# Kolejność wykonania

## 1. Najpierw diagnostyka kosztu domeny — bez zmiany fizyki

### Cel

Przestać zgadywać, ile kosztuje „puste powietrze”.

### Implementacja

Do prepare/summary dodać diagnostykę domeny PCB:

- bbox PCB / outline,
- bbox całej domeny,
- bbox ordinary domain bez PML,
- grubość paddingu po każdej stronie,
- liczba komórek całkowita,
- liczba komórek PML,
- liczba ordinary-air cells,
- liczba komórek, których XY leży wewnątrz footprintu PCB,
- liczba komórek poza footprintem PCB,
- liczba komórek laminatu,
- liczba komórek nad PCB,
- liczba komórek pod PCB,
- udziały procentowe każdej kategorii,
- excitation-only cell-updates dla całej domeny,
- opcjonalnie ten sam wskaźnik rozbity według kategorii.

Kategorie nie muszą udawać dokładnego profilera CPU. Mają odpowiadać na pytanie:
„które części domeny tworzą komórki aktualizowane przez FDTD?”.

### Dlaczego

Obraz 2D pokazujący ~10× większą powierzchnię niż płytka jest mocną wskazówką,
ale nie jest jeszcze pomiarem kosztu 3D. Ta diagnostyka daje bazę do świadomego
cięcia domeny.

### Acceptance

Prepare-only podaje jednoznaczny bilans komórek i zapisuje go w summary.json.
Nie uruchamia FDTD i nie zmienia istniejącej siatki.

---

## 2. Oddzielić domenę PCB od „antenowego” paddingu w długościach fali

### Problem

Obecne `air_padding_wavelengths` skaluje domenę jak dla struktury promieniującej.
Dla mikrostripu nad ground plane może to generować dziesiątki mm powietrza, mimo
że kluczowe pole jest skupione przy strukturze o skali sub-mm.

### Kierunek

Dodać PCB-specific absolute padding, niezależny dla osi:

- `xy_padding_mm`,
- `z_top_padding_mm`,
- `z_bottom_padding_mm`.

Nie usuwać od razu trybu wavelength-based; zachować go jako alternatywę /
fallback i dla porównań.

Przykładowy model konfiguracji:

```toml
domain_padding_mode = "absolute"
xy_padding_mm = 10.0
z_top_padding_mm = 10.0
z_bottom_padding_mm = 10.0
```

To są kandydaci do testu, nie jeszcze zatwierdzone wartości produkcyjne.

PML jest poza ordinary domain i nadal musi być poprawnie dodany.

### Dlaczego

Dla PCB 25 × 25 mm:

- obecne około 80 × 80 mm -> 64 cm² XY,
- przy 10 mm z każdej strony -> około 45 × 45 mm -> 20,25 cm² XY.

To nie oznacza automatycznie 68% oszczędności, bo mesh jest niejednorodny, ale
potencjał redukcji jest wystarczająco duży, żeby go zmierzyć.

### Ważne

Nie zakładać, że góra i dół wymagają tego samego paddingu. Ground plane może
sprawić, że optymalna domena Z będzie asymetryczna. Najpierw mierzyć, potem
ustalać defaulty.

---

## 3. Tani sweep domeny tylko prepare-only

Dla reprezentatywnej płytki testowej uruchomić bez FDTD kandydatów:

- 5 mm,
- 10 mm,
- 20 mm,
- obecny tryb wavelength-based.

Dla każdego zapisać:

- shape Nx×Ny×Nz,
- cells,
- min XYZ,
- CFL dt,
- estimated excitation steps,
- excitation-only cell-updates,
- udział PML / air / board-footprint,
- feature/port/component audits.

### Decyzja po prepare-only

Nie wybierać najmniejszej domeny automatycznie.
Wybrać 1–2 kandydatów dających największą redukcję kosztu bez patologicznego
mesha i dopiero je wysłać do FDTD.

---

## 4. Zbieżność domeny: minimalna liczba drogich FDTD

### Cel

Ustalić najmniejszą domenę, która nie zmienia istotnie wyniku elektrycznego.

### Procedura

Najpierw porównać:

- 10 mm,
- większe odniesienie, np. 20 mm albo aktualny tryb.

Jeśli różnica jest zbyt duża, dopiero wtedy badać wartość pośrednią.

Porównywać przez całe zapisane pasmo:

- R(f),
- X(f),
- |S11|(f),
- częstotliwości minimów / zer reaktancji,
- actual_iterations,
- termination status.

Nie dopasowywać domeny do oczekiwanych 50 Ω.
Interesuje nas stabilność wyniku względem rozszerzania domeny.

### Kryterium

Najpierw zebrać dane. Tolerancję produkcyjną ustalić po pierwszym porównaniu,
zamiast wpisywać arbitralny próg przed zobaczeniem skali błędu.

Jeśli 10 mm i większa domena dają praktycznie ten sam wynik, 10 mm może zostać
profilem preview/design. Verify powinien pozostać bardziej konserwatywny.

---

## 5. Zmienić field dump PCB: zapisuj to, co naprawdę chcemy oglądać

### Problem

Aktualne płaszczyzny są rozciągnięte przez prawie całą ordinary domain. To:

- daje mało czytelny viewer,
- zwiększa liczbę punktów DFT i I/O,
- nie pokazuje dobrze pola pomiędzy ścieżką i ground plane.

### Zmiana A — extent dumpu

Domyślny dump pól PCB powinien obejmować:

- bbox płytki + niewielki jawny margines,
- nie całą domenę FDTD.

Osobna opcja diagnostyczna może nadal zapisywać full-domain field plane.

To NIE zmienia solver domain. Zmniejsza tylko pasywny obszar próbkowania DFT.

### Zmiana B — nowe płaszczyzny

Domyślny zestaw dla PCB powinien zawierać:

1. `xy_air`
   - tuż nad top copper,
   - do oceny fringing/leakage nad PCB.

2. `xy_dielectric_mid`
   - w połowie grubości laminatu,
   - do pokazania pola biegnącego wzdłuż całej ścieżki.

3. pionowy przekrój przez feed / istotny odcinek,
   - top copper -> dielectric -> ground,
   - pokazuje bezpośrednio koncentrację pola między ścieżką i masą.

Nie uruchamiać dodatkowego FDTD.

### Zmiana C — składowe pola

Dla `xy_dielectric_mid` domyślnie pokazać co najmniej:

- `Ez` jako podpisaną chwilową składową do animacji fazowej,
- `|E|` albo envelope jako osobny, nieanimowany widok diagnostyczny.

Obecny XY viewer skupiony na Ex/Ey nie wystarcza dla mikrostripu, gdzie pionowa
składowa pola elektrycznego jest kluczowa.

---

## 6. Viewer: PCB ma zajmować ekran

### Domyślne zachowanie

- viewport = bbox PCB + około 5–10% marginesu wizualnego,
- E i H używają dokładnie tego samego cropu,
- plansza wykorzystuje realnie szerokość panelu,
- krok fazy = 15°,
- play działa na 0…345°.

### Kontrole

Dodać co najmniej:

- `Fit PCB`,
- `Full field extent`.

Opcjonalnie później:

- `Fit active copper`.

Nie kadrować domyślnie tylko do serpentyny: cała PCB, ground/pady/krawędzie są
częścią kontekstu EM.

### Dlaczego

Przy obecnym widoku tylko kilka procent powierzchni ekranu może zawierać
interesującą część struktury. To jest wada prezentacji, nie argument za zmianą
fizyki solvera.

---

## 7. Dopiero potem stroić profile preview/design/verify

PCB-013A poprawnie przeniosło profile do `parameters/openems_profiles.toml`.
Dalsze strojenie profili ma być oparte na pomiarze z kroków 1–6.

Kolejność strojenia:

1. domain size,
2. cells_per_wavelength,
3. EndCriteria,
4. ewentualny MaxTime dla jawnego draft/preview,
5. dopiero na końcu eksperymenty z BC (np. MUR vs PML).

Nie zmieniać kilku osi naraz, bo wtedy nie wiadomo, skąd pochodzi różnica.

### Preview

Ma być realnie szybkim narzędziem do oceny kierunku, nie „designem z inną etykietą”.
Może mieć mniej cells/λ i luźniejsze EndCriteria, ale nadal musi uruchamiać FDTD.

### Verify

Ma być konserwatywnym punktem odniesienia dla finalistów, a nie profilem do
codziennego sweepowania.

---

## 8. Boundary conditions dopiero po ustaleniu domeny

Nie przechodzić od razu na MUR tylko dlatego, że jest tańszy.

Najpierw:

- zoptymalizować rozmiar domeny z PML,
- uzyskać stabilne wyniki,
- dopiero potem zrobić jeden kontrolowany test mixed/MUR przeciw PML.

Powód: jednoczesna zmiana rozmiaru domeny i BC uniemożliwia rozdzielenie wpływu
odbicia od granicy od wpływu samej odległości granicy.

---

## 9. Raport końcowy dla każdego kandydata

Raport/summary powinien jasno pokazywać:

### Geometria
- geometry resolution,
- PCB dimensions,
- stackup thickness.

### Mesh/domain
- domain size XYZ,
- PCB padding per face,
- mesh shape,
- total cells,
- PML cells,
- ordinary-air cells,
- board-footprint cells,
- minimum XYZ.

### Time
- CFL dt,
- excitation duration,
- estimated excitation steps,
- actual iterations,
- EndCriteria,
- NrTS safety ceiling,
- MaxTime jeśli użyty.

### Cost
- excitation-only cell-updates,
- actual cell-updates = total cells × actual iterations,
- native reported MC/s,
- wall time wyłącznie jako zmierzony fakt po runie, nigdy jako predykcja.

### Fields
- dump extent,
- planes,
- frequencies,
- phase step,
- components shown.

To pozwoli porównywać dwa runy bez ręcznego grzebania w logach.

---

# Proponowana kolejność ticketów

## PCB-014A — domain cost diagnostics

Tylko bilans domeny i komórek. Bez zmiany fizyki, bez FDTD.

## PCB-014B — absolute PCB domain padding

Dodać jawny padding mm i prepare-only sweep 5/10/20/current.

## PCB-014C — domain convergence

Tylko 1–2 potrzebne FDTD. Wybrać produkcyjne paddingi preview/design/verify.

## PCB-014D — PCB field sampling

Crop dumpów do PCB, `xy_dielectric_mid`, Ez/|E|, pionowy przekrój.

## PCB-014E — field viewer usability

Fit PCB / Full extent, większe canvasy, 15° playback, wspólny crop E/H.

## PCB-014F — quality calibration

Dopiero na ustalonej domenie skalibrować cells/λ, EndCriteria i ewentualny
jawny draft/MaxTime.

Każdy ticket ma kończyć się commitem i pushem niezależnie od PASS/PARTIAL/FAIL.

---

# Warunek zakończenia tego etapu

Etap można uznać za udany, gdy:

1. preview uruchamia prawdziwe FDTD i daje wynik użyteczny kierunkowo,
2. design nie marnuje większości komórek na nieuzasadnioną domenę,
3. verify pozostaje większym, konserwatywnym odniesieniem,
4. zmniejszenie domeny ma wykazaną zbieżność Z/S11,
5. viewer pokazuje całą PCB jako główny obiekt, a nie mały element ogromnego pola,
6. można zobaczyć pole E w laminacie i pomiędzy ścieżką a ground plane,
7. pole przy 15° fazy nie wymaga dodatkowego solve,
8. summary pozwala policzyć, gdzie poszedł koszt przebiegu,
9. nie uruchamiamy drogich FDTD do decyzji, które można podjąć na prepare-only.
