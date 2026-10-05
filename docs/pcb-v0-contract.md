# PCB v0 — kontrakt architektoniczny

## 1. Cel

Rozszerzyć `antenna_solver_gpt` o drugi typ geometrii: małe struktury PCB importowane z Gerberów i symulowane w openEMS.

Pierwsza wersja ma obsługiwać wyłącznie:

- jedną warstwę miedzi `F.Cu`,
- jeden jednorodny laminat,
- obrys płytki,
- jeden port pomiędzy dwoma obszarami miedzi,
- powietrze dookoła,
- generowanie geometrii openEMS,
- generowanie siatki,
- `prepare`,
- docelowo `run`,
- impedancję wejściową,
- S11,
- SWR.

Pierwsza wersja nie obsługuje:

- vias,
- warstw wewnętrznych,
- `B.Cu`,
- soldermaski,
- komponentów 3D,
- automatycznego rozpoznawania footprintów,
- automatycznego rozpoznawania netów,
- modeli SPICE,
- modeli S-parameter komponentów,
- anizotropii laminatu,
- roughness miedzi,
- pełnej dyspersji materiału,
- prądów powierzchniowych,
- pól E/H,
- NF2FF,
- wielu portów.

Nie rozszerzać zakresu bez osobnego zadania.

---

# 2. Zasada architektoniczna

Nie refaktoryzować obecnego modelu anten drutowych tylko po to, żeby dodać PCB.

Obecne:

- `Wire`
- `Plate`
- `Port`
- `Geometry`
- Quados
- biquad

mają pozostać działające.

PCB otrzymuje równoległy model danych.

Nie próbować na tym etapie tworzyć jednego uniwersalnego systemu geometrii EM.

Docelowa relacja:

```text
Antenna Geometry                   PCB Geometry
----------------                   ------------

Geometry                           PcbGeometry
 ├─ Wire[]                          ├─ CopperPolygon[]
 ├─ Plate[]                         ├─ BoardOutline
 └─ Port                            ├─ Substrate
                                    └─ PcbPort

             \                     /
              \                   /
                 openEMS adapter
```

---

# 3. Proponowana struktura katalogów

Dodać:

```text
src/antenna_lab/pcb/
    __init__.py
    model.py
    config.py
    gerber.py
    transform.py
    port.py
    validation.py

src/antenna_lab/solvers/
    pcb_mesh.py
    openems_pcb.py
```

Docelowo mogą powstać również:

```text
src/antenna_lab/visualization/
    pcb_preview.py
```

Nie przenosić istniejącego kodu, jeśli nie jest to wymagane.

---

# 4. Model danych PCB

## 4.1 BoardOutline

```python
@dataclass(frozen=True)
class BoardOutline:
    vertices_xy_m: tuple[tuple[float, float], ...]
```

Reprezentuje zamknięty obrys płytki.

Wymagania:

- współrzędne w metrach,
- co najmniej 3 unikalne punkty,
- polygon zamknięty logicznie,
- brak NaN/Inf.

---

## 4.2 CopperPolygon

```python
@dataclass(frozen=True)
class CopperPolygon:
    id: str
    vertices_xy_m: tuple[tuple[float, float], ...]
    z_m: float
```

Pierwsza wersja obsługuje tylko płaską miedź równoległą do XY.

Nie przechowywać tutaj parametrów materiałowych.

Miedź jest geometrią.

Parametry materiałowe należą do konfiguracji PCB.

---

## 4.3 Substrate

```python
@dataclass(frozen=True)
class Substrate:
    outline: BoardOutline
    z_min_m: float
    z_max_m: float
    epsilon_r: float
    loss_tangent: float
```

W PCB v0:

```text
z_max_m = 0
z_min_m = -thickness
```

Miedź top znajduje się na:

```text
z = 0
```

---

## 4.4 PcbPort

```python
@dataclass(frozen=True)
class PcbPort:
    id: str
    negative_xy_m: tuple[float, float]
    positive_xy_m: tuple[float, float]
    width_m: float
```

Port jest początkowo definiowany przez użytkownika.

Nie rozpoznawać automatycznie footprintu z Gerbera.

Znaczenie:

```text
negative_xy_m
    punkt należący do pierwszego obszaru miedzi

positive_xy_m
    punkt należący do drugiego obszaru miedzi
```

