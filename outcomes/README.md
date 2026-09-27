# Kontrakt outcomes, wersja 1

Ten katalog zawiera specyfikację. Na M0 nie ma wyników symulacji.
Przebiegi trafią do `outcomes/runs/<run_id>/`; ich plików nie dodajemy
automatycznie do Git. Daty w danych są UTC z przesunięciem strefy, ID unikalne.

| Plik | Zawartość |
| --- | --- |
| `manifest.json` | Schemat, run_id, stan, czas utworzenia, kod i solver, częstotliwości, normalizacja, lista plików i SHA-256 |
| `parameters.resolved.json` | Wszystkie parametry fizyczne i numeryczne po rozwiązaniu wartości domyślnych, w SI |
| `geometry.json` | Węzły, krawędzie, promienie, połączenia, porty, materiały, identyfikatory części i przybliżenia |
| `model.nec` | Dokładne wejście NEC, bez zależności od pamięci aktualnej aplikacji |
| `currents.npz` | Prądy zespolone, centra i kierunki segmentów, długości, tagi, częstotliwości |
| `impedance.csv` | frequency_hz, resistance_ohm, reactance_ohm, reference_ohm, s11_real, s11_imag, swr |
| `far_field.npz` | Osie theta/phi, częstotliwości, zespolone E_theta/E_phi przy jawnej odległości odniesienia, zysk i polaryzacja |
| `fields/xz.npz` | Zespolone E/H w xz przy y = 0, współrzędne i maska |
| `fields/yz.npz` | Zespolone E/H w yz przy x = 0, współrzędne i maska |
| `fields/xy_front.npz` | Zespolone E/H w xy przy zapisanym z > H, współrzędne i maska |
| `summary.json` | Metryki, kierunek maksimum, szerokości wiązki i przód/tył wraz z definicją |
| `validation.json` | Kontrole geometrii, jednostek, zbieżności, normalizacji i status wiarygodności |
| `solver.log` | Komunikaty obliczeń i ostrzeżenia |
| `report.html` | Czytelny raport z parametrami, wykresami, założeniami i ograniczeniami |
| `plots/` | Wykresy wskazane w goal.md, zawsze z jednostkami |
| `animations/fields_xz.gif` | Pełny okres pola, stała skala i jawny krok fazy |

## Konwencje tablic

NPZ zawiera tablice numeryczne i tekstowe Unicode, bez obiektów Python/pickle.
Odczyt przez NumPy z `allow_pickle=False`. Liczby rzeczywiste float64,
zespolone complex128; indeksy i maski odpowiednich typów całkowitych/bool.

- Prądy: `frequency_hz` [nf], `current_a` [nf, ns], `center_m` [ns, 3],
  `direction` [ns, 3], `length_m` [ns], `tag` [ns], `segment_id` [ns].
  Dodatni prąd jest zgodny z `direction`. Pochodzenie każdej próbki jest jawne.
- Pola bliskie: `frequency_hz` [nf], `xyz_m` [np, 3], `e_v_per_m` [nf, np, 3],
  `h_a_per_m` [nf, np, 3], `valid_mask` [np], `grid_shape` [2],
  `axis_u_m` [nu], `axis_v_m` [nv], `axis_u_name`, `axis_v_name`.
  Spłaszczenie w C-order z kształtu [nv, nu, 3]; u zmienia się najszybciej.
  Nieprawidłowe próbki mają NaN i false w masce, a przyczyna jest w raporcie.
- Pole dalekie: `frequency_hz` [nf], `theta_deg` [nt], `phi_deg` [np],
  `e_theta_v_per_m` i `e_phi_v_per_m` [nf, nt, np], `reference_distance_m`
  [1], `gain_dbi` [nf, nt, np], `realized_gain_dbi` [nf, nt, np].
  Odległość dotyczy asymptotycznego pola dalekiego, nie pomiaru w tej odległości.
  Theta/phi i baza poprzeczna mają definicję w manifeście. Osie phi bez
  podwójnego liczenia 0° i 360° przy całkowaniu.

Prądy i pola są amplitudami szczytowymi fazorów po normalizacji do 1 W mocy
przyjętej przez antenę. `manifest.json` zapisuje współczynnik normalizacji
oraz moc i wymuszenie surowego rozwiązania. Warianty porównujemy przy tej
samej mocy przyjętej; strata niedopasowania jest osobnym wynikiem.

S11 liczymy względem jawnego, rzeczywistego dodatniego Z odniesienia:
(Z − Zref) / (Z + Zref). Zysk uwzględniający niedopasowanie używa tego samego
Zref. Nie dopisuje strat baluna, kabla i LNA, jeśli nie były modelowane.

Przód/tył w pierwszej wersji oznacza różnicę zysku dokładnie w +z i −z;
nie maksimum w całej tylnej półsferze. Szerokość −3 dB podaje się w danym
przekroju wokół wskazanego maksimum. Dla niejednoznacznej wiązki wartość jest
null z objaśnieniem, zamiast arbitralnego wyboru. Wartości nieskończone nie są
legalnym JSON: używaj null oraz pola wyjaśniającego brak skończonej metryki.

## Manifest i stany

Schemat: `schemas/run-manifest.schema.json` od korzenia repozytorium.
Stany: running, completed, failed, cancelled. Oddzielny status naukowej
kontroli: unverified, passed, failed. Zakończenie obliczeń nie oznacza
automatycznego zaliczenia kontroli fizycznej.

Lista artefaktów zawiera ścieżki względne i SHA-256. Manifest nie zawiera
skrótu samego siebie. Pliki uzupełnia się podczas przebiegu, a po ukończeniu
przebieg jest niezmienny. Ponowne renderowanie do innych ustawień tworzy
osobny katalog pochodny ze wskazaniem źródłowego run_id, nie nadpisuje danych.

