# FAST / APPROX: model quasi-TEM PCB

To oddzielny solver przybliżony (`reduced_quasi_tem`, `approximate`), bez
openEMS, 3-D domeny, PML, komórek Yee i pytania o profil. DESIGN/VERIFY nadal
używają niezmienionej ścieżki full-wave. Nie deklarujemy 1% błędu ani walidacji EM.

## Uruchomienie (CMD Windows)

```cmd
.\.venv\Scripts\python.exe -m antenna_lab.pcb.reduced_control gerbs\realpcb_microstrip\test_spirala.zip --geometry-resolution-um 10 --center-mhz 2000 --cutoff-mhz 1900 --sweep-start-mhz 1500 --sweep-stop-mhz 2500 --sweep-step-mhz 10
```

ZIP korzysta z istniejącego szukania stackupu/ENET lokalnie i w jednym katalogu
nadrzędnym; FlyingProbe pochodzi z archiwum. Katalog Gerber i `--pcb-config`
też są obsługiwane. Musi istnieć rzeczywista ciągła miedź bottom; domyślny
jednowarstwowy config nie tworzy sztucznej masy. Legacy top-only JSON odrzucamy.
Opcjonalne `--frequencies-mhz` zachowuje jednostki i walidację pasma PCB.
Sweep jest regularny: stop wchodzi tylko, gdy leży na siatce start+n*step.
`--reference-impedance-ohm` domyślnie 50. Nie jest rezystorem dołączanym do sieci.
Center/cutoff służą wyłącznie wspólnej kontroli pasma wynikowego ±0,8 cutoff;
solver częstotliwościowy nie emituje impulsu. `--loss-reference-mhz` zachowano
we wspólnym parserze, ale w tym bezstratnym modelu nie zmienia obliczeń.

## Dokładny zakres pierwszego checkpointu

- Jednorodny dielektryk i dokładnie top/bottom; bottom to jeden pełny polygon
  bez szczelin/otworów, pokrywający aktywną miedź i kontakty. Setback od obrysu
  jest dozwolony (PCB-015B1). Jest idealnym wspólnym odniesieniem.
- Paski prostokątne i jednoznaczne połączenia ortogonalne tej samej szerokości;
  możliwe współosiowe zmiany szerokości, gdy cechy i pokrycie są jednoznaczne.
- `compact_features()` dostarcza rzeczywistych granic szerokości i ich zakresów.
  Odtworzone prostokąty i narożniki muszą pokrywać całą miedź w dotychczasowej
  tolerancji numerycznej. Nie ma rasteryzacji, dopasowania ścieżki ani naprawy CAD.
- Graf jest dzielony w udowodnionych złączach. Terminale źródła i R/L/C muszą
  trafiać w jednoznaczne końce/złącza osi pasków. Kontrola pełnej szerokości
  kontaktów i pustego fizycznego prostokąta szczeliny pozostaje obowiązkowa.
- Sieć rozwiązuje źródło różnicowe 1 A, nie wymaga pojedynczej kaskady ABCD.
  R/L/C biorą wartości i lokalne terminale z istniejącego importera.

**PARTIAL — sprzężenie par nie jest jeszcze rozwiązane.** U/meander można
wyekstrahować, ale każdy rozdzielony równoległy overlap zatrzymuje solve.
Zapisujemy parę sekcji, rzeczywistą szczelinę i długość overlap. Nie ma
arbitralnego progu „wystarczająco daleko”. Serpentyna wymagająca sprzężeń
nie dostanie udawanego CSV z liniami niesprzężonymi. Najbliższa brakująca część
to model macierzy C/C0 lub modalny sprzężonego przekroju oraz stamp wieloportu.

Odrzucamy także: łuki/skosy, niejednoznaczne krótkie pady, rozgałęzione paski,
nieudowodnione przejścia szerokości, nieobsługiwane wiercenia/vias (poniżej), inner copper, różne
materiały w stackupie, ground slots, niepoprawne/singularne sieci. Trzy i więcej
równoległych odcinków również nie są obsługiwane. Nie ma fallback do FDTD.

## PCB-015B: idealne połączenia PTH do masy

Obsługiwany PTH ma dodatni skończony promień `equivalent_outer_radius_m`,
kontaktuje dokładnie jeden polygon top oraz wcześniej udowodnioną pełną
płaszczyznę bottom. Kontakt oznacza odległość środka od końcowej miedzi
(z uwzględnieniem otworów) nie większą niż ten promień. Nazwy warstw w
metadanych nie zastępują kontroli geometrii.