`width_m` określa poprzeczny rozmiar obszaru lumped port.

---

## 4.5 PcbGeometry

```python
@dataclass
class PcbGeometry:
    model: str
    outline: BoardOutline
    copper: list[CopperPolygon]
    substrate: Substrate
    port: PcbPort
    assumptions: list[str] = field(default_factory=list)
```

W PCB v0:

```text
model = "pcb"
```

Dodać:

```python
@property
def bounds(self):
    ...

def as_dict(self):
    ...
```

Kontrakt `as_dict()`:

- schema version,
- jednostki `m`,
- współrzędne,
- obrys,
- copper,
- substrate,
- port,
- assumptions.

---

# 5. Konfiguracja PCB

PCB nie powinno być definiowane wyłącznie przez Gerbery.

Minimalny zestaw wejściowy:

```text
F_Cu.gbr
Edge_Cuts.gbr
pcb.json
```

Przykładowy kontrakt:

```json
{
  "schema_version": 1,
  "model": "pcb",

  "files": {
    "copper_top": "F_Cu.gbr",
    "board_outline": "Edge_Cuts.gbr"
  },

  "copper": {
    "thickness_um": 35,
    "conductivity_s_m": 58000000,
    "model": "pec"
  },

  "substrate": {
    "thickness_mm": 1.6,
    "epsilon_r": 4.3,
    "loss_tangent": 0.018
  },

  "port": {
    "negative_mm": [10.0, 10.0],
    "positive_mm": [10.5, 10.0],
    "width_mm": 0.5
  }
}
```

PCB v0 wymaga:

```text
copper.model = "pec"
```

Obsługa `conducting_sheet` będzie osobnym zadaniem.

---

# 6. Import Gerbera

Nie pisać własnego parsera RS-274X.

Preferowana biblioteka:

```text
Gerbonara
```

Opcjonalnie dla operacji geometrycznych:

```text
Shapely
```

Najpierw sprawdzić kompatybilność z projektem i Pythonem używanym na Windows.

Importer ma robić wyłącznie:

```text
Gerber
    ↓
obiekty biblioteki
    ↓
polygonizacja
    ↓
normalizacja jednostek
    ↓
CopperPolygon[]
```

oraz:

```text
Edge.Cuts
    ↓
BoardOutline
```

Nie wykonywać w importerze:

- meshingu,
- tworzenia CSXCAD,
- definiowania portu,
- wyboru materiałów,
- uruchamiania openEMS.

---

# 7. Transformacja współrzędnych

PCB v0 może uprościć port openEMS przez normalizację orientacji.

Jeżeli:

```text
P1 = negative
P2 = positive
```

to po transformacji:

```text
P1.y == P2.y
P2.x > P1.x
```

Czyli port jest skierowany w osi `+x`.

Transformacja:

1. translacja do wygodnego początku układu,
2. obrót całej geometrii XY,
3. ten sam obrót dla:
   - copper,
   - outline,
   - port.

Zachować metadane transformacji.

Przykładowy obiekt:

```python
@dataclass(frozen=True)
class PcbTransform:
    translation_xy_m: tuple[float, float]
    rotation_rad: float
```

Wymagania:

- odległości nie zmieniają się,
- pola polygonów nie zmieniają się,
- wzajemne położenie elementów nie zmienia się,
- transformacja odwrotna jest możliwa.

---

# 8. Walidacja

`validate_pcb_geometry()` ma sprawdzać co najmniej:

## Geometria

- outline istnieje,
- copper nie jest puste,
- substrate thickness > 0,
- epsilon_r >= 1,
- loss_tangent >= 0,
- width portu > 0.

## Port

- negative leży na miedzi,
- positive leży na miedzi,
- negative i positive nie należą do tego samego ciągłego obszaru miedzi,
- długość portu > 0,
- port znajduje się wewnątrz obrysu PCB.

PCB v0 może odrzucać niejednoznaczne przypadki.

Nie zgadywać.

---

# 9. Workflow z pustymi obiektami

Najpierw ma powstać działający przepływ bez rzeczywistego Gerbera i bez rzeczywistego meshera.

To jest bardzo ważne.

## Pierwszy milestone

Program ma przechodzić przez:

