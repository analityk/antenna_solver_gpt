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
  pokrywający obrys, bez szczelin/otworów. Jest idealnym wspólnym odniesieniem.
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
nieudowodnione przejścia szerokości, wiercenia/vias, inner copper, różne
materiały w stackupie, ground slots, niepoprawne/singularne sieci. Trzy i więcej
równoległych odcinków również nie są obsługiwane. Nie ma fallback do FDTD.

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