Cały dotknięty polygon top staje się idealnym ekwipotencjalnym węzłem `ground`.
To świadoma aproksymacja FAST: pomijamy indukcyjność/straty przelotki i rozłożoną
impedancję tego polygonu. Nie deklarujemy fizycznie zerowej indukcyjności.
Polygon pozostaje w geometrii; jawna lista aktywnych ID wyłącza go jedynie
z ekstrakcji linii. Terminal źródła/R/L/C na nim trafia do `ground`; terminal
sygnałowy nadal musi odpowiadać rzeczywistemu końcowi/złączu osi ścieżki.
Kontrola pełnej powierzchni kontaktu i pustej szczeliny pozostaje obowiązkowa.

Odrzucamy wszystkie NPTH, brak kontaktu bottom, niejednoznaczny kontakt top,
inner copper, wadliwe promienie i niebezpieczne kontakty. Dwa terminale źródła
na masie oznaczają zwarcie; komponent z oboma terminalami na masie jest jawnie
odrzucany. Przelotka nie może przecinać prostokąta kontaktu komponentu/źródła.

`reduced_model.json` i `summary.json` zapisują `ground_vias`,
`ground_connected_top_conductors`, osobny `ground_reference` oraz pominięte
`via_inductance` i `via_barrel_loss`. Każdy PTH ma ID, środek, średnicę, promień,
ID kontaktowanej miedzi top/bottom i `treatment=ideal_ground_connection`.
Konsola podaje liczby przelotek i polygonów masy także przed odmową sprzężeń.
Ograniczenie `coupling_required` nadal zatrzymuje solve bez `impedance.csv`.
Nie zmienia się model przelotek full-wave ani siatka FDTD.

## Metoda i interpretacja wyników