```text
load pcb config
       ↓
make placeholder PcbGeometry
       ↓
validate
       ↓
normalize orientation
       ↓
make placeholder mesh
       ↓
install placeholder PCB into solver adapter
       ↓
prepare
```

Każdy krok może początkowo używać minimalnej sztucznej geometrii.

Przykładowa struktura testowa:

```text
board = 20 mm × 20 mm

Copper A:
x = 4..9 mm
y = 8..12 mm

Copper B:
x = 11..16 mm
y = 8..12 mm

gap = 2 mm

port:
(9 mm, 10 mm) -> (11 mm, 10 mm)
```

Nie używać prawdziwego Gerbera w pierwszym przebiegu infrastrukturalnym.

---

# 10. Minimalny sztuczny model

Dodać fixture/helper testowy:

```python
def make_test_pcb_geometry() -> PcbGeometry:
    ...
```

Powinien tworzyć:

```text
20 × 20 mm substrate

       Copper A     gap      Copper B
       ████████              ████████
       ████████ ----port---- ████████
       ████████              ████████
```

To jest główny przypadek infrastrukturalny.

---

# 11. `pcb_mesh.py`

Nie rozszerzać obecnego `mesh.py` o wiele `if model == "pcb"`.

PCB otrzymuje osobny mesher.

Interfejs:

```python
def make_pcb_mesh(
    geometry: PcbGeometry,
    config: dict
) -> tuple[dict[str, np.ndarray], dict]:
    ...
```

Pierwsza implementacja może być bardzo prosta.

Ważniejszy jest poprawny kontrakt.

---

# 12. Mesh anchors

Nie używać wszystkich wierzchołków Gerbera jako anchorów siatki.

To krytyczne wymaganie.

Gerber może zawierać tysiące punktów aproksymujących:

- łuki,
- okręgi,
- pady,
- regiony.

Geometria miedzi i anchory siatki są różnymi reprezentacjami.

Minimalne anchory dla copper polygon:

```text
xmin
xmax
xcenter

ymin
ymax
ycenter
```

Dodatkowo:

- board xmin/xmax,
- board ymin/ymax,
- port endpoints,
- port midpoint,
- port transverse edges,
- z_top,
- z_bottom substrate.

Później można dodać inteligentne anchory dla krytycznych szczelin.

---

# 13. Krytyczna okolica portu

Mesher musi lokalnie rozwiązać:

```text
Copper A | gap | Copper B
```

Port jest najważniejszą częścią siatki.

W okolicy portu wymagane są jawne linie siatki dla:

```text
negative endpoint
positive endpoint
midpoint
± width/2 w kierunku poprzecznym
```

Nie dopuścić do sytuacji, w której dwie strony portu zostają numerycznie scalone.

---

# 14. Grubość miedzi

PCB v0:

```text
PEC
zero-thickness planar polygon
```

Grubość miedzi może być zapisana w konfiguracji i metadanych, ale nie musi jeszcze wpływać na solver.

Następny etap:

```text
ConductingSheet
```

Nie tworzyć bryły 35 µm z kilku warstw komórek FDTD.

---

# 15. Laminat

PCB v0:

- jednorodny,
- izotropowy,
- stałe epsilon_r,
- stałe loss_tangent,
- pełny obrys płytki,
- zakres Z od `-thickness` do `0`.

Adapter openEMS tworzy materiał dielektryczny i bryłę substrate.

---

# 16. Adapter openEMS PCB

Dodać:

```text
src/antenna_lab/solvers/openems_pcb.py
```

Minimalny kontrakt:

```python
def install_pcb_geometry(
    csx,
    geometry: PcbGeometry,
    config: dict,
):
    ...
```

Ten moduł odpowiada wyłącznie za:

- substrate,
- copper,
- ewentualne materiały pomocnicze.

Nie odpowiada za:

- Run,
- FDTD settings,
- NF2FF,
- zapis wyników,
- raport,
- CalcPort.

Te rzeczy pozostają w głównym adapterze.

---

# 17. Minimalna zmiana `openems.py`

Główny adapter może mieć dispatch:

```python
if isinstance(geometry, Geometry):
    install_existing_antenna_geometry(...)

elif isinstance(geometry, PcbGeometry):
    install_pcb_geometry(...)
```

Nie przebudowywać całego adaptera.

Pierwszy cel:

```text
existing antenna prepare still works
+
PCB prepare works
```

---

# 18. Port openEMS

Po transformacji PCB port powinien być skierowany w `+x`.

Port korzysta z istniejącego mechanizmu `AddLumpedPort`.

Nie próbować w PCB v0 obsługiwać dowolnego kierunku w płaszczyźnie.

Wymagany wynik transformacji:

```text
negative.x < positive.x
negative.y == positive.y
```

z tolerancją numeryczną.

---

# 19. CLI

Nie projektować nowego dużego CLI.

Minimalny cel:

```text
python -m antenna_lab pcb-check --config path/to/pcb.json
```

oraz:

```text
python -m antenna_lab pcb-prepare --config path/to/pcb.json
```

Jeżeli istniejąca architektura CLI pozwala bezpiecznie używać obecnych:

```text
check
prepare
```

można później zunifikować interface.

Nie robić tego w pierwszym tasku.

---

# 20. Wyniki pierwszych milestone'ów

## M-PCB-0

Działa wyłącznie model danych.

Wyniki:

```text
PcbGeometry
serialization
validation
tests
```

---

## M-PCB-1

Działa pusty workflow.

```text
config
→ placeholder geometry
→ validation
→ transform
→ placeholder mesh
→ prepare dispatch
```

Bez Gerbera.

---

## M-PCB-2

Importer Gerbera.

```text
F.Cu
Edge.Cuts
→ PcbGeometry
```

Bez openEMS.

---

## M-PCB-3

Prawdziwy mesher PCB.

```text
PcbGeometry
→ mesh
```

---

## M-PCB-4

CSX/openEMS geometry.

```text
PCB geometry
→ model.xml
```

`prepare` musi działać.

---

## M-PCB-5

Pierwszy FDTD.

Tylko:

```text
Z
R
X
S11
SWR
```

Nie implementować pól ani NF2FF.

---

# 21. Plan ticketów dla Codex Light

## PCB-001 — model danych

Cel:

Zaimplementować:

```text
BoardOutline
CopperPolygon
Substrate
PcbPort
PcbGeometry
PcbTransform
```

oraz testy.

Zakres plików:

```text
src/antenna_lab/pcb/model.py
tests/test_pcb_model.py
```

Nie dotykać openEMS.

Acceptance:

- import działa,
- `as_dict()` działa,
- `bounds` działa,
- serializacja jest deterministyczna,
- existing tests pass.

---

## PCB-002 — walidacja

Zaimplementować:

```python
validate_pcb_geometry()
```

Zakres:

```text
src/antenna_lab/pcb/validation.py
tests/test_pcb_validation.py
```

Acceptance:

- poprawna sztuczna PCB przechodzi,
- pusty copper odpada,
- błędny substrate odpada,
- port poza miedzią odpada,
- oba końce portu na tym samym conductorze odpadają.

---

## PCB-003 — transformacja portu

Zaimplementować:

```text
normalizacja portu do osi +X
transformacja wszystkich polygonów
inverse transform
```

Zakres:

```text
src/antenna_lab/pcb/transform.py
tests/test_pcb_transform.py
```

Acceptance:

- dystanse zachowane,
- pola polygonów zachowane,
- port po transformacji leży na osi X,
- inverse odtwarza pierwotne współrzędne.

---

## PCB-004 — config

Dodać loader `pcb.json`.

Zakres:

```text
src/antenna_lab/pcb/config.py
schemas/pcb-config.schema.json
tests/test_pcb_config.py
```

Nie importować jeszcze Gerbera.

---

## PCB-005 — placeholder workflow

Dodać:

```python
make_test_pcb_geometry()
```

i przejście:

```text
config
→ test geometry
→ validate
→ transform
```

Celem jest sprawdzenie architektury, nie fizyki.

---

## PCB-006 — placeholder mesh

Dodać interfejs:

```python
make_pcb_mesh()
```

Początkowo może działać wyłącznie dla sztucznej prostokątnej geometrii testowej.

Zakres:

```text
src/antenna_lab/solvers/pcb_mesh.py
tests/test_pcb_mesh.py
```

Nie optymalizować.

---

## PCB-007 — openEMS PCB skeleton

Dodać:

```python
install_pcb_geometry()
```

Na tym etapie może obsługiwać tylko:

- prostokątny substrate,
- dwa prostokątne obszary copper fixture.

Nie implementować jeszcze Gerbera.