Izolowana linia: Hammerstad–Jensen, model quasi-static przy zerowej grubości,
wg [Qucs Technical Papers, Single microstrip line](https://qucs.github.io/tech/node75.html),
równania 11.4, 11.6, 11.15–18. Zastosowany zakres: 0,01 ≤ w/h ≤ 100,
1 ≤ epsilon_r ≤ 128. Z Z0 i prędkości fazowej wyprowadzamy L oraz C na metr.
Sieć stosuje dokładne równania linii dla zadanej częstotliwości; pomocnicza
niewiadoma prądu zapobiega sztucznej osobliwości stampu cotangent w półfali.
Prawdziwa osobliwość lub niepoprawny wynik powoduje błąd, bez obcinania danych.

Linie są bezstratne. Tylko jawne idealne R rozpraszają energię. Pominięto
straty laminatu/przewodnika, promieniowanie, dyspersję, skończony brzeg masy,
fringing końców/padów, pasożyty obudów i efekty 3-D zakrętów. Wartości
conductivity/tan-delta pozostają w provenance; ich zmiana nie dodaje tłumienia.
Idealne narożniki zapewniają ciągłość V/I, ale nie modelują nadmiarowej
pojemności/indukcyjności. Nie interpretować głębokości rezonansu bez kalibracji
z full-wave i stratami. Interakcje nierównoległe/nielokalne są pominięte.

`outcomes/pcb_reduced/<run>/` zawiera `summary.json`, `impedance.csv`,
`reduced_model.json`, `import.json`, `geometry.source.json`, `geometry.json`.
Model zapisuje graf, długości, szerokości, h, Z0/L/C, terminale i ograniczenia.
Błąd zostawia summary ze statusem failed i dostępną geometrią, bez CSV.
Brak nieskończonych liczb w JSON: null/empty SWR oznacza nieskończony SWR
bezstratnego obciążenia; null dB oznacza −infinity przy dokładnie zerowym S11.
S11 i Z nie są sztucznie obcinane. Raport antenowy nie jest tu generowany.


## PCB-015C0: źródłowe trasy Gerbera

Nowy import zapisuje `routes` i `route_provenance_available` w geometrii.
Każdy Line/Arc zachowuje oś, szerokość apertury kołowej, dla Arc środek/kierunek,
warstwę, polarity, kolejność obiektu, plik i SHA256 oraz polygonizowany obrys
tego stroke z istniejącym budżetem aproksymacji importera. Region/Flash nie
staje się trasą. Końcowy CopperPolygon nadal określa fizyczną miedź.

Po pełnej kompozycji dark/clear/restore cały stroke musi przetrwać w dokładnie
jednym conductorze (`source_status=verified`). Stan niepełny/niejednoznaczny
zostaje zapisany i zatrzymuje FAST; nie odrzuca poprawnego importu full-wave.
Normalizacja przekształca oś i obrys razem; geometry resolution używa tego samego
PcbGrid co miedź, zapisuje tick records i ponownie sprawdza przetrwanie/ownership.
Nie dodano tolerancji kąta, naprawy polygonu ani kotwic siatki. Surowe wartości
pozostają w geometry.source.json i snapshotach provenance projekcji.

FAST używa tych osi, nie granic polygonu. Line ma rzeczywistą długość endpointów
przy dowolnym kącie. W C0 późniejsza analiza sprzężeń linii skośnych ma jawny
guard — nigdy nie klasyfikuje ich jako pionowych. Aktywny Arc ma błąd z ID,
plikiem, indeksem obiektu i SHA256. Region-only import nie przechodzi do legacy
polygon extraction; brak routingu jest jawnym ograniczeniem. Syntetyczna
PcbGeometry bez provenance zachowuje dotychczasowy B2 path.

Pokrycie końcowej miedzi przez zweryfikowane strokes jest sprawdzane; tylko
istniejąca width-local aproksymacja końców/złączy może pozostawić lokalny pad.
Nie zgadujemy połączeń osi, lead length do kontaktów ani centrów padów.
Nieobsługiwane przecięcia/rozgałęzienia, zmienione clear/restore, niespójne
połączenia przez pady/regions kończą się błędem. Dokładny fizyczny audyt źródła,
RLC, PTH i setback pozostaje w mocy. Sprzężenia par nie są zaimplementowane.

Checkpoint C0 nie jest potwierdzeniem wyniku realnego test_spirala.zip;
ten plik nie jest dostępny agentowi. Pełną weryfikację wykonuje użytkownik.


### PCB-015C0.1 — przetrwanie źródłowej trasy po projekcji

Source footprint jest dowodem ordered dark/clear/restore przed projekcją,
a nie drugą fizyczną miedzią. Po geometry-resolution autorytatywne są finalne
CopperPolygon i istniejący audyt topology/connectivity z `quantization._audit`.
Jego sukces jest związany skrótem z wejściem i wynikiem projekcji; FAST odrzuca
brakujący albo nieaktualny dowód po późniejszej zmianie geometrii.

Route zachowuje użyteczność tylko przy źródłowym, jednoznacznym ownership,
niezapadniętej osi/szerokości i osi (łącznie z końcami) we właściwym finalnym
conductorze. Nie wymagamy containment niezależnie skwantyzowanego footprintu.
Kontrola pads/regions i pozalokalnych kontaktów stroke korzysta z obrazu
źródłowego; kontrola grafu osi działa również na wyniku projekcji. Arc jest
sprawdzany geometrycznie z dotychczasową aproksymacją Gerbonary, ale nadal
kończy FAST jawnym `source route Arc unsupported`, bez modelu TL łuku.

To lekcja architektoniczna PCB-012G: fizycznej prawdy nie zastępuje zgodność
dwóch wtórnych reprezentacji numerycznych. **Nie** przenosi to reguły 1/3–2/3
z mesha FDTD do FAST i nie dodaje tolerancji q ani q/2. Full-wave, mesh,
PML i geometria miedzi pozostają niezmienione.


### EasyEDA source-first — checkpoint D0/D1

Główna nowa ścieżka: `--easyeda-source PATH`, opcjonalnie `--source-config`
z jawnymi kontaktami i plating. `--inspect-source` zapisuje neutralny IR oraz
dostępną fizyczną geometrię bez wymogu portu. Nie ładuje Gerbera. Szczegóły,
jednostki i ograniczenia w [pcb-easyeda.md](pcb-easyeda.md). Źródłowy ARC
zachowuje signed sweep i nie staje się TL z długością cięciwy. Dotychczasowe
Gerber-only i synthetic pozostają kompatybilne. Zewnętrzne COMPONENT footprinty
nie są obecnie instancjonowane; missing geometry ma jawny diagnostic.