Celem jest:

```text
PcbGeometry
→ CSX
→ XML
```

---

## PCB-008 — prepare dispatch

Minimalnie rozszerzyć główny adapter:

```text
Geometry
→ obecna ścieżka

PcbGeometry
→ openems_pcb
```

Wymaganie:

wszystkie stare testy muszą pozostać zielone.

---

## PCB-009 — Gerber dependency spike

To ma być osobny eksperyment.

Sprawdzić:

- instalację Gerbonara na docelowym Pythonie,
- odczyt prostego F.Cu,
- odczyt Edge.Cuts,
- jednostki,
- regiony,
- pady,
- łuki.

Nie integrować jeszcze z głównym kodem.

Wynik:

```text
mały test
+
krótka notatka o ograniczeniach
```

---

## PCB-010 — Gerber importer

Dopiero po PCB-009.

Zaimplementować:

```python
load_copper()
load_board_outline()
```

oraz konwersję do modelu PCB.

---

# 22. Instrukcje dla każdego tasku Codexa

Każdy task powinien zaczynać się od:

```text
Read only:
- docs/pcb-v0-contract.md
- files explicitly listed in this task
- directly imported modules only when necessary

Do not perform repository-wide refactoring.

Do not modify existing Quados or biquad geometry.

Do not modify historical outcomes.

Do not change current physical interpretation of existing antenna runs.

Do not add features outside this ticket.

Prefer the smallest patch satisfying the acceptance criteria.
```

---

# 23. Format odpowiedzi Codexa

Po każdym tasku model ma zwrócić wyłącznie:

```text
Files changed:
- ...

Tests executed:
- ...

Result:
- pass/fail

Unresolved:
- max 5 short items
```

Nie wymagać długiego opisu procesu rozumowania.

---

# 24. Reguła modelowa

Domyślnie używać modelu Light do:

- dataclasses,
- schema,
- loaderów,
- serializacji,
- testów jednostkowych,
- transformacji,
- CLI glue,
- prostych adapterów,
- preview.

Silniejszy model używać tylko do zadań, w których trzeba podjąć decyzje dotyczące:

- meshingu,
- portu openEMS,
- materiałów stratnych,
- stabilności numerycznej,
- zbieżności,
- interpretacji impedancji,
- normalizacji wyników.

Nie używać silniejszego modelu tylko dlatego, że zadanie dotyczy openEMS.

---

# 25. Najważniejsza zasada implementacyjna

Najpierw musi działać:

```text
PcbGeometry
    ↓
validation
    ↓
transform
    ↓
mesh
    ↓
CSX
    ↓
model.xml
```

dla sztucznej geometrii utworzonej w Pythonie.

Dopiero potem:

```text
Gerber
    ↓
PcbGeometry
```

Gerber jest adapterem wejścia.

Nie może determinować całej architektury systemu.

---

# 26. Definition of Done PCB v0

PCB v0 jest zakończone dopiero, gdy:

1. istniejące Quados i biquad nie mają regresji,
2. `F.Cu.gbr` jest importowany,
3. `Edge.Cuts.gbr` jest importowany,
4. laminat ma jawnie zdefiniowane parametry,
5. port jest jawnie zdefiniowany w `pcb.json`,
6. port jest walidowany względem miedzi,
7. geometria jest normalizowana do portu +X,
8. PCB ma osobny mesher,
9. openEMS zapisuje poprawny `model.xml`,
10. pierwszy testowy PCB run kończy FDTD,
11. zapisywane są:
   - Z,
   - R,
   - X,
   - S11,
   - SWR,
12. wynik pozostaje oznaczony jako `unverified`,
13. wykonano co najmniej dwa poziomy zagęszczenia siatki dla sztucznego przypadku kontrolnego,
14. żadne istniejące wyniki anten nie zostały przepisane ani zmodyfikowane.

---

# 27. Poza PCB v0

Nie implementować przed zakończeniem powyższego:

```text
ConductingSheet
B.Cu
vias
multilayer
component models
capacitor ESR/ESL
S-parameters
IPC-356
KiCad semantic import
auto footprint detection
auto port detection
multiple ports
E/H plots
NF2FF
surface currents
soldermask
rough copper
anisotropic substrate
frequency-dependent substrate
```

Każda z tych funkcji będzie osobnym milestone'em.